"""
Core pipeline orchestrator.
Ties data access → preprocessing → features → inference → postprocessing
→ filtering → statistics → output together for a single analysis job.
"""
import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

from pipeline.data_access import load_bands_for_job
from pipeline.preprocessing import preprocess_bands, bands_to_rgb
from pipeline.features import build_feature_array
from pipeline.inference import run_rf_inference, get_model
from pipeline.postprocessing import (
    postprocess_change_map, vectorize_changes, build_geojson
)
from pipeline.filtering import (
    human_change_filter, generate_interpretation
)
from pipeline.statistics import compute_statistics
from utils.image_utils import (
    save_rgb_image, save_change_mask_png,
    save_geojson, ensure_output_dir
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output_files"


def run_analysis_pipeline(job_id: str, bbox: list,
                          date1: str, date2: str,
                          model_type: str = "rf",
                          progress_callback=None) -> dict:
    """
    Full change detection pipeline for a single T1/T2 analysis.
    progress_callback(pct: int, message: str) called at each stage.

    Returns result dict ready for DB storage and API response.
    """
    def progress(pct, msg):
        logger.info(f"[{job_id[:8]}] {pct}% — {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    out_dir = ensure_output_dir(OUTPUT_DIR, job_id)

    # ── Stage 1: Data access ─────────────────────────────────────────────
    progress(5, "Searching for cloud-free Sentinel-2 imagery...")
    (t1_bands, t2_bands,
     t1_actual_date, t2_actual_date,
     cloud1, cloud2, shape) = load_bands_for_job(bbox, date1, date2, out_dir)

    # ── Stage 2: Preprocessing ───────────────────────────────────────────
    progress(20, "Preprocessing bands...")
    t1_bands, t1_indices = preprocess_bands(t1_bands)
    t2_bands, t2_indices = preprocess_bands(t2_bands)

    # ── Stage 3: Export true-color images ───────────────────────────────
    progress(30, "Generating before/after images...")
    rgb_t1 = bands_to_rgb(t1_bands)
    rgb_t2 = bands_to_rgb(t2_bands)
    save_rgb_image(rgb_t1, out_dir / "before.png")
    save_rgb_image(rgb_t2, out_dir / "after.png")

    # ── Stage 4: Feature engineering ─────────────────────────────────────
    progress(40, "Engineering spectral and texture features...")
    features = build_feature_array(t1_bands, t2_bands, t1_indices, t2_indices,
                                   use_texture=True)

    # ── Stage 5: ML Inference ────────────────────────────────────────────
    progress(55, "Running AI change detection model...")
    model = get_model()
    prob_map = run_rf_inference(features, model)

    # ── Stage 6: Post-processing ─────────────────────────────────────────
    progress(70, "Post-processing change map...")
    change_mask = postprocess_change_map(prob_map, threshold=0.5, min_area_pixels=9)

    # ── Stage 7: Human-change filter ─────────────────────────────────────
    progress(78, "Filtering environmental changes...")
    change_mask = human_change_filter(change_mask, t1_indices, t2_indices)

    # ── Stage 8: Vectorize ───────────────────────────────────────────────
    progress(83, "Vectorizing change regions...")
    features_geojson = vectorize_changes(change_mask, bbox, prob_map)
    geojson = build_geojson(features_geojson)
    save_geojson(geojson, out_dir / "changes.geojson")

    # ── Stage 9: Save change mask PNG ────────────────────────────────────
    save_change_mask_png(change_mask, prob_map, out_dir / "change_mask.png")

    # ── Stage 10: Statistics ─────────────────────────────────────────────
    progress(88, "Computing statistics...")
    stats = compute_statistics(change_mask, prob_map)

    # ── Stage 11: Interpretation ─────────────────────────────────────────
    progress(93, "Generating interpretation...")
    interpretation = generate_interpretation(stats, t1_indices, t2_indices, bbox)

    # ── Stage 12: Assemble result ─────────────────────────────────────────
    progress(98, "Finalising results...")
    result = {
        "job_id":           job_id,
        "bbox":             bbox,
        "date1":            date1,
        "date2":            date2,
        "t1_actual_date":   t1_actual_date,
        "t2_actual_date":   t2_actual_date,
        "cloud_cover_t1":   round(cloud1, 1),
        "cloud_cover_t2":   round(cloud2, 1),
        "model_used":       model_type,
        "stats":            stats,
        "interpretation":   interpretation,
        "output_dir":       str(out_dir),
        "before_image_url": f"/files/{job_id}/before.png",
        "after_image_url":  f"/files/{job_id}/after.png",
        "change_mask_url":  f"/files/{job_id}/change_mask.png",
        "change_geojson_url": f"/files/{job_id}/changes.geojson",
        # Flatten stats for DB
        "changed_area_ha":       stats.get("changed_area_ha"),
        "change_percent":        stats.get("change_percent"),
        "num_clusters":          stats.get("num_clusters"),
        "mean_confidence":       stats.get("mean_confidence"),
        "high_confidence_area_ha": stats.get("high_confidence_area_ha"),
    }

    progress(100, "Analysis complete.")
    return result


def run_monitoring_pipeline(job_id: str, bbox: list,
                            dates: list,
                            progress_callback=None) -> dict:
    """
    Multi-date monitoring pipeline.
    Runs change detection relative to T1 for each subsequent date.
    """
    def progress(pct, msg):
        logger.info(f"[{job_id[:8]}] {pct}% — {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    from pipeline.statistics import compute_monitoring_timeline

    out_dir = ensure_output_dir(OUTPUT_DIR, job_id)
    timeline_masks = []
    timeline_dates = []
    step = 80 // max(len(dates) - 1, 1)

    progress(5, "Loading baseline imagery (T1)...")
    (t1_bands, _, t1_actual, _, cloud1, _, shape) = load_bands_for_job(
        bbox, dates[0], dates[0], out_dir)
    t1_bands, t1_indices = preprocess_bands(t1_bands)

    rgb_t1 = bands_to_rgb(t1_bands)
    save_rgb_image(rgb_t1, out_dir / "baseline.png")

    for i, date in enumerate(dates[1:], 1):
        pct = 10 + (i - 1) * step
        progress(pct, f"Processing date {i}/{len(dates)-1}: {date}...")

        (_, t2_bands, _, t2_actual, _, cloud2, _) = load_bands_for_job(
            bbox, date, date, out_dir)
        t2_bands, t2_indices = preprocess_bands(t2_bands)

        feats = build_feature_array(t1_bands, t2_bands, t1_indices, t2_indices,
                                    use_texture=False)
        model = get_model()
        prob_map = run_rf_inference(feats, model)
        mask = postprocess_change_map(prob_map)
        mask = human_change_filter(mask, t1_indices, t2_indices)

        rgb_t2 = bands_to_rgb(t2_bands)
        save_rgb_image(rgb_t2, out_dir / f"date_{i}.png")
        save_change_mask_png(mask, prob_map, out_dir / f"change_{i}.png")

        timeline_masks.append(mask)
        timeline_dates.append(t2_actual)

    progress(92, "Computing timeline statistics...")
    timeline = compute_monitoring_timeline(timeline_masks, timeline_dates)

    progress(100, "Monitoring complete.")
    return {
        "job_id":        job_id,
        "bbox":          bbox,
        "dates":         dates,
        "timeline":      timeline,
        "baseline_url":  f"/files/{job_id}/baseline.png",
        "output_dir":    str(out_dir),
    }
