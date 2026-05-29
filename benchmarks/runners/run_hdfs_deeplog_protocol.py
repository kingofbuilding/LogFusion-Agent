from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.public_logs.preprocess_hdfs import run_hdfs_preprocess
from benchmarks.runners._deeplog_protocol_common import DeepLogProtocolSpec, run_deeplog_protocol, save_protocol_outputs
from src.utils import Config, Logger


def main(config_path: str = "benchmarks/configs/hdfs.yaml"):
    config = Config(config_path)
    config.update_config({"benchmarks.public_logs.temporal_rnn_type": "lstm"}, persist=False)
    logger = Logger.get_logger("run_hdfs_deeplog_protocol", config)
    seq_df = run_hdfs_preprocess(config)
    spec = DeepLogProtocolSpec(
        dataset="hdfs",
        parser="Drain",
        sequence_protocol="session_id_block_grouping",
        score_mode="deeplog_topk_miss_ratio",
        train_normal_sequences=5000,
    )
    row, payload = run_deeplog_protocol(seq_df, config, spec, "run_hdfs_deeplog_protocol")
    csv_path, json_path = save_protocol_outputs(config, "hdfs", row, payload)
    logger.info("[HDFS] DeepLog protocol outputs csv=%s json=%s", csv_path, json_path)
    return csv_path, json_path


if __name__ == "__main__":
    main()
