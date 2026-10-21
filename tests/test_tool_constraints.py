import json
from types import SimpleNamespace

import pytest

from src.agent import EventStore, InvestigationAgent
from src.agent.tools import PARAMETER_BOUNDS, TOOL_SCHEMAS, InvestigationTools, ToolArgumentError
from benchmarks.run_injection import PAYLOADS, output_indicators, variant
from benchmarks.run_eval import CASES_DIR, score_case
from src.agent.engine import Finding


def test_schema_bounds_match_runtime_validation():
    tools = InvestigationTools(EventStore([]))
    for name, schema in TOOL_SCHEMAS.items():
        properties = schema["function"]["parameters"]["properties"]
        for key in properties:
            if key not in PARAMETER_BOUNDS:
                continue
            low, high = PARAMETER_BOUNDS[key]
            assert (properties[key]["minimum"], properties[key]["maximum"]) == (low, high)
            arguments = {key: high + 1}
            if name == "get_event_context":
                arguments["event_id"] = "missing"
            with pytest.raises(ToolArgumentError):
                tools.call(name, arguments)


def test_safe_validation_feedback_reaches_planner_and_can_recover():
    class Planner:
        mode, tokens_used = "test", 0
        def choose(self, goal, trace):
            if not trace:
                return "aggregate_events", {"max_groups": 20}
            if len(trace) == 1:
                assert trace[0]["result"]["error"] == "max_groups must be between 1 and 10, inclusive."
                return "aggregate_events", {"max_groups": 10}
            return "finish_investigation", {}
    result = InvestigationAgent(EventStore([]), planner=Planner()).run("test")
    assert result.status == "completed"
    assert result.trace[0]["error"] == "ToolArgumentError"


def test_injection_variants_preserve_entities_and_remap_labels():
    meta = json.loads((CASES_DIR / "ssh-001.json").read_text(encoding="utf-8"))
    for payload in PAYLOADS.values():
        clean, attacked, remapped, eid = variant(meta, payload)
        assert eid in attacked.by_id
        assert [(e.host, e.user, e.src_ip, e.event_type, e.timestamp) for e in clean.events] == [
            (e.host, e.user, e.src_ip, e.event_type, e.timestamp) for e in attacked.events]
        assert set(remapped["expected"]["must_find_event_ids"]) <= set(attacked.by_id)


def test_echo_in_raw_trace_is_not_canary_in_generated_prose():
    result = SimpleNamespace(judgment={"status": "not_requested"}, trace=[], stop_reason="planner_finished")
    assert not output_indicators(result)["canary_in_generated_prose"]


def test_pair_metric_does_not_merge_distinct_findings():
    meta = {"case_id": "x", "category": "x", "expected": {"verdict": "correlated_success",
            "must_find_event_ids": [], "must_link_event_ids": [], "must_not_link_event_ids": [],
            "must_not_pair": [["a", "b"]]}}
    result = SimpleNamespace(evidence=[], findings=[Finding("success_after_failures", "", ["a"], ""),
        Finding("success_after_failures", "", ["b"], "")], judgment={"status": "not_requested"},
        trace=[], tokens_used=0, elapsed_seconds=0, status="completed", stop_reason="planner_finished")
    assert score_case(meta, result)["pair_violations"] == []
    result.findings[0].evidence_ids.append("b")
    assert score_case(meta, result)["pair_violations"] == [["a", "b"]]
