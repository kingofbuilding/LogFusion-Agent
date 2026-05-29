from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.fusion_public import run_fusion_bgl_stat_semraw, run_fusion_bgl_stat_temp, run_fusion_public_mean, run_fusion_public_weighted
from benchmarks.models.semantic_public import run_semantic_public
from benchmarks.models.statistical_public import run_statistical_public
from benchmarks.models.temporal_public import evaluate_binary_metrics, score_temporal_public, train_temporal_public_model
from benchmarks.public_logs.preprocess_bgl import run_bgl_preprocess
from benchmarks.public_logs.split_utils import keep_only_normal_train, split_bgl_ordered, summarize_split
from src.utils import Config, Logger, set_random_seed


LITERATURE = [
    {"Dataset": "BGL", "Model": "DeepLog", "Precision": 89.74, "Recall": 82.78, "F1": 86.12, "AUC": None, "PR-AUC": None, "Status": "reported_baseline", "Notes": "reported in LogBERT", "Source": "reported_in_LogBERT"},
    {"Dataset": "BGL", "Model": "LogBERT", "Precision": 89.40, "Recall": 92.32, "F1": 90.83, "AUC": None, "PR-AUC": None, "Status": "reported_baseline", "Notes": "reported in LogBERT", "Source": "reported_in_LogBERT"},
]


def _normalize_row(model: str, metrics: dict | None, status: str, notes: str, source: str = "reproduced_in_this_work") -> dict:
    return {
        "Dataset": "BGL",
        "Model": model,
        "Precision": None if metrics is None else metrics.get("precision"),
        "Recall": None if metrics is None else metrics.get("recall"),
        "F1": None if metrics is None else metrics.get("f1"),
        "AUC": None if metrics is None else metrics.get("auc"),
        "PR-AUC": None if metrics is None else metrics.get("pr_auc"),
        "Status": status,
        "Notes": notes,
        "Source": source,
    }


def _majority_baseline(y_test: np.ndarray) -> dict:
    scores = np.zeros_like(y_test, dtype=float)
    return evaluate_binary_metrics(y_test, scores, 0.5)


