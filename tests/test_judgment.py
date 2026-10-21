import json
from types import SimpleNamespace

import pytest

from src.agent import EventStore, InvestigationAgent
from src.agent.demo import SimulatedJudgment
from src.agent.judgment import JudgmentValidationError, LLMJudgment, validate_judgment
from src.agent.tools import ROOT


def demo_store():
    return EventStore.from_path(ROOT / "data/demo/ssh_investigation.jsonl")


def payload(eid="E-known", cid="CASE-known"):
    return {"assessment": "suspicious", "claims": [{"kind": "hypothesis", "statement": "疑似集中认证失败。",
            "evidence_ids": [eid], "case_ids": [cid]}],
            "recommendations": [{"action": "核对账号授权", "rationale": "失败后成功登录需要核实",
                                 "evidence_ids": [eid], "case_ids": [cid]}],
            "uncertainties": ["未确认登录是否未经授权。"]}


class FakeCompletions:
    def __init__(self, invalid_count=0, usage=100, exception=None):
        self.calls = []
        self.invalid_count, self.usage, self.exception = invalid_count, usage, exception

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exception:
            raise self.exception
        context = json.loads(kwargs["messages"][-1]["content"])
        eid = "E-fabricated" if len(self.calls) <= self.invalid_count else context["evidence"][0]["event_id"]
        cid = context["reference_cases"][0]["case_id"]
        return SimpleNamespace(usage=SimpleNamespace(total_tokens=self.usage), choices=[SimpleNamespace(
            message=SimpleNamespace(tool_calls=[SimpleNamespace(function=SimpleNamespace(
                name="publish_judgment", arguments=json.dumps(payload(eid, cid))))]))])


def reviewer_for(completions):
    return LLMJudgment(SimpleNamespace(chat=SimpleNamespace(completions=completions)), "test-model")


def test_complete_simulated_chain_uses_real_retrieval_and_validation(tmp_path):
    result = InvestigationAgent(demo_store(), reviewer=SimulatedJudgment()).run("调查 SSH")
    assert result.status == "completed"
    assert result.judgment["status"] == "completed"
    assert result.judgment["backend"] == "simulated_llm"
    assert result.tokens_used == 0
    names = [t["tool"] for t in result.trace]
    assert names.index("retrieve_cases") < names.index("synthesize_judgment")
    assert result.case_references
    assert result.judgment["content"]["claims"]
    for claim in result.judgment["content"]["claims"]:
        assert set(claim["evidence_ids"]) <= {e["event_id"] for e in result.evidence}
        assert set(claim["case_ids"]) <= {c["case_id"] for c in result.case_references}
    report = result.to_markdown()
    assert "模拟模型" in report and "建议（未自动执行）" in report
    target = result.save(tmp_path)
    saved = json.loads((target / "investigation.json").read_text(encoding="utf-8"))
    assert saved["judgment"] == result.judgment


@pytest.mark.parametrize("change,code", [
    (lambda p: p["claims"][0].update(evidence_ids=["E-fake"]), "unknown_or_missing_evidence"),
    (lambda p: p["claims"][0].update(evidence_ids=[]), "unknown_or_missing_evidence"),
    (lambda p: p["claims"][0].update(case_ids=["CASE-fake"]), "unknown_case"),
    (lambda p: p["claims"][0].update(evidence_ids=["CASE-known"]), "unknown_or_missing_evidence"),
    (lambda p: p.update(assessment="compromised"), "invalid_assessment"),
    (lambda p: p.update(claims=[]), "assessment_without_evidence"),
    (lambda p: p.update(uncertainties=[]), "missing_uncertainties"),
    (lambda p: p["recommendations"][0].update(evidence_ids=["E-fake"]), "unknown_action_evidence"),
    (lambda p: p["recommendations"][0].update(case_ids=["CASE-fake"]), "unknown_action_case"),
    (lambda p: p.update(extra="untrusted"), "invalid_structure"),
])
def test_reject_invalid_citations_and_structure(change, code):
    p = payload()
    change(p)
    with pytest.raises(JudgmentValidationError, match=code):
        validate_judgment(p, {"E-known": {}}, {"CASE-known": {}})


def test_model_receives_observed_logs_cases_and_rule_findings():
    completion = FakeCompletions()
    result = InvestigationAgent(demo_store(), reviewer=reviewer_for(completion)).run("调查 SSH")
    request = completion.calls[0]
    context = json.loads(request["messages"][-1]["content"])
    assert context["evidence"] and context["reference_cases"] and context["rule_findings"]
    assert "UNTRUSTED DATA" in request["messages"][0]["content"]
    assert request["tool_choice"]["function"]["name"] == "publish_judgment"
    assert result.judgment["backend"] == "llm" and result.tokens_used == 100


def test_invalid_output_is_repaired_once_with_safe_feedback():
    completion = FakeCompletions(invalid_count=1)
    result = InvestigationAgent(demo_store(), reviewer=reviewer_for(completion)).run("调查 SSH")
    assert result.status == "completed" and len(completion.calls) == 2
    assert json.loads(completion.calls[1]["messages"][-1]["content"])["validation_feedback"] == "unknown_or_missing_evidence"
    assert result.tokens_used == 200
    assert result.trace[-2]["error"] == "JudgmentValidationError"
    assert "E-fabricated" not in json.dumps(result.to_dict())


