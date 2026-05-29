from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.data_processing.data_loader import DataLoader
from src.fusion.three_view_service import ThreeViewScoringService
from src.fusion.xgboost_fusion import XGBoostFusion
from src.utils import Config, Logger


def _binary_metrics(y_true, y_prob, threshold: float = 0.5):
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    y_pred = (y_prob >= float(threshold)).astype(int)
    out = {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }
    if len(np.unique(y_true)) > 1:
        out["auc"] = roc_auc_score(y_true, y_prob)
    else:
        out["auc"] = 0.0
    return out


def main():
    config = Config()
    logger = Logger.get_logger("train_xgboost", config)

    print("=" * 70)
    print("XGBoost 融合训练")
    print("=" * 70)

    data_loader = DataLoader(config)
    data = data_loader.prepare_data()
    x_train, x_val, x_test = data["X_train"], data.get("X_val"), data["X_test"]
    y_train, y_val, y_test = data["y_train"], data.get("y_val"), data["y_test"]
    t_train, t_val, t_test = data.get("T_train"), data.get("T_val"), data.get("T_test")
    semantic_train = data.get("S_train")
    semantic_val = data.get("S_val")
    semantic_test = data.get("S_test")
    raw_train = data.get("R_train")
    raw_val = data.get("R_val")
    raw_test = data.get("R_test")

    if y_train is None:
        print("缺少标签，无法训练融合模型")
        return

    max_train = int(config.get("experiment.max_train_samples", 20000))
    max_val = int(config.get("experiment.max_val_samples", config.get("experiment.max_test_samples", 5000)))
    max_test = int(config.get("experiment.max_test_samples", 5000))
    if len(x_train) > max_train:
        x_train, y_train = x_train[:max_train], y_train[:max_train]
        if t_train is not None:
            t_train = t_train[:max_train]
        if semantic_train is not None:
            semantic_train = semantic_train[:max_train]
        if raw_train is not None:
            raw_train = raw_train[:max_train]
    if x_val is None or y_val is None or len(x_val) == 0:
        raise ValueError("缺少验证集，请使用 ordered_pre_split + val_ratio 配置重跑 XGBoost 融合")
    if len(x_val) > max_val:
        x_val, y_val = x_val[:max_val], y_val[:max_val]
        if t_val is not None:
            t_val = t_val[:max_val]
        if semantic_val is not None:
            semantic_val = semantic_val[:max_val]
        if raw_val is not None:
            raw_val = raw_val[:max_val]
    if len(x_test) > max_test:
        x_test, y_test = x_test[:max_test], y_test[:max_test]
        if t_test is not None:
            t_test = t_test[:max_test]
        if semantic_test is not None:
            semantic_test = semantic_test[:max_test]
        if raw_test is not None:
            raw_test = raw_test[:max_test]

    scorer = ThreeViewScoringService(config)
    train_scores = scorer.score(x_train, semantic_train, seq_timestamps=t_train, raw_seq_texts=raw_train)
    val_scores = scorer.score(x_val, semantic_val, seq_timestamps=t_val, raw_seq_texts=raw_val)
    test_scores = scorer.score(x_test, semantic_test, seq_timestamps=t_test, raw_seq_texts=raw_test)

    x_meta_train = train_scores["meta_features"]
    x_meta_val = val_scores["meta_features"]
    x_meta_test = test_scores["meta_features"]

    cv_enabled = bool(config.get("experiment.cross_validation.enabled", False))
    n_folds = int(config.get("experiment.cross_validation.n_folds", 5))
    y_train = np.asarray(y_train).astype(int)
    y_val = np.asarray(y_val).astype(int)
    y_test = np.asarray(y_test).astype(int)

    if cv_enabled and n_folds >= 2 and len(np.unique(y_train)) > 1 and len(y_train) >= n_folds:
        logger.info(f"启用 {n_folds} 折交叉验证训练元学习器")
        skf = StratifiedKFold(
            n_splits=n_folds,
            shuffle=True,
            random_state=int(config.get("experiment.random_seed", 42)),
        )
        oof_prob = np.zeros(len(y_train), dtype=float)
        for fold_idx, (tr_idx, va_idx) in enumerate(skf.split(x_meta_train, y_train), 1):
            fold_fusion = XGBoostFusion(config)
            fold_fusion.train(
                x_meta_train[tr_idx],
                y_train[tr_idx],
                x_meta_train[va_idx],
                y_train[va_idx],
            )
            va_prob = fold_fusion.predict_proba(x_meta_train[va_idx])
            oof_prob[va_idx] = va_prob
            logger.info(f"fold={fold_idx} metrics={_binary_metrics(y_train[va_idx], va_prob)}")

        logger.info(f"OOF CV metrics={_binary_metrics(y_train, oof_prob)}")

    fusion = XGBoostFusion(config)
    fusion.train(x_meta_train, y_train, x_meta_val, y_val)
    metrics = fusion.evaluate(x_meta_test, y_test)
    metrics.update({
        "split_mode": str(data.get("split_metadata", {}).get("split_mode", "unknown")),
        "threshold_source": "val",
        "test_used_for_selection": False,
        "val_samples": int(len(y_val)),
    })
    logger.info(f"融合模型指标: {metrics}")

    model_dir = Path(config.get("paths.models.xgboost"))
    model_path = model_dir / "xgboost_fusion.joblib"
    fusion.save_model(model_path)

    print(f"融合模型已保存: {model_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
