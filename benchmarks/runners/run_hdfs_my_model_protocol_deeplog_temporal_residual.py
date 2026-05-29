from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.my_model_public_deeplog_temporal_residual import run_my_model_public_deeplog_temporal_residual
from benchmarks.models.temporal_public import evaluate_binary_metrics
from benchmarks.public_logs.preprocess_hdfs import run_hdfs_preprocess
from benchmarks.runners._deeplog_protocol_common import DeepLogProtocolSpec, _split_for_protocol
from src.utils import Config, Logger


def main(config_path: str = "benchmarks/configs/hdfs.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("run_hdfs_my_model_protocol_deeplog_temporal_residual", config)
    seq_df = run_hdfs_preprocess(config)
    spec = DeepLogProtocolSpec(
        dataset="hdfs",
        parser="Drain",
        sequence_protocol="session_id_block_grouping",
        train_normal_sequences=5000,
        threshold_r=None,
        use_val_split=True,
    )
    train_df, val_df, test_df = _split_for_protocol(seq_df, config, spec)
    train_df = train_df.iloc[: min(len(train_df), spec.train_normal_sequences)].copy().reset_index(drop=True)
    max_val = int(config.get("benchmarks.public_logs.max_val_samples", 0))
    max_test = int(config.get("benchmarks.public_logs.max_test_samples", 0))
    if max_val > 0 and len(val_df) > max_val:
        val_df = val_df.iloc[:max_val].copy().reset_index(drop=True)
    if max_test > 0 and len(test_df) > max_test:
        test_df = test_df.iloc[:max_test].copy().reset_index(drop=True)

    temporal_score_mode = str(config.get("benchmarks.public_logs.deeplog_temporal_score_mode", "deeplog_topk_miss_ratio"))
    metrics, art = run_my_model_public_deeplog_temporal_residual(
        train_df,
        val_df,
        test_df,
        config,
        fixed_threshold=None,
        temporal_score_mode=temporal_score_mode,
    )

    y_test = test_df["label"].astype(int).values
    stat_metrics = evaluate_binary_metrics(y_test, art.stat_test_scores, float(art.threshold))
    temp_metrics = evaluate_binary_metrics(y_test, art.temp_test_scores, float(art.temporal_threshold))
    sem_metrics = evaluate_binary_metrics(y_test, art.sem_test_scores, float(art.threshold))

    def _row(model: str, row_metrics: dict, notes: str, score_source: str) -> dict:
        return {
            "Dataset": "HDFS",
            "Model": model,
            "Precision": float(row_metrics.get("precision", 0.0)),
            "Recall": float(row_metrics.get("recall", 0.0)),
            "F1": float(row_metrics.get("f1", 0.0)),
            "AUC": float(row_metrics.get("auc", 0.0)),
            "PR-AUC": float(row_metrics.get("pr_auc", 0.0)),
            "train_normal_sequences": int(len(train_df)),
            "sequence_protocol": spec.sequence_protocol,
            "parser": spec.parser,
            "threshold_r": float(row_metrics.get("threshold", art.threshold)),
            "threshold_source": art.threshold_source,
            "temporal_threshold": float(art.temporal_threshold),
            "temporal_score_mode": temporal_score_mode,
            "stat_weight": float(art.stat_weight),
            "sem_weight": float(art.sem_weight),
            "score_source": score_source,
            "status": art.status,
            "notes": notes,
        }

    rows = [
        _row("MyModelThreeViewStatResidual", stat_metrics, "train-normal percentile calibrated statistical residual score under fusion threshold", "three_view_statistical_residual"),
        _row("MyModelThreeViewTempResidual", temp_metrics, f"DeepLog temporal main score evaluated with its own temporal threshold ({temporal_score_mode})", f"three_view_temporal_{temporal_score_mode}"),
        _row("MyModelThreeViewSemResidual", sem_metrics, "train-normal percentile calibrated semantic residual score under fusion threshold", "three_view_semantic_residual"),
        _row("MyModelThreeViewFusionResidual", metrics, art.notes, art.score_source),
    ]
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": "HDFS",
        "parser": spec.parser,
        "sequence_protocol": spec.sequence_protocol,
        "train_normal_sequences": int(len(train_df)),
        "val_sequences": int(len(val_df)),
        "test_sequences": int(len(test_df)),
        "threshold_r": float(metrics.get("threshold", art.threshold)),
        "threshold_source": art.threshold_source,
        "temporal_threshold": float(art.temporal_threshold),
        "temporal_score_mode": temporal_score_mode,
        "stat_weight": float(art.stat_weight),
        "sem_weight": float(art.sem_weight),
        "score_source": art.score_source,
        "metrics": {
            "statistical": stat_metrics,
            "temporal": temp_metrics,
            "semantic": sem_metrics,
            "fusion": metrics,
        },
        "component_means": {
            "stat_test_mean": float(art.stat_test_scores.mean()) if len(art.stat_test_scores) else 0.0,
            "temp_test_mean": float(art.temp_test_scores.mean()) if len(art.temp_test_scores) else 0.0,
            "sem_test_mean": float(art.sem_test_scores.mean()) if len(art.sem_test_scores) else 0.0,
            "fusion_test_mean": float(art.test_scores.mean()) if len(art.test_scores) else 0.0,
        },
    }

    out_dir = Path(config.get("paths.outputs.reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"my_model_protocol_hdfs_deeplog_temporal_residual_{ts}.csv"
    json_path = out_dir / f"my_model_protocol_hdfs_deeplog_temporal_residual_{ts}.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[HDFS] DeepLog-temporal residual my-model protocol outputs csv=%s json=%s", csv_path, json_path)
    return csv_path, json_path


if __name__ == "__main__":
    main()
