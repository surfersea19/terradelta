"""
Monitoring router — F3: Area Monitoring endpoints.
POST /api/monitoring/submit
GET  /api/monitoring/status/{job_id}
GET  /api/monitoring/result/{job_id}
"""
import uuid
import json
import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db.database import (
    get_db, create_job, update_job_progress,
    save_result, get_job, get_result, SavedArea, User
)
from pipeline.orchestrator import run_analysis_pipeline
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class MonitoringRequest(BaseModel):
    bbox: List[float]
    dates: List[str]     # YYYY-MM-DD, min 2, max 6

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError("bbox must have 4 values")
        return [float(x) for x in v]

    @field_validator("dates")
    @classmethod
    def validate_dates(cls, v):
        if len(v) < 2:
            raise ValueError("Need at least 2 dates")
        if len(v) > 6:
            raise ValueError("Maximum 6 dates for MVP")
        return v


def _run_monitoring_job(job_id: str, request: MonitoringRequest):
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        def progress_callback(pct, msg):
            update_job_progress(db, job_id, pct, status="processing")

        result = run_analysis_pipeline(
            job_id=job_id,
            bbox=request.bbox,
            dates=request.dates,
            progress_callback=progress_callback,
        )

        db_result = {
            "model_used":    result.get("model_used", "rf"),
            "output_dir":    result.get("output_dir"),
            "timeline_data": json.dumps(result.get("timeline", [])),
            "actual_dates":  json.dumps(result.get("actual_dates", [])),
            "cloud_covers":  json.dumps(result.get("cloud_covers", [])),
        }
        save_result(db, job_id, db_result)
        update_job_progress(db, job_id, 100, status="complete")

    except Exception as e:
        logger.error(f"Monitoring job {job_id[:8]} failed: {e}", exc_info=True)
        update_job_progress(db, job_id, 0, status="failed", error_message=str(e))
    finally:
        db.close()

# --- Saved Area Endpoints ---

class SavedAreaCreate(BaseModel):
    name: str
    bbox: List[float]

@router.post("/areas")
def save_area(area: SavedAreaCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_area = SavedArea(
        user_id=current_user.id,
        name=area.name,
        bbox=json.dumps(area.bbox)
    )
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return {"id": db_area.id, "name": db_area.name, "bbox": json.loads(db_area.bbox)}

@router.get("/areas")
def list_areas(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    areas = db.query(SavedArea).filter(SavedArea.user_id == current_user.id).all()
    return [{"id": a.id, "name": a.name, "bbox": json.loads(a.bbox)} for a in areas]

# --- Monitoring Job Endpoints ---


@router.post("/submit")
async def submit_monitoring(
    request: MonitoringRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job_id = str(uuid.uuid4())
    create_job(
        db, job_id,
        bbox=request.bbox,
        dates=request.dates,
        feature="monitoring",
    )
    background_tasks.add_task(_run_monitoring_job, job_id, request)
    estimated = len(request.dates) * 30
    return {"job_id": job_id, "status": "queued", "estimated_seconds": estimated}


@router.get("/status/{job_id}")
async def get_monitoring_status(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id":   job.id,
        "status":   job.status,
        "progress": job.progress,
        "message":  job.error_message or "",
    }


@router.get("/result/{job_id}")
async def get_monitoring_result(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=202, detail=f"Job status: {job.status}")

    result = get_result(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    dates = json.loads(job.dates) if job.dates else []
    timeline = json.loads(result.timeline_data or "[]")
    actual_dates = json.loads(result.actual_dates or "[]")
    cloud_covers = json.loads(result.cloud_covers or "[]")

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
        "job_id":       job_id,
        "bbox":         json.loads(job.bbox),
        "dates":        dates,
        "actual_dates": actual_dates,
        "cloud_covers": cloud_covers,
        "model_used":   result.model_used,
        "timeline":     timeline,
        "images":       image_urls,
    }
