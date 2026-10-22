"""Context management for the tool-calling loop.

The loop is a state machine whose observation log grows with every step, and an LLM that is
re-sent the whole log each turn makes context cost quadratic. This module owns the layer that
decides *what part of that log the model sees*, so the engine and the planner stay unaware of the
compression strategy.

Three layers, in the order the model reads them:

1. **Instruction layer** — system prompt plus the tool schemas (constant per call).
2. **Working memory** — the most recent ``recent_items`` trace items, replayed verbatim (bounded
   per observation by :func:`project_observation`).
3. **Episodic ledger** — everything older. Either a *locator projection* that keeps the event IDs
   and counts but drops raw text (:func:`fold_observation`), or, in ``compact`` mode, one prose
   ledger message replacing the older tool turns (:func:`build_ledger`).

Policies (``ContextPolicy.mode``):

* ``full``    — replay everything (pre-optimisation behaviour, kept for A/B replay)
* ``fold``    — default; keeps the assistant/tool message shape, so anything that reads the
                conversation still finds every evidence ID
* ``compact`` — constant history cost, at the price of dropping the original tool framing

Nothing here mutates the trace: the engine's completeness gate and the judgment validator read the
trace and the tool layer, so compression can never make "the evidence was actually retrieved" true
when it was not.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

# Working memory size: how many of the most recent trace items the model sees verbatim.
HISTORY_VERBATIM_ITEMS = 4
# Folding a tiny observation can cost more than replaying it (the digest carries its own note).
FOLD_MIN_CHARS = 420
# Hypothesis statements survive folding, truncated, so the plan stays readable.
FOLD_PLAN_STATEMENT = 120
# Rows kept per folded observation.
FOLD_KEEP_ROWS = 6

MODES = ("full", "fold", "compact")


def project_observation(result: dict, events: int = 20, raw_chars: int = 600) -> dict:
    """Bound one observation without losing IDs or aggregate counts."""
    observation = dict(result or {})
    if "events" in observation:
        rows = observation["events"]
        observation["events"] = [{**e, "raw": e.get("raw", "")[:raw_chars]} for e in rows[:events]]
        observation["planner_preview_truncated"] = (
            len(rows) > events or any(len(e.get("raw", "")) > raw_chars for e in rows))
    return observation


def fold_observation(result: dict, keep_rows: int = FOLD_KEEP_ROWS) -> dict:
    """Replace one old observation with a locator projection.

    The shape is preserved (``events`` / ``groups`` / ``cases`` stay lists) so downstream reading of
    the conversation still finds every evidence ID; only the verbose fields (``raw``, ``source``,
    ``line``) and all but the first few rows are dropped. Small observations are returned untouched.
    """
    if len(json.dumps(result, ensure_ascii=False)) < FOLD_MIN_CHARS:
        return result
    folded: dict = {"folded": True}
    for key in ("total", "returned", "total_groups", "truncated", "backend", "model_loaded",
                "error", "type", "missing"):
        if key in result:
            folded[key] = result[key]
    rows = result.get("events")
    if isinstance(rows, list):
        fields = ("event_id", "timestamp", "event_type", "host", "user", "src_ip")
        folded["events"] = [{k: e.get(k) for k in fields if e.get(k) is not None} for e in rows[:keep_rows]]
        folded["events_total"] = result.get("total", len(rows))
        folded["events_truncated"] = len(rows) > keep_rows
    groups = result.get("groups")
    if isinstance(groups, list):
        folded["groups"] = [{k: g.get(k) for k in ("src_ip", "user", "host", "count", "start", "end")
                             if g.get(k) is not None} | {"event_ids": list(g.get("event_ids") or [])[:4]}
                            for g in groups[:3]]
        folded["groups_total"] = result.get("total_groups", len(groups))
    cases = result.get("cases")
    if isinstance(cases, list):
        folded["cases"] = [{k: c.get(k) for k in ("case_id", "score", "match_level")} for c in cases[:3]]
    hypotheses = result.get("hypotheses")
    if isinstance(hypotheses, list):
        folded["hypotheses"] = [{"id": h.get("id"), "status": h.get("status"),
                                 "statement": str(h.get("statement", ""))[:FOLD_PLAN_STATEMENT]}
                                for h in hypotheses[:4]]
    folded["note"] = "已折叠为定位摘要；原文用 build_timeline 取回。"
    return folded


def _brief(tool: str, arguments: dict, result: dict, max_ids: int = 8) -> str:
    """One line describing one folded call: what was asked and what locators came back."""
    asked = ",".join(f"{k}={v}" for k, v in list(arguments.items())[:3]
                     if k != "rationale" and v not in ("", None))
    parts = [f"{tool}({asked})" if asked else tool]
    if isinstance(result.get("groups"), list):
        for g in result["groups"][:2]:
            parts.append(f"簇 {g.get('src_ip')}/{g.get('user')}@{g.get('host')}×{g.get('count')}")
    ids = []
    if isinstance(result.get("events"), list):
        ids = [str(e.get("event_id")) for e in result["events"] if e.get("event_id")]
    elif isinstance(result.get("groups"), list):
        ids = [str(i) for g in result["groups"] for i in (g.get("event_ids") or [])]
    if isinstance(result.get("cases"), list):
        parts.append("案例 " + ",".join(str(c.get("case_id")) for c in result["cases"][:3]))
    if ids:
        parts.append(f"事件 {','.join(list(dict.fromkeys(ids))[:max_ids])}")
    total = result.get("events_total", result.get("total", result.get("total_groups")))
    if total is not None:
        parts.append(f"共{total}条")
    return " — ".join(parts)


def build_ledger(trace: list) -> str:
    """Collapse older calls into one prose ledger instead of replaying every tool message."""
    lines = ["以下是此前已执行、现已折叠为台账的查询（只保留定位信息；原文可按需用 build_timeline "
             "或 get_event_context 取回）："]
    for step in trace:
        lines.append("- " + _brief(step["tool"], step.get("arguments") or {},
                                   project_observation(step.get("result") or {})))
    return "\n".join(lines)


@dataclass(frozen=True)
class ContextPolicy:
    """Which part of the observation log reaches the model, and in what shape."""

    mode: str = "fold"
    recent_items: int = HISTORY_VERBATIM_ITEMS
    fold_min_chars: int = FOLD_MIN_CHARS
    event_rows: int = FOLD_KEEP_ROWS

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown context mode: {self.mode}")

    @classmethod
    def from_env(cls, default: str = "fold") -> "ContextPolicy":
        requested = (os.getenv("AGENT_HISTORY_MODE") or default).strip().lower()
        return cls(mode=requested if requested in MODES else default)

    def build(self, goal: str, trace: list, system: str) -> list:
        """Rebuild the conversation the model sees on this turn."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": goal}]
        cut = max(0, len(trace) - self.recent_items)
        start = 0
        if self.mode == "compact" and cut:
            start = cut
            messages.append({"role": "user", "content": build_ledger(trace[:cut])})
        fold_before = cut if self.mode != "full" else 0
        for index, step in enumerate(trace):
            if index < start:
                continue
            call_id = f"call_{index}"
            messages.append({"role": "assistant", "content": None, "tool_calls": [{
                "id": call_id, "type": "function", "function": {
                    "name": step["tool"],
                    "arguments": json.dumps(step.get("arguments", {}), ensure_ascii=False)}}]})
            observation = project_observation(step.get("result") or {})
            if index < fold_before:
                observation = fold_observation(observation, self.event_rows)
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": json.dumps(observation, ensure_ascii=False)})
        return messages

    def layout(self, trace: list) -> dict:
        """How the current trace would be split across the layers (for reports, not decisions)."""
        cut = max(0, len(trace) - self.recent_items)
        return {"mode": self.mode, "total_items": len(trace),
                "ledger_items": cut if self.mode == "compact" else 0,
                "folded_items": cut if self.mode == "fold" else 0,
                "verbatim_items": len(trace) - cut}
