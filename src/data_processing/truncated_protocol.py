from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.data_processing.data_loader import DataLoader
from src.utils import Config

TRUNCATED_SPLIT_MODE = "truncated_ordered_pre_split"
TRUNCATED_PROTOCOL_ID = "truncated_ordered_pre_split_v1"
DATASET_CONFIGS = {
    "harrison": {"trunc_ratio": 0.80, "train_ratio": 0.60, "val_ratio": 0.15},
    "santos": {"trunc_ratio": 0.60, "train_ratio": 0.65, "val_ratio": 0.20},
    "fox": {"trunc_ratio": 0.55, "train_ratio": 0.60, "val_ratio": 0.20},
}
REQUIRED_RESULT_FIELDS = {
    "split_mode": TRUNCATED_SPLIT_MODE,
    "protocol_id": TRUNCATED_PROTOCOL_ID,
    "threshold_source": "val",
    "test_used_for_selection": False,
}


def load_labeled_df(loader: DataLoader) -> Tuple[pd.DataFrame, Optional[str]]:
    df = loader.load_parsed_data()
    labels_df = loader.load_labels()
    label_col = None
    if labels_df is not None:
        if {"line_num", "label"}.issubset(labels_df.columns):
            df = df.merge(labels_df, on="line_num", how="left")
            df["label"] = df["label"].fillna(0).astype(int)
            label_col = "label"
        elif {"source_file", "source_line_num", "label"}.issubset(labels_df.columns):
            if "source_line_num" not in df.columns:
                df["source_line_num"] = df["line_num"]
            df = df.merge(labels_df, on=["source_file", "source_line_num"], how="left")
            df["label"] = df["label"].fillna(0).astype(int)
            label_col = "label"
        elif {"BlockId", "label"}.issubset(labels_df.columns):
            if "raw_log" in df.columns:
                df["BlockId"] = df["raw_log"].apply(loader._extract_block_id)
                df = df.merge(labels_df, on="BlockId", how="left")
                df["label"] = df["label"].fillna(0).astype(int)
                label_col = "label"
    return df, label_col



def get_truncated_protocol_config(dataset: str) -> Dict[str, float]:
    key = str(dataset).lower().strip()
    if key not in DATASET_CONFIGS:
        raise KeyError(f"dataset={dataset} 没有配置截断时序协议参数")
    return dict(DATASET_CONFIGS[key])



def build_truncated_ordered_splits(
    cfg: Config,
    dataset: Optional[str] = None,
    full_data: bool = False,
    ratio_override: Optional[Dict[str, float]] = None,
    split_variant: str = "dataset_specific",
) -> Dict[str, Any]:
    if dataset is not None:
        cfg.config.setdefault("data", {})["dataset"] = str(dataset).lower()
    dataset_name = str(cfg.get("data.dataset", "")).lower()
    params = get_truncated_protocol_config(dataset_name)
    if ratio_override:
        if "train_ratio" in ratio_override:
            params["train_ratio"] = float(ratio_override["train_ratio"])
        if "val_ratio" in ratio_override:
            params["val_ratio"] = float(ratio_override["val_ratio"])

    cfg.config.setdefault("data", {})["split_mode"] = TRUNCATED_SPLIT_MODE
    loader = DataLoader(cfg)
    df, label_col = load_labeled_df(loader)
    if label_col is None:
        raise ValueError(f"dataset={dataset_name} 缺少标签，无法构造截断时序协议")

    original_total_rows = int(len(df))
    trunc_ratio = float(params["trunc_ratio"])
    trunc_rows = max(loader.sequence_length, int(original_total_rows * trunc_ratio))
    trunc_rows = min(original_total_rows, trunc_rows)
    truncated_df = df.iloc[:trunc_rows].copy()

    train_ratio = float(params["train_ratio"])
    val_ratio = float(params["val_ratio"])
    total_rows = int(len(truncated_df))
    train_end = int(total_rows * train_ratio)
    val_end = int(total_rows * (train_ratio + val_ratio))
    train_end = max(0, min(total_rows, train_end))
    val_end = max(train_end, min(total_rows, val_end))

    train_df = truncated_df.iloc[:train_end].copy()
    val_df = truncated_df.iloc[train_end:val_end].copy()
    test_df = truncated_df.iloc[val_end:].copy()

    max_default = int(cfg.get("experiment.max_sequences", 30000))
    configured_max_train = int(cfg.get("experiment.max_train_samples", max_default))
    configured_max_val = int(cfg.get("experiment.max_val_samples", cfg.get("experiment.max_test_samples", max_default)))
    configured_max_test = int(cfg.get("experiment.max_test_samples", max_default))

    if full_data:
        max_train = max(0, int(len(train_df)) - int(loader.sequence_length) + 1)
        max_val = max(0, int(len(val_df)) - int(loader.sequence_length) + 1)
        max_test = max(0, int(len(test_df)) - int(loader.sequence_length) + 1)
    else:
        max_train = configured_max_train
        max_val = configured_max_val
        max_test = configured_max_test

    train_bundle = loader._build_split_bundle(train_df, label_col, max_train, "train", 0)
    val_bundle = loader._build_split_bundle(val_df, label_col, max_val, "val", train_end)
    test_bundle = loader._build_split_bundle(test_df, label_col, max_test, "test", val_end)

    return {
        "dataset": dataset_name,
        "train": train_bundle,
        "val": val_bundle,
        "test": test_bundle,
        "metadata": {
            "protocol_id": TRUNCATED_PROTOCOL_ID,
            "split_mode": TRUNCATED_SPLIT_MODE,
            "dataset": dataset_name,
            "trunc_ratio": trunc_ratio,
            "original_total_rows": original_total_rows,
            "truncated_total_rows": total_rows,
            "active_row_range": [0, trunc_rows],
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": float(max(0.0, 1.0 - train_ratio - val_ratio)),
            "train_row_range": [0, train_end],
            "val_row_range": [train_end, val_end],
            "test_row_range": [val_end, total_rows],
            "sequence_length": int(loader.sequence_length),
            "sample_cap_mode": "full_data" if full_data else "configured_caps",
            "split_variant": split_variant,
            "configured_max_train_samples": configured_max_train,
            "configured_max_val_samples": configured_max_val,
            "configured_max_test_samples": configured_max_test,
            "effective_max_train_samples": int(max_train),
            "effective_max_val_samples": int(max_val),
            "effective_max_test_samples": int(max_test),
            "train_sequences": int(train_bundle["sequences"]),
            "val_sequences": int(val_bundle["sequences"]),
            "test_sequences": int(test_bundle["sequences"]),
            "expected_threshold_source": "val",
            "expected_test_used_for_selection": False,
        },
    }



def validate_protocol_row(row: Dict[str, Any]) -> None:
    for field, expected in REQUIRED_RESULT_FIELDS.items():
        actual = row.get(field)
        if actual != expected:
            raise ValueError(f"字段 {field}={actual!r} 与正式协议要求 {expected!r} 不一致")



def validate_protocol_dataframe(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        raise ValueError("结果表为空，无法校验协议")
    missing = [field for field in REQUIRED_RESULT_FIELDS if field not in df.columns]
    if missing:
        raise ValueError(f"结果表缺少协议字段: {missing}")
    for record in df.to_dict(orient="records"):
        validate_protocol_row(record)



def flatten_protocol_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(metadata)
    for key in ("active_row_range", "train_row_range", "val_row_range", "test_row_range"):
        if key in out:
            out[key] = list(out[key])
    return out
