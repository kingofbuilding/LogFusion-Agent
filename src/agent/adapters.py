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
        scores = []
        for _, row in result.sort_values("risk_score", ascending=False).head(limit).iterrows():
            e = store.events[int(row["line_num"]) - 1]
            scores.append({"event_id": e.event_id, "risk_score": float(row["risk_score"]),
                           "stat_score": float(row["stat_score"]), "temporal_score": float(row["temporal_score"]),
                           "semantic_score": float(row["semantic_score"])})
        return {"backend": "upstream_three_view_xgboost", "model_loaded": True, "scores": scores,
                "notice": "风险分属于序列窗口，以末行事件 ID 定位。各视图可能使用上游配置的代理/哈希回退，不代表全部神经模型已加载。"}
    return detect


def upstream_retriever():
    from src.rag import AttackCaseRAG
    from src.utils import Config
    rag = AttackCaseRAG(Config())
    if not rag.load_index_if_exists():
        raise FileNotFoundError("未找到原项目的 RAG 索引。先运行 python main.py --build-rag --rag-force")

    def retrieve(query, top_k):
        return rag.retrieve(query, top_k=top_k, auto_build=False)
    return retrieve
