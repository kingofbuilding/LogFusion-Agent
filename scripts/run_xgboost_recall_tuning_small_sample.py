from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from run_protocol_compare_random_window import (  # noqa: E402
    _calc_metrics,
    _search_best_threshold,
    _train_bilstm,
    _train_gru,
    _train_iforest,
)
from run_supervised_fusion_baselines import _build_fusion_features  # noqa: E402
from run_truncated_ordered_split import (  # noqa: E402
    DATASETS,
    SPLIT_RATIO_PRESETS,
    SPLIT_VARIANT_NAMES,
    _clone_config,
    _parse_datasets,
    _resolve_split_ratio,
)
from src.data_processing.truncated_protocol import (  # noqa: E402
    TRUNCATED_PROTOCOL_ID,
    TRUNCATED_SPLIT_MODE,
    build_truncated_ordered_splits,
)
from src.fusion.three_view_service import ThreeViewScoringService  # noqa: E402
from src.utils import Config, Logger, set_random_seed  # noqa: E402

FEATURE_SETS = [
    ("stat_parts", [1, 2, 3, 4, 5, 6]),
    ("stat_parts_plus_legacy", [0, 1, 2, 3, 4, 5, 6]),
]

VARIANTS = [
    {
        "variant_name": "default",
        "scale_pos_weight_multiplier": 1.0,
        "overrides": {},
    },
    {
        "variant_name": "spw_1_2",
        "scale_pos_weight_multiplier": 1.2,
        "overrides": {},
    },
    {
        "variant_name": "spw_1_5",
        "scale_pos_weight_multiplier": 1.5,
        "overrides": {},
    },
    {
        "variant_name": "spw_2_0",
        "scale_pos_weight_multiplier": 2.0,
        "overrides": {},
    },
    {
        "variant_name": "soft_regularization",
        "scale_pos_weight_multiplier": 1.0,
        "overrides": {"reg_lambda": 1.0, "gamma": 0.0, "min_child_weight": 1.0},
    },
    {
        "variant_name": "deeper_soft_regularization",
        "scale_pos_weight_multiplier": 1.0,
        "overrides": {"max_depth": 8, "reg_lambda": 1.0, "gamma": 0.0, "min_child_weight": 1.0},
    },
    {
        "variant_name": "recall_combo",
        "scale_pos_weight_multiplier": 1.5,
        "overrides": {"max_depth": 8, "reg_lambda": 1.0, "gamma": 0.0, "min_child_weight": 1.0},
    },
]


def _base_params(cfg):
    return {
        "n_estimators": int(cfg.get("models.xgboost.n_estimators", 100)),
        "max_depth": int(cfg.get("models.xgboost.max_depth", 6)),
        "learning_rate": float(cfg.get("models.xgboost.learning_rate", 0.1)),
        "subsample": float(cfg.get("models.xgboost.subsample", 0.8)),
        "colsample_bytree": float(cfg.get("models.xgboost.colsample_bytree", 0.8)),
        "reg_alpha": float(cfg.get("models.xgboost.reg_alpha", 0.0)),
        "reg_lambda": float(cfg.get("models.xgboost.reg_lambda", 1.0)),
        "min_child_weight": float(cfg.get("models.xgboost.min_child_weight", 1.0)),
        "gamma": float(cfg.get("models.xgboost.gamma", 0.0)),
        "objective": str(cfg.get("models.xgboost.objective", "binary:logistic")),
        "eval_metric": str(cfg.get("models.xgboost.eval_metric", "auc")),
        "random_state": 42,
        "tree_method": "hist",
        "device": "cpu",
        "n_jobs": -1,
    }


def _scale_pos_weight(y_train, multiplier):
    y = np.asarray(y_train, dtype=int)
    pos = float(np.sum(y == 1))
    neg = float(np.sum(y == 0))
    if pos <= 0:
        return 1.0
    return max(1.0, neg / pos) * float(multiplier)


def _fit_variant(cfg, variant, x_train, y_train, x_val, y_val, x_test):
    params = _base_params(cfg)
    params.update(variant["overrides"])
    params["scale_pos_weight"] = _scale_pos_weight(y_train, variant["scale_pos_weight_multiplier"])
    model = xgb.XGBClassifier(**params)
    model.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)
    return model.predict_proba(x_val)[:, 1], model.predict_proba(x_test)[:, 1], params


