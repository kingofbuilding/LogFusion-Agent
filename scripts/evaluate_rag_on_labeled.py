"""Evaluate case retrieval on labelled anomaly templates from the AIT-LDS datasets.

Samples come from benchmarks/labeled_templates.json, exported from the predecessor project:
each row is an anomalous log template with its inferred attack_type / case_group. A hit means a
retrieved case has the same attack_type (primary, as in the upstream script) or case_group.

Usage:
    python scripts/evaluate_rag_on_labeled.py
    RAG_EVAL_QUERY_FORM=template python scripts/evaluate_rag_on_labeled.py   # 模板（无元数据）
    RAG_EVAL_QUERY_FORM=raw python scripts/evaluate_rag_on_labeled.py        # 真实日志行（最接近生产）

Caveat: some cases were generated from these very templates, so a subset of samples is a self-match.
The script now always reports the clean/leaked split and the query form it used.
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


QUERY_FORM = os.getenv("RAG_EVAL_QUERY_FORM", "full").strip().lower()


def query_text(row: dict) -> str:
    """Three query forms, because they measure very different things.

    full     source + count + template — what this script originally used. ``source_file`` is
             evaluation metadata: the agent never has it at query time, so this form overstates
             production behaviour.
    template the template text alone, which is the closest proxy for "a line of log arrived".
    title    the human-written description of the template, which shares the label taxonomy with
             the case titles and therefore measures agreement between two hand-written artefacts.
    """
    if QUERY_FORM == "template":
        return row["template"]
    if QUERY_FORM == "title":
        return row["title"]
    if QUERY_FORM == "raw":
        return RAW_LINES.get(row["template"], row["template"])
    return f"source={row['source_file']}; count={row['count']}; template={row['template']}"


RAW_LINES: dict[str, str] = {}


def load_raw_lines() -> dict[str, str]:
    """One representative raw log line per template — the query the agent would really send.

    The evaluation metadata (source_file, count, title) does not exist at query time; a raw line
    does. AIT-LDS parsed CSVs live outside this repository, so the map is optional.
    """
    root = Path(os.getenv("AITLDS_PROCESSED_DIR", "D:/毕业设计/log_analysis_system_complete/data/processed"))
    mapping: dict[str, str] = {}
    if not root.exists():
        return mapping
    import pandas as pd
    for csv_path in sorted(root.glob("*/*_parsed.csv")):
        try:
            frame = pd.read_csv(csv_path, usecols=["template", "raw_log"]).dropna()
        except Exception:
            continue
        for template, raw in zip(frame["template"], frame["raw_log"]):
            mapping.setdefault(str(template), str(raw))
    return mapping


def leaked_templates() -> set[str]:
    """Templates that were turned into cases verbatim: querying them is a self-match."""
    path = ROOT / "data/rag/attack_cases.jsonl"
    if not path.exists():
        return set()
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return {case["template"] for case in cases if case.get("template")}


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


def evaluate(name: str, retriever, samples: list[dict], leaked: set[str] | None = None) -> dict:
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
            "leaked": sample["template"] in (leaked or set()),
        })
    summary = {"backend": name, "samples": len(rows)}
    for key in ("attack_type_hit1", "attack_type_hit3", "attack_type_hit5",
                "group_hit1", "group_hit3", "group_hit5"):
        summary[key] = _rate(rows, key)
    clean = [row for row in rows if not row["leaked"]]
    dirty = [row for row in rows if row["leaked"]]
    summary["query_form"] = QUERY_FORM
    summary["leaked_samples"] = len(dirty)
    summary["attack_type_hit1_clean"] = _rate(clean, "attack_type_hit1")
    summary["attack_type_hit1_leaked"] = _rate(dirty, "attack_type_hit1")
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
    if QUERY_FORM == "raw":
        RAW_LINES.update(load_raw_lines())
        if not RAW_LINES:
            print("未找到原始日志（设置 AITLDS_PROCESSED_DIR 指向含 *_parsed.csv 的目录）")
            return 2
    leaked = leaked_templates()
    payload = {"samples": len(samples), "query_form": QUERY_FORM,
               "leaked_samples": sum(1 for s in samples if s["template"] in leaked), "backends": {}}
    print(f"查询形态 {QUERY_FORM}；泄漏样本 {payload['leaked_samples']}/{len(samples)}")
    print(f"{'backend':8s} {'n':>4s} {'type@1':>7s} {'type@3':>7s} {'clean@1':>8s} {'leak@1':>7s}")
    for name, retriever in retrievers.items():
        data = evaluate(name, retriever, samples, leaked)
        payload["backends"][name] = data
        s = data["summary"]
        print(f"{name:8s} {s['samples']:4d} {s['attack_type_hit1']:7.3f} {s['attack_type_hit3']:7.3f} "
              f"{s['attack_type_hit1_clean']:8.3f} {s['attack_type_hit1_leaked']:7.3f}")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
