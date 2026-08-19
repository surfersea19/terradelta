"""
TerraDelta — FastAPI application entry point.
Registers routers, CORS, static file serving, startup/shutdown hooks.
"""
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR      = Path(__file__).parent / "output_files"
EXPLORER_STATIC = Path(__file__).parent / "explorer_data"

OUTPUT_DIR.mkdir(exist_ok=True)
EXPLORER_STATIC.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, pre-load ML model."""
    from db.database import init_db
    from pipeline.inference import get_model

    logger.info("Initialising database...")
    init_db()

    logger.info("Pre-loading ML model...")
    get_model()  # warms cache

    logger.info("TerraDelta backend ready.")
    yield
    logger.info("TerraDelta backend shutting down.")


app = FastAPI(
    title="TerraDelta API",
    description="Human change detection from Sentinel-2 satellite imagery",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ───────────────────────────────────────────────────────
app.mount("/files",           StaticFiles(directory=str(OUTPUT_DIR)),      name="files")
app.mount("/explorer-static", StaticFiles(directory=str(EXPLORER_STATIC)), name="explorer-static")

# ── Routers ───────────────────────────────────────────────────────────────────
from routers.analysis   import router as analysis_router
from routers.explorer   import router as explorer_router
from routers.monitoring import router as monitoring_router
from routers.auth       import router as auth_router
from routers.advisor    import router as advisor_router

app.include_router(analysis_router)
app.include_router(explorer_router)
app.include_router(monitoring_router)
app.include_router(auth_router)
app.include_router(advisor_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "TerraDelta API v1.0.0"}


@app.get("/")
async def root():
    return {
        "name":    "TerraDelta",
        "version": "1.0.0",
        "docs":    "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