def test_repeated_invalid_output_is_not_published_and_rules_remain():
    result = InvestigationAgent(demo_store(), reviewer=reviewer_for(FakeCompletions(invalid_count=10))).run("调查")
    assert result.status == "error" and result.stop_reason == "judgment_rejected"
    assert result.judgment["status"] == "rejected" and "content" not in result.judgment
    assert result.findings and result.evidence


def test_model_failure_does_not_leak_provider_exception_or_hide_rules():
    result = InvestigationAgent(demo_store(), reviewer=reviewer_for(FakeCompletions(
        exception=RuntimeError("Authorization: sk-private-secret")))).run("调查")
    assert result.judgment["status"] == "failed" and result.status == "error"
    assert result.findings and result.evidence
    assert "sk-private-secret" not in json.dumps(result.to_dict())


def test_final_stages_share_tool_and_token_budgets():
    result = InvestigationAgent(demo_store(), reviewer=SimulatedJudgment(), max_steps=6).run("调查")
    assert result.status == "limited" and result.stop_reason == "max_steps"
    assert result.judgment["status"] == "skipped"
    assert not any(t["tool"] == "synthesize_judgment" for t in result.trace)
    result = InvestigationAgent(demo_store(), reviewer=reviewer_for(FakeCompletions(usage=100)), max_tokens=50).run("调查")
    assert result.status == "limited" and result.stop_reason == "token_budget"
    assert result.judgment["status"] == "discarded" and "content" not in result.judgment
    assert result.tokens_used == 100


def test_agent_completion_retrieves_cases_when_planner_finishes_without_rag():
    class EarlyPlanner:
        mode, tokens_used = "test", 0
        def choose(self, goal, trace):
            return ("search_logs", {}) if not trace else ("finish_investigation", {})
    result = InvestigationAgent(demo_store(), planner=EarlyPlanner(), reviewer=SimulatedJudgment()).run("调查")
    assert result.status == "completed"
    assert [t["tool"] for t in result.trace] == ["search_logs", "retrieve_cases", "synthesize_judgment"]
    assert result.trace[1]["stage"] == "agent_completion"


def test_preview_limits_disallow_citations_to_unseen_evidence():
    completion = FakeCompletions()
    reviewer = reviewer_for(completion)
    events = {f"E-{i}": {"event_id": f"E-{i}", "raw": "x" * 2000} for i in range(65)}
    result = reviewer.synthesize("goal", events, {"CASE-known": {"case_id": "CASE-known"}}, [], {}, timeout=1)
    assert result["preview"]["events_truncated"] and result["preview"]["raw_truncated"]
    assert len(result["preview"]["event_ids"]) == 60
    context = json.loads(completion.calls[0]["messages"][-1]["content"])
    assert all(len(e["raw"]) == 1000 for e in context["evidence"])


def test_missing_evidence_allows_only_insufficient_assessment():
    p = {"assessment": "insufficient_evidence", "claims": [], "recommendations": [], "uncertainties": ["没有原始证据"]}
    assert validate_judgment(p, {}, {}) == p


def test_synthesis_state_cleared_between_runs():
    agent = InvestigationAgent(demo_store(), reviewer=SimulatedJudgment())
    first = agent.run("调查")
    second = agent.run("取消", cancelled=lambda: True)
    assert first.judgment["status"] == "completed"
    assert second.judgment["status"] == "skipped" and second.tokens_used == 0


def test_full_llm_planner_retrieval_synthesis_pipeline():
    from src.agent.planner import LLMPlanner, RulePlanner

    class FullClient(FakeCompletions):
        def create(self, **kwargs):
            if kwargs.get("tool_choice") == {"type": "function", "function": {"name": "publish_judgment"}}:
                return super().create(**kwargs)
            trace = []
            messages = kwargs["messages"]
            for index, message in enumerate(messages):
                if message["role"] == "assistant":
                    function = message["tool_calls"][0]["function"]
                    trace.append({"tool": function["name"], "arguments": json.loads(function["arguments"]),
                                  "result": json.loads(messages[index + 1]["content"])})
            name, arguments = RulePlanner().choose(messages[1]["content"], trace)
            return SimpleNamespace(usage=SimpleNamespace(total_tokens=50), choices=[SimpleNamespace(
                message=SimpleNamespace(tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name=name, arguments=json.dumps(arguments)))]))])

    completion = FullClient()
    reviewer = reviewer_for(completion)
    planner = LLMPlanner(reviewer.client, "test-model")
    result = InvestigationAgent(demo_store(), planner=planner, reviewer=reviewer).run("调查 SSH")
    assert result.mode == "llm_tool_calling" and result.status == "completed"
    assert result.judgment["status"] == "completed" and result.judgment["backend"] == "llm"
    assert result.case_references and result.judgment["content"]["claims"]
    assert result.tokens_used == 450
    assert result.trace[-1]["tool"] == "synthesize_judgment"
