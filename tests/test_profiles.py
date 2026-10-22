from __future__ import annotations

import json

from src.agent.engine import InvestigationAgent
from src.agent.events import EventStore
from src.agent.planner import RulePlanner, system_prompt
from src.agent.profiles import AUTH_GENERIC, DEFAULT_PROFILE, SSH_AUTH, get_profile

SSH_ROWS = [
    {"timestamp": "2026-01-15T10:00:00Z", "host": "web-01",
     "message": "sshd[1]: Failed password for alice from 198.51.100.23 port 40000 ssh2"},
    {"timestamp": "2026-01-15T10:01:00Z", "host": "web-01",
     "message": "sshd[2]: Accepted password for alice from 198.51.100.23 port 40001 ssh2"},
    {"timestamp": "2026-01-15T10:02:00Z", "host": "web-01",
     "message": "sudo[9]: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/cat /etc/shadow"},
]

GENERIC_ROWS = [
    {"timestamp": f"2026-01-15T10:0{i}:00Z", "host": "radius-01",
     "message": f"authsvc[7]: authentication failed for user=bob from 198.51.100.77 attempt={i}"}
    for i in range(6)
] + [
    {"timestamp": "2026-01-15T10:07:00Z", "host": "radius-01",
     "message": "authsvc[7]: session opened for user bob from 198.51.100.77"},
    {"timestamp": "2026-01-15T10:08:00Z", "host": "radius-01",
     "message": "authsvc[7]: elevated privileges for bob runas=root"},
]


def store(rows, profile=DEFAULT_PROFILE) -> EventStore:
    return EventStore.from_bytes("\n".join(json.dumps(r) for r in rows).encode(), "dialect.jsonl",
                                 profile=profile)


def test_default_profile_reproduces_the_ssh_dialect():
    events = store(SSH_ROWS).events
    assert [e.event_type for e in events] == ["auth_failure", "auth_success", "privileged_command"]
    assert [e.user for e in events] == ["alice", "alice", "alice"]
    assert events[0].src_ip == "198.51.100.23"


def test_generic_profile_classifies_a_different_dialect():
    events = store(GENERIC_ROWS, AUTH_GENERIC).events
    kinds = [e.event_type for e in events]
    assert kinds[:6] == ["auth_failure"] * 6
    assert kinds[6] == "auth_success"
    assert kinds[7] == "privileged_command"
    assert {e.user for e in events} == {"bob"}


def test_ssh_profile_leaves_generic_lines_unclassified():
    events = store(GENERIC_ROWS, SSH_AUTH).events
    assert {e.event_type for e in events} == {"other"}   # dialect vocabulary is not shared by accident


def test_agent_produces_findings_on_a_non_ssh_dialect():
    """The loop, gate and findings are dialect-agnostic; only the vocabulary comes from the profile."""
    logs = store(GENERIC_ROWS, AUTH_GENERIC)
    result = InvestigationAgent(logs).run("调查认证失败与后续成功访问")

    kinds = {f.kind for f in result.findings}
    assert "suspected_bruteforce" in kinds
    assert "success_after_failures" in kinds
    assert result.findings[0].evidence_ids                      # citations still resolve
    assert any(AUTH_GENERIC.label in note for note in result.limitations)
    # The planner was re-rendered for this dialect instead of the SSH one.
    assert result.mode == "rule_playbook"


def test_system_prompt_renders_the_profile_vocabulary():
    ssh = system_prompt(SSH_AUTH)
    generic = system_prompt(AUTH_GENERIC)
    assert "SSH 认证日志" in ssh and "auth_success" in ssh
    assert "通用认证日志" in generic and AUTH_GENERIC.success_type in generic
    assert "{label}" not in ssh


def test_unknown_profile_name_falls_back_instead_of_failing():
    assert get_profile("web_access") is DEFAULT_PROFILE
    assert get_profile("") is DEFAULT_PROFILE
    assert get_profile("auth_generic").name == "auth_generic"


def test_rule_planner_uses_the_profile_success_type():
    planner = RulePlanner(profile=AUTH_GENERIC)
    name, arguments = planner.choose("调查", [{"tool": "detect_anomalies", "arguments": {},
                                               "result": {"events": [{"event_id": "E-1"}]}}])
    assert name in ("aggregate_events", "search_logs")
    if name == "search_logs":                                   # only if a cluster was found
        assert arguments["event_type"] == AUTH_GENERIC.success_type
