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
from pydantic import BaseModel, field_validator
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
    dates: list         # List of YYYY-MM-DD
    location_name: Optional[str] = None

    @field_validator("bbox")
    @classmethod
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

    @field_validator("dates")
    @classmethod
    def validate_dates(cls, v):
        if len(v) < 2 or len(v) > 4:
            raise ValueError("Must provide between 2 and 4 dates for analysis")
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
            dates=request.dates,
            progress_callback=progress_callback,
        )

        # Save to DB
        db_result = {
            "model_used":       result.get("model_used", "rf"),
            "output_dir":       result.get("output_dir"),
            "timeline_data":    json.dumps(result.get("timeline", [])),
            "actual_dates":     json.dumps(result.get("actual_dates", [])),
            "cloud_covers":     json.dumps(result.get("cloud_covers", [])),
            "data_sources":     json.dumps(result.get("data_sources", [])),
            "fallback_reasons": json.dumps(result.get("fallback_reasons", [])),
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
        dates=request.dates,
        model="rf",
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
    dates = json.loads(job.dates) if job.dates else []
    timeline = json.loads(result.timeline_data or "[]")
    actual_dates = json.loads(result.actual_dates or "[]")
    cloud_covers = json.loads(result.cloud_covers or "[]")
    data_sources = json.loads(result.data_sources or "[]")
    fallback_reasons = json.loads(result.fallback_reasons or "[]")
    any_synthetic = any(s == "synthetic_fallback" for s in data_sources)

    image_urls = [{"date": actual_dates[0] if actual_dates else (dates[0] if dates else ""), "url": f"/files/{job_id}/date_0.png"}]
    for i in range(1, len(dates)):
        actual = actual_dates[i] if i < len(actual_dates) else dates[i]
        image_urls.append({
            "date":       actual,
            "url":        f"/files/{job_id}/date_{i}.png",
            "change_url": f"/files/{job_id}/change_{i}.png",
            "geojson":    f"/files/{job_id}/changes_{i}.geojson",
        })

    return {
        "job_id":            job_id,
        "bbox":              bbox,
        "dates":             dates,
        "actual_dates":      actual_dates,
        "cloud_covers":      cloud_covers,
        "data_sources":      data_sources,
        "fallback_reasons":  fallback_reasons,
        "any_synthetic":     any_synthetic,
        "model_used":        result.model_used,
        "timeline":     timeline,
        "images":       image_urls,
    }


@router.get("/download/report/{job_id}")
async def download_report(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=202, detail="Job not yet complete")

    result_row = get_result(db, job_id)
    job_dir = OUTPUT_DIR / job_id
    pdf_path = job_dir / "report.pdf"

    if not pdf_path.exists():
        dates = json.loads(job.dates) if job.dates else []
        timeline = json.loads(result_row.timeline_data or "[]")
        actual_dates = json.loads(result_row.actual_dates or "[]")
        cloud_covers = json.loads(result_row.cloud_covers or "[]")

        # Generate on demand
        data_sources = json.loads(result_row.data_sources or "[]")
        result_data = {
            "bbox":           json.loads(job.bbox),
            "dates":          dates,
            "actual_dates":   actual_dates,
            "cloud_covers":   cloud_covers,
            "model_used":     result_row.model_used,
            "timeline":       timeline,
            "data_sources":   data_sources,
        }
        generate_pdf_report(result_data, job_id, pdf_path, images_dir=job_dir)

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"terradelta_report_{job_id[:8]}.pdf",
    )
