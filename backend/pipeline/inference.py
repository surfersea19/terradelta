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
    Train a Random Forest on synthetic change/no-change data.
    Used when no pre-trained model exists (first run / dev environment).
    Produces a functional model — not production-quality without real labeled data.
    """
    logger.info("Training demo RF model on synthetic data...")
    rng = np.random.default_rng(42)

    n_features = 42  # with texture features
    n_samples = 20000

    # Simulate feature distributions for change vs no-change
    # Change pixels: higher diff features, lower NDVI diff, higher NDBI diff
    n_change = n_samples // 4
    n_nochange = n_samples - n_change

    # No-change: small random features
    X_nochange = rng.normal(0, 0.05, (n_nochange, n_features)).astype(np.float32)

    # Change: larger diffs in specific feature positions
    X_change = rng.normal(0, 0.05, (n_change, n_features)).astype(np.float32)
    # Feature positions 24-29: band differences (key change signal)
    X_change[:, 24:30] += rng.uniform(0.1, 0.3, (n_change, 6))
    # NDBI difference (index 30+4=34 approx)
    X_change[:, 30] -= rng.uniform(0.1, 0.25, n_change)  # NDVI drops
    X_change[:, 31] += rng.uniform(0.05, 0.15, n_change)  # NDBI rises

    X = np.vstack([X_nochange, X_change])
    y = np.array([0] * n_nochange + [1] * n_change)

    # Shuffle
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]

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
