"""
Statistics computation from change masks and probability maps.
"""
import numpy as np
import logging
from scipy import ndimage

logger = logging.getLogger(__name__)

PIXEL_AREA_M2 = 100  # 10m x 10m Sentinel-2 pixel


def compute_statistics(change_mask: np.ndarray,
                       prob_map: np.ndarray,
                       pixel_area_m2: int = PIXEL_AREA_M2) -> dict:
    """
    Compute full statistics from change mask and probability map.
    Returns dict suitable for API response and DB storage.
    """
    total_pixels   = change_mask.size
    changed_pixels = int(change_mask.sum())

    if changed_pixels == 0:
        return {
            "changed_area_m2": 0,
            "changed_area_ha": 0.0,
            "change_percent": 0.0,
            "num_clusters": 0,
            "mean_confidence": 0.0,
            "high_confidence_area_ha": 0.0,
        }

    labeled, n_clusters = ndimage.label(change_mask)

    # Cluster size distribution
    cluster_sizes = [
        int((labeled == i).sum()) for i in range(1, n_clusters + 1)
    ]

    change_probs = prob_map[change_mask == 1]
    mean_conf    = float(change_probs.mean())
    high_conf_px = int((prob_map > 0.75).sum())

    stats = {
        "changed_area_m2":        changed_pixels * pixel_area_m2,
        "changed_area_ha":        round(changed_pixels * pixel_area_m2 / 10000, 2),
        "change_percent":         round(changed_pixels / total_pixels * 100, 2),
        "num_clusters":           n_clusters,
        "mean_confidence":        round(mean_conf, 3),
        "high_confidence_area_ha": round(high_conf_px * pixel_area_m2 / 10000, 2),
        "largest_cluster_ha":     round(max(cluster_sizes) * pixel_area_m2 / 10000, 2),
        "median_cluster_ha":      round(
            float(np.median(cluster_sizes)) * pixel_area_m2 / 10000, 2
        ),
    }

    logger.info(f"Stats: {stats['changed_area_ha']} ha changed "
                f"({stats['change_percent']}%), {n_clusters} clusters")
    return stats


def compute_monitoring_timeline(masks: list, dates: list,
                                pixel_area_m2: int = PIXEL_AREA_M2) -> list:
    """
    Compute time-series stats for area monitoring (F3).
    masks: list of binary change masks relative to T1
    dates: list of date strings matching masks (from T2 onward)
    Returns list of {date, changed_area_ha, change_percent} dicts.
    """
    timeline = []
    for mask, date in zip(masks, dates):
        changed = int(mask.sum())
        total   = mask.size
        timeline.append({
            "date":             date,
            "changed_area_ha":  round(changed * pixel_area_m2 / 10000, 2),
            "change_percent":   round(changed / total * 100, 2),
        })
    return timeline
