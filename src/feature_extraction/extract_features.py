from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.data_processing.data_loader import DataLoader
from src.feature_extraction.semantic_features import SemanticFeatureExtractor
from src.feature_extraction.statistical_features import StatisticalFeatureExtractor, trim_statistical_window
from src.utils import Config, Logger


class FeatureExtractor:
    """Offline feature extraction for statistical and raw-log semantic views."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.data_loader = DataLoader(config)
        self.stat_extractor = StatisticalFeatureExtractor(config)
        self.semantic_extractor = SemanticFeatureExtractor(config)
        self.processed_dir = Path(config.get("paths.data.processed"))
        self.vector_dir = Path(config.get("paths.data.vectors"))

    def extract_all_features(self):
        self.logger.info("=" * 60)
        self.logger.info("开始提取离线特征")
        self.logger.info("=" * 60)

        data = self.data_loader.prepare_data()
        X_train, X_test = data["X_train"], data["X_test"]
        y_train, y_test = data["y_train"], data["y_test"]
        T_train, T_test = data.get("T_train"), data.get("T_test")
        semantic_train_texts = data.get("S_train")
        semantic_test_texts = data.get("S_test")
        raw_train_texts = data.get("R_train")
        raw_test_texts = data.get("R_test")

        max_train = int(self.config.get("experiment.max_train_samples", 2000))
        max_test = int(self.config.get("experiment.max_test_samples", 500))
        if len(X_train) > max_train:
            X_train = X_train[:max_train]
            if T_train is not None:
                T_train = T_train[:max_train]
            if y_train is not None:
                y_train = y_train[:max_train]
            if semantic_train_texts is not None:
                semantic_train_texts = semantic_train_texts[:max_train]
            if raw_train_texts is not None:
                raw_train_texts = raw_train_texts[:max_train]
        if len(X_test) > max_test:
            X_test = X_test[:max_test]
            if T_test is not None:
                T_test = T_test[:max_test]
            if y_test is not None:
                y_test = y_test[:max_test]
            if semantic_test_texts is not None:
                semantic_test_texts = semantic_test_texts[:max_test]
            if raw_test_texts is not None:
                raw_test_texts = raw_test_texts[:max_test]

        dataset = str(self.config.get("data.dataset", "hdfs"))
        out_dir = self.processed_dir / dataset
        out_dir.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)

        stat_len = int(self.config.get("data.statistical_sequence_length", X_train.shape[1]))
        X_train_stat, T_train_stat = trim_statistical_window(
            X_train,
            seq_timestamps=T_train,
            statistical_sequence_length=stat_len,
        )
        X_test_stat, T_test_stat = trim_statistical_window(
            X_test,
            seq_timestamps=T_test,
            statistical_sequence_length=stat_len,
        )

        self.logger.info("[1/2] 提取统计特征")
        train_stat = self.stat_extractor.extract_all_features(
            X_train_stat,
            seq_timestamps=T_train_stat,
            seq_texts=semantic_train_texts,
            seq_raw_texts=raw_train_texts,
        )["combined"]
        test_stat = self.stat_extractor.extract_all_features(
            X_test_stat,
            seq_timestamps=T_test_stat,
            seq_texts=semantic_test_texts,
            seq_raw_texts=raw_test_texts,
        )["combined"]
        np.save(out_dir / "train_stat_features.npy", train_stat)
        np.save(out_dir / "test_stat_features.npy", test_stat)

        self.logger.info("[2/2] 提取原始日志语义特征")
        if semantic_train_texts is None or semantic_test_texts is None:
            raise ValueError("缺少原始语义文本，无法提取语义特征")

        train_sem = self.semantic_extractor.extract_embeddings(list(semantic_train_texts), show_progress=False)
        test_sem = self.semantic_extractor.extract_embeddings(list(semantic_test_texts), show_progress=False)
        np.save(out_dir / "train_semantic_features.npy", train_sem)
        np.save(out_dir / "test_semantic_features.npy", test_sem)

        self.logger.info("离线特征提取完成")
        return {
            "train_stat": train_stat,
            "test_stat": test_stat,
            "train_semantic": train_sem,
            "test_semantic": test_sem,
            "y_train": y_train,
            "y_test": y_test,
        }


def main():
    config = Config()
    extractor = FeatureExtractor(config)
    features = extractor.extract_all_features()
    print("=" * 70)
    print("特征提取完成")
    print("train_stat:", features["train_stat"].shape)
    print("test_stat:", features["test_stat"].shape)
    print("train_semantic:", features["train_semantic"].shape)
    print("test_semantic:", features["test_semantic"].shape)
    print("=" * 70)


if __name__ == "__main__":
    main()
