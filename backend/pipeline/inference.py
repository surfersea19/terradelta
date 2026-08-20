"""
ML Inference for change detection.
Primary: Random Forest classifier (scikit-learn).
Includes model training on synthetic data when no pre-trained model exists.
"""
import os
import logging
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "models" / "rf_change_detector.pkl"


def train_demo_model() -> Pipeline:
    """
    Train a Random Forest on a SELF-CONSISTENT synthetic dataset.
    Used when no pre-trained model exists (first run / dev environment).

    Previously this generated hand-offset Gaussian vectors that assumed a
    feature-column layout that didn't match build_feature_array()'s real
    layout (see pipeline/synthetic_training.py docstring for the full
    explanation). This now runs synthetic imagery through the ACTUAL
    preprocessing + feature pipeline, so the 42 columns are guaranteed
    consistent with what orchestrator.py produces at inference time.

    Still a synthetic-data stopgap, not real Sentinel-2 — see
    pipeline/synthetic_training.py and ml/prepare_data.py for the path to
    training on real labeled imagery.
    """
    logger.info("Training demo RF model on self-consistent synthetic data...")
    from pipeline.synthetic_training import build_self_consistent_dataset

    X, y = build_self_consistent_dataset(n_scenes=24, max_pixels_per_scene=6000, seed=42)

    model = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_leaf=5,
            class_weight='balanced',
            n_jobs=-1,
            random_state=42
        ))
    ])
    model.fit(X, y)

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Demo model saved to {MODEL_PATH}")
    return model


def load_model() -> Pipeline:
    """Load pre-trained RF model, training a demo model if none exists."""
    if MODEL_PATH.exists():
        logger.info(f"Loading RF model from {MODEL_PATH}")
        return joblib.load(MODEL_PATH)
    else:
        logger.warning("No pre-trained model found. Training demo model.")
        return train_demo_model()


def run_rf_inference(features: np.ndarray, model: Pipeline) -> np.ndarray:
    """
    Run RF inference on (H, W, N_features) array.
    Returns probability map (H, W) float32 in [0, 1].
    """
    H, W, N = features.shape
    X = features.reshape(-1, N)

    # Handle potential feature count mismatch with demo model (42 features)
    model_n_features = model.named_steps['clf'].n_features_in_
    if N != model_n_features:
        logger.warning(f"Feature count mismatch: got {N}, model expects {model_n_features}. Padding/truncating.")
        if N < model_n_features:
            pad = np.zeros((X.shape[0], model_n_features - N), dtype=np.float32)
            X = np.hstack([X, pad])
        else:
            X = X[:, :model_n_features]

    # Predict in chunks to avoid memory issues
    chunk_size = 50000
    probs = np.zeros(X.shape[0], dtype=np.float32)

    for start in range(0, X.shape[0], chunk_size):
        end = min(start + chunk_size, X.shape[0])
        chunk_probs = model.predict_proba(X[start:end])[:, 1]
        probs[start:end] = chunk_probs

    return probs.reshape(H, W)


# Module-level model cache
_model_cache = None


def get_model() -> Pipeline:
    global _model_cache
    if _model_cache is None:
        _model_cache = load_model()
    return _model_cache
