"""
简易集成推理模块：
读取基础分数并调用 XGBoost 融合模型输出最终风险分数。
"""

import os
import sys
from pathlib import Path

import numpy as np
from joblib import load

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.fusion.xgboost_fusion import XGBoostFusion
from src.utils import Config, Logger


class EnsemblePredictor:
    """融合推理器。"""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.fusion = XGBoostFusion(config)

        model_path = Path(config.get("paths.models.xgboost")) / "xgboost_fusion.joblib"
        if model_path.exists():
            self.fusion.load_model(model_path)
        else:
            raise FileNotFoundError(f"融合模型不存在: {model_path}")

    def predict(self, statistical_scores, temporal_scores=None, semantic_scores=None):
        """Accept either three-view scores or a prepared meta feature matrix."""
        if temporal_scores is None and semantic_scores is None:
            X_meta = np.asarray(statistical_scores, dtype=float)
        else:
            X_meta = self.fusion.prepare_meta_features(
                np.asarray(statistical_scores),
                np.asarray(temporal_scores),
                np.asarray(semantic_scores),
            )
        y_pred = self.fusion.predict(X_meta)
        y_prob = self.fusion.predict_proba(X_meta)
        return y_pred, y_prob

    def predict_meta(self, X_meta):
        """Predict directly from a prepared meta feature matrix."""
        x = np.asarray(X_meta, dtype=float)
        y_pred = self.fusion.predict(x)
        y_prob = self.fusion.predict_proba(x)
        return y_pred, y_prob


def main():
    config = Config()
    predictor = EnsemblePredictor(config)
    n = 5
    stat = np.random.rand(n)
    temp = np.random.rand(n)
    sem = np.random.rand(n)
    pred, prob = predictor.predict(stat, temp, sem)
    print("预测标签:", pred)
    print("风险分数:", prob)


if __name__ == "__main__":
    main()
