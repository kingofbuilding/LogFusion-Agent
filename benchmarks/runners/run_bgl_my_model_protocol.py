from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.my_model_public import run_my_model_public
from benchmarks.models.temporal_public import evaluate_binary_metrics
from benchmarks.public_logs.preprocess_bgl import run_bgl_preprocess
from benchmarks.runners._deeplog_protocol_common import DeepLogProtocolSpec, _split_for_protocol
from src.utils import Config, Logger


def main(config_path: str = "benchmarks/configs/bgl.yaml"):
    config = Config(config_path)
    config.update_config(
        {
            "benchmarks.public_logs.bgl.window_minutes": 5,
            "benchmarks.public_logs.bgl.stride_minutes": 1,
        },
        persist=False,
    )
    logger = Logger.get_logger("run_bgl_my_model_protocol", config)
    seq_df = run_bgl_preprocess(config)
    spec = DeepLogProtocolSpec(
        dataset="bgl",
        parser="Drain",
        sequence_protocol="5_minute_time_window_stride_1_minute",
        train_normal_sequences=5000,
        threshold_r=float(config.get("benchmarks.public_logs.deeplog_threshold_r", 0.5)),
        use_val_split=False,
    )
    train_df, val_df, test_df = _split_for_protocol(seq_df, config, spec)
    max_test = int(config.get("benchmarks.public_logs.max_test_samples", 0))
    if max_test > 0 and len(test_df) > max_test:
        test_df = test_df.iloc[:max_test].copy().reset_index(drop=True)
    metrics, art = run_my_model_public(train_df, val_df, test_df, config, fixed_threshold=spec.threshold_r)
    y_test = test_df["label"].astype(int).values
    stat_metrics = evaluate_binary_metrics(y_test, art.stat_test_scores, float(spec.threshold_r))
    temp_metrics = evaluate_binary_metrics(y_test, art.temp_test_scores, float(spec.threshold_r))
    sem_metrics = evaluate_binary_metrics(y_test, art.sem_test_scores, float(spec.threshold_r))

    def _row(model: str, row_metrics: dict, notes: str, score_source: str) -> dict:
        return {
            "Dataset": "BGL",
            "Model": model,
            "Precision": float(row_metrics.get("precision", 0.0)),
            "Recall": float(row_metrics.get("recall", 0.0)),
            "F1": float(row_metrics.get("f1", 0.0)),
            "AUC": float(row_metrics.get("auc", 0.0)),
            "PR-AUC": float(row_metrics.get("pr_auc", 0.0)),
            "train_normal_sequences": int(len(train_df)),
            "sequence_protocol": spec.sequence_protocol,
            "parser": spec.parser,
            "threshold_r": float(row_metrics.get("threshold", spec.threshold_r)),
            "score_source": score_source,
            "status": art.status,
            "notes": notes,
        }

    rows = [
        _row("MyModelThreeViewStat", stat_metrics, "three-view statistical branch score", "three_view_statistical"),
        _row("MyModelThreeViewTemp", temp_metrics, "three-view temporal branch score", "three_view_temporal"),
        _row("MyModelThreeViewSem", sem_metrics, "three-view semantic branch score", "three_view_semantic"),
        _row("MyModelThreeViewFusion", metrics, art.notes, art.score_source),
    ]
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": "BGL",
        "parser": spec.parser,
        "sequence_protocol": spec.sequence_protocol,
        "train_normal_sequences": int(len(train_df)),
        "val_sequences": int(len(val_df)),
        "test_sequences": int(len(test_df)),
        "threshold_r": float(metrics.get("threshold", art.threshold)),
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
    csv_path = out_dir / f"my_model_protocol_bgl_{ts}.csv"
    json_path = out_dir / f"my_model_protocol_bgl_{ts}.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[BGL] My-model protocol outputs csv=%s json=%s", csv_path, json_path)
    return csv_path, json_path


if __name__ == "__main__":
    main()
