"""
SQLite database setup with SQLAlchemy.
"""
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./terradelta.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    saved_areas = relationship("SavedArea", back_populates="user")


class SavedArea(Base):
    __tablename__ = "saved_areas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    bbox = Column(Text, nullable=False) # JSON list [lon_min, lat_min, lon_max, lat_max]
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_areas")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="queued")
    progress = Column(Integer, default=0)
    bbox = Column(Text, nullable=False)          # JSON string
    dates = Column(Text, nullable=True)          # JSON array of strings
    model = Column(String, default="rf")
    feature = Column(String, default="analysis") # analysis | monitoring
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)


class Result(Base):
    __tablename__ = "results"

    job_id = Column(String, primary_key=True)
    model_used = Column(String, nullable=True)
    output_dir = Column(String, nullable=True)
    timeline_data = Column(Text, nullable=True)  # JSON for array of changes
    actual_dates = Column(Text, nullable=True)   # JSON array of dates
    cloud_covers = Column(Text, nullable=True)   # JSON array of cloud cover percentages
    data_sources = Column(Text, nullable=True)     # JSON array: "real_sentinel2" | "synthetic_fallback" per date
    fallback_reasons = Column(Text, nullable=True)  # JSON array of reason strings (or null) per date


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helper functions ---

def create_job(db, job_id: str, bbox: list,
               dates: list = None, model: str = "rf", feature: str = "analysis") -> Job:
    job = Job(
        id=job_id,
        status="queued",
        progress=0,
        bbox=json.dumps(bbox),
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
