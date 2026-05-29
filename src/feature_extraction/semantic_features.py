"""
语义特征提取：
优先使用 sentence-transformers；
离线/下载失败时回退到哈希向量，保证流程可运行。
"""

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("DISABLE_TF", "1")
os.environ.setdefault("USE_TORCH", "1")

import numpy as np
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import Config, Logger, get_device

# Force transformers to skip TensorFlow import path to avoid local TF DLL issues.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None


class SemanticFeatureExtractor:
    """语义特征提取器。"""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.device = get_device()

        self.model_name = config.get("features.semantic.model_name", "BAAI/bge-large-zh-v1.5")
        self.embedding_dim = int(config.get("features.semantic.embedding_dim", 384))
        self.batch_size = int(config.get("data.batch_size", 64))
        self.local_files_only = bool(config.get("features.semantic.local_files_only", True))
        self.force_hash_fallback = bool(config.get("features.semantic.force_hash_fallback", False)) or os.getenv("LOG_FORCE_HASH_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}
        self.model = None
        self.fallback_mode = False

    def load_model(self):
        """加载语义模型，失败则进入离线回退模式。"""
        if self.model is not None or self.fallback_mode:
            return

        if self.force_hash_fallback:
            self.logger.warning("?????????????? sentence-transformers ???")
            self.fallback_mode = True
            self.embedding_dim = min(self.embedding_dim, 256)
            return

        if SentenceTransformer is None:
            self.logger.warning("sentence-transformers 不可用，启用哈希向量回退。")
            self.fallback_mode = True
            # 回退模式下维度适当调小，节省时间与内存
            self.embedding_dim = min(self.embedding_dim, 256)
            return

        try:
            self.logger.info(f"加载语义模型: {self.model_name}")
            self.logger.info(f"语义模型优先设备: {self.device}")
            try:
                self.model = SentenceTransformer(
                    self.model_name,
                    device=str(self.device),
                    local_files_only=self.local_files_only,
                    model_kwargs={"use_safetensors": True},
                )
                self.logger.info("语义模型加载方式: safetensors")
            except Exception as first_error:
                self.logger.warning(f"safetensors 加载失败，尝试普通权重: {first_error}")
                self.model = SentenceTransformer(
                    self.model_name,
                    device=str(self.device),
                    local_files_only=self.local_files_only,
                )
                self.logger.info("语义模型加载方式: default weights")
            self.logger.info(f"模型加载成功，设备: {self.device}")
        except Exception as e:
            self.logger.warning(f"模型加载失败，启用哈希向量回退: {e}")
            self.fallback_mode = True
            self.embedding_dim = min(self.embedding_dim, 256)

    def _hash_embedding(self, text: str) -> np.ndarray:
        """将文本稳定映射为固定维度向量（离线可用）。"""
        vec = np.zeros(self.embedding_dim, dtype=np.float32)
        tokens = re.findall(r"\w+|[^\w\s]", str(text).lower())
        if not tokens:
            return vec

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8", errors="ignore")).hexdigest()
            idx = int(digest[:8], 16) % self.embedding_dim
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec) + 1e-8
        return vec / norm

    def extract_embeddings(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """提取文本 embedding。"""
        self.load_model()
        if len(texts) == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        if not self.fallback_mode and self.model is not None:
            self.logger.info(f"开始提取语义向量，样本数={len(texts)}")
            emb = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )
            return emb.astype(np.float32)

        # 回退模式：逐条哈希
        self.logger.info(f"使用哈希回退提取语义向量，样本数={len(texts)}")
        vectors = []
        iterator = texts if not show_progress else tqdm(texts, desc="hash-embedding")
        for text in iterator:
            vectors.append(self._hash_embedding(text))
        return np.vstack(vectors).astype(np.float32)

    def extract_template_embeddings(self, template_mapping: Dict[int, str]) -> Dict[int, np.ndarray]:
        """为所有模板生成向量。"""
        template_ids = sorted(template_mapping.keys())
        template_texts = [template_mapping[k] for k in template_ids]
        embeddings = self.extract_embeddings(template_texts)
        return {k: v for k, v in zip(template_ids, embeddings)}

    def extract_sequence_embeddings(
        self, sequences: np.ndarray, template_embeddings: Dict[int, np.ndarray]
    ) -> np.ndarray:
        """将模板序列映射为向量序列。"""
        self.logger.info(f"构建序列语义向量，序列数={len(sequences)}")
        zeros = np.zeros(self.embedding_dim, dtype=np.float32)
        seq_vectors = []
        for seq in tqdm(sequences, desc="sequence-embedding"):
            seq_vectors.append(
                np.array([template_embeddings.get(int(tid), zeros) for tid in seq], dtype=np.float32)
            )
        return np.array(seq_vectors, dtype=np.float32)

    def save_embeddings(self, embeddings: Dict, save_path: Path):
        """保存 embedding 文件。"""
        save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(save_path, embeddings)
        self.logger.info(f"已保存 embedding: {save_path}")

    def load_embeddings(self, load_path: Path) -> Dict:
        """加载 embedding 文件。"""
        embeddings = np.load(load_path, allow_pickle=True).item()
        self.logger.info(f"已加载 embedding: {load_path}")
        return embeddings


def main():
    config = Config()
    extractor = SemanticFeatureExtractor(config)
    texts = [
        "Failed password for invalid user admin",
        "Accepted password for user deploy",
        "Connection closed by peer",
    ]
    emb = extractor.extract_embeddings(texts)
    print("语义特征提取成功")
    print("embedding shape:", emb.shape)


if __name__ == "__main__":
    main()
