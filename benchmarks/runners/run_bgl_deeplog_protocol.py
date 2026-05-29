from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.public_logs.preprocess_bgl import run_bgl_preprocess
from benchmarks.runners._deeplog_protocol_common import DeepLogProtocolSpec, run_deeplog_protocol, save_protocol_outputs
from src.utils import Config, Logger


def main(config_path: str = "benchmarks/configs/bgl.yaml"):
    config = Config(config_path)
    config.update_config(
        {
            "benchmarks.public_logs.temporal_rnn_type": "lstm",
            "benchmarks.public_logs.bgl.window_minutes": 5,
            "benchmarks.public_logs.bgl.stride_minutes": 1,
            "benchmarks.public_logs.temporal_top_k": int(config.get("benchmarks.public_logs.temporal_top_k", 5)),
        },
        persist=False,
    )
    logger = Logger.get_logger("run_bgl_deeplog_protocol", config)
    seq_df = run_bgl_preprocess(config)
    spec = DeepLogProtocolSpec(
        dataset="bgl",
        parser="Drain",
        sequence_protocol="5_minute_time_window_stride_1_minute",
        score_mode="deeplog_topk_miss_ratio",
        train_normal_sequences=5000,
        threshold_r=float(config.get("benchmarks.public_logs.deeplog_threshold_r", 0.5)),
        use_val_split=False,
    )
    row, payload = run_deeplog_protocol(seq_df, config, spec, "run_bgl_deeplog_protocol")
    csv_path, json_path = save_protocol_outputs(config, "bgl", row, payload)
    logger.info("[BGL] DeepLog protocol outputs csv=%s json=%s", csv_path, json_path)
    return csv_path, json_path


if __name__ == "__main__":
    main()
