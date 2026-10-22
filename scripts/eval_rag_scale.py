"""Scale check for case retrieval on real logs, not the curated sample.

The labelled-template evaluation uses 104 hand-picked templates that were selected because they
match a case. That number answers "when the query is about a known case, does retrieval find it?"
It does not answer "what happens on an arbitrary line of a real log", which is what the agent
actually feeds the tool.

This script answers the second question. It has no ground truth to score against, so it reports the
things that do not need labels:

* score distribution of top-1 (mean / median / p90) and the share above each match threshold,
* how concentrated the top-1 hits are (a retriever that always returns the same case has no
  discriminative power, whatever its type@1 says),
* agreement between backends on the same query.

Usage:
    python scripts/eval_rag_scale.py --dataset harrison --csv <path>/harrison_parsed.csv
    python scripts/eval_rag_scale.py --dataset harrison --csv ... --query-mode raw --raw-samples 500
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.rag_index import (MEDIUM_MATCH, MINILM_MEDIUM, MINILM_STRONG, STRONG_MATCH,
                                 HybridCaseRetriever, MiniLMOnnxEncoder, TfidfCaseRetriever,
                                 normalize_query)

VECTORS = ROOT / "data/vectors"


def build_backends(names: list[str]) -> dict:
    backends = {}
    tfidf_path, tfidf_vec = VECTORS / "rag_attack_cases_tfidf.npz", VECTORS / "rag_attack_cases_tfidf.joblib"
    minilm_path, minilm_meta = VECTORS / "rag_attack_cases_minilm.npz", VECTORS / "rag_attack_cases_minilm.json"
    if "tfidf" in names and tfidf_path.exists() and tfidf_vec.exists():
        backends["tfidf"] = TfidfCaseRetriever(tfidf_path, tfidf_vec)
    if "minilm" in names and minilm_path.exists() and minilm_meta.exists():
        meta = json.loads(minilm_meta.read_text(encoding="utf-8"))
        backends["minilm"] = MiniLMOnnxEncoder(Path(meta["model_dir"]))
        backends["minilm_vectors"] = np.load(minilm_path, allow_pickle=True)
    if "hybrid" in names and minilm_path.exists() and minilm_meta.exists() and "tfidf" in backends:
        meta = json.loads(minilm_meta.read_text(encoding="utf-8"))
        from src.agent.rag_index import MiniLMRetriever
        backends["hybrid"] = HybridCaseRetriever(backends["tfidf"],
                                                 MiniLMRetriever(minilm_path, Path(meta["model_dir"])))
    return backends


def load_queries(csv_path: Path, mode: str, raw_samples: int, seed: int) -> list[str]:
    if mode == "template":
        frame = pd.read_csv(csv_path, usecols=["template"])
        return [str(t) for t in frame["template"].drop_duplicates()]
    frame = pd.read_csv(csv_path, usecols=["raw_log"])
    rows = frame["raw_log"].dropna().astype(str)
    if raw_samples and raw_samples < len(rows):
        rows = rows.sample(raw_samples, random_state=seed)
    return rows.tolist()


def score_dense(encoder: MiniLMOnnxEncoder, vectors: np.ndarray, queries: list[str]) -> tuple[np.ndarray, np.ndarray]:
    encoded = encoder.encode([normalize_query(q) for q in queries])
    sims = encoded @ vectors.T
    return sims.max(1), sims.argmax(1)


def summarise(name: str, dataset: str, mode: str, top_scores: np.ndarray, top_idx: np.ndarray,
              cases: list[dict], extra: dict | None = None) -> dict:
    strong = MINILM_STRONG if name == "minilm" else STRONG_MATCH
    medium = MINILM_MEDIUM if name == "minilm" else MEDIUM_MATCH
    ids = [cases[int(i)]["case_id"] for i in top_idx]
    counter = collections.Counter(ids)
    return {
        "backend": name, "dataset": dataset, "query_mode": mode, "n": int(len(top_scores)),
        "top1_mean": round(float(top_scores.mean()), 4),
        "top1_median": round(float(np.median(top_scores)), 4),
        "top1_p90": round(float(np.percentile(top_scores, 90)), 4),
        "share_strong": round(float((top_scores >= strong).mean()), 4),
        "share_medium_or_better": round(float((top_scores >= medium).mean()), 4),
        "share_weak": round(float((top_scores < medium).mean()), 4),
        "distinct_top1_cases": len(counter),
        "top1_top_case_share": round(counter.most_common(1)[0][1] / len(ids), 4) if ids else 0.0,
        "top1_group_dist": dict(collections.Counter(cases[int(i)]["case_group"] for i in top_idx)),
        **(extra or {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="<dataset>_parsed.csv（真实日志解析产物）")
    parser.add_argument("--dataset", default="harrison")
    parser.add_argument("--backends", default="minilm,tfidf")
    parser.add_argument("--query-mode", choices=["template", "raw"], default="template")
    parser.add_argument("--raw-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "benchmarks/results/rag_scale_eval.json")
    args = parser.parse_args()

    queries = load_queries(args.csv, args.query_mode, args.raw_samples, args.seed)
    print(f"{args.dataset} / {args.query_mode}：{len(queries)} 条查询")
    backends = build_backends([b.strip() for b in args.backends.split(",") if b.strip()])
    if not backends:
        print("没有可用索引：先运行 python scripts/rebuild_rag_index.py")
        return 2

    cases = None
    rows = []
    if "minilm" in backends:
        payload = backends["minilm_vectors"]
        cases = payload["payloads"].tolist()
        scores, idx = score_dense(backends["minilm"], payload["vectors"], queries)
        rows.append(summarise("minilm", args.dataset, args.query_mode, scores, idx, cases))
    if "tfidf" in backends:
        hits = [backends["tfidf"](q, 1) for q in queries]
        scores = np.array([h[0]["raw_score"] if h else 0.0 for h in hits])
        cases = cases or json.loads("[]")
        ids = [h[0]["case_id"] if h else "MISS" for h in hits]
        rows.append({
            "backend": "tfidf", "dataset": args.dataset, "query_mode": args.query_mode, "n": len(hits),
            "top1_mean": round(float(scores.mean()), 4), "top1_median": round(float(np.median(scores)), 4),
            "top1_p90": round(float(np.percentile(scores, 90)), 4),
            "share_strong": round(float((scores >= STRONG_MATCH).mean()), 4),
            "share_medium_or_better": round(float((scores >= MEDIUM_MATCH).mean()), 4),
            "share_weak": round(float((scores < MEDIUM_MATCH).mean()), 4),
            "distinct_top1_cases": len(set(ids)),
            "top1_top_case_share": round(collections.Counter(ids).most_common(1)[0][1] / len(ids), 4),
        })
    if "hybrid" in backends:
        hits = [backends["hybrid"](q, 1) for q in queries]
        scores = np.array([h[0]["raw_score"] if h else 0.0 for h in hits])
        ids = [h[0]["case_id"] if h else "MISS" for h in hits]
        rows.append({
            "backend": "hybrid", "dataset": args.dataset, "query_mode": args.query_mode, "n": len(hits),
            "top1_mean": round(float(scores.mean()), 4), "top1_median": round(float(np.median(scores)), 4),
            "top1_p90": round(float(np.percentile(scores, 90)), 4),
            "distinct_top1_cases": len(set(ids)),
            "top1_top_case_share": round(collections.Counter(ids).most_common(1)[0][1] / len(ids), 4),
        })

    print(f"{'backend':8s} {'n':>5s} {'mean':>6s} {'median':>7s} {'p90':>6s} {'≥strong':>8s} "
          f"{'≥medium':>8s} {'<medium':>8s} {'top1唯一':>8s} {'最热案例占比':>10s}")
    for row in rows:
        print(f"{row['backend']:8s} {row['n']:5d} {row['top1_mean']:6.3f} {row['top1_median']:7.3f} "
              f"{row['top1_p90']:6.3f} {row.get('share_strong', 0):8.3f} "
              f"{row.get('share_medium_or_better', 0):8.3f} {row.get('share_weak', 0):8.3f} "
              f"{row['distinct_top1_cases']:8d} {row['top1_top_case_share']:10.1%}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"csv": str(args.csv), "rows": rows}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
