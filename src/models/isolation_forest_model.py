from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from src.utils import Config, Logger


class IsolationForestModel:
    """IsolationForest wrapper with train-calibrated anomaly probability output."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.model = IsolationForest(
            n_estimators=int(config.get("models.isolation_forest.n_estimators", 100)),
            max_samples=config.get("models.isolation_forest.max_samples", 256),
            contamination=float(config.get("models.isolation_forest.contamination", 0.1)),
            random_state=int(config.get("models.isolation_forest.random_state", 42)),
            n_jobs=-1,
        )
        self.score_calibration = {
            "score_min": 0.0,
            "score_max": 1.0,
        }
        self.relative_calibration = {
            "median": None,
            "iqr": None,
            "score_min": 0.0,
            "score_max": 1.0,
        }

    def fit(self, x: np.ndarray):
        arr = np.asarray(x, dtype=float)
        self.logger.info(f"train isolation forest, shape={arr.shape}")
        self.model.fit(arr)
        aligned = self._align_features(arr)
        train_score = -np.asarray(self.model.decision_function(aligned), dtype=float)
        if train_score.size:
            lo = float(np.min(train_score))
            hi = float(np.max(train_score))
            if hi - lo <= 1e-12:
                hi = lo + 1.0
            self.score_calibration = {
                "score_min": lo,
                "score_max": hi,
            }
            self.logger.info(
                "isolation forest calibration prepared on training scores: "
                f"min={self.score_calibration['score_min']:.6f}, "
                f"max={self.score_calibration['score_max']:.6f}"
            )
        self._fit_relative_calibration(aligned)
        return self

    def decision_function(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.decision_function(self._align_features(x)), dtype=float)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        score = -self.decision_function(self._align_features(x))
        if score.size == 0:
            return score
        lo = float(self.score_calibration.get("score_min", 0.0))
        hi = float(self.score_calibration.get("score_max", 1.0))
        if hi - lo <= 1e-12:
            return np.zeros_like(score, dtype=float)
        return np.clip((score - lo) / (hi - lo + 1e-8), 0.0, 1.0)

    def predict_relative_anomaly(self, x: np.ndarray) -> np.ndarray:
        arr = self._align_features(x)
        median = self.relative_calibration.get("median")
        iqr = self.relative_calibration.get("iqr")
        if median is None or iqr is None:
            return np.zeros((arr.shape[0],), dtype=float)
        median_arr = np.asarray(median, dtype=float)
        iqr_arr = np.asarray(iqr, dtype=float)
        robust_z = np.abs(arr - median_arr) / np.maximum(iqr_arr, 1e-6)
        top_width = max(1, min(8, robust_z.shape[1]))
        topk = np.partition(robust_z, -top_width, axis=1)[:, -top_width:]
        raw_score = np.mean(topk, axis=1)
        lo = float(self.relative_calibration.get("score_min", 0.0))
        hi = float(self.relative_calibration.get("score_max", 1.0))
        if hi - lo <= 1e-12:
            return np.zeros_like(raw_score, dtype=float)
        return np.clip((raw_score - lo) / (hi - lo + 1e-8), 0.0, 1.0)

    def _fit_relative_calibration(self, arr: np.ndarray):
        arr = np.asarray(arr, dtype=float)
        if arr.ndim != 2 or arr.size == 0:
            self.relative_calibration = {"median": None, "iqr": None, "score_min": 0.0, "score_max": 1.0}
            return
        median = np.median(arr, axis=0)
        q1 = np.quantile(arr, 0.25, axis=0)
        q3 = np.quantile(arr, 0.75, axis=0)
        iqr = np.maximum(q3 - q1, 1e-6)
        robust_z = np.abs(arr - median) / iqr
        top_width = max(1, min(8, robust_z.shape[1]))
        topk = np.partition(robust_z, -top_width, axis=1)[:, -top_width:]
        raw_score = np.mean(topk, axis=1)
        lo = float(np.min(raw_score)) if raw_score.size else 0.0
        hi = float(np.max(raw_score)) if raw_score.size else 1.0
        if hi - lo <= 1e-12:
            hi = lo + 1.0
        self.relative_calibration = {
            "median": median.tolist(),
            "iqr": iqr.tolist(),
            "score_min": lo,
            "score_max": hi,
        }

    def save_model(self, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "score_calibration": self.score_calibration,
            "relative_calibration": self.relative_calibration,
        }
        joblib.dump(payload, save_path)
        self.logger.info(f"saved isolation forest: {save_path}")

    def load_model(self, load_path: Path):
        payload = joblib.load(load_path)
        if isinstance(payload, dict) and "model" in payload:
            self.model = payload["model"]
            calibration = payload.get("score_calibration") or {}
            self.score_calibration = {
                "score_min": float(calibration.get("score_min", 0.0)),
                "score_max": float(calibration.get("score_max", 1.0)),
            }
            rel = payload.get("relative_calibration") or {}
            self.relative_calibration = {
                "median": rel.get("median"),
                "iqr": rel.get("iqr"),
                "score_min": float(rel.get("score_min", 0.0)),
                "score_max": float(rel.get("score_max", 1.0)),
            }
        else:
            self.model = payload
            self.score_calibration = {
                "score_min": 0.0,
                "score_max": 1.0,
            }
            self.relative_calibration = {
                "median": None,
                "iqr": None,
                "score_min": 0.0,
                "score_max": 1.0,
            }
            self.logger.warning(
                "loaded legacy isolation forest without calibration; "
                "default score scale will be used until retrained."
            )
        self.logger.info(f"loaded isolation forest: {load_path}")
        return self

    def _align_features(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        expected = int(getattr(self.model, "n_features_in_", arr.shape[1] if arr.ndim == 2 else 1))
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] == expected:
            return arr
        if arr.shape[1] > expected:
            return arr[:, :expected]
        pad = np.zeros((arr.shape[0], expected - arr.shape[1]), dtype=arr.dtype)
        return np.hstack([arr, pad])