def _prepare_dataset(base_config, dataset, model_root, ratio_override, split_variant, full_data, logger):
    cfg = _clone_config(base_config, dataset, model_root)
    cfg.config.setdefault("data", {})["split_mode"] = TRUNCATED_SPLIT_MODE
    bundles = build_truncated_ordered_splits(
        cfg,
        dataset,
        full_data=full_data,
        ratio_override=ratio_override,
        split_variant=split_variant,
    )
    for key in ("bilstm", "gru", "isolation_forest", "xgboost"):
        Path(cfg.get(f"paths.models.{key}")).mkdir(parents=True, exist_ok=True)
    _train_iforest(cfg, bundles["train"])
    _train_bilstm(cfg, bundles["train"], bundles["val"], bundles["test"])
    _train_gru(cfg, bundles["train"], bundles["val"], bundles["test"])

    scorer = ThreeViewScoringService(cfg)
    train_scores = scorer.score(bundles["train"]["X"], bundles["train"]["S"], seq_timestamps=bundles["train"]["T"], raw_seq_texts=bundles["train"]["R"])
    val_scores = scorer.score(bundles["val"]["X"], bundles["val"]["S"], seq_timestamps=bundles["val"]["T"], raw_seq_texts=bundles["val"]["R"])
    test_scores = scorer.score(bundles["test"]["X"], bundles["test"]["S"], seq_timestamps=bundles["test"]["T"], raw_seq_texts=bundles["test"]["R"])
    x_train = _build_fusion_features(cfg, bundles["train"], train_scores)
    x_val = _build_fusion_features(cfg, bundles["val"], val_scores)
    x_test = _build_fusion_features(cfg, bundles["test"], test_scores)
    logger.info("prepared tuning dataset=%s train=%s val=%s test=%s", dataset, x_train.shape, x_val.shape, x_test.shape)
    return cfg, bundles, x_train, x_val, x_test


def _evaluate_dataset(base_config, dataset, model_root, ratio_override, split_variant, full_data, logger):
    cfg, bundles, x_train, x_val, x_test = _prepare_dataset(base_config, dataset, model_root, ratio_override, split_variant, full_data, logger)
    y_train = np.asarray(bundles["train"]["y"], dtype=int)
    y_val = np.asarray(bundles["val"]["y"], dtype=int)
    y_test = np.asarray(bundles["test"]["y"], dtype=int)
    rows = []
    for feature_set_name, columns in FEATURE_SETS:
        cur_x_train = x_train[:, columns]
        cur_x_val = x_val[:, columns]
        cur_x_test = x_test[:, columns]
        for variant in VARIANTS:
            model_name = f"xgb_{variant['variant_name']}_{feature_set_name}"
            logger.info("train xgboost recall tuning dataset=%s model=%s shape=%s", dataset, model_name, cur_x_train.shape)
            val_prob, test_prob, params = _fit_variant(cfg, variant, cur_x_train, y_train, cur_x_val, y_val, cur_x_test)
            threshold = _search_best_threshold(y_val, val_prob)
            row = {
                "dataset": dataset,
                "experiment_group": "xgboost_recall_tuning_small_sample",
                "model_name": model_name,
                "feature_set": feature_set_name,
                "train_samples": int(len(y_train)),
                "val_samples": int(len(y_val)),
                "test_samples": int(len(y_test)),
                "train_anomaly_ratio": float(np.mean(y_train)),
                "val_anomaly_ratio": float(np.mean(y_val)),
                "test_anomaly_ratio": float(np.mean(y_test)),
                "protocol_id": TRUNCATED_PROTOCOL_ID,
                "split_mode": TRUNCATED_SPLIT_MODE,
                "split_variant": split_variant,
                "sample_cap_mode": "full_data" if full_data else "small_sample",
                "threshold_source": "val_f1",
                "test_used_for_selection": False,
                "scale_pos_weight_multiplier": float(variant["scale_pos_weight_multiplier"]),
                "scale_pos_weight": float(params["scale_pos_weight"]),
                "max_depth": int(params["max_depth"]),
                "reg_lambda": float(params["reg_lambda"]),
                "gamma": float(params["gamma"]),
                "min_child_weight": float(params["min_child_weight"]),
            }
            row.update(_calc_metrics(y_test, test_prob, threshold))
            rows.append(row)
    return rows


