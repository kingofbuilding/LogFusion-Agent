from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.my_model_public import run_my_model_public
from benchmarks.public_logs.preprocess_hdfs import run_hdfs_preprocess
from benchmarks.runners._deeplog_protocol_common import DeepLogProtocolSpec, _split_for_protocol
from src.utils import Config, Logger


def main(config_path: str = "benchmarks/configs/hdfs.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("run_hdfs_my_model_protocol", config)
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
    metrics, art = run_my_model_public(train_df, val_df, test_df, config, fixed_threshold=None)

    row = {
        "Dataset": "HDFS",
        "Model": "MyModelThreeView",
        "Precision": float(metrics.get("precision", 0.0)),
        "Recall": float(metrics.get("recall", 0.0)),
        "F1": float(metrics.get("f1", 0.0)),
        "train_normal_sequences": int(len(train_df)),
        "sequence_protocol": spec.sequence_protocol,
        "parser": spec.parser,
        "threshold_r": float(metrics.get("threshold", art.threshold)),
        "score_source": art.score_source,
        "status": art.status,
        "notes": art.notes,
    }
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": "HDFS",
        "parser": spec.parser,
        "sequence_protocol": spec.sequence_protocol,
        "train_normal_sequences": int(len(train_df)),
        "val_sequences": int(len(val_df)),
        "test_sequences": int(len(test_df)),
        "threshold_r": float(metrics.get("threshold", art.threshold)),
        "score_source": art.score_source,
        "metrics": metrics,
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
    csv_path = out_dir / f"my_model_protocol_hdfs_{ts}.csv"
    json_path = out_dir / f"my_model_protocol_hdfs_{ts}.json"
    pd.DataFrame([row]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[HDFS] My-model protocol outputs csv=%s json=%s", csv_path, json_path)
    return csv_path, json_path


if __name__ == "__main__":
    main()
