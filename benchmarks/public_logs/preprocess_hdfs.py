from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_processing.drain_parser import DrainParser
from src.utils import Config, Logger

from benchmarks.public_logs.dataset_utils import extract_block_id, load_hdfs_labels, sequence_text_from_templates


def run_hdfs_preprocess(config: Config) -> pd.DataFrame:
    logger = Logger.get_logger("public_hdfs_preprocess", config)
    dataset_dir = Path(config.get("paths.data.raw")) / "hdfs"
    parsed_path = Path(config.get("benchmarks.public_logs.outputs.parsed_dir")) / "hdfs_parsed.csv"
    sequence_path = Path(config.get("benchmarks.public_logs.outputs.sequence_dir")) / "hdfs_sequences.csv"
    force_rebuild = bool(config.get("benchmarks.public_logs.force_rebuild", False))

    if sequence_path.exists() and not force_rebuild:
        logger.info(f"[HDFS] reuse existing sequence file: {sequence_path}")
        return pd.read_csv(sequence_path)

    if parsed_path.exists() and not force_rebuild:
        logger.info(f"[HDFS] reuse existing parsed file: {parsed_path}")
        parsed_df = pd.read_csv(parsed_path)
    else:
        parser = DrainParser(config)
        logger.info("[HDFS] parsing raw log into templates")
        parsed_df = parser.parse_log_file(dataset_dir / "HDFS.log", parsed_path)
    parsed_df["BlockId"] = parsed_df["raw_log"].map(extract_block_id)

    labels = load_hdfs_labels(dataset_dir)
    merged = parsed_df.merge(labels, on="BlockId", how="left")
    merged["label"] = merged["label"].fillna(0).astype(int)
    merged = merged.dropna(subset=["BlockId"]).copy()

    grouped = []
    for block_id, part in merged.groupby("BlockId", sort=False):
        part = part.sort_values("line_num").reset_index(drop=True)
        grouped.append(
            {
                "dataset": "HDFS",
                "sequence_id": str(block_id),
                "template_ids": " ".join(part["template_id"].astype(int).astype(str).tolist()),
                "templates": sequence_text_from_templates(part["template"].astype(str).tolist()),
                "raw_text": sequence_text_from_templates(part["raw_log"].astype(str).tolist()),
                "label": int((part["label"].astype(int) == 1).any()),
                "sequence_length": int(len(part)),
                "start_time": float(part["timestamp"].iloc[0]) if "timestamp" in part.columns and len(part) else None,
                "end_time": float(part["timestamp"].iloc[-1]) if "timestamp" in part.columns and len(part) else None,
            }
        )
    seq_df = pd.DataFrame(grouped)
    sequence_path.parent.mkdir(parents=True, exist_ok=True)
    seq_df.to_csv(sequence_path, index=False, encoding="utf-8-sig")
    logger.info(f"[HDFS] sequences saved: rows={len(seq_df)} path={sequence_path}")
    return seq_df
