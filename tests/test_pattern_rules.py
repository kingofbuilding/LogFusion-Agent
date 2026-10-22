from __future__ import annotations

import json

from benchmarks.run_eval import derived_verdict
from src.agent.engine import InvestigationAgent, grounded_findings
from src.agent.events import EventStore
from src.agent.tools import InvestigationTools


def build(rows) -> EventStore:
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "t.jsonl")


def row(stamp: str, message: str, host: str = "web-01") -> dict:
    return {"timestamp": stamp, "host": host, "message": message}


def failed(stamp: str, user: str = "alice", ip: str = "198.51.100.10", host: str = "web-01") -> dict:
    return row(stamp, f"sshd[1]: Failed password for {user} from {ip} port 40000 ssh2", host)


def success(stamp: str, user: str = "alice", ip: str = "198.51.100.10", host: str = "web-01") -> dict:
    return row(stamp, f"sshd[2]: Accepted password for {user} from {ip} port 40001 ssh2", host)


def observe_all(tools: InvestigationTools):
    tools.search_logs(limit=100, include_raw=True)


def test_distributed_spray_is_expressible_and_links_success():
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z", ip=f"203.0.113.{10 + i}") for i in range(20)]
    rows.append(success("2026-01-15T10:04:00Z", ip="203.0.113.10"))
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    findings = grounded_findings(tools)
    kinds = {f.kind for f in findings}
    assert "suspected_distributed_spray" in kinds
    assert "success_after_failures" in kinds
    assert derived_verdict(findings) == "correlated_success"


def test_spray_without_success_is_not_a_linked_chain():
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z", ip=f"203.0.113.{10 + i}") for i in range(20)]
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    findings = grounded_findings(tools)
    assert {f.kind for f in findings} == {"suspected_distributed_spray"}
    assert derived_verdict(findings) == "no_correlated_success"


def test_account_stuffing_from_single_source():
    rows = [failed(f"2026-01-15T10:00:{i * 6:02d}Z", user=f"user{i:02d}", ip="203.0.113.42") for i in range(15)]
    rows.append(success("2026-01-15T10:03:00Z", user="user00", ip="203.0.113.42"))
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    findings = grounded_findings(tools)
    assert "suspected_account_stuffing" in {f.kind for f in findings}
    assert derived_verdict(findings) == "correlated_success"


def test_low_and_slow_is_detected_without_a_five_in_five_cluster():
    rows = []
    for window in range(3):
        start = window * 10
        rows += [failed(f"2026-01-15T10:{start + i:02d}:00Z", user="bob", ip="203.0.113.77") for i in range(4)]
    rows.append(success("2026-01-15T10:26:00Z", user="bob", ip="203.0.113.77"))
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    findings = grounded_findings(tools)
    kinds = {f.kind for f in findings}
    assert "suspected_low_and_slow" in kinds
    assert "suspected_bruteforce" not in kinds
    assert derived_verdict(findings) == "correlated_success"


def test_cross_host_success_is_not_linked():
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z", user="carol", ip=f"203.0.113.{100 + i}") for i in range(20)]
    rows.append(success("2026-01-15T10:04:00Z", user="carol", ip="203.0.113.103", host="db-01"))
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    findings = grounded_findings(tools)
    assert {f.kind for f in findings} == {"suspected_distributed_spray"}
    assert derived_verdict(findings) == "no_correlated_success"


def test_standard_burst_does_not_trigger_new_patterns():
    rows = [failed(f"2026-01-15T10:0{i}:00Z") for i in range(8)]
    rows.append(success("2026-01-15T10:10:00Z"))
    tools = InvestigationTools(build(rows))
    observe_all(tools)
    kinds = {f.kind for f in grounded_findings(tools)}
    assert kinds == {"suspected_bruteforce", "success_after_failures"}


def test_playbook_stays_blind_even_though_the_rules_exist():
    """The rules can express spray, but the fixed playbook never observes the pattern."""
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z", ip=f"203.0.113.{10 + i}") for i in range(20)]
    rows.append(success("2026-01-15T10:04:00Z", ip="203.0.113.10"))
    result = InvestigationAgent(build(rows)).run("调查 SSH 暴力破解和后续登录")
    assert derived_verdict(result.findings) == "insufficient_evidence"


def test_search_logs_projects_compactly_and_dedupes():
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z") for i in range(10)]
    tools = InvestigationTools(build(rows))
    first = tools.search_logs(limit=5)
    assert "raw" not in first["events"][0]
    assert first["returned"] == 5 and first["already_seen"] == 0
    # The next page only reports events that were not returned before.
    second = tools.search_logs(limit=5)
    assert second["returned"] == 5 and second["already_seen"] == 5
    third = tools.search_logs(limit=5)
    assert third["returned"] == 0 and third["already_seen"] == 10
    full = tools.search_logs(limit=5, include_raw=True, dedupe=False)
    assert full["events"][0]["raw"].startswith("sshd[")


def test_group_by_user_surfaces_spray_in_one_call():
    rows = [failed(f"2026-01-15T10:00:{i:02d}Z", ip=f"203.0.113.{10 + i}") for i in range(20)]
    tools = InvestigationTools(build(rows))
    result = tools.call("aggregate_events", {"group_by": "user"})
    assert result["group_by"] == "user"
    group = result["groups"][0]
    assert group["user"] == "alice"
    assert group["count"] == 20 and group["distinct_src_ips"] == 20


def test_run_state_is_reset_between_runs():
    rows = [failed(f"2026-01-15T10:0{i}:00Z") for i in range(6)]
    rows.append(success("2026-01-15T10:08:00Z"))
    store = build(rows)
    tools = InvestigationTools(store)
    agent = InvestigationAgent(store, tools=tools)
    first = agent.run("调查 SSH 暴力破解")
    second = agent.run("调查 SSH 暴力破解")
    assert len(first.evidence) == len(second.evidence)
    assert tools.seen, "seen set must be populated during a run"
