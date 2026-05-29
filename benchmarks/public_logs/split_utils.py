from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SplitBundle:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def split_hdfs_by_block(df: pd.DataFrame, train_ratio: float, val_ratio: float) -> SplitBundle:
    blocks = df[["sequence_id", "label"]].drop_duplicates().reset_index(drop=True)
    normal_blocks = blocks[blocks["label"] == 0]["sequence_id"].tolist()
    abnormal_blocks = blocks[blocks["label"] == 1]["sequence_id"].tolist()

    n_train = max(1, int(len(normal_blocks) * train_ratio)) if normal_blocks else 0
    remain_normal = max(0, len(normal_blocks) - n_train)
    n_val_normal = int(remain_normal * (val_ratio / max(1e-8, 1.0 - train_ratio))) if remain_normal else 0

    train_ids = set(normal_blocks[:n_train])
    val_normal_ids = set(normal_blocks[n_train:n_train + n_val_normal])
    test_normal_ids = set(normal_blocks[n_train + n_val_normal:])

    n_val_abn = int(len(abnormal_blocks) * (val_ratio / max(1e-8, 1.0 - train_ratio))) if abnormal_blocks else 0
    val_abn_ids = set(abnormal_blocks[:n_val_abn])
    test_abn_ids = set(abnormal_blocks[n_val_abn:])

    val_ids = val_normal_ids | val_abn_ids
    test_ids = test_normal_ids | test_abn_ids

    train = df[df["sequence_id"].isin(train_ids)].copy()
    val = df[df["sequence_id"].isin(val_ids)].copy()
    test = df[df["sequence_id"].isin(test_ids)].copy()
    return SplitBundle(train=train, val=val, test=test)


def split_bgl_ordered(df: pd.DataFrame, train_ratio: float, val_ratio: float) -> SplitBundle:
    ordered = df.sort_values("window_start", ascending=True).reset_index(drop=True)
    total = len(ordered)
    train_end = int(total * train_ratio)
    val_end = int(total * (train_ratio + val_ratio))
    train = ordered.iloc[:train_end].copy()
    val = ordered.iloc[train_end:val_end].copy()
    test = ordered.iloc[val_end:].copy()
    return SplitBundle(train=train, val=val, test=test)


def keep_only_normal_train(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["label"] == 0].copy().reset_index(drop=True)


def assert_no_overlap(train_ids, val_ids, test_ids):
    train_ids = set(train_ids)
    val_ids = set(val_ids)
    test_ids = set(test_ids)
    if train_ids & val_ids or train_ids & test_ids or val_ids & test_ids:
        raise ValueError("split overlap detected")


def summarize_split(df: pd.DataFrame) -> dict:
    labels = df["label"].astype(int).values if len(df) else np.array([], dtype=int)
    return {
        "samples": int(len(df)),
        "anomaly_ratio": float(labels.mean()) if labels.size else 0.0,
        "anomalies": int(labels.sum()) if labels.size else 0,
        "normals": int((labels == 0).sum()) if labels.size else 0,
    }
