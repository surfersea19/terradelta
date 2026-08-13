"""
ml/prepare_data.py — Prepare training features from labeled imagery.

Given a directory of Sentinel-2 band files + binary change mask labels,
extracts pixel-level features and saves X_train.npy / y_train.npy.

Expected structure:
  data_dir/
    scene_01/
      T1/  B02.tif B03.tif B04.tif B08.tif B11.tif B12.tif
      T2/  B02.tif B03.tif B04.tif B08.tif B11.tif B12.tif
      change_mask.tif   (binary uint8, 1=change, 0=no-change)
    scene_02/
      ...

Usage:
    python prepare_data.py --data-dir ./raw_scenes --output-dir ./data
"""
import argparse
import logging
import sys
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

BANDS = ['B02', 'B03', 'B04', 'B08', 'B11', 'B12']


def load_scene(scene_dir: Path):
    """Load T1 bands, T2 bands, and change mask for one scene."""
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError:
        logger.error("rasterio not installed: pip install rasterio")
        sys.exit(1)

    t1_dir   = scene_dir / 'T1'
    t2_dir   = scene_dir / 'T2'
    mask_pth = scene_dir / 'change_mask.tif'

    if not (t1_dir.exists() and t2_dir.exists() and mask_pth.exists()):
        logger.warning(f"Skipping {scene_dir.name}: missing T1/T2/change_mask")
        return None, None, None

    def load_bands(band_dir, ref_shape=None):
        arrs = {}
        for b in BANDS:
            tif = band_dir / f'{b}.tif'
            if not tif.exists():
                logger.warning(f"Missing band {b} in {band_dir}")
                continue
            with rasterio.open(tif) as src:
                if ref_shape and src.shape != ref_shape:
                    data = src.read(1, out_shape=ref_shape,
                                    resampling=Resampling.bilinear)
                else:
                    data = src.read(1)
            arrs[b] = np.clip(data.astype(np.float32) / 10000.0, 0, 1)
        return arrs

    t1 = load_bands(t1_dir)
    if not t1:
        return None, None, None

    ref_shape = next(iter(t1.values())).shape
    t2 = load_bands(t2_dir, ref_shape)

    with rasterio.open(mask_pth) as src:
        mask = src.read(1)
    if mask.shape != ref_shape:
        import cv2
        mask = cv2.resize(mask.astype(np.uint8), (ref_shape[1], ref_shape[0]),
                          interpolation=cv2.INTER_NEAREST)

    return t1, t2, mask.astype(np.uint8)


def scene_to_features(t1_bands, t2_bands):
    """Extract feature array from band dicts. Returns (H, W, N_features)."""
    # Add parent dir to path so we can import pipeline modules
    sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
    from pipeline.preprocessing import compute_spectral_indices
    from pipeline.features import build_feature_array

    t1_indices = compute_spectral_indices(t1_bands)
    t2_indices = compute_spectral_indices(t2_bands)
    return build_feature_array(t1_bands, t2_bands, t1_indices, t2_indices,
                               use_texture=True)


def prepare(data_dir: Path, output_dir: Path,
            max_pixels_per_scene: int = 10000, balance: bool = True):
    output_dir.mkdir(parents=True, exist_ok=True)

    scene_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    if not scene_dirs:
        logger.error(f"No scene subdirectories found in {data_dir}")
        sys.exit(1)

    logger.info(f"Found {len(scene_dirs)} scenes in {data_dir}")

    X_all, y_all = [], []
    rng = np.random.default_rng(42)

    for scene_dir in scene_dirs:
        logger.info(f"Processing: {scene_dir.name}")
        t1, t2, mask = load_scene(scene_dir)
        if t1 is None:
            continue

        try:
            features = scene_to_features(t1, t2)  # (H, W, N)
        except Exception as e:
            logger.error(f"Feature extraction failed for {scene_dir.name}: {e}")
            continue

        H, W, N = features.shape
        X_flat = features.reshape(-1, N)
        y_flat = mask.reshape(-1)

        # Sample pixels (stratified)
        change_idx    = np.where(y_flat == 1)[0]
        nochange_idx  = np.where(y_flat == 0)[0]

        n_change   = min(len(change_idx),   max_pixels_per_scene // 2)
        n_nochange = min(len(nochange_idx),  max_pixels_per_scene // 2)

        if n_change == 0:
            logger.warning(f"No change pixels in {scene_dir.name}, skipping")
            continue

        sel_c  = rng.choice(change_idx,   n_change,   replace=False)
        sel_nc = rng.choice(nochange_idx, n_nochange, replace=False)
        sel    = np.concatenate([sel_c, sel_nc])

        X_all.append(X_flat[sel])
        y_all.append(y_flat[sel])
        logger.info(f"  Extracted {n_change} change + {n_nochange} no-change pixels")

    if not X_all:
        logger.error("No valid scenes processed. Exiting.")
        sys.exit(1)

    X = np.vstack(X_all).astype(np.float32)
    y = np.concatenate(y_all).astype(np.int32)

    # Shuffle
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]

    logger.info(f"\nFinal dataset: {X.shape[0]:,} samples × {X.shape[1]} features")
    logger.info(f"Change fraction: {y.mean():.2%}")

    np.save(output_dir / 'X_train.npy', X)
    np.save(output_dir / 'y_train.npy', y)
    logger.info(f"Saved X_train.npy and y_train.npy to {output_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare TerraDelta training features')
    parser.add_argument('--data-dir',             type=Path, default=Path('./raw_scenes'))
    parser.add_argument('--output-dir',           type=Path, default=Path('./data'))
    parser.add_argument('--max-pixels-per-scene', type=int,  default=10000)
    args = parser.parse_args()
    prepare(args.data_dir, args.output_dir, args.max_pixels_per_scene)
