"""
轻量向量库（最小可运行版）：
使用 numpy 余弦相似度，不依赖外部服务。
"""

from pathlib import Path

import numpy as np


class SimpleVectorStore:
    """简单向量存储。"""

    def __init__(self):
        self.vectors = None
        self.payloads = []

    def add(self, vectors: np.ndarray, payloads: list):
        vectors = np.asarray(vectors, dtype=np.float32)
        if self.vectors is None:
            self.vectors = vectors
        else:
            self.vectors = np.vstack([self.vectors, vectors])
        self.payloads.extend(payloads)

    def search(self, query_vec: np.ndarray, top_k: int = 3):
        if self.vectors is None or len(self.payloads) == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
        q = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-8)
        v = self.vectors / (np.linalg.norm(self.vectors, axis=1, keepdims=True) + 1e-8)
        sims = (v @ q.T).reshape(-1)
        idx = np.argsort(-sims)[:top_k]
        return [{"score": float(sims[i]), "payload": self.payloads[i]} for i in idx]

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, vectors=self.vectors, payloads=np.array(self.payloads, dtype=object))

    def load(self, path: Path):
        data = np.load(path, allow_pickle=True)
        self.vectors = data["vectors"]
        self.payloads = data["payloads"].tolist()
