"""Group A: upstream one-shot baseline (detector + RAG, no iterative investigation).

The upstream project produces a ranked list of risk *windows* and a report, not event-level
verdicts. To compare it with the agent groups under the same conclusion layer, this baseline
expands the highest-ranked window into its original events (window-level evidence, as upstream
actually flags regions rather than single lines), retrieves reference cases once, and derives
findings with the shared ``grounded_findings`` rules.

Consequences that must be reported with the numbers:
- The evidence set is coarse (one ~50-line window), so recall is easy but precision is low.
- ``evidence_precision`` (labelled events / observed events) is the metric that exposes this.
- It does not claim the upstream project ships this verdict mapping.
"""
from __future__ import annotations

import time

from src.agent.engine import InvestigationResult, grounded_findings
from src.agent.tools import InvestigationTools

GOAL = "调查是否存在 SSH 暴力破解、后续成功登录及可疑账户活动"
MAX_WINDOW_EVENTS = 150


def run_upstream_once(store, detector, retriever=None, limit: int = 30, windows: int = 1,
                      goal: str = GOAL) -> InvestigationResult:
    started = time.monotonic()
    tools = InvestigationTools(store, detector=detector, retriever=retriever)
    trace = []
    status, reason = "completed", "oneshot_finished"

    entry = {"step": 1, "tool": "detect_anomalies", "arguments": {"top_windows": max(1, windows)}}
    try:
        detected = detector(store, limit)
        entry["result"] = {"backend": detected.get("backend"), "model_loaded": detected.get("model_loaded"),
                           "scores": len(detected.get("scores", []))}
        index = {event.event_id: i for i, event in enumerate(store.events)}
        spans = detected.get("windows", [])[:max(1, windows)]
        for span in spans:
            start, end = index.get(span["start_event_id"]), index.get(span["end_event_id"])
            if start is None or end is None:
                raise ValueError("Detector returned unknown event ID")
            # Window-level evidence: the sequence the model actually scored.
            for event in store.events[start:end + 1][:MAX_WINDOW_EVENTS]:
                tools.evidence.setdefault(event.event_id, event.to_dict())
        if not spans:
            raise ValueError("Detector returned no windows")
    except Exception as exc:
        entry.update(error=type(exc).__name__, result={"error": "Tool failed", "type": type(exc).__name__})
        status, reason = "error", "detector_unavailable:" + type(exc).__name__
    trace.append(entry)

    if status == "completed":
        entry = {"step": 2, "tool": "retrieve_cases",
                 "arguments": {"query": "SSH brute force failed password accepted sudo", "top_k": 3}}
        try:
            entry["result"] = tools.call("retrieve_cases", entry["arguments"])
        except Exception as exc:
            entry.update(error=type(exc).__name__, result={"error": "Tool failed"})
        trace.append(entry)

    findings = grounded_findings(tools)
    coverage = store.coverage()
    limitations = ["A 组为上游一次性基线：仅展开最高风险窗口与一次案例检索，不做迭代式工具调查。",
                   "结论映射复用与 Agent 相同的证据规则，只为可比性，不代表上游项目原生输出该判定。",
                   "证据粒度为窗口（约 50 条日志），因此召回偏高、精度偏低，应按证据精度而非仅召回解读。",
                   "上游向量索引在本机以哈希回退嵌入构建，阈值下几乎不命中；RAG 分支实际为空。"]
    return InvestigationResult(f"INV-A-{coverage['events']}-{coverage['start'][:10]}", goal, "upstream_oneshot",
                               status, reason, coverage, findings,
                               list(tools.evidence.values()), list(tools.case_references.values()),
                               trace, limitations, round(time.monotonic() - started, 3), 0,
                               {"status": "not_requested"})
