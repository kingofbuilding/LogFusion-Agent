from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from run_protocol_compare_random_window import (  # noqa: E402
    _calc_metrics,
    _predict_saved_sequence_model,
    _search_best_threshold,
    _train_bilstm,
    _train_gru,
    _train_iforest,
)
from run_supervised_fusion_baselines import (  # noqa: E402
    _build_fusion_features,
    _classifier_specs,
    _fit_predict_classifier,
    _predict_xgboost,
)
from run_truncated_ordered_split import (  # noqa: E402
    SPLIT_RATIO_PRESETS,
    SPLIT_VARIANT_NAMES,
    _clone_config,
    _resolve_split_ratio,
)
from src.data_processing.truncated_protocol import (  # noqa: E402
    TRUNCATED_PROTOCOL_ID,
    TRUNCATED_SPLIT_MODE,
    build_truncated_ordered_splits,
)
from src.fusion.three_view_service import ThreeViewScoringService  # noqa: E402
from src.models.gru_classifier import GRUClassifier  # noqa: E402
from src.utils import Config, Logger, set_random_seed  # noqa: E402

TRANSFER_PAIRS = [
    (("harrison", "santos"), "fox"),
    (("harrison", "fox"), "santos"),
    (("santos", "fox"), "harrison"),
]


def _ensure_view_models(cfg, bundles):
    for key in ("bilstm", "gru", "isolation_forest", "xgboost"):
        Path(cfg.get(f"paths.models.{key}")).mkdir(parents=True, exist_ok=True)
    _train_iforest(cfg, bundles["train"])
    _train_bilstm(cfg, bundles["train"], bundles["val"], bundles["test"])
    _train_gru(cfg, bundles["train"], bundles["val"], bundles["test"])


def _score_bundle(cfg, bundle):
    scorer = ThreeViewScoringService(cfg)
    scores = scorer.score(
        bundle["X"],
        bundle["S"],
        seq_timestamps=bundle["T"],
        raw_seq_texts=bundle["R"],
    )
    return _build_fusion_features(cfg, bundle, scores)


