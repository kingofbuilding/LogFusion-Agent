from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_processing.drain_parser import DrainParser
from src.utils import Config, Logger

from benchmarks.public_logs.dataset_utils import choose_time_column, load_bgl_line_labels, sequence_text_from_templates, to_unix_seconds


def _time_token(value: float) -> str:
    text = f"{float(value):g}"
    return text.replace(".", "p")



def run_bgl_preprocess(config: Config) -> pd.DataFrame:
    logger = Logger.get_logger("public_bgl_preprocess", config)
    dataset_dir = Path(config.get("paths.data.raw")) / "bgl"
    parsed_path = Path(config.get("benchmarks.public_logs.outputs.parsed_dir")) / "bgl_parsed.csv"
    window_minutes = float(config.get("benchmarks.public_logs.bgl.window_minutes", 5.0))
    stride_minutes = float(config.get("benchmarks.public_logs.bgl.stride_minutes", 1.0))
    sequence_path = (
        Path(config.get("benchmarks.public_logs.outputs.sequence_dir"))
        / f"bgl_sequences_w{_time_token(window_minutes)}_s{_time_token(stride_minutes)}.csv"
    )
    force_rebuild = bool(config.get("benchmarks.public_logs.force_rebuild", False))

    if sequence_path.exists() and not force_rebuild:
        logger.info(f"[BGL] reuse existing sequence file: {sequence_path}")
        return pd.read_csv(sequence_path)

    if parsed_path.exists() and not force_rebuild:
        logger.info(f"[BGL] reuse existing parsed file: {parsed_path}")
        parsed_df = pd.read_csv(parsed_path)
    else:
        parser = DrainParser(config)
        logger.info("[BGL] parsing raw log into templates")
        parsed_df = parser.parse_log_file(dataset_dir / "BGL.log", parsed_path)
    labels = load_bgl_line_labels(dataset_dir)
    merged = parsed_df.merge(labels, on="line_num", how="left")
    merged["label"] = merged["label"].fillna(0).astype(int)
    time_col = choose_time_column(merged)
    merged["event_ts"] = to_unix_seconds(merged[time_col])
    merged = merged.sort_values("event_ts").reset_index(drop=True)

    window_seconds = int(window_minutes * 60)
    stride_seconds = int(stride_minutes * 60)
    min_ts = int(merged["event_ts"].min())
    max_ts = int(merged["event_ts"].max())

    rows = []
    cursor = min_ts
    window_id = 0
    while cursor <= max_ts:
        end_ts = cursor + window_seconds
        part = merged[(merged["event_ts"] >= cursor) & (merged["event_ts"] < end_ts)].copy()
        if len(part):
            rows.append(
                {
                    "dataset": "BGL",
                    "sequence_id": f"window_{window_id:07d}",
                    "window_start": float(cursor),
                    "window_end": float(end_ts),
                    "template_ids": " ".join(part["template_id"].astype(int).astype(str).tolist()),
                    "templates": sequence_text_from_templates(part["template"].astype(str).tolist()),
                    "raw_text": sequence_text_from_templates(part["raw_log"].astype(str).tolist()),
                    "label": int((part["label"].astype(int) == 1).any()),
                    "sequence_length": int(len(part)),
                }
            )
        cursor += stride_seconds
        window_id += 1

    seq_df = pd.DataFrame(rows)
    sequence_path.parent.mkdir(parents=True, exist_ok=True)
    seq_df.to_csv(sequence_path, index=False, encoding="utf-8-sig")
    logger.info(
        f"[BGL] windows saved: rows={len(seq_df)} path={sequence_path} window_minutes={window_minutes} stride_minutes={stride_minutes}"
    )
    return seq_df
