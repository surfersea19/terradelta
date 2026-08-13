"""
ml/train_siamese.py — Siamese ResNet-18 patch classifier training script.
Designed to run on Google Colab (free T4 GPU).

Architecture: two ResNet-18 encoders (shared weights) → concat embeddings → MLP → change prob
Input: 32×32 patches from T1 and T2 (6 bands each)
Output: binary change probability

Usage (Colab):
    !python train_siamese.py --data-dir /content/drive/MyDrive/terradelta/data
"""
import argparse
import logging
import json
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


def build_model(in_channels: int = 6):
    """Build Siamese ResNet-18 patch classifier."""
    import torch
    import torch.nn as nn
    import torchvision.models as models

    class SiameseResNet(nn.Module):
        def __init__(self, in_channels=6):
            super().__init__()
            backbone = models.resnet18(weights=None)
            # Adapt first conv for 6-band input
            backbone.conv1 = nn.Conv2d(
                in_channels, 64, kernel_size=7, stride=2, padding=3, bias=False)
            # Use all layers except the final FC
            self.encoder = nn.Sequential(*list(backbone.children())[:-1])  # (B, 512, 1, 1)

            self.classifier = nn.Sequential(
                nn.Linear(512 * 3, 256),
                nn.BatchNorm1d(256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(256, 64),
                nn.ReLU(inplace=True),
                nn.Linear(64, 1),
                nn.Sigmoid(),
            )

        def encode(self, x):
            return self.encoder(x).flatten(1)  # (B, 512)

        def forward(self, x1, x2):
            e1 = self.encode(x1)
            e2 = self.encode(x2)
            diff = (e1 - e2).abs()
            combined = torch.cat([e1, e2, diff], dim=1)  # (B, 1536)
            return self.classifier(combined).squeeze(1)  # (B,)

    return SiameseResNet(in_channels)


def make_synthetic_patches(n_change: int = 2000, n_nochange: int = 6000,
                           patch_size: int = 32, n_bands: int = 6, seed: int = 42):
    """
    Generate synthetic T1/T2 patch pairs with change labels.
    Returns (patches_t1, patches_t2, labels) as numpy arrays.
    """
    rng = np.random.default_rng(seed)

    # No-change pairs: both patches drawn from similar distributions
    t1_nc = rng.uniform(0.02, 0.35, (n_nochange, n_bands, patch_size, patch_size)).astype(np.float32)
    t2_nc = t1_nc + rng.normal(0, 0.01, t1_nc.shape).astype(np.float32)
    t2_nc = np.clip(t2_nc, 0, 1)

    # Change pairs: T2 has built-up spectral shift
    t1_c = rng.uniform(0.02, 0.35, (n_change, n_bands, patch_size, patch_size)).astype(np.float32)
    t2_c = t1_c.copy()
    # Simulate construction: NIR (ch 3) drops, SWIR (ch 4,5) rise, visible rise
    shift = rng.uniform(0.05, 0.15, (n_change, 1, patch_size, patch_size)).astype(np.float32)
    t2_c[:, 0:3] += shift * 0.6    # visible bands increase
    t2_c[:, 3] -= shift[:, 0] * 1.2  # NIR drops
    t2_c[:, 4:] += shift[:, 0] * 1.0  # SWIR rises
    t2_c = np.clip(t2_c + rng.normal(0, 0.01, t2_c.shape).astype(np.float32), 0, 1)

    t1 = np.vstack([t1_nc, t1_c])
    t2 = np.vstack([t2_nc, t2_c])
    y  = np.array([0] * n_nochange + [1] * n_change, dtype=np.float32)

    idx = rng.permutation(len(t1))
    return t1[idx], t2[idx], y[idx]


def train(data_dir: Path, output_dir: Path, epochs: int = 30, batch_size: int = 64):
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import TensorDataset, DataLoader
    except ImportError:
        logger.error("PyTorch not installed. Install with: pip install torch torchvision")
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Training on: {device}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load or generate data
    t1_path = data_dir / 'patches_t1.npy'
    t2_path = data_dir / 'patches_t2.npy'
    y_path  = data_dir / 'patch_labels.npy'

    if t1_path.exists() and t2_path.exists() and y_path.exists():
        logger.info("Loading real patch data...")
        t1 = np.load(t1_path).astype(np.float32)
        t2 = np.load(t2_path).astype(np.float32)
        y  = np.load(y_path).astype(np.float32)
    else:
        logger.warning("No patch data found — using synthetic patches.")
        logger.info("For real data: save patches_t1.npy, patches_t2.npy (N, 6, 32, 32) "
                    "and patch_labels.npy (N,) in data dir.")
        t1, t2, y = make_synthetic_patches(n_change=3000, n_nochange=9000)

    logger.info(f"Dataset: {len(y):,} patches, change fraction: {y.mean():.2%}")

    # Train/val split (80/20)
    n = len(y)
    split = int(n * 0.8)
    rng = np.random.default_rng(42)
    idx = rng.permutation(n)

    def make_loader(indices, shuffle):
        t1_t = torch.tensor(t1[indices])
        t2_t = torch.tensor(t2[indices])
        y_t  = torch.tensor(y[indices])
        return DataLoader(TensorDataset(t1_t, t2_t, y_t),
                          batch_size=batch_size, shuffle=shuffle,
                          num_workers=0, pin_memory=(device.type == 'cuda'))

    train_loader = make_loader(idx[:split], shuffle=True)
    val_loader   = make_loader(idx[split:], shuffle=False)

    model = build_model(in_channels=t1.shape[1]).to(device)

    # Class imbalance weight
    pos_weight = torch.tensor([(y == 0).sum() / max((y == 1).sum(), 1)]).to(device)
    criterion  = nn.BCELoss()  # Sigmoid already in model
    optimizer  = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    scheduler  = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_f1 = 0.0
    history = []

    for epoch in range(1, epochs + 1):
        # ── Train ──
        model.train()
        train_loss = 0.0
        for x1, x2, labels in train_loader:
            x1, x2, labels = x1.to(device), x2.to(device), labels.to(device)
            optimizer.zero_grad()
            preds = model(x1, x2)
            loss  = criterion(preds, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()
        scheduler.step()

        # ── Validate ──
        model.eval()
        val_preds, val_labels = [], []
        with torch.no_grad():
            for x1, x2, labels in val_loader:
                x1, x2 = x1.to(device), x2.to(device)
                preds = model(x1, x2).cpu().numpy()
                val_preds.extend((preds > 0.5).astype(int).tolist())
                val_labels.extend(labels.numpy().astype(int).tolist())

        from sklearn.metrics import f1_score, precision_score, recall_score
        vp = np.array(val_preds)
        vl = np.array(val_labels)
        val_f1   = f1_score(vl, vp, zero_division=0)
        val_prec = precision_score(vl, vp, zero_division=0)
        val_rec  = recall_score(vl, vp, zero_division=0)

        avg_train_loss = train_loss / len(train_loader)
        logger.info(f"Epoch {epoch:3d}/{epochs} | loss={avg_train_loss:.4f} | "
                    f"val F1={val_f1:.4f} prec={val_prec:.4f} rec={val_rec:.4f}")

        history.append({'epoch': epoch, 'train_loss': avg_train_loss,
                        'val_f1': val_f1, 'val_precision': val_prec, 'val_recall': val_rec})

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_path = output_dir / 'siamese_resnet18_best.pt'
            torch.save(model.state_dict(), best_path)
            logger.info(f"  ✓ New best saved (F1={val_f1:.4f})")

    # Save final model
    final_path = output_dir / 'siamese_resnet18.pt'
    torch.save(model.state_dict(), final_path)
    logger.info(f"\nFinal model saved: {final_path}")
    logger.info(f"Best validation F1: {best_val_f1:.4f}")

    # Save history
    with open(output_dir / 'siamese_history.json', 'w') as f:
        json.dump(history, f, indent=2)

    # Copy best to backend
    backend_dir = Path(__file__).parent.parent / 'backend' / 'models'
    backend_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(best_path, backend_dir / 'siamese_resnet18.pt')
    logger.info(f"Best model copied to backend: {backend_dir / 'siamese_resnet18.pt'}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Siamese ResNet-18 change detector')
    parser.add_argument('--data-dir',   type=Path, default=Path('./data'))
    parser.add_argument('--output-dir', type=Path, default=Path('./models'))
    parser.add_argument('--epochs',     type=int,  default=30)
    parser.add_argument('--batch-size', type=int,  default=64)
    args = parser.parse_args()
    train(args.data_dir, args.output_dir, args.epochs, args.batch_size)