def _write_markdown(df, out_path, full_data):
    core = df[[
        "dataset", "feature_set", "model_name", "precision", "recall", "f1", "auc", "pr_auc", "threshold",
        "scale_pos_weight_multiplier", "max_depth", "reg_lambda", "gamma", "min_child_weight",
    ]].copy()
    core = core.sort_values(["dataset", "feature_set", "f1"], ascending=[True, True, False])
    best = core.groupby(["dataset", "feature_set"], as_index=False).head(1)
    sample_mode_text = "全量样本" if full_data else "小样本"
    cap_mode_text = "full-data 模式" if full_data else "小样本 cap 模式，即不启用 `--full-data`"
    lines = [
        f"# XGBoost 融合层{sample_mode_text}召回调参实验",
        "",
        "## 实验说明",
        "",
        "- 协议：`truncated_ordered_pre_split`，`65% / 15% / 20%`。",
        f"- 数据规模：{cap_mode_text}。",
        "- 输入特征：分别测试本文主模型相关的 `stat_parts` 与 `stat_parts_plus_legacy` 两种口径。`stat_parts` 使用时序、语义和四类统计子分数；`stat_parts_plus_legacy` 额外加入原统计总分。",
        "- 调参方向：放大 `scale_pos_weight`、降低 `reg_lambda/gamma/min_child_weight`、增加 `max_depth`。",
        "- 阈值：验证集搜索 F1 最优阈值，测试集仅最终评估。",
        "",
        "## 全部结果",
        "",
        core.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 各数据集最佳变体",
        "",
        best.to_markdown(index=False, floatfmt=".4f"),
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run small-sample XGBoost recall tuning experiments")
    parser.add_argument("--datasets", default="harrison,santos,fox")
    parser.add_argument("--split-ratio", default="65/15/20", choices=sorted(SPLIT_RATIO_PRESETS))
    parser.add_argument("--full-data", action="store_true")
    args = parser.parse_args()

    base_config = Config()
    logger = Logger.get_logger("xgboost_recall_tuning_small_sample", base_config)
    set_random_seed(int(base_config.get("experiment.random_seed", 42)))
    selected_datasets = _parse_datasets(args.datasets)
    ratio_override, split_variant = _resolve_split_ratio(args.split_ratio, False)
    sample_mode = "full_data" if args.full_data else "small_sample"
    suffix = ""
    if split_variant != "dataset_specific":
        suffix += f"_{SPLIT_VARIANT_NAMES[args.split_ratio]}" if args.split_ratio in SPLIT_VARIANT_NAMES else f"_{split_variant}"

    out_dir = PROJECT_ROOT / "outputs" / "reports" / f"xgboost_recall_tuning_{sample_mode}_{split_variant}"
    model_root = PROJECT_ROOT / "outputs" / "strict_retrain" / f"xgboost_recall_tuning_{sample_mode}_{split_variant}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for dataset in selected_datasets:
        all_rows.extend(_evaluate_dataset(base_config, dataset, model_root, ratio_override, split_variant, args.full_data, logger))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"xgboost_recall_tuning_{sample_mode}_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.csv"
    json_path = out_dir / f"xgboost_recall_tuning_{sample_mode}_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.json"
    md_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"xgboost_recall_tuning_{sample_mode}_uniform_65_15_20_{ts}.md"
    thesis_csv_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"xgboost_recall_tuning_{sample_mode}_uniform_65_15_20_{ts}.csv"

    df = pd.DataFrame(all_rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_csv(thesis_csv_path, index=False, encoding="utf-8-sig")
    _write_markdown(df, md_path, args.full_data)
    summary = {
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "split_variant": split_variant,
        "sample_cap_mode": sample_mode,
        "datasets": selected_datasets,
        "csv": str(csv_path.relative_to(PROJECT_ROOT)),
        "thesis_csv": str(thesis_csv_path.relative_to(PROJECT_ROOT)),
        "markdown": str(md_path.relative_to(PROJECT_ROOT)),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
