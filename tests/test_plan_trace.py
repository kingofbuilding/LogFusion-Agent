from __future__ import annotations

import json

import pytest

from src.agent.engine import InvestigationAgent
from src.agent.events import EventStore
from src.agent.tools import TOOL_SCHEMAS, InvestigationTools, ToolArgumentError


def demo_store() -> EventStore:
    rows = []
    for minute in range(6):
        rows.append({"timestamp": f"2026-01-15T10:0{minute}:00Z", "host": "server-a",
                     "message": "sshd[1]: Failed password for alice from 198.51.100.23 port 40000 ssh2"})
    rows.append({"timestamp": "2026-01-15T10:06:00Z", "host": "server-a",
                 "message": "sshd[2]: Accepted password for alice from 198.51.100.23 port 40001 ssh2"})
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "demo.jsonl")


class PlannerWithPlan:
    mode = "test"
    tokens_used = 0
    supports_plan = True

    def __init__(self, script, hypotheses=("集中失败来源",)):
        self.script, self.hypotheses, self.step = list(script), list(hypotheses), 0

    def plan(self, goal, digest=""):
        return self.hypotheses

    def choose(self, goal, trace):
        action = self.script[min(self.step, len(self.script) - 1)]
        self.step += 1
        return action


def test_rule_planner_records_a_visible_plan():
    result = InvestigationAgent(demo_store()).run("调查 SSH 暴力破解")
    assert [item["id"] for item in result.plan] == ["H1", "H2", "H3"]
    statuses = {item["id"]: item["status"] for item in result.plan}
    # The playbook confirms the failure cluster and the linked success, refutes post-login activity.
    assert statuses == {"H1": "confirmed", "H2": "confirmed", "H3": "refuted"}
    assert all(item.get("updated_at_step") for item in result.plan)
    report = result.to_markdown()
    assert "## 调查计划与假设" in report and "H1" in report
    assert result.trace[0]["tool"] == "plan" and result.trace[0]["stage"] == "plan"


def test_rationale_is_recorded_but_not_passed_to_the_tool():
    planner = PlannerWithPlan([("search_logs", {"limit": 5, "rationale": "先确认日志范围"}),
                               ("finish_investigation", {})])
    result = InvestigationAgent(demo_store(), planner=planner).run("调查 SSH")
    search = next(item for item in result.trace if item["tool"] == "search_logs")
    assert search["rationale"] == "先确认日志范围"
    assert "rationale" not in search["arguments"]
    assert "理由：先确认日志范围" in result.to_markdown()


def test_hypothesis_status_is_updated_by_the_agent():
    planner = PlannerWithPlan([("update_hypothesis", {"hypothesis_id": "H1", "status": "confirmed",
                                                      "note": "存在 6 次集中失败"}),
                               ("finish_investigation", {})])
    result = InvestigationAgent(demo_store(), planner=planner).run("调查 SSH")
    assert result.plan[0]["status"] == "confirmed"
    assert result.plan[0]["note"] == "存在 6 次集中失败"
    assert result.plan[0]["updated_at_step"] == 1
    assert "状态：confirmed" in result.to_markdown()


def test_unknown_hypothesis_id_is_reported_not_applied():
    planner = PlannerWithPlan([("update_hypothesis", {"hypothesis_id": "H9", "status": "refuted"}),
                               ("finish_investigation", {})])
    result = InvestigationAgent(demo_store(), planner=planner).run("调查 SSH")
    assert result.plan[0]["status"] == "open"
    entry = next(item for item in result.trace if item["tool"] == "update_hypothesis")
    assert entry["error"] == "UnknownHypothesis"


def test_update_hypothesis_tool_validates_status():
    tools = InvestigationTools(demo_store())
    with pytest.raises(ToolArgumentError):
        tools.call("update_hypothesis", {"hypothesis_id": "H1", "status": "maybe"})
    assert tools.call("update_hypothesis", {"hypothesis_id": "H1", "status": "open"})["status"] == "open"


def test_every_tool_schema_accepts_a_rationale():
    for name, schema in TOOL_SCHEMAS.items():
        assert "rationale" in schema["function"]["parameters"]["properties"], name
