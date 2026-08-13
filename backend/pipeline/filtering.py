"""
Human-change filtering layer.
Uses spectral index deltas to suppress environmental/seasonal changes,
retaining only likely human-caused development signals.
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)


def human_change_filter(change_mask: np.ndarray,
                        t1_indices: dict,
                        t2_indices: dict,
                        ndbi_threshold: float = 0.04,
                        ndvi_threshold: float = -0.12,
                        ndwi_threshold: float = 0.15) -> np.ndarray:
    """
    Multi-rule spectral filter applied ON TOP of ML change mask.

    Keep a changed pixel if ANY of:
      Rule 1: NDBI increased significantly (new built-up surface)
      Rule 2: NDVI dropped AND NDBI didn't drop (construction clearing)
      Rule 3: BSI increased (bare soil — construction/excavation phase)

    Suppress if:
      Water rule: NDWI increased significantly (likely flooding)

    Returns filtered binary mask (uint8).
    """
    delta_ndvi = t2_indices["NDVI"] - t1_indices["NDVI"]
    delta_ndbi = t2_indices["NDBI"] - t1_indices["NDBI"]
    delta_ndwi = t2_indices["NDWI"] - t1_indices["NDWI"]
    delta_bsi  = t2_indices["BSI"]  - t1_indices["BSI"]

    # Human activity indicators
    new_builtup       = delta_ndbi > ndbi_threshold
    clearing_signal   = (delta_ndvi < ndvi_threshold) & (delta_ndbi > -0.02)
    excavation_signal = delta_bsi > 0.08

    human_indicator = new_builtup | clearing_signal | excavation_signal

    # Suppression: flooding / water body expansion
    water_expansion = delta_ndwi > ndwi_threshold

    # Apply filter to change mask
    filtered = change_mask.astype(bool) & human_indicator & ~water_expansion

    n_before = int(change_mask.sum())
    n_after  = int(filtered.sum())
    logger.info(f"Human filter: {n_before} → {n_after} change pixels "
                f"({n_before - n_after} removed as likely environmental)")

    return filtered.astype(np.uint8)


def temporal_stability_filter(masks: list) -> np.ndarray:
    """
    For multi-date monitoring: keep pixels that changed and STAYED changed.
    masks: list of binary np.ndarrays aligned to same shape.
    Returns mask of pixels changed in >= 60% of time steps.
    """
    if len(masks) < 2:
        return masks[0] if masks else np.array([])

    stack = np.stack(masks, axis=0).astype(np.float32)
    persistence = stack.mean(axis=0)  # fraction of dates showing change
    stable_change = (persistence >= 0.6).astype(np.uint8)

    logger.info(f"Temporal stability filter: {stable_change.sum()} persistent change pixels")
    return stable_change


def generate_interpretation(stats: dict,
                            t1_indices: dict,
                            t2_indices: dict,
                            bbox: list) -> str:
    """
    Rule-based plain-English interpretation of detected changes.
    No LLM dependency — deterministic and auditable.
    """
    area   = stats.get("changed_area_ha", 0)
    pct    = stats.get("change_percent", 0)
    n_clus = stats.get("num_clusters", 0)
    conf   = stats.get("mean_confidence", 0)

    if area == 0 or pct == 0:
        return ("No significant human-caused changes were detected in this area "
                "for the selected time period. The region appears stable, "
                "or any changes present are below the detection threshold.")

    # Spectral character of detected changes
    mean_delta_ndbi = float((t2_indices["NDBI"] - t1_indices["NDBI"]).mean())
    mean_delta_ndvi = float((t2_indices["NDVI"] - t1_indices["NDVI"]).mean())

    change_type = "land surface"
    if mean_delta_ndbi > 0.05:
        change_type = "impervious surface (buildings or roads)"
    elif mean_delta_ndbi > 0.02:
        change_type = "built-up area development"
    elif mean_delta_ndvi < -0.1:
        change_type = "vegetation clearance (possible pre-construction)"

    # Magnitude descriptor
    if pct > 20:
        magnitude = "Extensive"
    elif pct > 10:
        magnitude = "Significant"
    elif pct > 5:
        magnitude = "Moderate"
    else:
        magnitude = "Localised"

    # Cluster description
    cluster_desc = "concentrated in a single cluster" if n_clus == 1 \
        else f"distributed across {n_clus} distinct clusters"

    # Confidence note
    conf_note = ""
    if conf < 0.6:
        conf_note = " (lower confidence — visual verification recommended)"
    elif conf > 0.8:
        conf_note = " (high confidence)"

    interpretation = (
        f"{magnitude} {change_type} detected, covering approximately "
        f"{area:.1f} ha ({pct:.1f}% of the analysed area), "
        f"{cluster_desc}. "
        f"Changes are consistent with human-driven development activity{conf_note}. "
        f"Note: Sentinel-2 at 10 m resolution reliably detects objects >30 m; "
        f"individual buildings may not be resolved."
    )

    return interpretation
