"""Lazy adapters for the original detector and vector RAG; optional heavy dependencies."""
from __future__ import annotations

from pathlib import Path

from .tools import ROOT


def upstream_detector():
    from src.utils import Config
    config = Config()
    model_path = Path(config.get("paths.models.xgboost")) / "xgboost_fusion.joblib"
    if not model_path.exists():
        raise FileNotFoundError("缺少已训练融合模型。请先按 docs/UPSTREAM_README.md 训练，或使用规则候选信号。")

    def detect(store, limit):
        from frontend.helpers import parse_lines_to_template_df
        from frontend.runtime import run_pipeline
        frame = parse_lines_to_template_df(config, [e.raw for e in store.events])
        if frame.empty:
            raise ValueError("Original parser returned no events")
        # Preserve original source line mapping even if the upstream parser skipped a record.
        frame["log_text"] = [store.events[int(i) - 1].raw for i in frame["line_num"]]
        frame["timestamp"] = [store.events[int(i) - 1].timestamp for i in frame["line_num"]]
        length = int(config.get("data.temporal_sequence_length", 50))
        result, _ = run_pipeline(config, frame, length, float(config.get("frontend.controls.default_threshold", .68)))
        if result.empty:
            raise ValueError(f"日志不足以构建 {length} 条窗口，不能返回模型分数")
        if not result["fusion_model"].eq("xgboost_fusion").all():
            raise RuntimeError("融合模型加载失败；不将回退分数标为模型结果")
        ranked = result.sort_values("risk_score", ascending=False)
        scores, windows = [], []
        for _, row in ranked.head(limit).iterrows():
            line_no = int(row["line_num"])
            e = store.events[line_no - 1]
            scores.append({"event_id": e.event_id, "risk_score": float(row["risk_score"]),
                           "stat_score": float(row["stat_score"]), "temporal_score": float(row["temporal_score"]),
                           "semantic_score": float(row["semantic_score"])})
            # A score belongs to a sequence window, not a single line. Expose the span so callers can
            # judge window-level evidence instead of silently treating the last line as the whole hit.
            start = max(1, line_no - length + 1)
            windows.append({"start_event_id": store.events[start - 1].event_id,
                            "end_event_id": e.event_id, "risk_score": float(row["risk_score"])})
        return {"backend": "upstream_three_view_xgboost", "model_loaded": True, "scores": scores,
                "windows": windows, "window_length": length, "total_windows": int(len(ranked)),
                "notice": "风险分属于序列窗口，以末行事件 ID 定位。各视图可能使用上游配置的代理/哈希回退，不代表全部神经模型已加载。"}
    return detect


def minilm_case_retriever():
    """Dense MiniLM index built from a local ONNX export; preferred when present."""
    import json as _json

    from .rag_index import MiniLMRetriever

    index_path = ROOT / "data/vectors/rag_attack_cases_minilm.npz"
    meta_path = ROOT / "data/vectors/rag_attack_cases_minilm.json"
    if not (index_path.exists() and meta_path.exists()):
        raise FileNotFoundError("缺少 MiniLM 索引。运行 python scripts/rebuild_rag_index.py --backend minilm 重建。")
    model_dir = _json.loads(meta_path.read_text(encoding="utf-8"))["model_dir"]
    return MiniLMRetriever(index_path, Path(model_dir))


def hybrid_case_retriever():
    """TF-IDF + MiniLM fused by reciprocal rank: exact log terms plus paraphrase coverage."""
    from .rag_index import HybridCaseRetriever

    try:
        return HybridCaseRetriever(tfidf_case_retriever(), minilm_case_retriever())
    except Exception:
        # The dense backend is optional; never let it disable retrieval entirely.
        return tfidf_case_retriever()


def tfidf_case_retriever():
    """Offline TF-IDF case index; preferred over the hash-embedding index when present."""
    from .rag_index import TfidfCaseRetriever

    index_path = ROOT / "data/vectors/rag_attack_cases_tfidf.npz"
    vector_path = ROOT / "data/vectors/rag_attack_cases_tfidf.joblib"
    if not (index_path.exists() and vector_path.exists()):
        raise FileNotFoundError("缺少 TF-IDF 案例索引。运行 python scripts/rebuild_rag_index.py 重建。")
    return TfidfCaseRetriever(index_path, vector_path)


def upstream_retriever():
    """Pick a case retriever: TF-IDF by default (most accurate here), MiniLM or hash on request.

    Set AGENT_RAG_BACKEND=tfidf|minilm|hash to override the order.
    """
    import os

    from src.rag import AttackCaseRAG
    from src.utils import Config

    preferred = os.getenv("AGENT_RAG_BACKEND", "").strip().lower()
    minilm_ready = (ROOT / "data/vectors/rag_attack_cases_minilm.npz").exists()
    tfidf_ready = (ROOT / "data/vectors/rag_attack_cases_tfidf.npz").exists()
    if preferred == "hash":
        tfidf_ready = minilm_ready = False
    try:
        if preferred == "tfidf" and tfidf_ready:
            return tfidf_case_retriever()
        if preferred == "hybrid" and tfidf_ready and minilm_ready:
            return hybrid_case_retriever()
        if preferred == "minilm" and minilm_ready:
            return minilm_case_retriever()
        # Default: dense retrieval wins on the labelled-template evaluation; lexical is the fallback.
        if minilm_ready:
            return minilm_case_retriever()
        if tfidf_ready:
            return tfidf_case_retriever()
    except Exception:
        # A broken local index must fall through to the upstream hash index, not crash the run.
        pass
    rag = AttackCaseRAG(Config())
    if not rag.load_index_if_exists():
        raise FileNotFoundError("未找到原项目的 RAG 索引。先运行 python main.py --build-rag --rag-force")

    def retrieve(query, top_k):
        # The upstream UI retrieves in candidate mode and labels each hit with raw score and
        # evidence_usable; the strict 0.65/0.7 thresholds almost never pass with hash embeddings,
        # so using the default threshold here would silently turn RAG into an empty tool.
        # The 0.4 UI floor also rejects paraphrases, so the agent takes the ranked top-k and lets the
        # tool disclose the raw scores instead of dropping every candidate.
        rag.ui_candidate_min_raw_score = 0.0
        hits = rag.retrieve(query, top_k=top_k, auto_build=False, apply_threshold=False)
        for hit in hits:
            hit.setdefault("evidence_usable", bool(hit.get("threshold_passed", False)))
            hit.setdefault("confidence_level", "high" if hit["evidence_usable"] else "candidate")
        return hits
    retrieve.backend = "upstream_vector_rag"
    return retrieve
