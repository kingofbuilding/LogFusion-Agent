from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader as TorchDataLoader, TensorDataset

from src.data_processing.data_loader import DataLoader
from src.models.bilstm_attention import BiLSTMAttention
from src.utils import Config, Logger, get_device


def _infer_vocab_size(*arrays: np.ndarray, template_mapping: dict | None = None) -> int:
    max_template_id = 0

    if template_mapping:
        try:
            max_template_id = max(max_template_id, max(int(k) for k in template_mapping.keys()))
        except (TypeError, ValueError):
            pass

    for arr in arrays:
        if arr is None:
            continue
        np_arr = np.asarray(arr)
        if np_arr.size == 0:
            continue
        max_template_id = max(max_template_id, int(np_arr.max(initial=0)))

    return max_template_id + 2


def _search_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    best_thr, best_f1 = 0.5, -1.0
    for thr in np.linspace(0.05, 0.95, 181):
        pred = (y_prob >= thr).astype(int)
        cur = f1_score(y_true, pred, zero_division=0)
        if cur > best_f1:
            best_f1 = float(cur)
            best_thr = float(thr)
    return best_thr


def _metrics(y_true: np.ndarray, y_prob: np.ndarray, thr: float):
    pred = (y_prob >= thr).astype(int)
    out = {
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
    }
    if len(np.unique(y_true)) > 1:
        out["auc"] = roc_auc_score(y_true, y_prob)
    else:
        out["auc"] = 0.0
    return out


def _predict_prob(model, loader, device):
    model.eval()
    parts = []
    with torch.no_grad():
        for (x,) in loader:
            logits, _ = model(x.to(device))
            parts.append(torch.sigmoid(logits.squeeze(-1)).cpu().numpy())
    return np.concatenate(parts, axis=0) if parts else np.array([], dtype=float)


def _make_validation_split(
    x_train: np.ndarray,
    y_train: np.ndarray,
    config: Config,
):
    val_ratio = float(config.get("models.bilstm.validation_split", 0.2))
    random_state = int(config.get("models.bilstm.validation_random_state", 42))

    if len(x_train) < 2 or val_ratio <= 0.0:
        return x_train, x_train, y_train, y_train, False

    val_ratio = min(max(val_ratio, 0.05), 0.5)
    can_stratify = len(np.unique(y_train)) > 1 and np.min(np.bincount(y_train.astype(int))) >= 2
    stratify = y_train if can_stratify else None

    try:
        x_subtrain, x_val, y_subtrain, y_val = train_test_split(
            x_train,
            y_train,
            test_size=val_ratio,
            random_state=random_state,
            stratify=stratify,
        )
        return x_subtrain, x_val, y_subtrain, y_val, True
    except ValueError:
        return x_train, x_train, y_train, y_train, False


def main():
    config = Config()
    logger = Logger.get_logger("train_bilstm", config)
    device = get_device()

    print("=" * 70)
    print("Bi-LSTM 训练")
    print("=" * 70)

    data = DataLoader(config).prepare_data()
    x_train = data["X_train"]
    x_val = data.get("X_val")
    y_train = data["y_train"]
    y_val = data.get("y_val")
    if y_train is None:
        print("缺少标签，无法训练 Bi-LSTM")
        return

    max_train = int(config.get("experiment.max_train_samples", 20000))
    max_val = int(config.get("experiment.max_val_samples", config.get("experiment.max_test_samples", 5000)))
    if len(x_train) > max_train:
        x_train = x_train[:max_train]
        y_train = y_train[:max_train]
    if x_val is not None and len(x_val) > max_val:
        x_val = x_val[:max_val]
        y_val = y_val[:max_val]

    x_train = np.asarray(x_train, dtype=np.int64)
    y_train = np.asarray(y_train, dtype=np.int64)
    if x_val is not None and y_val is not None and len(x_val) and len(y_val):
        x_subtrain = x_train
        y_subtrain = y_train
        x_val = np.asarray(x_val, dtype=np.int64)
        y_val = np.asarray(y_val, dtype=np.int64)
        has_validation_split = True
    else:
        x_subtrain, x_val, y_subtrain, y_val, has_validation_split = _make_validation_split(
            x_train,
            y_train,
            config,
        )
    if not has_validation_split:
        logger.warning("Validation split unavailable; reusing train split for checkpoint selection.")

    vocab_size = _infer_vocab_size(
        x_train,
        data.get("X_test"),
        template_mapping=data.get("template_mapping"),
    )
    logger.info(f"Bi-LSTM vocab_size={vocab_size} derived from global template-id range.")

    model = BiLSTMAttention(config, vocab_size=vocab_size).to(device)
    lr = float(config.get("models.bilstm.learning_rate", 1e-3))
    epochs = int(config.get("models.bilstm.epochs", 8))
    patience = int(config.get("models.bilstm.early_stopping_patience", 3))
    batch_size = int(config.get("data.batch_size", 64))

    classes = np.unique(y_subtrain)
    if len(classes) > 1:
        weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_subtrain)
        pos_weight = float(weights[list(classes).index(1)] / max(weights[list(classes).index(0)], 1e-8)) if 1 in classes and 0 in classes else 1.0
    else:
        pos_weight = 1.0
    pos_weight = min(pos_weight, float(config.get("models.bilstm.max_pos_weight", 50.0)))

    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    train_loader = TorchDataLoader(
        TensorDataset(torch.from_numpy(x_subtrain), torch.from_numpy(y_subtrain).float()),
        batch_size=batch_size,
        shuffle=True,
    )
    val_loader = TorchDataLoader(
        TensorDataset(torch.from_numpy(x_val)),
        batch_size=int(config.get("models.bilstm.infer_batch_size", 128)),
        shuffle=False,
    )

    best = None
    best_f1 = -1.0
    no_improve = 0
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad()
            logits, _ = model(xb)
            loss = criterion(logits.squeeze(-1), yb)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))

        val_prob = _predict_prob(model, val_loader, device)
        thr = _search_best_threshold(y_val, val_prob) if len(np.unique(y_val)) > 1 else 0.5
        metrics = _metrics(y_val, val_prob, thr)
        logger.info(f"epoch={epoch} loss={np.mean(losses):.4f} metrics={metrics} thr={thr:.4f}")
        if metrics["f1"] > best_f1:
            best_f1 = float(metrics["f1"])
            best = {
                "model_state_dict": model.state_dict(),
                "best_threshold": float(thr),
                "metrics": metrics,
                "vocab_size": vocab_size,
            }
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info("early stopping triggered")
                break

    save_path = Path(config.get("paths.models.bilstm")) / "best_model.pth"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best or {"model_state_dict": model.state_dict(), "best_threshold": 0.5, "vocab_size": vocab_size}, save_path)
    print(f"时序模型已保存: {save_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