def _random_baseline(y_val: np.ndarray, y_test: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    val_scores = rng.random(len(y_val))
    test_scores = rng.random(len(y_test))
    best_thr, best_f1 = 0.5, -1.0
    for cand in np.linspace(0.05, 0.95, 181):
        cur = evaluate_binary_metrics(y_val, val_scores, cand)["f1"]
        if cur > best_f1:
            best_f1 = cur
            best_thr = float(cand)
    return evaluate_binary_metrics(y_test, test_scores, best_thr)


def _truncate_split(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    if limit <= 0 or len(df) <= limit:
        return df.reset_index(drop=True)
    return df.iloc[:limit].copy().reset_index(drop=True)


def main(config_path: str = "benchmarks/configs/bgl.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("run_bgl_public", config)
    set_random_seed(int(config.get("experiment.random_seed", 42)))
    seq_df = run_bgl_preprocess(config)
    split = split_bgl_ordered(seq_df, float(config.get("benchmarks.public_logs.train_ratio", 0.6)), float(config.get("benchmarks.public_logs.val_ratio", 0.2)))
    train_df = keep_only_normal_train(split.train)
    val_df = split.val.reset_index(drop=True)
    test_df = split.test.reset_index(drop=True)

    max_train_samples = int(config.get("benchmarks.public_logs.max_train_samples", 0))
    max_val_samples = int(config.get("benchmarks.public_logs.max_val_samples", 0))
    max_test_samples = int(config.get("benchmarks.public_logs.max_test_samples", 0))
    if max_train_samples > 0 or max_val_samples > 0 or max_test_samples > 0:
        train_df = _truncate_split(train_df, max_train_samples)
        val_df = _truncate_split(val_df, max_val_samples)
        test_df = _truncate_split(test_df, max_test_samples)
        logger.info(
            f"[BGL] subset validation enabled max_train={max_train_samples} max_val={max_val_samples} max_test={max_test_samples}"
        )

    logger.info(f"[BGL] split summary train={summarize_split(train_df)} val={summarize_split(val_df)} test={summarize_split(test_df)}")
    temporal_model, temporal_window_size, temporal_device, train_normal_temporal = train_temporal_public_model(
        train_df, val_df, test_df, config
    )
    temporal_metrics, temporal_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="mean_miss_ratio",
    )
    temporal_seq_metrics, temporal_seq_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="sequence_miss_burst_ratio",
    )
    temporal_deeplog_miss_metrics, temporal_deeplog_miss_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="deeplog_topk_miss_ratio",
    )
    temporal_deeplog_metrics, temporal_deeplog_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="deeplog_true_prob_mean",
    )
    temporal_deeplog_topk_metrics, temporal_deeplog_topk_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="deeplog_true_prob_topk_mean",
    )
    temporal_deeplog_max_metrics, temporal_deeplog_max_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="deeplog_true_prob_min",
    )
    temporal_deeplog_nll_topk_metrics, temporal_deeplog_nll_topk_art = score_temporal_public(
        temporal_model,
        temporal_window_size,
        temporal_device,
        train_normal_temporal,
        val_df,
        test_df,
        config,
        score_mode="deeplog_nll_topk_mean",
    )
    sem_tpl_metrics, sem_tpl_art = run_semantic_public(train_df, val_df, test_df, config, mode="template")
    sem_raw_metrics, sem_raw_art = run_semantic_public(train_df, val_df, test_df, config, mode="raw")
    sem_hash_metrics, sem_hash_art = run_semantic_public(train_df, val_df, test_df, config, mode="hash")
    stat_metrics, stat_art = run_statistical_public(train_df, val_df, test_df, config)

    semantic_for_fusion = sem_hash_art
    semantic_name_for_fusion = "semantic_public_hash"
    if sem_tpl_art.status == "valid":
        semantic_for_fusion = sem_tpl_art
        semantic_name_for_fusion = "semantic_public_template"
    else:
        logger.warning("[BGL] semantic_public_template excluded from formal rows and fusion input due to hash fallback")

    fusion_stat_semraw_metrics, fusion_stat_semraw_art = run_fusion_bgl_stat_semraw(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        sem_raw_art.val_scores,
        sem_raw_art.test_scores,
        config,
    )
    fusion_mean_metrics, fusion_mean_art = run_fusion_public_mean(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        semantic_for_fusion.val_scores,
        semantic_for_fusion.test_scores,
        temporal_art.val_scores,
        temporal_art.test_scores,
        config,
    )
    fusion_weighted_metrics, fusion_weighted_art = run_fusion_public_weighted(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        semantic_for_fusion.val_scores,
        semantic_for_fusion.test_scores,
        temporal_art.val_scores,
        temporal_art.test_scores,
        config,
    )
    fusion_mean_deeplog_metrics, fusion_mean_deeplog_art = run_fusion_public_mean(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        semantic_for_fusion.val_scores,
        semantic_for_fusion.test_scores,
        temporal_deeplog_art.val_scores,
        temporal_deeplog_art.test_scores,
        config,
    )
    fusion_stat_temp_deeplog_metrics, fusion_stat_temp_deeplog_art = run_fusion_bgl_stat_temp(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        temporal_deeplog_art.val_scores,
        temporal_deeplog_art.test_scores,
        config,
        label="fusion_bgl_stat_temp_deeplog",
    )
    fusion_weighted_deeplog_metrics, fusion_weighted_deeplog_art = run_fusion_public_weighted(
        val_df,
        test_df,
        stat_art.val_scores,
        stat_art.test_scores,
        semantic_for_fusion.val_scores,
        semantic_for_fusion.test_scores,
        temporal_deeplog_art.val_scores,
        temporal_deeplog_art.test_scores,
        config,
    )

    y_val = val_df["label"].astype(int).values
    majority_metrics = _majority_baseline(test_df["label"].astype(int).values)
    random_metrics = _random_baseline(y_val, test_df["label"].astype(int).values, int(config.get("experiment.random_seed", 42)))

    rows = [
        _normalize_row("temporal_public", temporal_metrics, temporal_art.status, temporal_art.notes),
        _normalize_row("temporal_public_bgl_sequence", temporal_seq_metrics, temporal_seq_art.status, temporal_seq_art.notes),
        _normalize_row("temporal_public_bgl_deeplog_topk_miss", temporal_deeplog_miss_metrics, temporal_deeplog_miss_art.status, temporal_deeplog_miss_art.notes),
        _normalize_row("temporal_public_bgl_deeplog", temporal_deeplog_metrics, temporal_deeplog_art.status, temporal_deeplog_art.notes),
        _normalize_row("temporal_public_bgl_deeplog_prob_topk", temporal_deeplog_topk_metrics, temporal_deeplog_topk_art.status, temporal_deeplog_topk_art.notes),
        _normalize_row("temporal_public_bgl_deeplog_prob_max", temporal_deeplog_max_metrics, temporal_deeplog_max_art.status, temporal_deeplog_max_art.notes),
        _normalize_row("temporal_public_bgl_deeplog_nll_topk", temporal_deeplog_nll_topk_metrics, temporal_deeplog_nll_topk_art.status, temporal_deeplog_nll_topk_art.notes),
        _normalize_row("semantic_public_hash", sem_hash_metrics, sem_hash_art.status, sem_hash_art.notes),
        _normalize_row("semantic_public_raw", sem_raw_metrics, sem_raw_art.status, sem_raw_art.notes),
        _normalize_row("statistical_public", stat_metrics, "valid", "IsolationForest on public statistical features; threshold selected on val only"),
        _normalize_row("majority_baseline", majority_metrics, "valid", "zero-score baseline"),
        _normalize_row("random_baseline", random_metrics, "valid", "random score baseline with threshold tuned on val"),
    ]
    if sem_tpl_art.status != "valid":
        rows.append(_normalize_row("semantic_public_template", None, sem_tpl_art.status, sem_tpl_art.notes))
    else:
        rows.append(_normalize_row("semantic_public_template", sem_tpl_metrics, sem_tpl_art.status, sem_tpl_art.notes))
    rows.extend(LITERATURE)

    out_dir = Path(config.get("paths.outputs.reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"public_benchmark_bgl_{ts}.csv"
    json_path = out_dir / f"public_benchmark_bgl_{ts}.json"
    payload = {
        "rows": rows,
        "threshold_source": "val",
        "generated_at": ts,
        "sort_strategy": "sort_by_event_ts_before_windowing",
        "split_strategy": "ordered_time_split_after_windowing",
        "train_filter": "normal_only",
        "window_minutes": float(config.get("benchmarks.public_logs.bgl.window_minutes", 5.0)),
        "stride_minutes": float(config.get("benchmarks.public_logs.bgl.stride_minutes", 1.0)),
        "max_train_samples": max_train_samples,
        "max_val_samples": max_val_samples,
        "max_test_samples": max_test_samples,
        "semantic_input_mode": sem_tpl_art.input_mode,
        "semantic_input_modes": {
            "template": sem_tpl_art.input_mode,
            "raw": sem_raw_art.input_mode,
            "hash": sem_hash_art.input_mode,
        },
        "temporal_score_mode": temporal_art.score_mode,
        "temporal_comparison_score_mode": temporal_seq_art.score_mode,
        "temporal_deeplog_topk_miss_score_mode": temporal_deeplog_miss_art.score_mode,
        "temporal_deeplog_score_mode": temporal_deeplog_art.score_mode,
        "temporal_deeplog_prob_topk_score_mode": temporal_deeplog_topk_art.score_mode,
        "temporal_deeplog_prob_max_score_mode": temporal_deeplog_max_art.score_mode,
        "temporal_deeplog_nll_topk_score_mode": temporal_deeplog_nll_topk_art.score_mode,
    }
    audit_path = out_dir / "bgl_semantic_raw_audit.json"
    audit_payload = {
        "dataset": "BGL",
        "generated_at": ts,
        "sort_strategy": payload["sort_strategy"],
        "split_strategy": payload["split_strategy"],
        "train_filter": payload["train_filter"],
        "window_minutes": payload["window_minutes"],
        "stride_minutes": payload["stride_minutes"],
        "semantic_input_mode": sem_raw_art.input_mode,
        "raw_text_retained": True,
        "threshold_source": "val",
        "template_semantic": {
            "f1": None if sem_tpl_metrics is None else sem_tpl_metrics.get("f1"),
            "auc": None if sem_tpl_metrics is None else sem_tpl_metrics.get("auc"),
            "pr_auc": None if sem_tpl_metrics is None else sem_tpl_metrics.get("pr_auc"),
            "status": sem_tpl_art.status,
            "backend": sem_tpl_art.backend,
            "input_mode": sem_tpl_art.input_mode,
        },
        "raw_semantic": {
            "f1": None if sem_raw_metrics is None else sem_raw_metrics.get("f1"),
            "auc": None if sem_raw_metrics is None else sem_raw_metrics.get("auc"),
            "pr_auc": None if sem_raw_metrics is None else sem_raw_metrics.get("pr_auc"),
            "status": sem_raw_art.status,
            "backend": sem_raw_art.backend,
            "input_mode": sem_raw_art.input_mode,
        },
        "statistical_public": {
            "f1": stat_metrics.get("f1"),
        },
        "fusion_bgl_stat_semraw": {
            "f1": fusion_stat_semraw_metrics.get("f1"),
            "threshold": fusion_stat_semraw_art.threshold,
        },
        "semraw_beats_statistical": bool(fusion_stat_semraw_metrics.get("f1", 0.0) > stat_metrics.get("f1", 0.0)),
        "comparison_against_template_semantic": {
            "f1_delta_raw_minus_template": (0.0 if sem_raw_metrics is None else float(sem_raw_metrics.get("f1", 0.0))) - (0.0 if sem_tpl_metrics is None else float(sem_tpl_metrics.get("f1", 0.0))),
            "auc_delta_raw_minus_template": (0.0 if sem_raw_metrics is None else float(sem_raw_metrics.get("auc", 0.0))) - (0.0 if sem_tpl_metrics is None else float(sem_tpl_metrics.get("auc", 0.0))),
            "pr_auc_delta_raw_minus_template": (0.0 if sem_raw_metrics is None else float(sem_raw_metrics.get("pr_auc", 0.0))) - (0.0 if sem_tpl_metrics is None else float(sem_tpl_metrics.get("pr_auc", 0.0))),
        },
    }
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[BGL] result files saved csv={csv_path} json={json_path}")
    logger.info(f"[BGL] semantic raw audit saved path={audit_path}")
    return csv_path, json_path


if __name__ == "__main__":
    main()
