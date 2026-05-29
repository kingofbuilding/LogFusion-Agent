from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from run_protocol_compare_random_window import (
    DATASETS,
    ORDERED_SOURCES,
    _clone_config,
    _derive_accuracy_from_ordered_row,
    _evaluate_score_family,
    _predict_saved_fusion,
    _predict_saved_sequence_model,
    _predict_subset_xgb,
    _train_bilstm,
    _train_gru,
    _train_iforest,
    _train_saved_fusion,
)
from src.data_processing.truncated_protocol import (
    DATASET_CONFIGS,
    TRUNCATED_PROTOCOL_ID,
    TRUNCATED_SPLIT_MODE,
    build_truncated_ordered_splits,
    flatten_protocol_metadata,
    validate_protocol_dataframe,
)
from src.fusion.evaluate_views import _compute_stat_subscores
from src.fusion.three_view_service import ThreeViewScoringService
from src.models.gru_classifier import GRUClassifier
from src.utils import Config, Logger, set_random_seed
METRIC_COLUMNS = [
    "accuracy",
    "precision",
    "recall",
    "f1",
    "auc",
    "pr_auc",
    "threshold",
    "train_anomaly_ratio",
    "val_anomaly_ratio",
    "test_anomaly_ratio",
]
SPLIT_RATIO_PRESETS = {
    "dataset_specific": None,
    "60/20/20": {"train_ratio": 0.60, "val_ratio": 0.20},
    "60/15/25": {"train_ratio": 0.60, "val_ratio": 0.15},
    "65/20/15": {"train_ratio": 0.65, "val_ratio": 0.20},
    "65/15/20": {"train_ratio": 0.65, "val_ratio": 0.15},
}
SPLIT_VARIANT_NAMES = {
    "dataset_specific": "dataset_specific",
    "60/20/20": "uniform_60_20_20",
    "60/15/25": "uniform_60_15_25",
    "65/20/15": "uniform_65_20_15",
    "65/15/20": "uniform_65_15_20",
}


def _find_latest_report(reports_dir: Path, pattern: str) -> Path:
    matches = list(reports_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"report not found for pattern: {pattern}")
    return max(matches, key=lambda path: path.stat().st_mtime)



