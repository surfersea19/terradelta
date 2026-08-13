"""
SQLite database setup with SQLAlchemy.
"""
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./terradelta.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="queued")
    progress = Column(Integer, default=0)
    bbox = Column(Text, nullable=False)          # JSON string
    date1 = Column(String, nullable=True)
    date2 = Column(String, nullable=True)
    dates = Column(Text, nullable=True)          # JSON array for monitoring
    model = Column(String, default="rf")
    feature = Column(String, default="analysis") # analysis | monitoring
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)


class Result(Base):
    __tablename__ = "results"

    job_id = Column(String, primary_key=True)
    changed_area_ha = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    num_clusters = Column(Integer, nullable=True)
    mean_confidence = Column(Float, nullable=True)
    high_confidence_area_ha = Column(Float, nullable=True)
    interpretation = Column(Text, nullable=True)
    t1_actual_date = Column(String, nullable=True)
    t2_actual_date = Column(String, nullable=True)
    cloud_cover_t1 = Column(Float, nullable=True)
    cloud_cover_t2 = Column(Float, nullable=True)
    model_used = Column(String, nullable=True)
    output_dir = Column(String, nullable=True)
    timeline_data = Column(Text, nullable=True)  # JSON for monitoring


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helper functions ---

def create_job(db, job_id: str, bbox: list, date1: str = None, date2: str = None,
               dates: list = None, model: str = "rf", feature: str = "analysis") -> Job:
    job = Job(
        id=job_id,
        status="queued",
        progress=0,
        bbox=json.dumps(bbox),
        date1=date1,
        date2=date2,
        dates=json.dumps(dates) if dates else None,
        model=model,
        feature=feature,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_progress(db, job_id: str, progress: int, status: str = "processing",
                        error_message: str = None):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.progress = progress
        job.status = status
        if error_message:
            job.error_message = error_message
        job.updated_at = datetime.utcnow()
        db.commit()


def save_result(db, job_id: str, result_data: dict):
    result = Result(job_id=job_id, **result_data)
    db.add(result)
    db.commit()


def get_job(db, job_id: str) -> Job:
    return db.query(Job).filter(Job.id == job_id).first()


def get_result(db, job_id: str) -> Result:
    return db.query(Result).filter(Result.job_id == job_id).first()
