"""
ml/train_rf.py — Random Forest change detection training script.

Usage:
    python train_rf.py --data-dir ./data --output-dir ./models

If no labeled data is available, runs in self-supervised demo mode
using synthetic Sentinel-2 scenes with known change labels.

After training, copies model to ../backend/models/rf_change_detector.pkl
"""
import argparse
import logging
import sys
import os
import json
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import (
    f1_score, precision_score, recall_score, jaccard_score,
    classification_report, confusion_matrix
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ── Synthetic data generation ─────────────────────────────────────────────────

def make_synthetic_dataset(n_scenes: int = 20, pixels_per_scene: int = 5000,
                           n_features: int = 42, seed: int = 42) -> tuple:
    """
    Generate synthetic change / no-change feature vectors.
    Simulates a plausible Sentinel-2 spectral + texture feature space.
    """
    rng = np.random.default_rng(seed)
    X_list, y_list = [], []

    for scene_i in range(n_scenes):
        scene_seed = seed + scene_i * 7
        rng_s = np.random.default_rng(scene_seed)

        # No-change pixels (~75% of scene)
        n_nc = int(pixels_per_scene * 0.75)
        X_nc = rng_s.normal(0, 0.05, (n_nc, n_features)).astype(np.float32)
        # Small residual noise in difference channels (24-35)
        X_nc[:, 24:36] = rng_s.normal(0, 0.02, (n_nc, 12))

        # Change pixels (~25% of scene) — simulated urban expansion
        n_c = pixels_per_scene - n_nc
        X_c = rng_s.normal(0, 0.05, (n_c, n_features)).astype(np.float32)
        # Band differences (T2 - T1): SWIR increases, NIR decreases
        X_c[:, 24] += rng_s.uniform(0.02, 0.06, n_c)   # B02 diff
        X_c[:, 25] += rng_s.uniform(0.02, 0.06, n_c)   # B03 diff
        X_c[:, 26] += rng_s.uniform(0.02, 0.05, n_c)   # B04 diff
        X_c[:, 27] -= rng_s.uniform(0.05, 0.15, n_c)   # B08 diff (NIR drops)
        X_c[:, 28] += rng_s.uniform(0.05, 0.12, n_c)   # B11 diff (SWIR rises)
        X_c[:, 29] += rng_s.uniform(0.03, 0.08, n_c)   # B12 diff
        # NDVI diff (drops) and NDBI diff (rises)
        X_c[:, 30] -= rng_s.uniform(0.10, 0.25, n_c)   # NDVI diff
        X_c[:, 31] += rng_s.uniform(0.05, 0.15, n_c)   # NDBI diff
        # Log ratio features
        X_c[:, 36:42] += rng_s.uniform(0.05, 0.2, (n_c, 6))

        X_list.append(np.vstack([X_nc, X_c]))
        y_list.append(np.array([0] * n_nc + [1] * n_c))

    X = np.vstack(X_list)
    y = np.concatenate(y_list)

    # Shuffle
    idx = np.random.default_rng(seed + 1).permutation(len(X))
    return X[idx], y[idx]


# ── Training ──────────────────────────────────────────────────────────────────

def train(data_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try to load real labeled data (OSCD format)
    # Expected: data_dir/X_train.npy, data_dir/y_train.npy
    X_path = data_dir / 'X_train.npy'
    y_path = data_dir / 'y_train.npy'

    if X_path.exists() and y_path.exists():
        logger.info(f"Loading real training data from {data_dir}")
        X = np.load(X_path).astype(np.float32)
        y = np.load(y_path).astype(int)
        logger.info(f"Dataset: {X.shape[0]:,} samples, {X.shape[1]} features, "
                    f"change fraction: {y.mean():.2%}")
    else:
        logger.warning(f"No training data at {data_dir}. Using synthetic dataset.")
        logger.info("To use real data: save X_train.npy (N, 42) and y_train.npy (N,) "
                    "built from OSCD or custom labeled patches.")
        X, y = make_synthetic_dataset(n_scenes=30, pixels_per_scene=8000)
        logger.info(f"Synthetic dataset: {X.shape[0]:,} samples, "
                    f"change fraction: {y.mean():.2%}")

    # ── Cross-validation ──────────────────────────────────────────────────
    logger.info("Running 5-fold cross-validation...")
    base_clf = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_leaf=5,
            class_weight='balanced',
            n_jobs=-1,
            random_state=42,
        ))
    ])

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(
        base_clf, X, y,
        cv=skf,
        scoring=['f1', 'precision', 'recall'],
        n_jobs=-1,
        verbose=0,
    )

    logger.info("Cross-validation results:")
    for metric in ['test_f1', 'test_precision', 'test_recall']:
        scores = cv_results[metric]
        logger.info(f"  {metric:20s}: {scores.mean():.4f} ± {scores.std():.4f}")

    # ── Final training on full dataset ────────────────────────────────────
    logger.info("Training final model on full dataset...")
    final_model = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_leaf=5,
            class_weight='balanced',
            n_jobs=-1,
            random_state=42,
        ))
    ])
    final_model.fit(X, y)

    # Evaluation on training data (sanity check — real eval needs held-out set)
    y_pred = final_model.predict(X)
    y_prob = final_model.predict_proba(X)[:, 1]

    metrics = {
        'f1':           float(f1_score(y, y_pred)),
        'precision':    float(precision_score(y, y_pred)),
        'recall':       float(recall_score(y, y_pred)),
        'iou':          float(jaccard_score(y, y_pred)),
        'cv_f1_mean':   float(cv_results['test_f1'].mean()),
        'cv_f1_std':    float(cv_results['test_f1'].std()),
        'n_samples':    int(len(X)),
        'n_features':   int(X.shape[1]),
        'change_frac':  float(y.mean()),
    }

    logger.info("Final model metrics (train set — held-out test needed for real eval):")
    for k, v in metrics.items():
        logger.info(f"  {k:25s}: {v:.4f}" if isinstance(v, float) else f"  {k:25s}: {v}")

    logger.info("\nClassification Report:")
    print(classification_report(y, y_pred, target_names=['No Change', 'Change']))

    # Feature importance top-10
    importances = final_model.named_steps['clf'].feature_importances_
    top_idx = np.argsort(importances)[::-1][:10]
    FEATURE_NAMES = (
        [f'T1_{b}' for b in ['B02','B03','B04','B08','B11','B12']] +
        [f'T2_{b}' for b in ['B02','B03','B04','B08','B11','B12']] +
        ['T1_NDVI','T1_NDBI','T1_NDWI','T1_BSI'] +
        ['T2_NDVI','T2_NDBI','T2_NDWI','T2_BSI'] +
        [f'DIFF_{b}' for b in ['B02','B03','B04','B08','B11','B12']] +
        ['DIFF_NDVI','DIFF_NDBI','DIFF_NDWI','DIFF_BSI'] +
        [f'LRATIO_{b}' for b in ['B02','B03','B04','B08','B11','B12']] +
        ['T1_contrast','T1_homogeneity','T1_energy',
         'T2_contrast','T2_homogeneity','T2_energy']
    )
    # Pad names if needed
    while len(FEATURE_NAMES) < len(importances):
        FEATURE_NAMES.append(f'feat_{len(FEATURE_NAMES)}')

    logger.info("Top-10 feature importances:")
    for rank, idx in enumerate(top_idx):
        name = FEATURE_NAMES[idx] if idx < len(FEATURE_NAMES) else f'feat_{idx}'
        logger.info(f"  {rank+1:2d}. {name:25s}: {importances[idx]:.4f}")

    # ── Save ──────────────────────────────────────────────────────────────
    model_path = output_dir / 'rf_change_detector.pkl'
    joblib.dump(final_model, model_path)
    logger.info(f"\nModel saved: {model_path}")

    metrics_path = output_dir / 'training_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Metrics saved: {metrics_path}")

    # Copy to backend/models
    backend_model_dir = Path(__file__).parent.parent / 'backend' / 'models'
    backend_model_dir.mkdir(parents=True, exist_ok=True)
    backend_model_path = backend_model_dir / 'rf_change_detector.pkl'
    import shutil
    shutil.copy(model_path, backend_model_path)
    logger.info(f"Model copied to backend: {backend_model_path}")

    return final_model, metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train TerraDelta RF change detector')
    parser.add_argument('--data-dir',   type=Path, default=Path('./data'),
                        help='Directory with X_train.npy and y_train.npy')
    parser.add_argument('--output-dir', type=Path, default=Path('./models'),
                        help='Where to save trained model')
    args = parser.parse_args()

    train(args.data_dir, args.output_dir)
