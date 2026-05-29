from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.models.fusion_public import run_fusion_public_mean, run_fusion_public_weighted
from benchmarks.models.semantic_public import run_semantic_public
from benchmarks.models.statistical_public import run_statistical_public
from benchmarks.public_logs.preprocess_hdfs import run_hdfs_preprocess
from benchmarks.public_logs.split_utils import keep_only_normal_train, split_hdfs_by_block
from src.utils import Config, Logger, set_random_seed


def _pick_metric(df: pd.DataFrame, model: str) -> dict:
    row = df[df["Model"] == model].iloc[0]
    return row.to_dict()


def main(config_path: str = "benchmarks/configs/hdfs.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("run_hdfs_semantic_fusion_refresh", config)
    set_random_seed(int(config.get("experiment.random_seed", 42)))

    seq_df = run_hdfs_preprocess(config)
    split = split_hdfs_by_block(
        seq_df,
        float(config.get("benchmarks.public_logs.train_ratio", 0.6)),
        float(config.get("benchmarks.public_logs.val_ratio", 0.2)),
    )
    train_df = keep_only_normal_train(split.train)
    val_df = split.val.reset_index(drop=True)
    test_df = split.test.reset_index(drop=True)

    existing_path = Path(config.get("paths.outputs.reports")) / "hdfs" / "hdfs_metrics.csv"
    existing_df = pd.read_csv(existing_path)
    temporal_row = _pick_metric(existing_df, "temporal_public")
    logger.info(f"[HDFS-refresh] reuse temporal_public row from {existing_path}")

    sem_tpl_metrics, sem_tpl_art = run_semantic_public(train_df, val_df, test_df, config, mode="template")
    sem_hash_metrics, sem_hash_art = run_semantic_public(train_df, val_df, test_df, config, mode="hash")
    stat_metrics, stat_art = run_statistical_public(train_df, val_df, test_df, config)

    semantic_for_fusion = sem_hash_art
    semantic_name_for_fusion = "semantic_public_hash"
    if sem_tpl_art.status == "valid":
        semantic_for_fusion = sem_tpl_art
        semantic_name_for_fusion = "semantic_public_template"

    temporal_score_cache = Path(config.get("paths.outputs.reports")) / "hdfs" / "hdfs_split_audit.json"
    logger.info(f"[HDFS-refresh] semantic for fusion={semantic_name_for_fusion}")
    logger.info(f"[HDFS-refresh] split audit reference={temporal_score_cache}")

    raise RuntimeError("Incremental semantic+fusion refresh requires cached temporal val/test scores, which are not yet persisted. Run full HDFS once after adding score cache support.")


if __name__ == "__main__":
    main()
