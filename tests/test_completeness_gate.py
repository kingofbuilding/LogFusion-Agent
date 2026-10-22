from __future__ import annotations

import json
from types import SimpleNamespace

from src.agent.__main__ import run_suite
from src.agent.engine import InvestigationAgent
from src.agent.events import EventStore


def make_store() -> EventStore:
    rows = [{"timestamp": f"2026-01-15T10:0{i}:00Z", "host": "web-01",
             "message": "sshd[1]: Failed password for alice from 198.51.100.23 port 40000 ssh2"}
            for i in range(6)]
    rows.append({"timestamp": "2026-01-15T10:06:00Z", "host": "web-01",
                 "message": "sshd[2]: Accepted password for alice from 198.51.100.23 port 40001 ssh2"})
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "gate.jsonl")


class FinishOnly:
    mode = "test"
    tokens_used = 0

    def choose(self, goal, trace):
        return "finish_investigation", {}


def test_gate_refuses_twice_then_lets_the_run_finish():
    result = InvestigationAgent(make_store(), planner=FinishOnly()).run("调查 SSH 暴力破解")
    assert result.status == "completed"
    assert result.gate_triggers == 2
    gates = [t for t in result.trace if t["tool"] == "completeness_gate"]
    assert len(gates) == 2 and gates[0]["result"]["missing"]
    assert any("闸门" in note for note in result.limitations)


def test_gate_passes_when_cluster_and_context_were_checked():
    store = make_store()
    success_id = next(event.event_id for event in store.events if event.event_type == "auth_success")

    class Complete:
        mode = "test"
        tokens_used = 0

        def choose(self, goal, trace):
            actions = [t for t in trace if t.get("stage") not in ("plan", "gate", "wrap_up")]
            if not actions:
                return "search_logs", {"user": "alice", "host": "web-01", "event_type": "auth_success"}
            if len(actions) == 1:
                return "get_event_context", {"event_id": success_id}
            return "finish_investigation", {}

    result = InvestigationAgent(store, planner=Complete()).run("调查 SSH 暴力破解")
    assert result.status == "completed" and result.gate_triggers == 0


def test_gate_can_be_disabled_for_focused_tests():
    result = InvestigationAgent(make_store(), planner=FinishOnly(), completeness_gate=False).run("调查")
    assert result.gate_triggers == 0
    assert not any(t["tool"] == "completeness_gate" for t in result.trace)


def test_demo_suite_runs_three_trajectories(tmp_path):
    args = SimpleNamespace(mode="rule", llm_judge=False, with_detector=False, vector_rag=False,
                           max_steps=16, max_seconds=60, max_tokens=24_000, output=tmp_path,
                           goal="调查是否存在 SSH 暴力破解、后续成功登录及可疑账户活动")
    assert run_suite(args) == 0
    reports = list(tmp_path.glob("INV-*/report.md"))
    assert len(reports) == 3
    for report in reports:
        text = report.read_text(encoding="utf-8")
        assert "## 调查计划与假设" in text


class NeverFinishes:
    """Keeps exploring and never calls finish_investigation: the case wrap-up must handle."""

    mode = "test"

    def __init__(self, tokens_per_call: int = 0):
        self.tokens_per_call = tokens_per_call
        self.tokens_used = 0
        self.calls = 0

    def choose(self, goal, trace):
        self.calls += 1
        self.tokens_used += self.tokens_per_call
        return "search_logs", {"limit": min(100, 10 + self.calls)}


def test_wrap_up_starts_before_the_token_limit_when_a_run_never_finishes():
    # 3000 tokens per call against a 16k tool budget: a fixed 90% threshold would be crossed by the
    # same call that hits the hard limit, so wrap-up would never get a turn.
    planner = NeverFinishes(tokens_per_call=3000)
    result = InvestigationAgent(make_store(), planner=planner, max_steps=8, max_tokens=24_000).run("调查")

    assert any(t["tool"] == "wrap_up" and t.get("stage") == "wrap_up" for t in result.trace)
    assert result.status == "completed_partial"
    assert result.stop_reason in ("gate_unresolved", "wrap_up_terminal", "evidence_budget")


def test_terminal_audit_fires_when_the_run_ends_without_finishing():
    result = InvestigationAgent(make_store(), planner=NeverFinishes(), max_steps=6).run("调查")

    terminal = [t for t in result.trace if t["tool"] == "completeness_gate" and t.get("terminal")]
    assert result.status == "completed_partial"
    assert result.gate_triggers == 1 and len(terminal) == 1
    assert terminal[0]["result"]["missing"]
    assert any("结束前仍未覆盖" in note for note in result.limitations)


class WrapUpLooper:
    """Accepts wrap-up but keeps consolidating instead of finishing."""

    mode = "test"
    tokens_used = 0
    supports_wrap_up = True

    def __init__(self):
        self.calls = 0

    def choose(self, goal, trace, wrap_up=False, final=False):
        self.calls += 1
        if not wrap_up:
            return "search_logs", {"limit": min(100, self.calls)}
        if final:
            return "finish_investigation", {}
        return "build_timeline", {"limit": self.calls}


def test_terminal_wrap_up_forces_a_finish_that_the_gate_can_refuse():
    result = InvestigationAgent(make_store(), planner=WrapUpLooper(), max_steps=8).run("调查")

    assert result.stop_reason == "gate_unresolved"
    assert result.status == "completed_partial"
    gate = [t for t in result.trace if t["tool"] == "completeness_gate"]
    assert len(gate) == 1 and gate[0]["terminal"] and gate[0]["result"]["missing"]
    assert any("结束前仍未覆盖" in note for note in result.limitations)


def test_terminal_audit_respects_the_disabled_gate():
    result = InvestigationAgent(make_store(), planner=NeverFinishes(), max_steps=6,
                                completeness_gate=False).run("调查")

    assert result.gate_triggers == 0
    assert not any(t["tool"] == "completeness_gate" for t in result.trace)
