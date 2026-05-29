from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


BLOCK_RE = re.compile(r"(blk_-?\d+)")


def extract_block_id(raw_log: str) -> str | None:
    match = BLOCK_RE.search(str(raw_log or ""))
    return match.group(1) if match else None


def load_hdfs_labels(dataset_dir: Path) -> pd.DataFrame:
    label_path = dataset_dir / "anomaly_label.csv"
    if not label_path.exists():
        raise FileNotFoundError(f"HDFS label file not found: {label_path}")
    df = pd.read_csv(label_path)
    if not {"BlockId", "Label"}.issubset(df.columns):
        raise ValueError("HDFS anomaly_label.csv missing BlockId/Label columns")
    out = df[["BlockId", "Label"]].copy()
    out["label"] = out["Label"].astype(str).str.lower().map({"anomaly": 1, "normal": 0})
    out = out.dropna(subset=["label"])
    out["label"] = out["label"].astype(int)
    return out[["BlockId", "label"]]


def load_bgl_line_labels(dataset_dir: Path) -> pd.DataFrame:
    log_path = dataset_dir / "BGL.log"
    if not log_path.exists():
        raise FileNotFoundError(f"BGL log file not found: {log_path}")
    rows = []
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            text = str(line).strip()
            if not text:
                continue
            token = text.split(maxsplit=1)[0]
            rows.append({"line_num": idx, "label": 0 if token == "-" else 1})
    return pd.DataFrame(rows)


def to_unix_seconds(series: pd.Series) -> np.ndarray:
    num = pd.to_numeric(series, errors="coerce")
    if float(num.notna().mean()) >= 0.8:
        values = num.astype(float).values
        median = np.nanmedian(values)
        if np.isfinite(median) and median > 1e12:
            values = values / 1000.0
        return values
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    if float(dt.notna().mean()) < 0.5:
        raise ValueError("timestamp column cannot be parsed to unix seconds")
    return (dt.astype("int64") / 1e9).astype(float).values


def choose_time_column(df: pd.DataFrame) -> str:
    candidates = ["timestamp", "time", "datetime", "event_time", "event_ts", "ts"]
    lower_map = {str(c).lower(): str(c) for c in df.columns}
    for key in candidates:
        if key in lower_map:
            return lower_map[key]
    raise ValueError("no timestamp-like column found in parsed dataframe")


def sequence_text_from_templates(templates: Iterable[str]) -> str:
    return " [SEQ] ".join(str(x or "") for x in templates)


def safe_auc_ready(y: np.ndarray) -> bool:
    y = np.asarray(y)
    return y.size > 0 and len(np.unique(y)) > 1
