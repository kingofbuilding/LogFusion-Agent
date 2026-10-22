from __future__ import annotations

import json

import pytest

from src.agent.events import EventStore
from src.agent.tools import OBSERVATION_CHAR_LIMIT, InvestigationTools, ToolArgumentError


def make_store(count: int = 12) -> EventStore:
    rows = [{"timestamp": f"2026-01-15T10:{i // 60:02d}:{i % 60:02d}Z", "host": "web-01",
             "message": f"sshd[1]: Failed password for user{i} from 198.51.100.{i} port {40000 + i} ssh2"}
            for i in range(count)]
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "t.jsonl")


def fake_detector(total: int = 17):
    """Mimic the upstream adapter: parallel score/window lists plus the untruncated total."""

    def detect(store, limit):
        windows, scores = [], []
        for i, event in enumerate(store.events[:limit]):
            start = store.events[max(0, i - 2)]
            risk = round(0.9 - i * 0.05, 4)
            windows.append({"start_event_id": start.event_id, "end_event_id": event.event_id, "risk_score": risk})
            scores.append({"event_id": event.event_id, "risk_score": risk,
                           "stat_score": 0.1 * (i % 3), "temporal_score": 0.2, "semantic_score": 0.7})
        return {"backend": "fake_three_view", "model_loaded": True, "scores": scores,
                "windows": windows, "total_windows": total}

    return detect


def test_detector_returns_bounded_windows_not_raw_scores():
    tools = InvestigationTools(make_store(), detector=fake_detector(17))
    result = tools.call("detect_anomalies", {"top_windows": 3})
    assert len(result["windows"]) == 3
    assert "scores" not in result, "raw per-line scores must not reach the planner"
    assert result["total_windows"] == 17
    assert result["truncated"] is True
    assert result["returned_windows"] == 3
    assert result["windows"][0]["dominant_view"] in ("statistical", "temporal", "semantic")
    # Both window anchors become evidence so get_event_context works on either end.
    anchors = {eid for w in result["windows"] for eid in (w["start_event_id"], w["end_event_id"])}
    assert anchors <= set(tools.evidence)
    assert len(tools.evidence) <= 2 * 3


def test_detector_window_span_points_back_into_the_log():
    store = make_store()
    tools = InvestigationTools(store, detector=fake_detector(5))
    result = tools.call("detect_anomalies", {"top_windows": 2})
    for window in result["windows"]:
        assert window["start_event_id"] in store.by_id
        assert window["end_event_id"] in store.by_id


def test_detector_rejects_unknown_event_id():
    def broken(store, limit):
        return {"backend": "fake", "model_loaded": True, "scores": [],
                "windows": [{"start_event_id": "E-missing", "end_event_id": "E-missing", "risk_score": 0.9}],
                "total_windows": 1}

    tools = InvestigationTools(make_store(), detector=broken)
    with pytest.raises(ValueError):
        tools.call("detect_anomalies", {"top_windows": 1})


def test_top_windows_out_of_range_is_rejected_with_guidance():
    tools = InvestigationTools(make_store(), detector=fake_detector(5))
    with pytest.raises(ToolArgumentError) as excinfo:
        tools.call("detect_anomalies", {"top_windows": 50})
    assert "1" in str(excinfo.value) and "10" in str(excinfo.value)


def test_rule_mode_detector_stays_bounded():
    tools = InvestigationTools(make_store(40))
    result = tools.call("detect_anomalies", {"top_windows": 5})
    assert result["backend"] == "rule_signals"
    assert len(result["events"]) == 5


def test_every_tool_observation_is_capped_before_reaching_the_planner():
    tools = InvestigationTools(make_store(200))
    result = tools.call("search_logs", {"limit": 100})
    payload = json.dumps(result, ensure_ascii=False)
    assert len(payload) <= OBSERVATION_CHAR_LIMIT
    assert result["observation_truncated"] is True
    assert len(result["events"]) < 100


def test_small_observations_are_not_touched():
    tools = InvestigationTools(make_store(5))
    result = tools.call("build_timeline", {})
    assert "observation_truncated" not in result
