"""
XGBoost fusion model.
Fuse statistical/temporal/semantic scores into final anomaly probability.
"""

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import xgboost as xgb
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import Config, Logger

try:
    import torch
except Exception:
    torch = None


class XGBoostFusion:
    """XGBoost meta learner."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.use_cross_features = bool(config.get("models.xgboost.use_cross_features", True))
        self.feature_names = ["Statistical", "Temporal", "Semantic"]

        gpu_enabled = bool(config.get("models.xgboost.use_gpu", True))
        cuda_ready = bool(torch is not None and torch.cuda.is_available())
        device = "cuda" if gpu_enabled and cuda_ready else "cpu"
        self.params = {
            "n_estimators": config.get("models.xgboost.n_estimators", 100),
            "max_depth": config.get("models.xgboost.max_depth", 6),
            "learning_rate": config.get("models.xgboost.learning_rate", 0.1),
            "subsample": config.get("models.xgboost.subsample", 0.8),
            "colsample_bytree": config.get("models.xgboost.colsample_bytree", 0.8),
            "reg_alpha": config.get("models.xgboost.reg_alpha", 0.0),
            "reg_lambda": config.get("models.xgboost.reg_lambda", 1.0),
            "min_child_weight": config.get("models.xgboost.min_child_weight", 1.0),
            "gamma": config.get("models.xgboost.gamma", 0.0),
            "objective": config.get("models.xgboost.objective", "binary:logistic"),
            "eval_metric": config.get("models.xgboost.eval_metric", "auc"),
            "random_state": 42,
            "tree_method": "hist",
            "device": device,
        }

        self.model = xgb.XGBClassifier(**self.params)
        self.logger.info("XGBoost fusion initialized")
        self.logger.info(f"params: {self.params}")

    def prepare_meta_features(self, statistical_scores, temporal_scores=None, semantic_scores=None):
        """Prepare fusion features from either 3-view arrays or an already assembled meta matrix."""
        if temporal_scores is None and semantic_scores is None:
            base = np.asarray(statistical_scores, dtype=float)
            if base.ndim == 1:
                base = base.reshape(1, -1)
        else:
            base = np.column_stack([
                np.asarray(statistical_scores, dtype=float),
                np.asarray(temporal_scores, dtype=float),
                np.asarray(semantic_scores, dtype=float),
            ])
        return self._expand_features(base)

    def _expand_features(self, x_meta: np.ndarray) -> np.ndarray:
        arr = np.asarray(x_meta, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != 3:
            if arr.shape[1] == 7:
                self.feature_names = [
                    "Statistical",
                    "Temporal",
                    "Semantic",
                    "StatDist",
                    "StatAuth",
                    "StatWeb",
                    "StatDns",
                ]
            elif arr.shape[1] == 6:
                self.feature_names = [
                    "Temporal",
                    "Semantic",
                    "StatDist",
                    "StatAuth",
                    "StatWeb",
                    "StatDns",
                ]
            else:
                self.feature_names = [f"Feature{i+1}" for i in range(arr.shape[1])]
            return arr
        if not self.use_cross_features:
            self.feature_names = ["Statistical", "Temporal", "Semantic"]
            return arr

        stat = arr[:, 0]
        temp = arr[:, 1]
        sem = arr[:, 2]
        cross = np.column_stack(
            [
                stat * temp,
                stat * sem,
                temp * sem,
                np.maximum(np.maximum(stat, temp), sem),
                stat - temp,
                temp - sem,
                sem - stat,
            ]
        )
        self.feature_names = [
            "Statistical",
            "Temporal",
            "Semantic",
            "StatXTemp",
            "StatXSem",
            "TempXSem",
            "MaxScore",
            "StatMinusTemp",
            "TempMinusSem",
            "SemMinusStat",
        ]
        return np.column_stack([arr, cross])

    @staticmethod
    def _calc_scale_pos_weight(y_train: np.ndarray) -> float:
        y = np.asarray(y_train).astype(int)
        pos = float((y == 1).sum())
        neg = float((y == 0).sum())
        if pos <= 0.0:
            return 1.0
        return max(1.0, neg / pos)

    def train(self, X_meta_train, y_train, X_meta_val=None, y_val=None):
        X_meta_train = self._expand_features(X_meta_train)
        if X_meta_val is not None:
            X_meta_val = self._expand_features(X_meta_val)

        self.logger.info(f"train xgboost, shape={X_meta_train.shape}")
        spw = self._calc_scale_pos_weight(y_train)
        self.model.set_params(scale_pos_weight=spw)
        self.logger.info(f"scale_pos_weight={spw:.4f}")

        eval_set = []
        if X_meta_val is not None and y_val is not None:
            eval_set = [(X_meta_val, y_val)]

        try:
            self.model.fit(X_meta_train, y_train, eval_set=eval_set, verbose=False)
        except Exception as exc:
            if self.params.get("device") == "cuda":
                self.logger.warning(f"xgboost cuda train failed, fallback to cpu: {exc}")
                self.params["device"] = "cpu"
                self.model = xgb.XGBClassifier(**self.params)
                self.model.set_params(scale_pos_weight=spw)
                self.model.fit(X_meta_train, y_train, eval_set=eval_set, verbose=False)
            else:
                raise
        self.logger.info("xgboost train finished")

        importance = self.model.feature_importances_
        self.logger.info("feature importance:")
        for name, imp in zip(self.feature_names, importance):
            self.logger.info(f"  {name}: {imp:.4f}")

    def predict(self, X_meta):
        self._force_cpu_inference()
        x = self._align_model_features(self._expand_features(X_meta))
        return self.model.predict(x)

    def predict_proba(self, X_meta):
        self._force_cpu_inference()
        x = self._align_model_features(self._expand_features(X_meta))
        return self.model.predict_proba(x)[:, 1]

    def _force_cpu_inference(self) -> None:
        """Avoid CUDA-backed boosters crashing Streamlit on Windows."""
        try:
            self.model.set_params(device="cpu")
        except Exception:
            pass
        try:
            self.model.get_booster().set_param({"device": "cpu"})
        except Exception:
            pass

    def _align_model_features(self, x_meta: np.ndarray) -> np.ndarray:
        """Keep backward compatibility with old saved models."""
        expected = None
        if hasattr(self.model, "n_features_in_"):
            expected = int(getattr(self.model, "n_features_in_"))
        if expected is None:
            try:
                expected = int(self.model.get_booster().num_features())
            except Exception:
                expected = None
        if expected is None:
            return x_meta
        if x_meta.shape[1] == expected:
            return x_meta
        if x_meta.shape[1] > expected:
            return x_meta[:, :expected]
        pad = np.zeros((x_meta.shape[0], expected - x_meta.shape[1]), dtype=x_meta.dtype)
        return np.hstack([x_meta, pad])

    def evaluate(self, X_meta, y_true):
        self.logger.info("evaluate xgboost fusion")
        y_pred = self.predict(X_meta)
        y_prob = self.predict_proba(X_meta)

        metrics = {
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
        }
        if len(np.unique(y_true)) > 1:
            metrics["auc"] = roc_auc_score(y_true, y_prob)
        else:
            metrics["auc"] = 0.0

        self.logger.info("fusion eval metrics:")
        for metric, value in metrics.items():
            self.logger.info(f"  {metric}: {value:.4f}")
        return metrics

    def save_model(self, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "use_cross_features": self.use_cross_features,
        }
        joblib.dump(payload, save_path)
        self.logger.info(f"model saved: {save_path}")

    def load_model(self, load_path: Path):
        obj = joblib.load(load_path)
        if isinstance(obj, dict) and "model" in obj:
            self.model = obj["model"]
            self.use_cross_features = bool(obj.get("use_cross_features", self.use_cross_features))
        else:
            # backward compatibility with old plain model file
            self.model = obj
        self._force_cpu_inference()
        self.logger.info(f"model loaded: {load_path}")


if __name__ == "__main__":
    cfg = Config()
    np.random.seed(42)
    n = 1000
    y = np.hstack([np.zeros(900), np.ones(100)])
    idx = np.random.permutation(len(y))

    stat = np.random.rand(n)[idx]
    temp = np.random.rand(n)[idx]
    sem = np.random.rand(n)[idx]
    y = y[idx]

    fusion = XGBoostFusion(cfg)
    X = fusion.prepare_meta_features(stat, temp, sem)
    split = int(0.8 * len(X))
    fusion.train(X[:split], y[:split], X[split:], y[split:])
    print(fusion.evaluate(X[split:], y[split:]))
