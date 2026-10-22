"""Rebuild the RAG case index offline (TF-IDF by default; MiniLM only if it is installed).

Usage:
    python scripts/rebuild_rag_index.py                  # TF-IDF, 67 cases
    python scripts/rebuild_rag_index.py --backend minilm # requires sentence-transformers + model

Outputs (data/vectors/):
    rag_attack_cases_tfidf.npz        vectors (float32) + payloads
    rag_attack_cases_tfidf.joblib     fitted TfidfVectorizer for query encoding
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.agent.rag_index import build_tfidf_index, case_text, load_cases

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/rag/attack_cases.jsonl"
OUT_DIR = ROOT / "data/vectors"


def build_minilm(cases: list[dict], out_dir: Path, model_name: str) -> dict:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vectors = np.asarray(model.encode([case_text(case) for case in cases], normalize_embeddings=True),
                         dtype=np.float32)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "rag_attack_cases_minilm.npz", vectors=vectors, payloads=np.array(cases, dtype=object))
    return {"backend": "minilm", "cases": len(cases), "dim": int(vectors.shape[1]), "model": model_name}


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 RAG 案例索引（默认 TF-IDF，离线可用）")
    parser.add_argument("--backend", choices=["tfidf", "minilm"], default="tfidf")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        print(f"未找到案例：{args.cases}")
        return 2
    summary = (build_tfidf_index(cases, args.out) if args.backend == "tfidf"
               else build_minilm(cases, args.out, args.model))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
