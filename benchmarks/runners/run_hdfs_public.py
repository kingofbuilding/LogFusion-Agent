from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.fusion_public import run_fusion_public_mean, run_fusion_public_weighted
from benchmarks.models.semantic_public import run_semantic_public
from benchmarks.models.statistical_public import run_statistical_public
from benchmarks.models.temporal_public import evaluate_binary_metrics, run_temporal_public
from benchmarks.public_logs.preprocess_hdfs import run_hdfs_preprocess
from benchmarks.public_logs.split_utils import assert_no_overlap, keep_only_normal_train, split_hdfs_by_block, summarize_split
from src.utils import Config, Logger, set_random_seed


LITERATURE = [
    {"Dataset": "HDFS", "Model": "DeepLog", "Precision": 88.44, "Recall": 69.49, "F1": 77.34, "AUC": None, "PR-AUC": None, "Status": "reported_baseline", "Notes": "reported in LogBERT", "Source": "reported_in_LogBERT"},
    {"Dataset": "HDFS", "Model": "LogBERT", "Precision": 87.02, "Recall": 78.10, "F1": 82.32, "AUC": None, "PR-AUC": None, "Status": "reported_baseline", "Notes": "reported in LogBERT", "Source": "reported_in_LogBERT"},
]


def _normalize_row(model: str, metrics: dict | None, status: str, notes: str, source: str = "reproduced_in_this_work") -> dict:
    return {
        "Dataset": "HDFS",
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


def main(config_path: str = "benchmarks/configs/hdfs.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("run_hdfs_public", config)
    set_random_seed(int(config.get("experiment.random_seed", 42)))
    seq_df = run_hdfs_preprocess(config)
    split = split_hdfs_by_block(seq_df, float(config.get("benchmarks.public_logs.train_ratio", 0.6)), float(config.get("benchmarks.public_logs.val_ratio", 0.2)))

    train_ids = set(split.train["sequence_id"].astype(str).tolist())
    val_ids = set(split.val["sequence_id"].astype(str).tolist())
    test_ids = set(split.test["sequence_id"].astype(str).tolist())
    intersections = {
        "train_val": len(train_ids & val_ids),
        "train_test": len(train_ids & test_ids),
        "val_test": len(val_ids & test_ids),
    }
    logger.info(f"[HDFS] BlockId counts train={len(train_ids)} val={len(val_ids)} test={len(test_ids)}")
    logger.info(f"[HDFS] BlockId intersections {intersections}")
    if any(intersections.values()):
        raise RuntimeError(f"BlockId leakage detected: {intersections}")
    assert_no_overlap(train_ids, val_ids, test_ids)

    train_df = keep_only_normal_train(split.train)
    val_df = split.val.reset_index(drop=True)
    test_df = split.test.reset_index(drop=True)
    logger.info("[HDFS] split order=split by BlockId first, then assign train/val/test")
    logger.info(f"[HDFS] split summary train={summarize_split(train_df)} val={summarize_split(val_df)} test={summarize_split(test_df)}")

    temporal_metrics, temporal_art = run_temporal_public(train_df, val_df, test_df, config)
    sem_tpl_metrics, sem_tpl_art = run_semantic_public(train_df, val_df, test_df, config, mode="template")
    sem_hash_metrics, sem_hash_art = run_semantic_public(train_df, val_df, test_df, config, mode="hash")
    stat_metrics, stat_art = run_statistical_public(train_df, val_df, test_df, config)

    semantic_for_fusion = sem_hash_art
    semantic_name_for_fusion = "semantic_public_hash"
    if sem_tpl_art.status == "valid":
        semantic_for_fusion = sem_tpl_art
        semantic_name_for_fusion = "semantic_public_template"
    else:
        logger.warning("[HDFS] semantic_public_template excluded from formal rows and fusion input due to hash fallback")

    suspicious_tokens = ("label", "target", "anomaly", "ground_truth", "future", "rate")
    fusion_feature_names = ["statistical_public_score", f"{semantic_name_for_fusion}_score", "temporal_public_score"]
    suspicious_features = [name for name in fusion_feature_names if any(tok in name.lower() for tok in suspicious_tokens)]
    logger.info(f"[HDFS] fusion feature columns={fusion_feature_names}")
    if suspicious_features:
        raise RuntimeError(f"Suspicious fusion features detected: {suspicious_features}")

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

    y_val = val_df["label"].astype(int).values
    majority_metrics = _majority_baseline(test_df["label"].astype(int).values)
    random_metrics = _random_baseline(y_val, test_df["label"].astype(int).values, int(config.get("experiment.random_seed", 42)))

    audit_valid = True
    audit_issues = []
    if any(intersections.values()):
        audit_valid = False
        audit_issues.append("BlockId intersection non-zero")
    if suspicious_features:
        audit_valid = False
        audit_issues.append("Suspicious fusion features present")
    logger.info("[HDFS] threshold source=val")

    rows = [
        _normalize_row("temporal_public", temporal_metrics, temporal_art.status, temporal_art.notes),
        _normalize_row("semantic_public_hash", sem_hash_metrics, sem_hash_art.status, sem_hash_art.notes),
        _normalize_row("statistical_public", stat_metrics, "valid", "IsolationForest on public statistical features; threshold selected on val only"),
        _normalize_row("fusion_public_mean", fusion_mean_metrics, fusion_mean_art.status, fusion_mean_art.notes),
        _normalize_row("fusion_public_weighted", fusion_weighted_metrics, fusion_weighted_art.status, fusion_weighted_art.notes),
        _normalize_row("majority_baseline", majority_metrics, "valid", "zero-score baseline"),
        _normalize_row("random_baseline", random_metrics, "valid", "random score baseline with threshold tuned on val"),
    ]
    if sem_tpl_art.status != "valid":
        rows.append(_normalize_row("semantic_public_template", None, sem_tpl_art.status, sem_tpl_art.notes))
    else:
        rows.append(_normalize_row("semantic_public_template", sem_tpl_metrics, sem_tpl_art.status, sem_tpl_art.notes))
    rows.extend(LITERATURE)

    out_dir = Path(config.get("paths.outputs.reports")) / "hdfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    split_audit = {
        "dataset": "HDFS",
        "sequence_construction": "BlockId grouped sequence",
        "train_block_count": len(train_ids),
        "val_block_count": len(val_ids),
        "test_block_count": len(test_ids),
        "blockid_intersections": intersections,
        "train_summary": summarize_split(train_df),
        "val_summary": summarize_split(val_df),
        "test_summary": summarize_split(test_df),
        "threshold_source": "val",
        "fusion_inputs": fusion_feature_names,
        "fusion_mean_threshold": fusion_mean_art.threshold,
        "fusion_weighted_threshold": fusion_weighted_art.threshold,
        "fusion_weighted_weights": fusion_weighted_art.weights,
        "audit_valid": audit_valid,
        "issues": audit_issues,
    }
    feature_audit = {
        "dataset": "HDFS",
        "parser_fit_scope": "parser currently runs on full HDFS raw log before BlockId split",
        "semantic_fit_scope": "semantic embeddings/center fit on train normal only; template result is invalidated if it falls back to hash",
        "temporal_fit_scope": "next-event predictor fit on normal-only train sequences; anomaly score is sequence-level top-k miss ratio",
        "statistical_fit_scope": "IsolationForest fit on train normal only",
        "fusion_fit_scope": "mean and weighted score fusion over statistical/semantic/temporal anomaly scores; weights and thresholds selected on val only",
        "fusion_feature_columns": fusion_feature_names,
        "suspicious_feature_columns": suspicious_features,
        "threshold_source": "val",
        "uses_test_for_threshold_search": False,
        "leakage_audit_passed": audit_valid,
        "notes": [
            "BlockId split is enforced before train/val/test assignment.",
            "Sequence-level labels are derived per BlockId sequence.",
            "Current parser/template miner still parses the full raw HDFS log before split; this is protocol-aligned preprocessing but should be interpreted as a shared parser stage, not a train-only fitted vocabulary.",
            "supervision-based fusion_public is no longer reported for strict normal-only HDFS; score fusion is used instead.",
        ],
    }

    (out_dir / "hdfs_split_audit.json").write_text(json.dumps(split_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "hdfs_feature_audit.json").write_text(json.dumps(feature_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(out_dir / "hdfs_metrics.csv", index=False, encoding="utf-8-sig")
    (out_dir / "hdfs_metrics.md").write_text("# HDFS Public Benchmark Metrics\n\n" + metrics_df.to_markdown(index=False), encoding="utf-8")
    logger.info(f"[HDFS] result files saved under {out_dir}")
    return out_dir / "hdfs_metrics.csv", out_dir / "hdfs_split_audit.json"


if __name__ == "__main__":
    main()
