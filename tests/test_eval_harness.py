from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks import generate_cases, run_eval
from src.agent.engine import Finding

CASES_DIR = Path(run_eval.CASES_DIR)
METAS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("ssh-*.json"))}


def test_committed_cases_match_the_generator():
    """The suite is reproducible: regenerating must not change checked-in files."""
    assert generate_cases.check() == []


def test_every_case_has_a_reachable_label():
    assert len(METAS) == 42
    for case_id, meta in METAS.items():
        expected = meta["expected"]
        assert (CASES_DIR / meta["log_file"]).exists()
        assert expected["verdict"] in ("correlated_success", "no_correlated_success", "insufficient_evidence")
        assert meta["case_id"] == case_id
        # A labelled event ID must be a real event of this case, never a dangling reference.
        from src.agent.events import EventStore
        store = EventStore.from_path(CASES_DIR / meta["log_file"])
        known = set(store.by_id)
        for key in ("must_find_event_ids", "must_link_event_ids", "must_not_link_event_ids"):
            assert set(expected[key]) <= known, key
        for pair in expected["must_not_pair"]:
            assert len(pair) == 2 and set(pair) <= known


def test_labels_never_reach_the_log_file():
    """Only timestamp/host/message may appear in the .jsonl the tools read."""
    for meta in METAS.values():
        rows = (CASES_DIR / meta["log_file"]).read_text(encoding="utf-8").splitlines()
        for line in rows:
            assert set(json.loads(line)) == {"timestamp", "host", "message"}
        text = "\n".join(rows)
        assert '"verdict"' not in text and "must_find" not in text


@pytest.mark.parametrize("category,verdict", [
    ("bruteforce_then_success", "correlated_success"),
    ("bruteforce_no_success", "no_correlated_success"),
    ("success_other_account", "no_correlated_success"),
    ("success_other_host", "no_correlated_success"),
    ("success_outside_window", "no_correlated_success"),
    ("benign_retries", "insufficient_evidence"),
    ("multi_cluster", "correlated_success"),
])
def test_derived_verdict_matches_label_for_rule_group(category, verdict):
    """The rule playbook must reproduce the intended verdict for every category (deterministic)."""
    metas = [m for m in METAS.values() if m["category"] == category][:2]
    data = run_eval.run_group("rule", metas, 1, progress=lambda *_: None)
    assert data["summary"]["cases"] == len(metas)
    for row in data["cases"]:
        assert row["verdict_actual"] == verdict
        assert row["false_links"] == []
        assert row["status"] == "completed"


def test_decoy_success_is_retrieved_but_never_linked():
    """A wrong-account success may be observed; linking it is the error the suite measures."""
    meta = METAS["ssh-015"]  # success_other_account
    data = run_eval.run_group("rule", [meta], 1, progress=lambda *_: None)
    row = data["cases"][0]
    assert row["verdict_ok"]
    assert row["false_links"] == []
    assert row["judgment_decoy_citations"] == []


def test_verdict_derivation_prefers_the_strongest_finding():
    brute = Finding("suspected_bruteforce", "", ["e1"], "")
    link = Finding("success_after_failures", "", ["e1", "e2"], "")
    assert run_eval.derived_verdict([brute]) == "no_correlated_success"
    assert run_eval.derived_verdict([brute, link]) == "correlated_success"
    assert run_eval.derived_verdict([Finding("insufficient_evidence", "", [], "")]) == "insufficient_evidence"


def test_summary_skips_undefined_metrics():
    summary = run_eval.summarize([
        {"category": "benign_retries", "verdict_ok": True, "evidence_recall": None, "evidence_precision": None,
         "link_recall": None, "false_links": [], "judgment_decoy_citations": [], "pair_violations": [],
         "tool_steps": 4, "tokens": 0, "status": "completed", "judgment_status": "not_requested",
         "evidence_count": 12},
    ])
    assert summary["evidence_recall"] is None
    assert summary["verdict_accuracy"] == 1.0
    assert summary["by_category"]["benign_retries"]["cases"] == 1
