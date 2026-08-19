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

OUTPUT_DIR = Path(__file__).parent.parent / "output_files"


def run_analysis_pipeline(job_id: str, bbox: list,
                          dates: list,
                          progress_callback=None) -> dict:
    """
    Full change detection pipeline for consecutive dates.
    """
    def progress(pct, msg):
        logger.info(f"[{job_id[:8]}] {pct}% — {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    from pipeline.statistics import compute_monitoring_timeline

    out_dir = ensure_output_dir(OUTPUT_DIR, job_id)
    timeline = []
    actual_dates = []
    cloud_covers = []
    step = 90 // max(len(dates) - 1, 1)

    progress(5, f"Loading imagery for {dates[0]}...")
    (prev_bands, _, prev_actual, _, cloud1, _, shape) = load_bands_for_job(
        bbox, dates[0], dates[0], out_dir)
    prev_bands, prev_indices = preprocess_bands(prev_bands)

    rgb_prev = bands_to_rgb(prev_bands)
    save_rgb_image(rgb_prev, out_dir / "date_0.png")
    
    actual_dates.append(prev_actual)
    cloud_covers.append(round(cloud1, 1))

    for i in range(1, len(dates)):
        pct = 10 + (i - 1) * step
        progress(pct, f"Processing {dates[i-1]} → {dates[i]}...")

        (_, curr_bands, _, curr_actual, _, cloud2, _) = load_bands_for_job(
            bbox, dates[i], dates[i], out_dir)
        curr_bands, curr_indices = preprocess_bands(curr_bands)

        actual_dates.append(curr_actual)
        cloud_covers.append(round(cloud2, 1))

        feats = build_feature_array(prev_bands, curr_bands, prev_indices, curr_indices,
                                    use_texture=True)
        model = get_model()
        prob_map = run_rf_inference(feats, model)
        mask = postprocess_change_map(prob_map)
        mask = human_change_filter(mask, prev_indices, curr_indices)

        rgb_curr = bands_to_rgb(curr_bands)
        save_rgb_image(rgb_curr, out_dir / f"date_{i}.png")
        save_change_mask_png(mask, prob_map, out_dir / f"change_{i}.png")
        
        features_geojson = vectorize_changes(mask, bbox, prob_map)
        geojson = build_geojson(features_geojson)
        save_geojson(geojson, out_dir / f"changes_{i}.geojson")

        stats = compute_statistics(mask, prob_map)
        interpretation = generate_interpretation(stats, prev_indices, curr_indices, bbox)
        
        timeline.append({
            "date": curr_actual,
            "stats": stats,
            "interpretation": interpretation
        })
        
        # curr becomes prev for next iteration
        prev_bands, prev_indices = curr_bands, curr_indices

    progress(100, "Analysis complete.")
    return {
        "job_id":        job_id,
        "bbox":          bbox,
        "dates":         dates,
        "actual_dates":  actual_dates,
        "cloud_covers":  cloud_covers,
        "timeline":      timeline,
        "model_used":    "rf",
        "output_dir":    str(out_dir),
    }

def run_monitoring_pipeline(job_id: str, bbox: list,
                            dates: list,
                            progress_callback=None) -> dict:
    return run_analysis_pipeline(job_id, bbox, dates, progress_callback)
