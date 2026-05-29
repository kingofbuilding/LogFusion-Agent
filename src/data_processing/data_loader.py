"""
Data loading and preprocessing for parsed log sequences.
"""

from __future__ import annotations

import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.fusion.semantic_text import build_sequence_raw_texts_from_logs, build_sequence_semantic_texts_from_logs

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import Config, Logger, set_random_seed


class DataLoader:
    """Load parsed logs, labels, and build template-id sequences."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.dataset_name = str(config.get("data.dataset", "hdfs")).lower()
        self.sequence_length = int(config.get("data.sequence_length", 50))
        set_random_seed(config.get("experiment.random_seed", 42))

    def _get_source_filter_profile(self) -> Optional[dict]:
        profile_name = str(self.config.get("data.source_filter_profile", "") or "").strip()
        if not profile_name:
            return None
        profile = self.config.get(f"data.source_filter_profiles.{profile_name}")
        if not isinstance(profile, dict):
            self.logger.warning(f"source filter profile not found: {profile_name}")
            return None
        return profile

    def _apply_source_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        profile = self._get_source_filter_profile()
        if profile is None:
            return df
        if "source_file" not in df.columns:
            self.logger.warning("source filter requested but source_file column is missing")
            return df

        include_patterns = [str(x) for x in profile.get("include_patterns", []) if str(x).strip()]
        exclude_patterns = [str(x) for x in profile.get("exclude_patterns", []) if str(x).strip()]
        source_series = df["source_file"].astype(str)

        if include_patterns:
            include_mask = np.zeros(len(df), dtype=bool)
            for pattern in include_patterns:
                include_mask |= source_series.str.contains(pattern, regex=True, na=False)
        else:
            include_mask = np.ones(len(df), dtype=bool)

        if exclude_patterns:
            exclude_mask = np.zeros(len(df), dtype=bool)
            for pattern in exclude_patterns:
                exclude_mask |= source_series.str.contains(pattern, regex=True, na=False)
        else:
            exclude_mask = np.zeros(len(df), dtype=bool)

        filtered = df[include_mask & ~exclude_mask].copy()
        self.logger.info(
            "applied source filter profile '%s': %s -> %s rows, matched_sources=%s" % (
                str(self.config.get("data.source_filter_profile", "")),
                len(df),
                len(filtered),
                int(filtered["source_file"].astype(str).nunique()) if not filtered.empty else 0,
            )
        )
        if filtered.empty:
            self.logger.warning("source filter removed all rows; fallback to unfiltered parsed data")
            return df
        return filtered

    def load_parsed_data(self) -> pd.DataFrame:
        processed_dir = Path(self.config.get("paths.data.processed"))
        file_path = processed_dir / self.dataset_name / f"{self.dataset_name}_parsed.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"parsed file not found: {file_path}")
        df = pd.read_csv(file_path)
        self.logger.info(f"loaded parsed data: {file_path}, shape={df.shape}")
        df = self._apply_source_filter(df)
        return df

    def _extract_block_id(self, raw_log: str):
        if not isinstance(raw_log, str):
            return None
        match = re.search(r"(blk_-?\d+)", raw_log)
        return match.group(1) if match else None

    @staticmethod
    def _find_time_column(df: pd.DataFrame) -> Optional[str]:
        candidates = ["timestamp", "time", "datetime", "event_time", "event_ts", "ts"]
        cols = {str(c).lower(): str(c) for c in df.columns}
        for key in candidates:
            if key in cols:
                return cols[key]
        return None

    @staticmethod
    def _to_unix_seconds(series: pd.Series) -> Optional[np.ndarray]:
        if series is None or len(series) == 0:
            return None

        num = pd.to_numeric(series, errors="coerce")
        valid_ratio = float(num.notna().mean()) if len(num) else 0.0
        if valid_ratio >= 0.8:
            vals = num.astype(float).values
            med = np.nanmedian(vals)
            if np.isfinite(med) and med > 1e12:
                vals = vals / 1000.0
            return vals

        dt = pd.to_datetime(series, errors="coerce", utc=True)
        if float(dt.notna().mean()) < 0.5:
            return None
        return (dt.astype("int64") / 1e9).astype(float).values

    def load_labels(self):
        raw_dir = Path(self.config.get("paths.data.raw")) / self.dataset_name
        candidates = [raw_dir / "labels.csv", raw_dir / "anomaly_label.csv"]
        label_file = next((p for p in candidates if p.exists()), None)

        if label_file is None:
            if (raw_dir / "labels").exists():
                return self._load_ait_lds_labels(raw_dir)
            if self.dataset_name == "bgl":
                return self._load_bgl_labels(raw_dir)
            if self.dataset_name == "openstack":
                return self._load_openstack_labels()
            self.logger.warning(f"label file not found: {raw_dir}")
            return None

        labels = pd.read_csv(label_file)
        self.logger.info(f"loaded labels: {label_file}, shape={labels.shape}")

        if {"BlockId", "Label"}.issubset(labels.columns):
            out = labels[["BlockId", "Label"]].copy()
            out["label"] = out["Label"].astype(str).str.lower().map({"anomaly": 1, "normal": 0})
            out = out.dropna(subset=["label"])
            out["label"] = out["label"].astype(int)
            return out[["BlockId", "label"]]

        if {"line_num", "label"}.issubset(labels.columns):
            out = labels[["line_num", "label"]].copy()
            out["label"] = out["label"].astype(int)
            return out

        self.logger.warning("unsupported label format, skip labels")
        return None

    def _load_ait_lds_labels(self, raw_dir: Path):
        labels_root = raw_dir / "labels"
        label_files = sorted(labels_root.rglob("*.log"))
        if not label_files:
            self.logger.warning(f"ait-lds labels not found: {labels_root}")
            return None

        rows = []
        for label_file in label_files:
            rel = label_file.relative_to(labels_root)
            source_file = str(Path("gather") / rel).replace("\\", "/")
            with open(label_file, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    raw = str(raw).strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except Exception:
                        continue
                    line_num = obj.get("line")
                    if line_num is None:
                        continue
                    labels = obj.get("labels") or []
                    rows.append(
                        {
                            "source_file": source_file,
                            "source_line_num": int(line_num),
                            "label": 1 if len(labels) else 0,
                            "ait_labels": "|".join(sorted({str(x) for x in labels if str(x).strip()})),
                        }
                    )

        out = pd.DataFrame(rows)
        if out.empty:
            self.logger.warning("ait-lds labels are empty")
            return None
        self.logger.info(f"loaded AIT-LDS labels, shape={out.shape}")
        return out

    def _load_bgl_labels(self, raw_dir: Path):
        bgl_log = raw_dir / "BGL.log"
        if not bgl_log.exists():
            self.logger.warning(f"bgl label source not found: {raw_dir}")
            return None

        labels = []
        with open(bgl_log, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                text = str(line).strip()
                if not text:
                    continue
                first_token = text.split(maxsplit=1)[0]
                labels.append({"line_num": idx, "label": 0 if first_token == "-" else 1})

        out = pd.DataFrame(labels)
        self.logger.info(f"generated BGL line labels, shape={out.shape}")
        return out

    def _load_openstack_labels(self):
        parsed_path = (
            Path(self.config.get("paths.data.processed"))
            / self.dataset_name
            / f"{self.dataset_name}_parsed.csv"
        )
        if not parsed_path.exists():
            self.logger.warning("OpenStack parsed file missing, run parse first")
            return None

        parsed_df = pd.read_csv(parsed_path, usecols=["line_num", "source_file"])
        source_series = parsed_df["source_file"].astype(str).str.lower()
        out = pd.DataFrame(
            {
                "line_num": parsed_df["line_num"].astype(int),
                "label": source_series.str.contains("abnormal").astype(int),
            }
        )
        self.logger.info(f"generated OpenStack weak labels from filenames, shape={out.shape}")
        return out

    def create_sequences(
        self,
        df: pd.DataFrame,
        label_col: str = None,
        max_sequences: Optional[int] = None,
        start_indices: Optional[np.ndarray] = None,
        return_indices: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], np.ndarray, np.ndarray]:
        template_ids = df["template_id"].astype(int).values
        time_col = self._find_time_column(df)
        seq_times = []
        time_values = None
        if time_col:
            time_values = self._to_unix_seconds(df[time_col])
            if time_values is None:
                self.logger.warning(f"time column exists but cannot parse: {time_col}")

        if max_sequences is None:
            max_sequences = int(self.config.get("experiment.max_sequences", 30000))
        total_sequences = max(0, len(template_ids) - self.sequence_length + 1)
        if start_indices is None:
            selected_idx = self._select_sequence_indices(df, total_sequences, label_col, int(max_sequences))
        else:
            selected_idx = np.asarray(start_indices, dtype=np.int64)

        sequences = []
        labels = []
        for i in selected_idx:
            sequences.append(template_ids[i : i + self.sequence_length])
            if label_col and label_col in df.columns:
                labels.append(int(df.iloc[i + self.sequence_length - 1][label_col]))
            if time_values is not None:
                seq_times.append(time_values[i : i + self.sequence_length])

        semantic_source_col = "raw_log" if "raw_log" in df.columns else "template"
        raw_source_texts = df[semantic_source_col].astype(str).tolist()
        semantic_texts = build_sequence_semantic_texts_from_logs(
            raw_source_texts,
            sequence_length=self.sequence_length,
            start_indices=selected_idx,
            max_steps=int(self.config.get("features.semantic.sequence_context_window", 6)),
            min_tokens=int(self.config.get("features.semantic.distillation.min_tokens", 3)),
        )
        raw_texts = build_sequence_raw_texts_from_logs(
            raw_source_texts,
            sequence_length=self.sequence_length,
            start_indices=selected_idx,
            max_steps=int(self.config.get("features.statistical_behavior_context_window", 12)),
        )
        X = np.array(sequences, dtype=np.int64)
        y = np.array(labels, dtype=np.int64) if labels else None
        T = np.array(seq_times, dtype=float) if seq_times else None
        S = np.asarray(semantic_texts, dtype=object)
        R = np.asarray(raw_texts, dtype=object)
        self.logger.info(
            f"built sequences: {X.shape}, labels={None if y is None else y.shape}, "
            f"time_matrix={None if T is None else T.shape}, semantic_texts={S.shape}, raw_texts={R.shape}"
        )
        if return_indices:
            return X, y, T, S, R, selected_idx
        return X, y, T, S, R

    def _select_sequence_indices(
        self,
        df: pd.DataFrame,
        total_sequences: int,
        label_col: str,
        max_sequences: int,
    ) -> np.ndarray:
        if total_sequences <= 0:
            return np.array([], dtype=np.int64)
        if total_sequences <= max_sequences:
            return np.arange(total_sequences, dtype=np.int64)

        seed = int(self.config.get("experiment.random_seed", 42))
        rng = np.random.default_rng(seed)

        if label_col and label_col in df.columns:
            end_labels = df[label_col].astype(int).values[self.sequence_length - 1 :]
            pos_idx = np.flatnonzero(end_labels == 1)
            neg_idx = np.flatnonzero(end_labels == 0)
            if len(pos_idx) and len(neg_idx):
                pos_target = int(round(max_sequences * (len(pos_idx) / total_sequences)))
                pos_target = max(1, min(len(pos_idx), pos_target))
                neg_target = max_sequences - pos_target
                neg_target = min(len(neg_idx), neg_target)
                remaining = max_sequences - pos_target - neg_target
                if remaining > 0:
                    extra_neg = min(len(neg_idx) - neg_target, remaining)
                    neg_target += max(0, extra_neg)
                    remaining = max_sequences - pos_target - neg_target
                    if remaining > 0:
                        pos_target += min(len(pos_idx) - pos_target, remaining)

                picked = np.concatenate(
                    [
                        rng.choice(pos_idx, size=pos_target, replace=False),
                        rng.choice(neg_idx, size=neg_target, replace=False),
                    ]
                )
                return np.sort(picked.astype(np.int64))

        return np.linspace(0, total_sequences - 1, num=max_sequences, dtype=np.int64)

    def split_train_test(
        self,
        X: np.ndarray,
        y: np.ndarray = None,
        train_ratio: float = None,
        T: Optional[np.ndarray] = None,
        S: Optional[np.ndarray] = None,
        R: Optional[np.ndarray] = None,
        start_indices: Optional[np.ndarray] = None,
        split_mode: Optional[str] = None,
    ) -> Tuple:
        if train_ratio is None:
            train_ratio = float(self.config.get("data.train_ratio", 0.8))
        if split_mode is None:
            split_mode = str(self.config.get("data.split_mode", "random_window_split") or "random_window_split")

        idx = np.arange(len(X), dtype=np.int64)
        if split_mode == "blocked_gap_split":
            if len(idx) == 0:
                idx_train = idx_test = idx
                y_train = y_test = y
            else:
                starts = np.asarray(start_indices if start_indices is not None else idx, dtype=np.int64)
                split_pos = max(1, min(len(idx) - 1, int(len(idx) * train_ratio)))
                train_end_pos = split_pos - 1
                test_start_pos = split_pos
                while test_start_pos < len(starts) and (starts[test_start_pos] - starts[train_end_pos]) < self.sequence_length:
                    test_start_pos += 1
                idx_train = idx[: train_end_pos + 1]
                idx_test = idx[test_start_pos:]
                y_train = y[idx_train] if y is not None else None
                y_test = y[idx_test] if y is not None else None
                self.logger.info(
                    f"blocked gap split: train={len(idx_train)} test={len(idx_test)} gap_start={int(starts[test_start_pos]) if len(idx_test) else 'none'}"
                )
        elif split_mode == "ordered_window_split":
            split_idx = int(len(idx) * train_ratio)
            idx_train, idx_test = idx[:split_idx], idx[split_idx:]
            y_train = y[idx_train] if y is not None else None
            y_test = y[idx_test] if y is not None else None
        else:
            if y is not None:
                stratify = y if len(np.unique(y)) > 1 else None
                idx_train, idx_test, y_train, y_test = train_test_split(
                    idx, y, train_size=train_ratio, random_state=42, stratify=stratify
                )
            else:
                split_idx = int(len(idx) * train_ratio)
                idx_train, idx_test = idx[:split_idx], idx[split_idx:]
                y_train, y_test = None, None

        X_train, X_test = X[idx_train], X[idx_test]
        T_train = T[idx_train] if T is not None else None
        T_test = T[idx_test] if T is not None else None
        S_train = S[idx_train] if S is not None else None
        S_test = S[idx_test] if S is not None else None
        R_train = R[idx_train] if R is not None else None
        R_test = R[idx_test] if R is not None else None
        self.logger.info(f"train/test split [{split_mode}]: {len(X_train)} / {len(X_test)}")
        return X_train, X_test, y_train, y_test, T_train, T_test, S_train, S_test, R_train, R_test

    def _build_split_bundle(
        self,
        split_df: pd.DataFrame,
        label_col: Optional[str],
        max_sequences: int,
        split_name: str,
        row_offset: int,
    ) -> Dict[str, object]:
        X, y, T, S, R, start_idx = self.create_sequences(
            split_df,
            label_col,
            max_sequences=max_sequences,
            return_indices=True,
        )
        start_idx = np.asarray(start_idx, dtype=np.int64)
        global_start_idx = start_idx + int(row_offset)
        return {
            "X": X,
            "y": y,
            "T": T,
            "S": S,
            "R": R,
            "start_indices": start_idx,
            "global_start_indices": global_start_idx,
            "rows": int(len(split_df)),
            "sequences": int(len(X)),
            "positive_ratio": float(np.mean(y)) if y is not None and len(y) else None,
            "split_name": split_name,
            "row_offset": int(row_offset),
        }

    def _prepare_ordered_pre_split(self, df: pd.DataFrame, label_col: Optional[str]) -> Dict[str, object]:
        train_ratio = float(self.config.get("data.train_ratio", 0.8))
        val_ratio = float(self.config.get("data.val_ratio", 0.1))
        train_ratio = min(max(train_ratio, 0.1), 0.95)
        val_ratio = min(max(val_ratio, 0.0), 0.4)
        if train_ratio + val_ratio >= 0.98:
            val_ratio = min(val_ratio, max(0.0, 0.98 - train_ratio))

        total_rows = int(len(df))
        train_end = int(total_rows * train_ratio)
        val_end = int(total_rows * (train_ratio + val_ratio))
        train_end = max(0, min(total_rows, train_end))
        val_end = max(train_end, min(total_rows, val_end))

        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        test_df = df.iloc[val_end:].copy()

        max_default = int(self.config.get("experiment.max_sequences", 30000))
        max_train = int(self.config.get("experiment.max_train_samples", max_default))
        max_val = int(self.config.get("experiment.max_val_samples", self.config.get("experiment.max_test_samples", max_default)))
        max_test = int(self.config.get("experiment.max_test_samples", max_default))

        train_bundle = self._build_split_bundle(train_df, label_col, max_train, "train", 0)
        val_bundle = self._build_split_bundle(val_df, label_col, max_val, "val", train_end)
        test_bundle = self._build_split_bundle(test_df, label_col, max_test, "test", val_end)

        self.logger.info(
            "prepared ordered_pre_split from raw rows: "
            f"train_rows={train_bundle['rows']} val_rows={val_bundle['rows']} test_rows={test_bundle['rows']} "
            f"train_seq={train_bundle['sequences']} val_seq={val_bundle['sequences']} test_seq={test_bundle['sequences']}"
        )

        return {
            "train": train_bundle,
            "val": val_bundle,
            "test": test_bundle,
            "metadata": {
                "split_mode": "ordered_pre_split",
                "train_ratio": float(train_ratio),
                "val_ratio": float(val_ratio),
                "test_ratio": float(max(0.0, 1.0 - train_ratio - val_ratio)),
                "train_row_range": [0, train_end],
                "val_row_range": [train_end, val_end],
                "test_row_range": [val_end, total_rows],
                "total_rows": total_rows,
                "sequence_length": int(self.sequence_length),
            },
        }

    def get_template_mapping(self, df: pd.DataFrame) -> dict:
        return df.groupby("template_id")["template"].first().to_dict()

    def prepare_data(self) -> dict:
        df = self.load_parsed_data()
        labels_df = self.load_labels()

        label_col = None
        if labels_df is not None:
            if {"line_num", "label"}.issubset(labels_df.columns):
                df = df.merge(labels_df, on="line_num", how="left")
                df["label"] = df["label"].fillna(0).astype(int)
                label_col = "label"
            elif {"source_file", "source_line_num", "label"}.issubset(labels_df.columns):
                if "source_line_num" not in df.columns:
                    df["source_line_num"] = df["line_num"]
                df = df.merge(labels_df, on=["source_file", "source_line_num"], how="left")
                df["label"] = df["label"].fillna(0).astype(int)
                label_col = "label"
            elif {"BlockId", "label"}.issubset(labels_df.columns):
                if "raw_log" in df.columns:
                    df["BlockId"] = df["raw_log"].apply(self._extract_block_id)
                    df = df.merge(labels_df, on="BlockId", how="left")
                    df["label"] = df["label"].fillna(0).astype(int)
                    label_col = "label"

        split_mode = str(self.config.get("data.split_mode", "random_window_split") or "random_window_split")
        split_metadata = {
            "split_mode": split_mode,
            "sequence_length": int(self.sequence_length),
            "total_rows": int(len(df)),
        }
        train_start_idx = val_start_idx = test_start_idx = None
        if split_mode in {"ordered_pre_split", "truncated_ordered_pre_split"}:
            if split_mode == "ordered_pre_split":
                ordered = self._prepare_ordered_pre_split(df, label_col)
            else:
                from src.data_processing.truncated_protocol import build_truncated_ordered_splits
                ordered = build_truncated_ordered_splits(self.config)
            train_bundle = ordered["train"]
            val_bundle = ordered["val"]
            test_bundle = ordered["test"]
            split_metadata.update(ordered["metadata"])

            X_train, y_train, T_train, S_train, R_train = (
                train_bundle["X"],
                train_bundle["y"],
                train_bundle["T"],
                train_bundle["S"],
                train_bundle["R"],
            )
            X_val, y_val, T_val, S_val, R_val = (
                val_bundle["X"],
                val_bundle["y"],
                val_bundle["T"],
                val_bundle["S"],
                val_bundle["R"],
            )
            X_test, y_test, T_test, S_test, R_test = (
                test_bundle["X"],
                test_bundle["y"],
                test_bundle["T"],
                test_bundle["S"],
                test_bundle["R"],
            )
            train_start_idx = train_bundle["global_start_indices"]
            val_start_idx = val_bundle["global_start_indices"]
            test_start_idx = test_bundle["global_start_indices"]
        else:
            X, y, T, S, R, start_idx = self.create_sequences(df, label_col, return_indices=True)
            X_train, X_test, y_train, y_test, T_train, T_test, S_train, S_test, R_train, R_test = self.split_train_test(
                X, y, T=T, S=S, R=R, start_indices=start_idx, split_mode=split_mode
            )
            X_val = np.empty((0, self.sequence_length), dtype=np.int64)
            y_val = np.empty((0,), dtype=np.int64) if y_train is not None else None
            T_val = np.empty((0, self.sequence_length), dtype=float) if T_train is not None else None
            S_val = np.empty((0,), dtype=object)
            R_val = np.empty((0,), dtype=object)
            train_start_idx = np.asarray(start_idx[: len(X_train)], dtype=np.int64)
            val_start_idx = np.empty((0,), dtype=np.int64)
            test_start_idx = np.asarray(start_idx[-len(X_test):], dtype=np.int64) if len(X_test) else np.empty((0,), dtype=np.int64)
        template_mapping = self.get_template_mapping(df)

        return {
            "X_train": X_train,
            "X_val": X_val,
            "X_test": X_test,
            "y_train": y_train,
            "y_val": y_val,
            "y_test": y_test,
            "T_train": T_train,
            "T_val": T_val,
            "T_test": T_test,
            "S_train": S_train,
            "S_val": S_val,
            "S_test": S_test,
            "R_train": R_train,
            "R_val": R_val,
            "R_test": R_test,
            "start_idx_train": train_start_idx,
            "start_idx_val": val_start_idx,
            "start_idx_test": test_start_idx,
            "split_metadata": split_metadata,
            "template_mapping": template_mapping,
            "df": df,
        }


def main():
    config = Config()
    loader = DataLoader(config)
    data = loader.prepare_data()
    print("DataLoader run success")
    print(f"X_train: {data['X_train'].shape}")
    print(f"X_test: {data['X_test'].shape}")
    print(f"has labels: {data['y_train'] is not None}")


if __name__ == "__main__":
    main()
