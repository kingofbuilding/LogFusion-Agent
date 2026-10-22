"""Offline case retrieval: rebuild and query a TF-IDF index over the RAG case base.

The published index used hash embeddings, which score related text around 0.05-0.15 and made
retrieval look broken. sentence-transformers cannot be downloaded here, so the rebuilt index uses
TF-IDF (still vector retrieval with cosine similarity). Everything is offline and deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CASE_FIELDS = ("title", "content", "technique", "attack_type", "advice_cn")
STRONG_MATCH = 0.35
MEDIUM_MATCH = 0.20
# MiniLM cosine runs on a different scale than TF-IDF.
MINILM_STRONG = 0.55
MINILM_MEDIUM = 0.40


def case_text(case: dict) -> str:
    return " ".join(str(case.get(key, "")) for key in CASE_FIELDS).strip()


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def build_tfidf_index(cases: list[dict], out_dir: Path) -> dict:
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = normalize(vectorizer.fit_transform([case_text(case) for case in cases])).astype(np.float32)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "rag_attack_cases_tfidf.npz",
             vectors=matrix.toarray(), payloads=np.array(cases, dtype=object))
    joblib.dump(vectorizer, out_dir / "rag_attack_cases_tfidf.joblib")
    return {"backend": "tfidf", "cases": len(cases), "dim": int(matrix.shape[1])}


class TfidfCaseRetriever:
    """Callable matching the agent retriever contract: (query, top_k) -> ranked cases."""

    backend = "local_tfidf_cases"

    def __init__(self, index_path: Path, vectorizer_path: Path):
        import joblib

        payload = np.load(index_path, allow_pickle=True)
        self.vectors = payload["vectors"]
        self.cases = payload["payloads"].tolist()
        self.vectorizer = joblib.load(vectorizer_path)

    def __call__(self, query: str, top_k: int) -> list[dict]:
        from sklearn.preprocessing import normalize

        encoded = normalize(self.vectorizer.transform([str(query)])).toarray().astype(np.float32)
        sims = (self.vectors @ encoded.T).ravel()
        hits = []
        for index in np.argsort(-sims)[:top_k]:
            score = round(float(sims[index]), 4)
            hits.append({**self.cases[int(index)], "raw_score": score, "score": score,
                         "evidence_usable": score >= STRONG_MATCH,
                         "match_level": ("strong" if score >= STRONG_MATCH
                                         else "medium" if score >= MEDIUM_MATCH else "weak")})
        return hits


class MiniLMOnnxEncoder:
    """Real sentence embeddings from a local MiniLM ONNX export (no network required)."""

    def __init__(self, model_dir: Path, max_length: int = 256):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = Path(model_dir)
        onnx_path = model_dir / "onnx/model_quantized.onnx"
        if not onnx_path.exists():
            onnx_path = model_dir / "onnx/model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"未找到 ONNX 模型：{model_dir}")
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self.input_names = {item.name for item in self.session.get_inputs()}

    def encode(self, texts) -> np.ndarray:
        batch = self.tokenizer.encode_batch([str(text) for text in texts])
        ids = np.array([item.ids for item in batch], dtype=np.int64)
        mask = np.array([item.attention_mask for item in batch], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self.session.run(None, feeds)[0]
        weights = mask[..., None].astype(np.float32)
        pooled = (hidden * weights).sum(1) / np.clip(weights.sum(1), 1e-6, None)
        return (pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-6, None)).astype(np.float32)


def build_minilm_index(cases: list[dict], out_dir: Path, model_dir: Path) -> dict:
    encoder = MiniLMOnnxEncoder(model_dir)
    vectors = encoder.encode([case_text(case) for case in cases])
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "rag_attack_cases_minilm.npz",
             vectors=vectors, payloads=np.array(cases, dtype=object))
    (out_dir / "rag_attack_cases_minilm.json").write_text(
        json.dumps({"model_dir": str(model_dir), "dim": int(vectors.shape[1])}, ensure_ascii=False),
        encoding="utf-8")
    return {"backend": "minilm", "cases": len(cases), "dim": int(vectors.shape[1]),
            "model_dir": str(model_dir)}


class MiniLMRetriever:
    """Dense semantic retrieval over MiniLM embeddings."""

    backend = "local_minilm_cases"

    def __init__(self, index_path: Path, model_dir: Path):
        payload = np.load(index_path, allow_pickle=True)
        self.vectors = payload["vectors"]
        self.cases = payload["payloads"].tolist()
        self.encoder = MiniLMOnnxEncoder(model_dir)

    def __call__(self, query: str, top_k: int) -> list[dict]:
        encoded = self.encoder.encode([query])
        sims = (self.vectors @ encoded.T).ravel()
        hits = []
        for index in np.argsort(-sims)[:top_k]:
            score = round(float(sims[index]), 4)
            hits.append({**self.cases[int(index)], "raw_score": score, "score": score,
                         "evidence_usable": score >= MINILM_STRONG,
                         "match_level": ("strong" if score >= MINILM_STRONG
                                         else "medium" if score >= MINILM_MEDIUM else "weak")})
        return hits
