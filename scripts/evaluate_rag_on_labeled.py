"""Evaluate case retrieval on labelled anomaly templates from the AIT-LDS datasets.

Samples come from benchmarks/labeled_templates.json, exported from the predecessor project:
each row is an anomalous log template with its inferred attack_type / case_group. A hit means a
retrieved case has the same attack_type (primary, as in the upstream script) or case_group.

Usage:
    python scripts/evaluate_rag_on_labeled.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.rag_index import HybridCaseRetriever, MiniLMRetriever, TfidfCaseRetriever

SAMPLES = ROOT / "benchmarks/labeled_templates.json"
VECTORS = ROOT / "data/vectors"
RESULTS = ROOT / "benchmarks/results/rag_labeled_eval.json"


def query_text(row: dict) -> str:
    return f"source={row['source_file']}; count={row['count']}; template={row['template']}"


def hash_retriever():
    """Original upstream index through the candidate-mode adapter."""
    previous = os.environ.get("AGENT_RAG_BACKEND")
    os.environ["AGENT_RAG_BACKEND"] = "hash"
    try:
        from src.agent.adapters import upstream_retriever
        return upstream_retriever()
    finally:
        if previous is None:
            os.environ.pop("AGENT_RAG_BACKEND", None)
        else:
            os.environ["AGENT_RAG_BACKEND"] = previous


def build_retrievers() -> dict:
    retrievers = {}
    try:
        retrievers["hash"] = hash_retriever()
    except Exception:
        pass
    tfidf_path = VECTORS / "rag_attack_cases_tfidf.npz"
    minilm_path = VECTORS / "rag_attack_cases_minilm.npz"
    if tfidf_path.exists():
        retrievers["tfidf"] = TfidfCaseRetriever(tfidf_path, VECTORS / "rag_attack_cases_tfidf.joblib")
    if minilm_path.exists():
        meta = json.loads((VECTORS / "rag_attack_cases_minilm.json").read_text(encoding="utf-8"))
        retrievers["minilm"] = MiniLMRetriever(minilm_path, meta["model_dir"])
    if "tfidf" in retrievers and "minilm" in retrievers:
        retrievers["hybrid"] = HybridCaseRetriever(retrievers["tfidf"], retrievers["minilm"])
    return retrievers


def _rate(rows, key):
    return round(sum(row[key] for row in rows) / len(rows), 4) if rows else None


def evaluate(name: str, retriever, samples: list[dict]) -> dict:
    rows = []
    for sample in samples:
        hits = retriever(query_text(sample), 5) or []
        attack_type, case_group = sample["attack_type"], sample["case_group"]
        rows.append({
            "dataset": sample["dataset"],
            "attack_type_hit1": int(any(hit.get("attack_type") == attack_type for hit in hits[:1])),
            "attack_type_hit3": int(any(hit.get("attack_type") == attack_type for hit in hits[:3])),
            "attack_type_hit5": int(any(hit.get("attack_type") == attack_type for hit in hits[:5])),
            "group_hit1": int(any(hit.get("case_group") == case_group for hit in hits[:1])),
            "group_hit3": int(any(hit.get("case_group") == case_group for hit in hits[:3])),
            "group_hit5": int(any(hit.get("case_group") == case_group for hit in hits[:5])),
        })
    summary = {"backend": name, "samples": len(rows)}
    for key in ("attack_type_hit1", "attack_type_hit3", "attack_type_hit5",
                "group_hit1", "group_hit3", "group_hit5"):
        summary[key] = _rate(rows, key)
    summary["by_dataset"] = {
        dataset: {key: _rate([row for row in rows if row["dataset"] == dataset], key)
                  for key in ("attack_type_hit1", "attack_type_hit3")}
        for dataset in sorted({row["dataset"] for row in rows})
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    if not SAMPLES.exists():
        print(f"未找到标注样本：{SAMPLES}")
        return 2
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    retrievers = build_retrievers()
    if not retrievers:
        print("没有可用索引：先运行 python scripts/rebuild_rag_index.py")
        return 2
    payload = {"samples": len(samples), "backends": {}}
    print(f"{'backend':8s} {'n':>4s} {'type@1':>7s} {'type@3':>7s} {'group@1':>8s} {'group@3':>8s}")
    for name, retriever in retrievers.items():
        data = evaluate(name, retriever, samples)
        payload["backends"][name] = data
        s = data["summary"]
        print(f"{name:8s} {s['samples']:4d} {s['attack_type_hit1']:7.3f} {s['attack_type_hit3']:7.3f} "
              f"{s['group_hit1']:8.3f} {s['group_hit3']:8.3f}")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
