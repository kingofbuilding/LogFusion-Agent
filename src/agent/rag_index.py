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
