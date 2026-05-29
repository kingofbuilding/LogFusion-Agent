from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from benchmarks.models.temporal_public import evaluate_binary_metrics, score_temporal_public, train_temporal_public_model
from benchmarks.public_logs.split_utils import keep_only_normal_train, split_bgl_ordered, split_hdfs_by_block, summarize_split
from src.utils import Config, Logger, set_random_seed


@dataclass
class DeepLogProtocolSpec:
    dataset: str
    parser: str
    sequence_protocol: str
    score_mode: str = "deeplog_topk_miss_ratio"
    train_normal_sequences: int = 5000
    threshold_r: float | None = None
    use_val_split: bool = True


def _truncate(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    if limit <= 0 or len(df) <= limit:
        return df.reset_index(drop=True)
    return df.iloc[:limit].copy().reset_index(drop=True)


def _split_for_protocol(seq_df: pd.DataFrame, config: Config, spec: DeepLogProtocolSpec):
    train_ratio = float(config.get("benchmarks.public_logs.train_ratio", 0.6))
    val_ratio = float(config.get("benchmarks.public_logs.val_ratio", 0.2))
    dataset = spec.dataset.lower()
    if dataset == "hdfs":
        split = split_hdfs_by_block(seq_df, train_ratio, val_ratio)
        train_df = keep_only_normal_train(split.train)
        val_df = split.val.reset_index(drop=True)
        test_df = split.test.reset_index(drop=True)
        return train_df, val_df, test_df

    ordered = seq_df.sort_values("window_start", ascending=True).reset_index(drop=True)
    normal_only = ordered[ordered["label"].astype(int) == 0].copy().reset_index(drop=True)
    train_df = _truncate(normal_only, spec.train_normal_sequences)
    train_ids = set(train_df["sequence_id"].astype(str).tolist())
    remaining = ordered[~ordered["sequence_id"].astype(str).isin(train_ids)].copy().reset_index(drop=True)
    if spec.use_val_split:
        split = split_bgl_ordered(remaining, 0.0, val_ratio)
        val_df = split.val.reset_index(drop=True)
        test_df = split.test.reset_index(drop=True)
    else:
        val_df = remaining.iloc[:0].copy().reset_index(drop=True)
        test_df = remaining.reset_index(drop=True)
    return train_df.reset_index(drop=True), val_df, test_df


def run_deeplog_protocol(seq_df: pd.DataFrame, config: Config, spec: DeepLogProtocolSpec, logger_name: str):
    logger = Logger.get_logger(logger_name, config)
    set_random_seed(int(config.get("experiment.random_seed", 42)))

    config.update_config(
        {
            "benchmarks.public_logs.temporal_rnn_type": "lstm",
            "benchmarks.public_logs.temporal_topk_aggregate_k": int(config.get("benchmarks.public_logs.temporal_topk_aggregate_k", 5)),
        },
        persist=False,
    )

    train_df, val_df, test_df = _split_for_protocol(seq_df, config, spec)
    if spec.dataset.lower() == "hdfs":
        train_df = _truncate(train_df, spec.train_normal_sequences)
    max_val = int(config.get("benchmarks.public_logs.max_val_samples", 0)) if spec.use_val_split else 0
    max_test = int(config.get("benchmarks.public_logs.max_test_samples", 0))
    val_df = _truncate(val_df, max_val)
    test_df = _truncate(test_df, max_test)

    logger.info(
        "[%s] protocol split summary train=%s val=%s test=%s",
        spec.dataset,
        summarize_split(train_df),
        summarize_split(val_df),
        summarize_split(test_df),
    )

    model, window_size, device, train_normal = train_temporal_public_model(train_df, val_df, test_df, config)
    metrics, art = score_temporal_public(
        model,
        window_size,
        device,
        train_normal,
        val_df,
        test_df,
        config,
        score_mode=spec.score_mode,
        fixed_threshold=spec.threshold_r,
    )

    row = {
        "Dataset": spec.dataset.upper(),
        "Model": "DeepLog",
        "Precision": float(metrics.get("precision", 0.0)),
        "Recall": float(metrics.get("recall", 0.0)),
        "F1": float(metrics.get("f1", 0.0)),
        "top_g": int(config.get("benchmarks.public_logs.temporal_top_k", 5)),
        "threshold_r": float(metrics.get("threshold", art.threshold)),
        "train_normal_sequences": int(len(train_df)),
        "sequence_protocol": spec.sequence_protocol,
        "parser": spec.parser,
        "score_mode": spec.score_mode,
        "status": art.status,
        "notes": art.notes,
    }
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": spec.dataset.upper(),
        "parser": spec.parser,
        "sequence_protocol": spec.sequence_protocol,
        "train_normal_sequences": int(len(train_df)),
        "val_sequences": int(len(val_df)),
        "test_sequences": int(len(test_df)),
        "top_g": int(config.get("benchmarks.public_logs.temporal_top_k", 5)),
        "threshold_r": float(metrics.get("threshold", art.threshold)),
        "score_mode": spec.score_mode,
        "window_size_h": int(window_size),
        "metrics": metrics,
    }
    return row, payload


def save_protocol_outputs(config: Config, dataset: str, row: dict, payload: dict):
    out_dir = Path(config.get("paths.outputs.reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"deeplog_protocol_{dataset.lower()}_{ts}.csv"
    json_path = out_dir / f"deeplog_protocol_{dataset.lower()}_{ts}.json"
    pd.DataFrame([row]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path
