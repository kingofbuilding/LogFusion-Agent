"""Evaluate case retrieval over the small labelled query set in benchmarks/rag_queries.json.

This is an agent-side sanity check, not the thesis hit-rate protocol: each query lists the case IDs
that are acceptable as a top-1/top-3 answer.

Usage:
    python scripts/evaluate_case_retrieval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.rag_index import HybridCaseRetriever, MiniLMRetriever, TfidfCaseRetriever

QUERIES = ROOT / "benchmarks/rag_queries.json"
VECTORS = ROOT / "data/vectors"
RESULTS = ROOT / "benchmarks/results/rag_retrieval_eval.json"


def build_retrievers() -> dict:
    retrievers = {}
    tfidf_index = VECTORS / "rag_attack_cases_tfidf.npz"
    minilm_index = VECTORS / "rag_attack_cases_minilm.npz"
    if tfidf_index.exists():
        retrievers["tfidf"] = TfidfCaseRetriever(tfidf_index, VECTORS / "rag_attack_cases_tfidf.joblib")
    if minilm_index.exists():
        meta = json.loads((VECTORS / "rag_attack_cases_minilm.json").read_text(encoding="utf-8"))
        retrievers["minilm"] = MiniLMRetriever(minilm_index, meta["model_dir"])
    if "tfidf" in retrievers and "minilm" in retrievers:
        retrievers["hybrid"] = HybridCaseRetriever(retrievers["tfidf"], retrievers["minilm"])
    return retrievers


def evaluate(name: str, retriever, queries: list[dict]) -> dict:
    rows = []
    for item in queries:
        hits = retriever(item["query"], 3)
        ids = [hit["case_id"] for hit in hits]
        rows.append({"query": item["query"], "kind": item["kind"], "expected": item["expected"],
                     "top3": ids,
                     "top1": int(bool(ids) and ids[0] in item["expected"]),
                     "top3_hit": int(bool(set(ids) & set(item["expected"])))})
    total = len(rows)
    summary = {"backend": name, "n": total,
               "top1": round(sum(row["top1"] for row in rows) / total, 4),
               "top3": round(sum(row["top3_hit"] for row in rows) / total, 4)}
    for kind in ("log", "paraphrase"):
        subset = [row for row in rows if row["kind"] == kind]
        if subset:
            summary[f"top1_{kind}"] = round(sum(row["top1"] for row in subset) / len(subset), 4)
            summary[f"top3_{kind}"] = round(sum(row["top3_hit"] for row in subset) / len(subset), 4)
    return {"summary": summary, "rows": rows}


def main() -> int:
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    retrievers = build_retrievers()
    if not retrievers:
        print("没有可用索引：先运行 python scripts/rebuild_rag_index.py")
        return 2
    payload = {"queries": str(QUERIES.relative_to(ROOT)), "backends": {}}
    print(f"{'backend':8s} {'top1':>6s} {'top3':>6s} {'log1':>6s} {'para1':>6s}")
    for name, retriever in retrievers.items():
        data = evaluate(name, retriever, queries)
        payload["backends"][name] = data
        summary = data["summary"]
        print(f"{name:8s} {summary['top1']:6.2f} {summary['top3']:6.2f} "
              f"{summary.get('top1_log', 0):6.2f} {summary.get('top1_paraphrase', 0):6.2f}")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
