"""
Analysis router — F1: Change Analysis endpoints.
POST /api/analysis/submit
GET  /api/analysis/status/{job_id}
GET  /api/analysis/result/{job_id}
GET  /api/analysis/download/report/{job_id}
"""
import uuid
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from db.database import get_db, create_job, update_job_progress, save_result, get_job, get_result
from pipeline.orchestrator import run_analysis_pipeline
from reports.pdf_generator import generate_pdf_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])

OUTPUT_DIR = Path(__file__).parent.parent / "output_files"


# ── Pydantic models ──────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    bbox: list          # [lon_min, lat_min, lon_max, lat_max]
    date1: str          # YYYY-MM-DD
    date2: str          # YYYY-MM-DD
    model: str = "rf"   # rf | siamese
    location_name: Optional[str] = None

    @validator("bbox")
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError("bbox must have 4 values: [lon_min, lat_min, lon_max, lat_max]")
        lon_min, lat_min, lon_max, lat_max = v
        if lon_max <= lon_min or lat_max <= lat_min:
            raise ValueError("Invalid bbox: max must be greater than min")
        # AOI size guard (~100 km² max)
        lon_span = abs(lon_max - lon_min)
        lat_span = abs(lat_max - lat_min)
        if lon_span > 1.0 or lat_span > 1.0:
            raise ValueError("AOI too large. Maximum ~100 km² (≈1° × 1°)")
        return [float(x) for x in v]

    @validator("model")
    def validate_model(cls, v):
        if v not in ("rf", "siamese"):
            raise ValueError("model must be 'rf' or 'siamese'")
        return v


# ── Background task ──────────────────────────────────────────────────────────

def _run_job(job_id: str, request: AnalysisRequest):
    """Background task: run full pipeline and update DB."""
    from db.database import SessionLocal

    db = SessionLocal()
    try:
        def progress_callback(pct: int, msg: str):
            update_job_progress(db, job_id, pct, status="processing")

        result = run_analysis_pipeline(
            job_id=job_id,
            bbox=request.bbox,
            date1=request.date1,
            date2=request.date2,
            model_type=request.model,
            progress_callback=progress_callback,
        )

        # Save to DB (only scalar fields)
        db_result = {
            "job_id":                  job_id,
            "changed_area_ha":         result.get("changed_area_ha"),
            "change_percent":          result.get("change_percent"),
            "num_clusters":            result.get("num_clusters"),
            "mean_confidence":         result.get("mean_confidence"),
            "high_confidence_area_ha": result.get("high_confidence_area_ha"),
            "interpretation":          result.get("interpretation"),
            "t1_actual_date":          result.get("t1_actual_date"),
            "t2_actual_date":          result.get("t2_actual_date"),
            "cloud_cover_t1":          result.get("cloud_cover_t1"),
            "cloud_cover_t2":          result.get("cloud_cover_t2"),
            "model_used":              result.get("model_used"),
            "output_dir":              result.get("output_dir"),
        }
        save_result(db, job_id, db_result)
        update_job_progress(db, job_id, 100, status="complete")
        logger.info(f"Job {job_id[:8]} complete.")

    except Exception as e:
        logger.error(f"Job {job_id[:8]} failed: {e}", exc_info=True)
        update_job_progress(db, job_id, 0, status="failed", error_message=str(e))
    finally:
        db.close()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/submit")
async def submit_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job_id = str(uuid.uuid4())
    create_job(
        db, job_id,
        bbox=request.bbox,
        date1=request.date1,
        date2=request.date2,
        model=request.model,
        feature="analysis",
    )
    background_tasks.add_task(_run_job, job_id, request)
    logger.info(f"Submitted analysis job {job_id[:8]} bbox={request.bbox}")
    return {"job_id": job_id, "status": "queued", "estimated_seconds": 45}


@router.get("/status/{job_id}")
async def get_status(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id":   job.id,
        "status":   job.status,
        "progress": job.progress,
        "message":  job.error_message or _status_message(job.status, job.progress),
    }


def _status_message(status: str, progress: int) -> str:
    if status == "queued":       return "Waiting to start..."
    if status == "complete":     return "Analysis complete"
    if status == "failed":       return "Analysis failed"
    if progress < 20:            return "Searching for imagery..."
    if progress < 40:            return "Preprocessing bands..."
    if progress < 60:            return "Running AI model..."
    if progress < 80:            return "Post-processing results..."
    return "Finalising..."


@router.get("/result/{job_id}")
async def get_result_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=202, detail=f"Job status: {job.status}")

    result = get_result(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    bbox = json.loads(job.bbox)

    return {
        "job_id":               job_id,
        "bbox":                 bbox,
        "date1":                job.date1,
        "date2":                job.date2,
        "t1_actual_date":       result.t1_actual_date,
        "t2_actual_date":       result.t2_actual_date,
        "cloud_cover_t1":       result.cloud_cover_t1,
        "cloud_cover_t2":       result.cloud_cover_t2,
        "model_used":           result.model_used,
        "before_image_url":     f"/files/{job_id}/before.png",
        "after_image_url":      f"/files/{job_id}/after.png",
        "change_mask_url":      f"/files/{job_id}/change_mask.png",
        "change_geojson_url":   f"/files/{job_id}/changes.geojson",
        "stats": {
            "changed_area_ha":         result.changed_area_ha,
            "change_percent":          result.change_percent,
            "num_clusters":            result.num_clusters,
            "mean_confidence":         result.mean_confidence,
            "high_confidence_area_ha": result.high_confidence_area_ha,
        },
        "interpretation":       result.interpretation,
    }


@router.get("/download/report/{job_id}")
async def download_report(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=202, detail="Job not yet complete")

    result_row = get_result(db, job_id)
    pdf_path = OUTPUT_DIR / job_id / "report.pdf"

    if not pdf_path.exists():
        # Generate on demand
        result_data = {
            "bbox":           json.loads(job.bbox),
            "date1":          job.date1,
            "date2":          job.date2,
            "t1_actual_date": result_row.t1_actual_date,
            "t2_actual_date": result_row.t2_actual_date,
            "cloud_cover_t1": result_row.cloud_cover_t1,
            "cloud_cover_t2": result_row.cloud_cover_t2,
            "model_used":     result_row.model_used,
            "interpretation": result_row.interpretation,
            "stats": {
                "changed_area_ha":         result_row.changed_area_ha,
                "changed_area_m2":         int((result_row.changed_area_ha or 0) * 10000),
                "change_percent":          result_row.change_percent,
                "num_clusters":            result_row.num_clusters,
                "mean_confidence":         result_row.mean_confidence,
                "high_confidence_area_ha": result_row.high_confidence_area_ha,
                "largest_cluster_ha":      0,
            },
        }
        generate_pdf_report(result_data, job_id, pdf_path)

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"terradelta_report_{job_id[:8]}.pdf",
    )
