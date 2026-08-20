"""
Self-consistent synthetic training data for the demo/fallback RF model.

WHY THIS FILE EXISTS:
The previous demo-model trainers (backend/pipeline/inference.py::train_demo_model
and ml/train_rf.py::make_synthetic_dataset) hand-crafted 42-dim feature vectors
by injecting Gaussian offsets at HARD-CODED column indices that they assumed
matched pipeline/features.py::build_feature_array()'s layout. They didn't:
  - train_demo_model wrote "change" signal into columns 24:30 and 30/31,
    but the real layout has those as DIFF_B11/B12/NDVI/NDBI/NDWI/BSI (24-29)
    and LRATIO_B02/B03 (30-31) — not the band-diff/NDVI-diff/NDBI-diff it
    intended.
  - ml/train_rf.py's synthetic generator had a similar, differently-wrong
    offset scheme, and even referenced indices 36:42 as "log ratio" when
    that block is actually the texture features.
So even setting aside "trained on fake data, not real imagery", the model
was mis-calibrated against its OWN feature space.

This module removes that entire class of bug by construction: it generates
synthetic Sentinel-2-like band scenes (the same generator used for the
demo/fallback imagery), inserts known "development" patches with a real
ground-truth mask, then runs those bands through the ACTUAL preprocessing +
feature pipeline (preprocess_bands + build_feature_array) — the exact same
code path used at inference time. Whatever the real feature layout is, the
training data is built the same way, so there can be no index drift.

This remains a synthetic-data stopgap (not real Sentinel-2 imagery) until a
real labeled dataset is available — see ml/prepare_data.py for that path.
"""
import logging
import numpy as np

from pipeline.data_access import generate_synthetic_sentinel2, generate_change_scene
from pipeline.preprocessing import preprocess_bands
from pipeline.features import build_feature_array

logger = logging.getLogger(__name__)


def build_self_consistent_dataset(n_scenes: int = 24,
                                  max_pixels_per_scene: int = 6000,
                                  seed: int = 42) -> tuple:
    """
    Generate (X, y) by running synthetic T1/T2 scenes through the real
    feature-extraction pipeline, labeled with the true inserted-patch mask.
    Returns (X: (N, 42) float32, y: (N,) int32).
    """
    rng = np.random.default_rng(seed)
    X_all, y_all = [], []

    for i in range(n_scenes):
        seed1 = int(rng.integers(0, 1_000_000))
        seed2 = seed1 + 500

        t1_bands, _, _ = generate_synthetic_sentinel2([0, 0, 0.02, 0.02], seed=seed1)
        # Vary intensity across scenes so the model learns to detect both
        # strong, unambiguous change AND weaker/partial change — matches
        # both real-world partial/gradual development and the synthetic
        # fallback's progressive multi-date demo (see _progression_fraction
        # in pipeline/data_access.py).
        intensity = float(rng.uniform(0.4, 1.0))
        t2_bands, change_mask = generate_change_scene(
            t1_bands, change_fraction=rng.uniform(0.08, 0.25), seed=seed2,
            return_mask=True, intensity=intensity)

        t1_bands_p, t1_indices = preprocess_bands(t1_bands)
        t2_bands_p, t2_indices = preprocess_bands(t2_bands)

        features = build_feature_array(t1_bands_p, t2_bands_p, t1_indices, t2_indices,
                                       use_texture=True)
        H, W, N = features.shape
        X_flat = features.reshape(-1, N)
        y_flat = change_mask.reshape(-1)

        change_idx = np.where(y_flat == 1)[0]
        nochange_idx = np.where(y_flat == 0)[0]
        if len(change_idx) == 0:
            continue

        n_change = min(len(change_idx), max_pixels_per_scene // 2)
        n_nochange = min(len(nochange_idx), max_pixels_per_scene // 2)

        sel_c = rng.choice(change_idx, n_change, replace=False)
        sel_nc = rng.choice(nochange_idx, n_nochange, replace=False)
        sel = np.concatenate([sel_c, sel_nc])

        X_all.append(X_flat[sel])
        y_all.append(y_flat[sel])

    X = np.vstack(X_all).astype(np.float32)
    y = np.concatenate(y_all).astype(np.int32)

    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]

    logger.info(f"Self-consistent synthetic dataset: {X.shape[0]:,} samples x "
                f"{X.shape[1]} features, change fraction {y.mean():.2%}")
    return X, y
