from __future__ import annotations

import numpy as np

from src.agent.rag_index import TfidfCaseRetriever, build_tfidf_index, load_cases
from src.agent.tools import ROOT

CASES = ROOT / "data/rag/attack_cases.jsonl"


def _retriever(directory) -> TfidfCaseRetriever:
    build_tfidf_index(load_cases(CASES), directory)
    return TfidfCaseRetriever(directory / "rag_attack_cases_tfidf.npz",
                              directory / "rag_attack_cases_tfidf.joblib")


def test_rebuilt_index_ranks_the_matching_case(tmp_path):
    summary = build_tfidf_index(load_cases(CASES), tmp_path)
    assert summary["cases"] == 67 and summary["dim"] > 100
    retriever = TfidfCaseRetriever(tmp_path / "rag_attack_cases_tfidf.npz",
                                   tmp_path / "rag_attack_cases_tfidf.joblib")
    hits = retriever("Failed password for invalid user admin from 203.0.113.9 port 5555 ssh2", 3)
    assert hits[0]["case_id"] == "CASE-SEC-001"
    assert hits[0]["raw_score"] > 0.2
    assert hits[0]["match_level"] in ("strong", "medium", "weak")


def test_index_is_deterministic(tmp_path):
    cases = load_cases(CASES)
    build_tfidf_index(cases, tmp_path / "a")
    build_tfidf_index(cases, tmp_path / "b")
    left = np.load(tmp_path / "a" / "rag_attack_cases_tfidf.npz", allow_pickle=True)["vectors"]
    right = np.load(tmp_path / "b" / "rag_attack_cases_tfidf.npz", allow_pickle=True)["vectors"]
    assert np.array_equal(left, right)


def test_retriever_marks_unrelated_text_as_candidate(tmp_path):
    retriever = _retriever(tmp_path)
    hits = retriever("weather forecast for tomorrow", 3)
    assert hits and all(hit["evidence_usable"] is False for hit in hits)


def test_minilm_index_if_present():
    import json

    import pytest

    index_path = ROOT / "data/vectors/rag_attack_cases_minilm.npz"
    meta_path = ROOT / "data/vectors/rag_attack_cases_minilm.json"
    if not (index_path.exists() and meta_path.exists()):
        pytest.skip("MiniLM 索引未生成（scripts/rebuild_rag_index.py --backend minilm）")
    from src.agent.rag_index import MiniLMRetriever

    retriever = MiniLMRetriever(index_path, json.loads(meta_path.read_text(encoding="utf-8"))["model_dir"])
    hits = retriever("Accepted password for root from 198.51.100.7 port 2200 ssh2", 3)
    assert len(hits) == 3
    assert hits[0]["raw_score"] > 0.3
    assert hits[0]["case_id"] == "CASE-SEC-013"
