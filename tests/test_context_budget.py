from __future__ import annotations

import json
from types import SimpleNamespace

from src.agent.engine import InvestigationAgent, is_empty_observation
from src.agent.events import EventStore
from src.agent.planner import (HISTORY_VERBATIM_ITEMS, build_messages, fold_observation,
                               project_observation)


def make_store() -> EventStore:
    rows = [{"timestamp": f"2026-01-15T10:0{i}:00Z", "host": "web-01",
             "message": "sshd[1]: Failed password for alice from 198.51.100.23 port 40000 ssh2"}
            for i in range(6)]
    rows.append({"timestamp": "2026-01-15T10:06:00Z", "host": "web-01",
                 "message": "sshd[2]: Accepted password for alice from 198.51.100.23 port 40001 ssh2"})
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "budget.jsonl")


def busy_trace(steps: int = 10) -> list:
    """Synthetic trace where every observation is large enough to be worth folding."""
    trace = []
    for i in range(steps):
        events = [{"event_id": f"E-{i:02d}{j:03d}", "timestamp": "2026-01-15T10:00:00+00:00",
                   "event_type": "auth_failure", "host": "web-01", "user": "alice",
                   "src_ip": "198.51.100.23",
                   "raw": "sshd[18738]: Failed password for alice from 198.51.100.23 port 51764 ssh2" * 3}
                  for j in range(15)]
        trace.append({"step": i + 1, "tool": "get_event_context",
                      "arguments": {"event_id": f"E-{i:02d}000",
                                    "rationale": "核对同一实体的后继活动" * 3},
                      "result": {"total": 15, "returned": 15, "events": events}})
    return trace


def test_folding_cuts_payload_and_keeps_every_event_id():
    trace = busy_trace()
    full = json.dumps(build_messages("调查", trace, fold=False), ensure_ascii=False)
    folded = json.dumps(build_messages("调查", trace, fold=True), ensure_ascii=False)

    assert len(folded) < len(full) * 0.6
    # Evidence IDs from folded turns must stay visible: the judgment stage cites them.
    for i in range(len(trace) - HISTORY_VERBATIM_ITEMS):
        assert f"E-{i:02d}005" in folded
    # The most recent turns keep their raw text so the planner can quote it.
    assert "port 51764" in folded
    folded_flags = [json.loads(m["content"]).get("folded")
                    for m in build_messages("调查", trace, fold=True) if m["role"] == "tool"]
    assert folded_flags.count(True) == len(trace) - HISTORY_VERBATIM_ITEMS
    assert folded_flags[-1] is None  # newest observation is still verbatim


def test_small_observations_are_left_alone():
    small = {"total": 0, "events": []}
    assert fold_observation(small) == small


def test_ledger_mode_is_strictly_cheaper_than_folding():
    trace = busy_trace(12)
    folded = json.dumps(build_messages("调查", trace, fold=True), ensure_ascii=False)
    compact = json.dumps(build_messages("调查", trace, fold=True, compact=True), ensure_ascii=False)

    assert len(compact) < len(folded)
    assert "台账" in compact
    assert "E-00005" in compact


def test_project_observation_bounds_events_and_raw():
    observation = project_observation(busy_trace(1)[0]["result"], events=3, raw_chars=10)
    assert len(observation["events"]) == 3
    assert observation["planner_preview_truncated"] is True
    assert all(len(e["raw"]) <= 10 for e in observation["events"])


def test_empty_observation_detection_distinguishes_failure_from_no_rows():
    assert is_empty_observation({"total": 0, "events": []}) is True
    assert is_empty_observation({"groups": [], "total_groups": 0}) is True
    assert is_empty_observation({"events": [{"event_id": "E-1"}]}) is False
    assert is_empty_observation({"error": "ToolArgumentError"}) is False
    assert is_empty_observation({"hypothesis_id": "H1", "status": "confirmed"}) is False


class EmptySearchPlanner:
    """Always searches a different empty source IP, so no call is an exact repeat."""

    mode = "test"
    supports_wrap_up = True
    tokens_used = 0

    def __init__(self):
        self.calls = 0

    def plan(self, goal):
        return ["存在失败簇"]

    def choose(self, goal, trace, wrap_up=False, final=False):
        self.calls += 1
        if wrap_up or final:
            return "finish_investigation", {}
        return "search_logs", {"src_ip": f"203.0.113.{self.calls}", "event_type": "auth_success"}


def test_consecutive_empty_results_hint_then_wrap_up():
    planner = EmptySearchPlanner()
    result = InvestigationAgent(make_store(), planner=planner, max_steps=12).run("调查 SSH 暴力破解")

    hints = [t for t in result.trace if t.get("control") == "EmptyResultHint"]
    assert len(hints) == 1
    assert hints[0]["result"]["streak"] == 2
    # The breaker stops the leak instead of spending all 12 steps on empty queries.
    assert planner.calls <= 5
    assert result.stop_reason in ("evidence_budget", "planner_finished", "gate_unresolved")


def test_cache_hit_tokens_are_recorded_separately_from_budget():
    from src.agent.planner import LLMPlanner

    class CachedClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    usage = SimpleNamespace(total_tokens=1_000, prompt_tokens=900,
                                            completion_tokens=100, prompt_cache_hit_tokens=640)
                    call = SimpleNamespace(function=SimpleNamespace(
                        name="search_logs", arguments=json.dumps({"src_ip": "198.51.100.23"})))
                    return SimpleNamespace(usage=usage, choices=[SimpleNamespace(
                        message=SimpleNamespace(tool_calls=[call]))])

    planner = LLMPlanner(CachedClient(), "test-model")
    planner.choose("调查", [])
    assert planner.tokens_used == 1_000      # budget stays conservative
    assert planner.cached_tokens == 640      # cost accounting keeps the split


def test_context_policy_rejects_unknown_mode_and_reads_env(monkeypatch):
    from src.agent.context import ContextPolicy

    assert ContextPolicy.from_env().mode == "fold"
    monkeypatch.setenv("AGENT_HISTORY_MODE", "compact")
    assert ContextPolicy.from_env().mode == "compact"
    monkeypatch.setenv("AGENT_HISTORY_MODE", "bogus")   # unknown values fall back instead of failing a run
    assert ContextPolicy.from_env().mode == "fold"
    import pytest
    with pytest.raises(ValueError):
        ContextPolicy(mode="bogus")


def test_context_policy_layout_reports_the_three_layers():
    from src.agent.context import ContextPolicy

    trace = busy_trace(9)
    assert ContextPolicy(mode="fold").layout(trace) == {
        "mode": "fold", "total_items": 9, "ledger_items": 0, "folded_items": 5, "verbatim_items": 4}
    assert ContextPolicy(mode="compact").layout(trace)["ledger_items"] == 5
    assert ContextPolicy(mode="full").layout(trace)["folded_items"] == 0


def test_full_mode_matches_pre_optimisation_behaviour():
    from src.agent.context import ContextPolicy

    trace = busy_trace(8)
    legacy = json.dumps(build_messages("调查", trace, fold=False), ensure_ascii=False)
    explicit = json.dumps(ContextPolicy(mode="full").build("调查", trace, "调查起点"), ensure_ascii=False)
    # Same number of tool messages, and the oldest ones still carry raw text.
    assert legacy.count('"role": "tool"') == explicit.count('"role": "tool"')
    assert "port 51764" in explicit
