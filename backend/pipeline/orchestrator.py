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

from pipeline.data_access import load_bands_for_date
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
    data_sources = []       # "real_sentinel2" | "synthetic_fallback" per date
    fallback_reasons = []   # None, or a human-readable reason, per date
    step = 90 // max(len(dates) - 1, 1)

    progress(5, f"Loading imagery for {dates[0]}...")
    scene0 = load_bands_for_date(bbox, dates[0], out_dir)
    prev_bands, prev_indices = preprocess_bands(scene0["bands"])

    rgb_prev = bands_to_rgb(prev_bands)
    save_rgb_image(rgb_prev, out_dir / "date_0.png")

    actual_dates.append(scene0["actual_date"])
    cloud_covers.append(round(scene0["cloud_pct"], 1))
    data_sources.append(scene0["data_source"])
    fallback_reasons.append(scene0["fallback_reason"])

    # Keep the very first date's preprocessed bands around (separate from
    # prev_bands, which gets overwritten each loop iteration) so we can
    # additionally compute an overall first-vs-last summary after the
    # consecutive-pair loop finishes. This is ADDITIVE — the consecutive
    # date-to-date comparisons above remain the primary DETECT output; this
    # is a convenience "big picture" summary layered on top, per the
    # product's Area Monitoring requirements.
    first_bands, first_indices = prev_bands, prev_indices
    curr_bands, curr_indices = prev_bands, prev_indices

    for i in range(1, len(dates)):
        pct = 10 + (i - 1) * step
        progress(pct, f"Processing {dates[i-1]} → {dates[i]}...")

        scene_i = load_bands_for_date(bbox, dates[i], out_dir)
        curr_bands, curr_indices = preprocess_bands(scene_i["bands"])

        actual_dates.append(scene_i["actual_date"])
        cloud_covers.append(round(scene_i["cloud_pct"], 1))
        data_sources.append(scene_i["data_source"])
        fallback_reasons.append(scene_i["fallback_reason"])

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
            "date": scene_i["actual_date"],
            "stats": stats,
            "interpretation": interpretation,
            "data_source": scene_i["data_source"],
        })
        
        # curr becomes prev for next iteration
        prev_bands, prev_indices = curr_bands, curr_indices

    overall_change = None
    if len(dates) >= 3:
        # Overall T1-vs-Tn summary — only meaningful (and non-redundant with
        # the consecutive breakdown above) when there are 3+ dates.
        progress(95, f"Computing overall change {dates[0]} → {dates[-1]}...")
        feats_overall = build_feature_array(first_bands, curr_bands, first_indices,
                                            curr_indices, use_texture=True)
        model = get_model()
        prob_overall = run_rf_inference(feats_overall, model)
        mask_overall = postprocess_change_map(prob_overall)
        mask_overall = human_change_filter(mask_overall, first_indices, curr_indices)

        save_change_mask_png(mask_overall, prob_overall, out_dir / "change_overall.png")
        geojson_overall = build_geojson(vectorize_changes(mask_overall, bbox, prob_overall))
        save_geojson(geojson_overall, out_dir / "changes_overall.geojson")

        stats_overall = compute_statistics(mask_overall, prob_overall)
        interpretation_overall = generate_interpretation(
            stats_overall, first_indices, curr_indices, bbox)

        overall_change = {
            "from_date": actual_dates[0],
            "to_date": actual_dates[-1],
            "stats": stats_overall,
            "interpretation": interpretation_overall,
        }

    progress(100, "Analysis complete.")

    any_synthetic = any(s == "synthetic_fallback" for s in data_sources)
    return {
        "job_id":           job_id,
        "bbox":             bbox,
        "dates":            dates,
        "actual_dates":     actual_dates,
        "cloud_covers":     cloud_covers,
        "timeline":         timeline,
        "overall_change":   overall_change,
        "model_used":       "rf",
        "output_dir":       str(out_dir),
        "data_sources":     data_sources,
        "fallback_reasons": fallback_reasons,
        # Convenience summary flag: True if ANY date in this job used
        # synthetic fallback rather than real Sentinel-2 imagery — the UI/PDF
        # must surface this prominently rather than presenting mixed results
        # as uniformly "real".
        "any_synthetic":    any_synthetic,
    }

def run_monitoring_pipeline(job_id: str, bbox: list,
                            dates: list,
                            progress_callback=None) -> dict:
    return run_analysis_pipeline(job_id, bbox, dates, progress_callback)