def _prepare_dataset(base_config, dataset, model_root, full_data, ratio_override, split_variant, logger):
    cfg = _clone_config(base_config, dataset, model_root)
    cfg.config.setdefault("data", {})["split_mode"] = TRUNCATED_SPLIT_MODE
    bundles = build_truncated_ordered_splits(
        cfg,
        dataset,
        full_data=full_data,
        ratio_override=ratio_override,
        split_variant=split_variant,
    )
    _ensure_view_models(cfg, bundles)
    x_train = _score_bundle(cfg, bundles["train"])
    x_val = _score_bundle(cfg, bundles["val"])
    x_test = _score_bundle(cfg, bundles["test"])
    gru_test = _predict_saved_sequence_model(cfg, bundles["test"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")
    logger.info("prepared dataset=%s train=%s val=%s test=%s", dataset, x_train.shape, x_val.shape, x_test.shape)
    return {
        "dataset": dataset,
        "cfg": cfg,
        "bundles": bundles,
        "x_train": x_train,
        "x_val": x_val,
        "x_test": x_test,
        "y_train": np.asarray(bundles["train"]["y"], dtype=int),
        "y_val": np.asarray(bundles["val"]["y"], dtype=int),
        "y_test": np.asarray(bundles["test"]["y"], dtype=int),
        "gru_test": gru_test,
    }


def _concat(items, key):
    return np.concatenate([item[key] for item in items], axis=0)


def _metric_row(name, source_datasets, target_dataset, y_source_train, y_source_val, y_target_test, val_prob, test_prob, metadata):
    threshold = _search_best_threshold(y_source_val, val_prob)
    row = {
        "source_datasets": "+".join(source_datasets),
        "target_dataset": target_dataset,
        "model_name": name,
        "train_samples": int(len(y_source_train)),
        "val_samples": int(len(y_source_val)),
        "test_samples": int(len(y_target_test)),
        "source_train_anomaly_ratio": float(np.mean(y_source_train)),
        "source_val_anomaly_ratio": float(np.mean(y_source_val)),
        "target_test_anomaly_ratio": float(np.mean(y_target_test)),
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "threshold_source": "source_val",
        "test_used_for_selection": False,
    }
    row.update(_calc_metrics(y_target_test, test_prob, threshold))
    row.update(metadata)
    return row


def _evaluate_xgboost_variant(cfg, name, source_datasets, target_dataset, x_train, y_train, x_val, y_val, x_test, y_test, columns, metadata):
    val_prob, test_prob = _predict_xgboost(
        cfg,
        x_train[:, columns],
        y_train,
        x_val[:, columns],
        y_val,
        x_test[:, columns],
    )
    return _metric_row(name, source_datasets, target_dataset, y_train, y_val, y_test, val_prob, test_prob, metadata)


def _evaluate_pair(pair, prepared, logger):
    source_datasets, target_dataset = pair
    source_items = [prepared[name] for name in source_datasets]
    target = prepared[target_dataset]
    x_train = _concat(source_items, "x_train")
    y_train = _concat(source_items, "y_train")
    x_val = _concat(source_items, "x_val")
    y_val = _concat(source_items, "y_val")
    x_test = target["x_test"]
    y_test = target["y_test"]
    metadata = {
        "source_count": len(source_datasets),
        "target_train_samples_not_used": int(len(target["y_train"])),
        "target_val_samples_not_used": int(len(target["y_val"])),
    }

    rows = []
    mean_val = (x_val[:, 0] + x_val[:, 1] + x_val[:, 2]) / 3.0
    mean_test = (x_test[:, 0] + x_test[:, 1] + x_test[:, 2]) / 3.0
    rows.append(_metric_row("mean_fusion_transfer", source_datasets, target_dataset, y_train, y_val, y_test, mean_val, mean_test, metadata))

    cfg = source_items[0]["cfg"]
    rows.append(_evaluate_xgboost_variant(cfg, "our_xgboost_base_3view_transfer", source_datasets, target_dataset, x_train, y_train, x_val, y_val, x_test, y_test, [0, 1, 2], metadata))
    rows.append(_evaluate_xgboost_variant(cfg, "our_xgboost_stat_parts_transfer", source_datasets, target_dataset, x_train, y_train, x_val, y_val, x_test, y_test, [1, 2, 3, 4, 5, 6], metadata))
    rows.append(_evaluate_xgboost_variant(cfg, "our_xgboost_stat_parts_plus_legacy_transfer", source_datasets, target_dataset, x_train, y_train, x_val, y_val, x_test, y_test, [0, 1, 2, 3, 4, 5, 6], metadata))

    for name, model in _classifier_specs(y_train, "stat_parts_plus_legacy"):
        transfer_name = name.replace("_stat_parts_plus_legacy", "_transfer")
        logger.info("train transfer baseline source=%s target=%s model=%s shape=%s", "+".join(source_datasets), target_dataset, transfer_name, x_train.shape)
        val_prob, test_prob = _fit_predict_classifier(model, x_train, y_train, x_val, x_test)
        rows.append(_metric_row(transfer_name, source_datasets, target_dataset, y_train, y_val, y_test, val_prob, test_prob, metadata))
    return rows


def _write_markdown(df, out_path):
    core = df[["source_datasets", "target_dataset", "model_name", "precision", "recall", "f1", "auc", "pr_auc", "threshold"]].copy()
    core = core.sort_values(["target_dataset", "f1"], ascending=[True, False])
    best = core.groupby(["source_datasets", "target_dataset"], as_index=False).head(1)
    lines = [
        "# 跨数据集融合层迁移实验（65/15/20）",
        "",
        "## 实验说明",
        "",
        "- 协议：`truncated_ordered_pre_split`，full-data，`65% / 15% / 20%`。",
        "- 迁移方式：源数据集训练融合层，源数据集验证集选择阈值，目标数据集测试集仅用于最终评估。",
        "- 目标：观察多视图融合特征和融合分类器跨日志场景的泛化能力。",
        "",
        "## 全部结果",
        "",
        core.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 每组迁移最佳结果",
        "",
        best.to_markdown(index=False, floatfmt=".4f"),
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run cross-dataset supervised fusion transfer experiments")
    parser.add_argument("--full-data", action="store_true")
    parser.add_argument("--split-ratio", default="65/15/20", choices=sorted(SPLIT_RATIO_PRESETS))
    args = parser.parse_args()

    base_config = Config()
    logger = Logger.get_logger("cross_dataset_fusion_transfer", base_config)
    set_random_seed(int(base_config.get("experiment.random_seed", 42)))
    ratio_override, split_variant = _resolve_split_ratio(args.split_ratio, False)
    suffix = "_full_data" if args.full_data else ""
    if split_variant != "dataset_specific":
        suffix += f"_{SPLIT_VARIANT_NAMES[args.split_ratio]}" if args.split_ratio in SPLIT_VARIANT_NAMES else f"_{split_variant}"

    out_dir = PROJECT_ROOT / "outputs" / "reports" / f"cross_dataset_fusion_transfer_{split_variant}"
    model_root = PROJECT_ROOT / "outputs" / "strict_retrain" / f"cross_dataset_fusion_transfer_{split_variant}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    datasets = sorted({name for source, target in TRANSFER_PAIRS for name in (*source, target)})
    prepared = {}
    for dataset in datasets:
        prepared[dataset] = _prepare_dataset(base_config, dataset, model_root, args.full_data, ratio_override, split_variant, logger)

    rows = []
    for pair in TRANSFER_PAIRS:
        rows.extend(_evaluate_pair(pair, prepared, logger))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"cross_dataset_fusion_transfer_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.csv"
    json_path = out_dir / f"cross_dataset_fusion_transfer_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.json"
    md_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"cross_dataset_fusion_transfer_uniform_65_15_20_{ts}.md"
    thesis_csv_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"cross_dataset_fusion_transfer_uniform_65_15_20_{ts}.csv"

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_csv(thesis_csv_path, index=False, encoding="utf-8-sig")
    _write_markdown(df, md_path)
    summary = {
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "split_variant": split_variant,
        "transfer_pairs": [{"source": list(source), "target": target} for source, target in TRANSFER_PAIRS],
        "csv": str(csv_path.relative_to(PROJECT_ROOT)),
        "thesis_csv": str(thesis_csv_path.relative_to(PROJECT_ROOT)),
        "markdown": str(md_path.relative_to(PROJECT_ROOT)),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
