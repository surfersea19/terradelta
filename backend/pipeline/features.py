"""
Feature engineering for change detection.
Constructs a 34-feature vector per pixel from T1/T2 band arrays + indices.
Features: raw bands (6+6), spectral indices (4+4), differences (10), ratios (4)
"""
import numpy as np
import logging
from skimage.feature import graycomatrix, graycoprops

logger = logging.getLogger(__name__)

BAND_NAMES = ["B02", "B03", "B04", "B08", "B11", "B12"]
INDEX_NAMES = ["NDVI", "NDBI", "NDWI", "BSI"]


def compute_glcm_features(band: np.ndarray, window: int = 5) -> dict:
    """
    Compute GLCM texture features (contrast, homogeneity, energy) over a band.
    Uses a simplified per-patch approach — efficient for moderate AOI sizes.
    Returns dict of (H, W) float32 arrays.
    """
    H, W = band.shape
    contrast   = np.zeros((H, W), dtype=np.float32)
    homogeneity = np.zeros((H, W), dtype=np.float32)
    energy     = np.zeros((H, W), dtype=np.float32)

    # Quantize to 32 levels for GLCM computation
    band_q = np.clip((band * 31).astype(np.uint8), 0, 31)

    half = window // 2
    # Pad to avoid border issues
    pad = np.pad(band_q, half, mode='reflect')

    for i in range(H):
        for j in range(W):
            patch = pad[i:i + window, j:j + window]
            glcm = graycomatrix(patch, distances=[1], angles=[0],
                                levels=32, symmetric=True, normed=True)
            contrast[i, j]    = graycoprops(glcm, 'contrast')[0, 0]
            homogeneity[i, j] = graycoprops(glcm, 'homogeneity')[0, 0]
            energy[i, j]      = graycoprops(glcm, 'energy')[0, 0]

    return {"contrast": contrast, "homogeneity": homogeneity, "energy": energy}


def compute_glcm_fast(band: np.ndarray, window: int = 7) -> dict:
    """
    Fast approximation of GLCM features using local statistics.
    For production speed — proper GLCM is too slow for large AOIs pixel-wise.
    """
    from scipy.ndimage import uniform_filter, generic_filter

    band_f = band.astype(np.float32)

    # Local mean
    local_mean = uniform_filter(band_f, size=window)
    # Local variance (proxy for contrast)
    local_sq_mean = uniform_filter(band_f ** 2, size=window)
    local_var = np.clip(local_sq_mean - local_mean ** 2, 0, None)
    contrast = local_var.astype(np.float32)

    # Local range (proxy for energy inverse)
    def local_range(values):
        return values.max() - values.min()
    from scipy.ndimage import generic_filter
    # Approximate with std deviation
    local_std = np.sqrt(local_var)
    energy = (1.0 / (1.0 + local_std)).astype(np.float32)  # inverse std = smoothness
    homogeneity = energy.copy()

    return {"contrast": contrast, "homogeneity": homogeneity, "energy": energy}


def build_feature_array(t1_bands: dict, t2_bands: dict,
                        t1_indices: dict, t2_indices: dict,
                        use_texture: bool = True) -> np.ndarray:
    """
    Build (H, W, N_features) float32 array.

    Feature groups:
    - T1 raw bands (6)
    - T2 raw bands (6)
    - T1 spectral indices (4)
    - T2 spectral indices (4)
    - Difference (T2 - T1): raw bands (6) + indices (4) = (10)
    - Log ratio: log(T2/T1 + eps) for raw bands (6)
    - Optional texture: T1 contrast/homogeneity/energy on B04 (3)
    - Optional texture: T2 contrast/homogeneity/energy on B04 (3)
    Total without texture: 36 | With texture: 42
    """
    eps = 1e-6

    # Reference shape
    H, W = t1_bands["B04"].shape
    feature_maps = []

    # T1 bands
    for b in BAND_NAMES:
        arr = t1_bands[b]
        if arr.shape != (H, W):
            arr = np.zeros((H, W), dtype=np.float32)
        feature_maps.append(arr)

    # T2 bands
    for b in BAND_NAMES:
        arr = t2_bands[b]
        if arr.shape != (H, W):
            arr = np.zeros((H, W), dtype=np.float32)
        feature_maps.append(arr)

    # T1 indices
    for idx in INDEX_NAMES:
        feature_maps.append(t1_indices.get(idx, np.zeros((H, W), dtype=np.float32)))

    # T2 indices
    for idx in INDEX_NAMES:
        feature_maps.append(t2_indices.get(idx, np.zeros((H, W), dtype=np.float32)))

    # Difference: T2 - T1 for bands
    for b in BAND_NAMES:
        diff = t2_bands[b] - t1_bands[b]
        feature_maps.append(diff.astype(np.float32))

    # Difference: T2 - T1 for indices
    for idx in INDEX_NAMES:
        diff = t2_indices.get(idx, np.zeros((H, W))) - t1_indices.get(idx, np.zeros((H, W)))
        feature_maps.append(diff.astype(np.float32))

    # Log ratio for raw bands
    for b in BAND_NAMES:
        ratio = np.log(t2_bands[b] / (t1_bands[b] + eps) + eps)
        feature_maps.append(np.clip(ratio, -5, 5).astype(np.float32))

    # Texture features (fast approximation)
    if use_texture:
        t1_tex = compute_glcm_fast(t1_bands["B04"])
        t2_tex = compute_glcm_fast(t2_bands["B04"])
        for key in ["contrast", "homogeneity", "energy"]:
            feature_maps.append(t1_tex[key])
            feature_maps.append(t2_tex[key])

    # Stack to (H, W, N_features)
    features = np.stack(feature_maps, axis=2)

    # Replace NaNs (cloud masked pixels) with 0
    features = np.nan_to_num(features, nan=0.0)

    logger.info(f"Feature array shape: {features.shape}")
    return features.astype(np.float32)
