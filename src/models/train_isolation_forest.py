from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from src.data_processing.data_loader import DataLoader
from src.feature_extraction.statistical_features import StatisticalFeatureExtractor, trim_statistical_window
from src.models.isolation_forest_model import IsolationForestModel
from src.utils import Config, Logger


def main():
    config = Config()
    logger = Logger.get_logger("train_isolation_forest", config)

    print("=" * 70)
    print("Isolation Forest 训练")
    print("=" * 70)

    data = DataLoader(config).prepare_data()
    x_train, x_test = data["X_train"], data["X_test"]
    y_test = data.get("y_test")
    t_train, t_test = data.get("T_train"), data.get("T_test")
    s_train, s_test = data.get("S_train"), data.get("S_test")
    r_train, r_test = data.get("R_train"), data.get("R_test")

    stat_len = int(config.get("data.statistical_sequence_length", config.get("data.sequence_length", 50)))
    x_train_stat, t_train_stat = trim_statistical_window(x_train, t_train, stat_len)
    x_test_stat, t_test_stat = trim_statistical_window(x_test, t_test, stat_len)

    extractor = StatisticalFeatureExtractor(config)
    train_feat = extractor.extract_all_features(x_train_stat, seq_timestamps=t_train_stat, seq_texts=s_train, seq_raw_texts=r_train)["combined"]
    test_feat = extractor.extract_all_features(x_test_stat, seq_timestamps=t_test_stat, seq_texts=s_test, seq_raw_texts=r_test)["combined"]

    model = IsolationForestModel(config)
    model.fit(train_feat)
    test_prob = model.predict_proba(test_feat)
    if y_test is not None and len(np.unique(y_test)) > 1:
        logger.info(f"IsolationForest test auc={roc_auc_score(y_test, test_prob):.4f}")

    save_path = Path(config.get("paths.models.isolation_forest")) / "iforest_model.joblib"
    model.save_model(save_path)
    print(f"统计模型已保存: {save_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