def _evaluate_truncated_dataset(base_config: Config, dataset: str, model_root: Path, logger, full_data: bool = False, ratio_override: dict | None = None, split_variant: str = "dataset_specific"):
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
    train_scores = scorer.score(
        bundles["train"]["X"],
        bundles["train"]["S"],
        seq_timestamps=bundles["train"]["T"],
        raw_seq_texts=bundles["train"]["R"],
    )
    val_scores = scorer.score(
        bundles["val"]["X"],
        bundles["val"]["S"],
        seq_timestamps=bundles["val"]["T"],
        raw_seq_texts=bundles["val"]["R"],
    )
    test_scores = scorer.score(
        bundles["test"]["X"],
        bundles["test"]["S"],
        seq_timestamps=bundles["test"]["T"],
        raw_seq_texts=bundles["test"]["R"],
    )

    y_train = bundles["train"]["y"]
    y_val = bundles["val"]["y"]
    y_test = bundles["test"]["y"]
    split_metadata = bundles["metadata"]

    stat_train = np.asarray(train_scores["stat_scores"], dtype=float)
    temp_train = np.asarray(train_scores["temporal_scores"], dtype=float)
    sem_train = np.asarray(train_scores["semantic_scores"], dtype=float)
    stat_val = np.asarray(val_scores["stat_scores"], dtype=float)
    temp_val = np.asarray(val_scores["temporal_scores"], dtype=float)
    sem_val = np.asarray(val_scores["semantic_scores"], dtype=float)
    stat_test = np.asarray(test_scores["stat_scores"], dtype=float)
    temp_test = np.asarray(test_scores["temporal_scores"], dtype=float)
    sem_test = np.asarray(test_scores["semantic_scores"], dtype=float)
    gru_train = _predict_saved_sequence_model(cfg, bundles["train"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")
    gru_val = _predict_saved_sequence_model(cfg, bundles["val"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")
    gru_test = _predict_saved_sequence_model(cfg, bundles["test"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")

    rows = []
    rows.append(_evaluate_score_family("statistical_view", dataset, "single_view", bundles, stat_train, stat_val, stat_test, split_metadata))
    rows.append(_evaluate_score_family("temporal_view", dataset, "single_view", bundles, temp_train, temp_val, temp_test, split_metadata))
    rows.append(_evaluate_score_family("gru_temporal_view", dataset, "single_view", bundles, gru_train, gru_val, gru_test, split_metadata))
    rows.append(_evaluate_score_family("semantic_view", dataset, "single_view", bundles, sem_train, sem_val, sem_test, split_metadata))

    mean_all_train = (stat_train + temp_train + sem_train) / 3.0
    mean_all_val = (stat_val + temp_val + sem_val) / 3.0
    mean_all_test = (stat_test + temp_test + sem_test) / 3.0
    rows.append(_evaluate_score_family("mean_fusion_all", dataset, "fusion", bundles, mean_all_train, mean_all_val, mean_all_test, split_metadata))

    subset_specs = [
        ("ablation_stat_temporal_mean", (stat_train + temp_train) / 2.0, (stat_val + temp_val) / 2.0, (stat_test + temp_test) / 2.0),
        ("ablation_stat_semantic_mean", (stat_train + sem_train) / 2.0, (stat_val + sem_val) / 2.0, (stat_test + sem_test) / 2.0),
        ("ablation_temporal_semantic_mean", (temp_train + sem_train) / 2.0, (temp_val + sem_val) / 2.0, (temp_test + sem_test) / 2.0),
    ]
    for name, train_score, val_score, test_score in subset_specs:
        rows.append(_evaluate_score_family(name, dataset, "ablation_mean", bundles, train_score, val_score, test_score, split_metadata))

    stat_sub_train = _compute_stat_subscores(cfg, bundles["train"]["X"], bundles["train"]["T"], bundles["train"]["S"], bundles["train"]["R"])
    stat_sub_val = _compute_stat_subscores(cfg, bundles["val"]["X"], bundles["val"]["T"], bundles["val"]["S"], bundles["val"]["R"])
    stat_sub_test = _compute_stat_subscores(cfg, bundles["test"]["X"], bundles["test"]["T"], bundles["test"]["S"], bundles["test"]["R"])

    x_meta_train = np.column_stack([stat_train, temp_train, sem_train])
    x_meta_val = np.column_stack([stat_val, temp_val, sem_val])
    x_meta_test = np.column_stack([stat_test, temp_test, sem_test])

    x_meta_train_stat_parts = np.column_stack([
        temp_train,
        sem_train,
        stat_sub_train["stat_dist_score"],
        stat_sub_train["stat_auth_score"],
        stat_sub_train["stat_web_score"],
        stat_sub_train["stat_dns_score"],
    ])
    x_meta_val_stat_parts = np.column_stack([
        temp_val,
        sem_val,
        stat_sub_val["stat_dist_score"],
        stat_sub_val["stat_auth_score"],
        stat_sub_val["stat_web_score"],
        stat_sub_val["stat_dns_score"],
    ])
    x_meta_test_stat_parts = np.column_stack([
        temp_test,
        sem_test,
        stat_sub_test["stat_dist_score"],
        stat_sub_test["stat_auth_score"],
        stat_sub_test["stat_web_score"],
        stat_sub_test["stat_dns_score"],
    ])

    x_meta_train_stat_parts_plus_legacy = np.column_stack([
        stat_train,
        temp_train,
        sem_train,
        stat_sub_train["stat_dist_score"],
        stat_sub_train["stat_auth_score"],
        stat_sub_train["stat_web_score"],
        stat_sub_train["stat_dns_score"],
    ])
    x_meta_val_stat_parts_plus_legacy = np.column_stack([
        stat_val,
        temp_val,
        sem_val,
        stat_sub_val["stat_dist_score"],
        stat_sub_val["stat_auth_score"],
        stat_sub_val["stat_web_score"],
        stat_sub_val["stat_dns_score"],
    ])
    x_meta_test_stat_parts_plus_legacy = np.column_stack([
        stat_test,
        temp_test,
        sem_test,
        stat_sub_test["stat_dist_score"],
        stat_sub_test["stat_auth_score"],
        stat_sub_test["stat_web_score"],
        stat_sub_test["stat_dns_score"],
    ])

    _train_saved_fusion(cfg, x_meta_train, y_train, x_meta_val, y_val)
    xgb_train_prob = _predict_saved_fusion(cfg, x_meta_train)
    xgb_val_prob = _predict_saved_fusion(cfg, x_meta_val)
    xgb_test_prob = _predict_saved_fusion(cfg, x_meta_test)
    rows.append(_evaluate_score_family("xgboost_fusion_saved_model", dataset, "fusion", bundles, xgb_train_prob, xgb_val_prob, xgb_test_prob, split_metadata))

    ablation_xgb_specs = [
        ("ablation_stat_temporal_xgb", "ablation_xgb", np.column_stack([stat_train, temp_train]), np.column_stack([stat_val, temp_val]), np.column_stack([stat_test, temp_test])),
        ("ablation_stat_semantic_xgb", "ablation_xgb", np.column_stack([stat_train, sem_train]), np.column_stack([stat_val, sem_val]), np.column_stack([stat_test, sem_test])),
        ("ablation_temporal_semantic_xgb", "ablation_xgb", np.column_stack([temp_train, sem_train]), np.column_stack([temp_val, sem_val]), np.column_stack([temp_test, sem_test])),
        ("xgboost_fusion_retrained", "fusion", x_meta_train, x_meta_val, x_meta_test),
        ("xgboost_fusion_stat_parts_xgb", "fusion", x_meta_train_stat_parts, x_meta_val_stat_parts, x_meta_test_stat_parts),
        ("xgboost_fusion_stat_parts_plus_legacy_xgb", "fusion", x_meta_train_stat_parts_plus_legacy, x_meta_val_stat_parts_plus_legacy, x_meta_test_stat_parts_plus_legacy),
    ]
    for name, group, sub_train, sub_val, sub_test in ablation_xgb_specs:
        val_prob, test_prob = _predict_subset_xgb(cfg, sub_train, y_train, sub_val, y_val, sub_test)
        rows.append(_evaluate_score_family(name, dataset, group, bundles, np.zeros_like(y_train, dtype=float), val_prob, test_prob, split_metadata))

    for row in rows:
        for key, value in split_metadata.items():
            if key not in row and isinstance(value, (str, int, float, bool)):
                row[key] = value

    logger.info(
        "dataset=%s truncated-ordered mode=%s ratios train=%.6f val=%.6f test=%.6f trunc_ratio=%.2f trunc_rows=%d original_rows=%d train_seq=%d val_seq=%d test_seq=%d"
        % (
            dataset,
            str(split_metadata["sample_cap_mode"]),
            float(np.mean(y_train)),
            float(np.mean(y_val)),
            float(np.mean(y_test)),
            float(split_metadata["trunc_ratio"]),
            int(split_metadata["truncated_total_rows"]),
            int(split_metadata["original_total_rows"]),
            int(split_metadata["train_sequences"]),
            int(split_metadata["val_sequences"]),
            int(split_metadata["test_sequences"]),
        )
    )
    return rows, split_metadata



def _load_protocol_df(df: pd.DataFrame, protocol: str, source_csv: str) -> pd.DataFrame:
    out = df.copy()
    out["protocol"] = protocol
    out["source_csv"] = source_csv.replace("\\", "/")
    if "accuracy" not in out.columns:
        out["accuracy"] = out.apply(_derive_accuracy_from_ordered_row, axis=1)
    return out



def _parse_datasets(raw: str) -> list[str]:
    if not raw.strip():
        return list(DATASETS)
    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    unknown = sorted(set(requested) - set(DATASETS))
    if unknown:
        raise ValueError(f"unknown datasets: {unknown}; allowed={DATASETS}")
    return requested



def _resolve_split_ratio(raw: str, uniform_60_20_20: bool) -> tuple[dict | None, str]:
    ratio_key = "60/20/20" if uniform_60_20_20 else raw.strip()
    if ratio_key not in SPLIT_RATIO_PRESETS:
        raise ValueError(f"unknown split ratio: {ratio_key}; allowed={list(SPLIT_RATIO_PRESETS)}")
    return SPLIT_RATIO_PRESETS[ratio_key], SPLIT_VARIANT_NAMES[ratio_key]



def main():
    parser = argparse.ArgumentParser(description="Run truncated ordered split evaluation")
    parser.add_argument("--full-data", action="store_true", help="use all available windows in each truncated split")
    parser.add_argument("--datasets", default="", help="comma-separated datasets; default uses all configured datasets")
    parser.add_argument(
        "--split-ratio",
        default="dataset_specific",
        choices=sorted(SPLIT_RATIO_PRESETS),
        help="train/val/test ratio preset while keeping truncation ratios",
    )
    parser.add_argument("--uniform-split-60-20-20", action="store_true", help="compatibility alias for --split-ratio 60/20/20")
    args = parser.parse_args()

    base_config = Config()
    logger = Logger.get_logger("truncated_ordered_protocol", base_config)
    set_random_seed(int(base_config.get("experiment.random_seed", 42)))

    project_root = Path(__file__).resolve().parents[1]
    selected_datasets = _parse_datasets(args.datasets)
    ratio_override, split_variant = _resolve_split_ratio(args.split_ratio, args.uniform_split_60_20_20)
    suffix = "_full_data" if args.full_data else ""
    if split_variant != "dataset_specific":
        suffix += f"_{split_variant}"
    out_dir = project_root / "outputs" / "reports"
    model_root = project_root / "outputs" / "strict_retrain" / "truncated_ordered_protocol"
    if args.full_data:
        if split_variant == "dataset_specific":
            out_dir = out_dir / "full_data_truncated_ordered"
            model_root = project_root / "outputs" / "strict_retrain" / "truncated_ordered_protocol_full_data"
        else:
            out_dir = out_dir / f"full_data_truncated_ordered_{split_variant}"
            model_root = project_root / "outputs" / "strict_retrain" / f"truncated_ordered_protocol_full_data_{split_variant}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    all_rows = []
    metadata_by_dataset = {}
    for dataset in selected_datasets:
        logger.info(f"start truncated-ordered evaluation for {dataset} full_data={args.full_data} split_variant={split_variant}")
        dataset_rows, dataset_metadata = _evaluate_truncated_dataset(
            base_config,
            dataset,
            model_root,
            logger,
            full_data=args.full_data,
            ratio_override=ratio_override,
            split_variant=split_variant,
        )
        all_rows.extend(dataset_rows)
        metadata_by_dataset[dataset] = dataset_metadata

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    truncated_csv = out_dir / f"view_eval_truncated_ordered_pre_split{suffix}_{ts}.csv"
    truncated_json = out_dir / f"view_eval_truncated_ordered_pre_split{suffix}_{ts}.json"
    truncated_df = pd.DataFrame(all_rows)
    truncated_df.to_csv(truncated_csv, index=False, encoding="utf-8-sig")

    validate_protocol_dataframe(truncated_df)

    truncated_summary = {
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "sample_cap_mode": "full_data" if args.full_data else "configured_caps",
        "split_variant": split_variant,
        "datasets": selected_datasets,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": int(len(truncated_df)),
        "dataset_configs": {dataset: {**DATASET_CONFIGS[dataset], **(ratio_override or {})} for dataset in selected_datasets},
        "best_by_dataset": {},
    }
    if not truncated_df.empty:
        for dataset, sub in truncated_df.groupby("dataset"):
            best = sub.sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).head(1)
            truncated_summary["best_by_dataset"][dataset] = best.to_dict(orient="records")[0]
    truncated_json.write_text(json.dumps(truncated_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    ordered_parts = []
    for dataset, rel_path in ORDERED_SOURCES.items():
        if dataset not in selected_datasets:
            continue
        df = pd.read_csv(project_root / rel_path)
        ordered_parts.append(_load_protocol_df(df, "ordered_pre_split", rel_path))
    ordered_df = pd.concat(ordered_parts, ignore_index=True)

    random_source = _find_latest_report(project_root / "outputs" / "reports", "view_eval_random_window_stratified_3way_*.csv")
    random_df = _load_protocol_df(
        pd.read_csv(random_source),
        "random_window_stratified_3way",
        str(random_source.relative_to(project_root)),
    )

    truncated_df_cmp = _load_protocol_df(
        truncated_df,
        TRUNCATED_SPLIT_MODE,
        str(truncated_csv.relative_to(project_root)),
    )

    random_df = random_df[random_df["dataset"].isin(selected_datasets)].copy()

    compare_df = pd.concat([ordered_df, random_df, truncated_df_cmp], ignore_index=True, sort=False)
    compare_csv = out_dir / f"protocol_compare_ordered_random_truncated{suffix}_{ts}.csv"
    compare_df.to_csv(compare_csv, index=False, encoding="utf-8-sig")

    merge_keys = ["dataset", "experiment_group", "model_name"]
    ordered_small = ordered_df[merge_keys + METRIC_COLUMNS].rename(columns=lambda c: f"ordered_{c}" if c not in merge_keys else c)
    random_small = random_df[merge_keys + METRIC_COLUMNS].rename(columns=lambda c: f"random_{c}" if c not in merge_keys else c)
    truncated_small = truncated_df_cmp[merge_keys + METRIC_COLUMNS].rename(columns=lambda c: f"truncated_{c}" if c not in merge_keys else c)

    summary_df = ordered_small.merge(random_small, on=merge_keys, how="inner")
    summary_df = summary_df.merge(truncated_small, on=merge_keys, how="inner")
    for metric in ["accuracy", "precision", "recall", "f1", "auc", "pr_auc"]:
        summary_df[f"delta_random_vs_ordered_{metric}"] = summary_df[f"random_{metric}"] - summary_df[f"ordered_{metric}"]
        summary_df[f"delta_truncated_vs_ordered_{metric}"] = summary_df[f"truncated_{metric}"] - summary_df[f"ordered_{metric}"]
        summary_df[f"delta_truncated_vs_random_{metric}"] = summary_df[f"truncated_{metric}"] - summary_df[f"random_{metric}"]
    summary_df = summary_df.sort_values(
        ["dataset", "delta_truncated_vs_random_f1", "delta_truncated_vs_ordered_f1"],
        ascending=[True, False, False],
    )
    summary_csv = out_dir / f"protocol_compare_ordered_random_truncated_summary{suffix}_{ts}.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    compare_summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sample_cap_mode": "full_data" if args.full_data else "configured_caps",
        "split_variant": split_variant,
        "datasets": selected_datasets,
        "ordered_sources": {dataset: ORDERED_SOURCES[dataset] for dataset in selected_datasets},
        "random_source": str(random_source.relative_to(project_root)).replace("\\", "/"),
        "truncated_source": str(truncated_csv.relative_to(project_root)).replace("\\", "/"),
        "dataset_configs": {dataset: {**DATASET_CONFIGS[dataset], **(ratio_override or {})} for dataset in selected_datasets},
        "best_by_dataset": {},
    }
    protocol_frames = {
        "ordered_pre_split": ordered_df,
        "random_window_stratified_3way": random_df,
        TRUNCATED_SPLIT_MODE: truncated_df_cmp,
    }
    for dataset in selected_datasets:
        compare_summary["best_by_dataset"][dataset] = {}
        for protocol, frame in protocol_frames.items():
            subset = frame[frame["dataset"] == dataset]
            best = subset.sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).head(1)
            compare_summary["best_by_dataset"][dataset][protocol] = best.to_dict(orient="records")[0]
    compare_json = out_dir / f"protocol_compare_ordered_random_truncated_summary{suffix}_{ts}.json"
    compare_json.write_text(json.dumps(compare_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "sample_cap_mode": "full_data" if args.full_data else "configured_caps",
        "split_variant": split_variant,
        "datasets": selected_datasets,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_configs": {dataset: {**DATASET_CONFIGS[dataset], **(ratio_override or {})} for dataset in selected_datasets},
        "truncated_metadata": {k: flatten_protocol_metadata(v) for k, v in metadata_by_dataset.items()},
        "truncated_csv": str(truncated_csv.relative_to(project_root)).replace("\\", "/"),
        "truncated_json": str(truncated_json.relative_to(project_root)).replace("\\", "/"),
        "compare_csv": str(compare_csv.relative_to(project_root)).replace("\\", "/"),
        "summary_csv": str(summary_csv.relative_to(project_root)).replace("\\", "/"),
        "summary_json": str(compare_json.relative_to(project_root)).replace("\\", "/"),
        "random_source_csv": str(random_source.relative_to(project_root)).replace("\\", "/"),
    }
    manifest_path = out_dir / f"protocol_compare_ordered_random_truncated_manifest{suffix}_{ts}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print(f"TRUNCATED CSV: {truncated_csv}")
    print(f"TRUNCATED JSON: {truncated_json}")
    print(f"COMPARE CSV: {compare_csv}")
    print(f"SUMMARY CSV: {summary_csv}")
    print(f"SUMMARY JSON: {compare_json}")
    print(f"MANIFEST JSON: {manifest_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
