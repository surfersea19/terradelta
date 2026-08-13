"""
Image export utilities: save before/after true-color PNGs and change mask PNGs.
"""
import numpy as np
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def save_rgb_image(rgb_array: np.ndarray, path: Path) -> None:
    """Save (H, W, 3) uint8 array as PNG."""
    img = Image.fromarray(rgb_array, mode="RGB")
    img.save(str(path), format="PNG", optimize=True)
    logger.info(f"Saved RGB image: {path} ({rgb_array.shape})")


def save_change_mask_png(change_mask: np.ndarray,
                         prob_map: np.ndarray,
                         path: Path) -> None:
    """
    Save change mask as RGBA PNG:
    - Changed pixels: red with alpha proportional to confidence
    - No-change pixels: fully transparent
    """
    H, W = change_mask.shape
    rgba = np.zeros((H, W, 4), dtype=np.uint8)

    # Red channel for change pixels
    change_bool = change_mask.astype(bool)
    rgba[change_bool, 0] = 230   # R
    rgba[change_bool, 1] = 50    # G (slight orange tint)
    rgba[change_bool, 2] = 30    # B
    # Alpha proportional to confidence
    if prob_map is not None:
        alpha = np.clip(prob_map * 255, 100, 220).astype(np.uint8)
        rgba[change_bool, 3] = alpha[change_bool]
    else:
        rgba[change_bool, 3] = 180

    img = Image.fromarray(rgba, mode="RGBA")
    img.save(str(path), format="PNG")
    logger.info(f"Saved change mask: {path}")


def save_geojson(geojson: dict, path: Path) -> None:
    """Save GeoJSON dict to file."""
    import json
    with open(path, "w") as f:
        json.dump(geojson, f, indent=2)
    logger.info(f"Saved GeoJSON: {path} ({len(geojson.get('features', []))} features)")


def ensure_output_dir(base_dir: Path, job_id: str) -> Path:
    """Create and return output directory for a job."""
    out_dir = base_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
