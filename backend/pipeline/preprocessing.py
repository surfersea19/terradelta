"""
Band preprocessing: normalization, resampling, cloud masking.
Works on dict of float32 numpy arrays already in [0,1] reflectance.
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)


def clip_reflectance(bands: dict) -> dict:
    """Clip all bands to [0, 1] — handles sensor saturation artefacts."""
    return {k: np.clip(v, 0.0, 1.0) for k, v in bands.items()}


def compute_spectral_indices(bands: dict) -> dict:
    """
    Compute NDVI, NDBI, NDWI, BSI from band arrays.
    All indices returned in range [-1, 1].
    """
    eps = 1e-6
    B02 = bands["B02"]
    B03 = bands["B03"]
    B04 = bands["B04"]
    B08 = bands["B08"]
    B11 = bands["B11"]
    B12 = bands["B12"]

    NDVI = (B08 - B04) / (B08 + B04 + eps)
    NDBI = (B11 - B08) / (B11 + B08 + eps)
    NDWI = (B03 - B08) / (B03 + B08 + eps)
    BSI  = ((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02) + eps)

    return {
        "NDVI": np.clip(NDVI, -1, 1).astype(np.float32),
        "NDBI": np.clip(NDBI, -1, 1).astype(np.float32),
        "NDWI": np.clip(NDWI, -1, 1).astype(np.float32),
        "BSI":  np.clip(BSI,  -1, 1).astype(np.float32),
    }


def resample_to_10m(bands: dict) -> dict:
    """
    Resample any 20m bands (B11, B12) to match 10m bands.
    For synthetic data this is a no-op (all already same resolution).
    In real pipeline: use rasterio bilinear resampling.
    """
    import cv2
    reference = bands.get("B04")
    if reference is None:
        reference = next(iter(bands.values()))
    H, W = reference.shape
    resampled = {}
    for name, arr in bands.items():
        if arr.shape != (H, W):
            arr = cv2.resize(arr, (W, H), interpolation=cv2.INTER_LINEAR)
        resampled[name] = arr.astype(np.float32)
    return resampled


def apply_cloud_mask(bands: dict, cloud_mask: np.ndarray = None) -> dict:
    """
    Apply cloud mask (1=cloud, 0=clear) by setting masked pixels to NaN.
    If cloud_mask is None (synthetic data), no masking applied.
    """
    if cloud_mask is None:
        return bands
    masked = {}
    for name, arr in bands.items():
        arr = arr.copy().astype(np.float32)
        arr[cloud_mask == 1] = np.nan
        masked[name] = arr
    return masked


def preprocess_bands(bands: dict, cloud_mask: np.ndarray = None) -> tuple:
    """
    Full preprocessing chain for one image epoch.
    Returns: (preprocessed_bands, spectral_indices)
    """
    bands = clip_reflectance(bands)
    bands = resample_to_10m(bands)
    bands = apply_cloud_mask(bands, cloud_mask)
    indices = compute_spectral_indices(bands)
    return bands, indices


def bands_to_rgb(bands: dict, gamma: float = 0.5) -> np.ndarray:
    """
    Convert Sentinel-2 bands to display-ready RGB uint8.
    Uses B04(R), B03(G), B02(B) with gamma stretch.
    Returns (H, W, 3) uint8.
    """
    r = bands["B04"]
    g = bands["B03"]
    b = bands["B02"]

    # Stack and normalize — Sentinel-2 typical range ~0.0 - 0.3 for most scenes
    rgb = np.stack([r, g, b], axis=2)
    rgb = np.clip(rgb, 0, 0.3) / 0.3  # stretch to common range
    rgb = np.power(rgb, gamma)         # gamma for visual brightness
    rgb = np.clip(rgb * 255, 0, 255).astype(np.uint8)
    return rgb
