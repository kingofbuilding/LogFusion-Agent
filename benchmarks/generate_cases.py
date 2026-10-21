"""Generate the labelled SSH investigation suite used by the agent evaluation harness.

Usage:
    python -m benchmarks.generate_cases              # write benchmarks/cases/
    python -m benchmarks.generate_cases --check      # regenerate in memory, compare with disk

Design constraints (see docs/EVAL_REPORT.md):
- Logs are synthetic (no LogHub OpenSSH sample is bundled) and generated from a fixed seed,
  so the suite is reproducible and shares no events with the upstream training data.
- Labels live only in the sibling ``<case>.json`` expectation file. ``run_eval`` never passes
  that file to the tools; the agent only ever sees ``<case>.jsonl``.
- Every case is self-checked: the intended failure groups must be exactly the groups that the
  agent's own ``failure_clusters`` helper derives from the written file, so a case cannot
  silently encode an unreachable label.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.agent.events import EventStore
from src.agent.tools import failure_clusters

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks/cases"
GOAL = "调查是否存在 SSH 暴力破解、后续成功登录及可疑账户活动"
DEFAULT_SEED = 20260115
T0 = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

HOSTS = ["web-01", "web-02", "db-01", "bastion-01"]
NOISE_USERS = ["deploy", "ops", "backup", "monitor", "svc-cron", "alice", "bob", "carol", "dave"]

# Scenario source addresses stay in the documentation ranges reserved for examples;
# background noise always uses 192.0.2.0/24 so it cannot share an entity with a scenario.
SCENARIO_IPS = ["198.51.100.23", "203.0.113.77", "198.51.100.91", "203.0.113.45"]

CATEGORIES = [
    "bruteforce_then_success",
    "bruteforce_no_success",
    "success_other_account",
    "success_other_host",
    "success_outside_window",
    "benign_retries",
    "multi_cluster",
]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(ts: datetime, host: str, message: str, tag: str = "") -> dict:
    return {"ts": ts, "host": host, "message": message, "tag": tag}


def _failed(rng, ts, host, user, ip, tag="cluster") -> dict:
    return _row(ts, host, f"sshd[{rng.randint(1000, 30000)}]: Failed password for {user} "
                          f"from {ip} port {rng.randint(40000, 60000)} ssh2", tag)


def _accepted(rng, ts, host, user, ip, tag="success", method="password") -> dict:
    return _row(ts, host, f"sshd[{rng.randint(1000, 30000)}]: Accepted {method} for {user} "
                          f"from {ip} port {rng.randint(40000, 60000)} ssh2", tag)


def _sudo(rng, ts, host, user, tag=""):
    return _row(ts, host, f"sudo: {user} : TTY=pts/{rng.randint(0, 3)} ; PWD=/home/{user} ; "
                          f"USER=root ; COMMAND=/usr/bin/id", tag)


def _cluster(rng, ts, host, user, ip, count, tag="cluster", spread=35):
    """``count`` failures for one entity, all inside a 5-minute window."""
    return [_failed(rng, ts + timedelta(seconds=spread * i + rng.randint(0, 4)), host, user, ip, tag)
            for i in range(count)]


def _noise(rng, base, count):
    """Filler traffic: unique-ish IPs per record, so no accidental failure cluster appears."""
    rows = []
    start = base - timedelta(minutes=95)
    for offset in sorted(rng.uniform(0, 150) for _ in range(count)):
        ts = start + timedelta(minutes=offset)
        host = rng.choice(HOSTS)
        user = rng.choice(NOISE_USERS)
        ip = f"192.0.2.{rng.randint(2, 250)}"
        pid, port = rng.randint(1000, 30000), rng.randint(40000, 60000)
        kind = rng.choices(["failed", "publickey", "invalid", "closed", "session", "disconnect"],
                           weights=[4, 3, 2, 2, 2, 2])[0]
        if kind == "failed":
            rows.append(_row(ts, host, f"sshd[{pid}]: Failed password for {user} from {ip} port {port} ssh2"))
        elif kind == "publickey":
            rows.append(_row(ts, host, f"sshd[{pid}]: Accepted publickey for {user} from {ip} port {port} ssh2"))
        elif kind == "invalid":
            rows.append(_row(ts, host, f"sshd[{pid}]: Invalid user {user} from {ip} port {port}"))
        elif kind == "closed":
            rows.append(_row(ts, host, f"sshd[{pid}]: Connection closed by {ip} port {port} [preauth]"))
        elif kind == "session":
            rows.append(_row(ts, host, f"sshd[{pid}]: pam_unix(sshd:session): session opened for user {user} by (uid=0)"))
        else:
            rows.append(_row(ts, host, f"sshd[{pid}]: Disconnected from authenticating user {user} {ip} port {port}"))
    return rows


def _case_bruteforce_then_success(rng, base, index):
    ip, user, host = SCENARIO_IPS[0], "alice", "web-01"
    count = rng.randint(6, 8)
    rows = _cluster(rng, base, host, user, ip, count)
    end = max(r["ts"] for r in rows)
    rows.append(_accepted(rng, end + timedelta(minutes=rng.randint(1, 8)), host, user, ip))
    rows.append(_sudo(rng, end + timedelta(minutes=rng.randint(9, 14)), host, user))
    return rows, {"verdict": "correlated_success", "must_find": ["cluster", "success"],
                  "must_link": ["success"], "must_not_link": [], "clusters": 1}


def _case_bruteforce_no_success(rng, base, index):
    ip, user, host = SCENARIO_IPS[1], "bob", "db-01"
    rows = _cluster(rng, base, host, user, ip, rng.randint(6, 9))
    return rows, {"verdict": "no_correlated_success", "must_find": ["cluster"],
                  "must_link": [], "must_not_link": [], "clusters": 1}


def _case_success_other_account(rng, base, index):
    ip, host = SCENARIO_IPS[0], "bastion-01"
    rows = _cluster(rng, base, host, "alice", ip, rng.randint(5, 8))
    end = max(r["ts"] for r in rows)
    # Same source IP and host, different account: must never be attached to alice's failures.
    rows.append(_accepted(rng, end + timedelta(minutes=rng.randint(1, 6)), host, "bob", ip, tag="decoy_success"))
    return rows, {"verdict": "no_correlated_success", "must_find": ["cluster"],
                  "must_link": [], "must_not_link": ["decoy_success"], "clusters": 1}


def _case_success_other_host(rng, base, index):
    ip = SCENARIO_IPS[2]
    rows = _cluster(rng, base, "web-02", "carol", ip, rng.randint(5, 8))
    end = max(r["ts"] for r in rows)
    rows.append(_accepted(rng, end + timedelta(minutes=rng.randint(1, 6)), "db-01", "carol", ip, tag="decoy_success"))
    return rows, {"verdict": "no_correlated_success", "must_find": ["cluster"],
                  "must_link": [], "must_not_link": ["decoy_success"], "clusters": 1}


def _case_success_outside_window(rng, base, index):
    ip, user, host = SCENARIO_IPS[3], "dave", "web-01"
    rows = _cluster(rng, base, host, user, ip, rng.randint(5, 7))
    end = max(r["ts"] for r in rows)
    rows.append(_accepted(rng, end + timedelta(minutes=rng.randint(18, 40)), host, user, ip, tag="decoy_success"))
    return rows, {"verdict": "no_correlated_success", "must_find": ["cluster"],
                  "must_link": [], "must_not_link": ["decoy_success"], "clusters": 1}


def _case_benign_retries(rng, base, index):
    ip, user, host = "192.0.2.31", "alice", "bastion-01"
    # Three typos in two minutes, i.e. below the documented 5-in-5-minutes threshold.
    rows = _cluster(rng, base, host, user, ip, 3, tag="retry", spread=40)
    end = max(r["ts"] for r in rows)
    rows.append(_accepted(rng, end + timedelta(minutes=1), host, user, ip, tag="benign_success"))
    return rows, {"verdict": "insufficient_evidence", "must_find": [],
                  "must_link": [], "must_not_link": ["benign_success"], "clusters": 0}


def _case_multi_cluster(rng, base, index):
    rows = _cluster(rng, base, "web-01", "alice", SCENARIO_IPS[0], rng.randint(6, 8), tag="cluster")
    end = max(r["ts"] for r in rows)
    rows.append(_accepted(rng, end + timedelta(minutes=rng.randint(2, 8)), "web-01", "alice", SCENARIO_IPS[0]))
    # A second, independent brute-force burst with no follow-up login.
    rows += _cluster(rng, base + timedelta(minutes=25), "web-01", "carol", SCENARIO_IPS[1],
                     rng.randint(5, 7), tag="cluster_other")
    return rows, {"verdict": "correlated_success", "must_find": ["cluster", "success"],
                  "must_link": ["success"], "must_not_link": [],
                  "must_not_pair": [["success", "cluster_other"]], "clusters": 2}


BUILDERS = {
    "bruteforce_then_success": _case_bruteforce_then_success,
    "bruteforce_no_success": _case_bruteforce_no_success,
    "success_other_account": _case_success_other_account,
    "success_other_host": _case_success_other_host,
    "success_outside_window": _case_success_outside_window,
    "benign_retries": _case_benign_retries,
    "multi_cluster": _case_multi_cluster,
}


def _resolve(spec: dict, rt: dict) -> dict:
    def ids(tags):
        return [event_id for tag in tags for event_id in rt["ids"][tag]]

    expected = {
        "verdict": spec["verdict"],
        "must_find_event_ids": ids(spec.get("must_find", [])),
        "must_link_event_ids": ids(spec.get("must_link", [])),
        "must_not_link_event_ids": ids(spec.get("must_not_link", [])),
        "must_not_pair": [[ids([a])[0], ids([b])[0]] for a, b in spec.get("must_not_pair", [])],
    }
    return expected


def _build_case(case_id: str, category: str, seed: int, index: int) -> tuple[str, str, dict]:
    rng = random.Random(f"{seed}:{case_id}")
    base = T0 + timedelta(hours=6 * index)
    scenario, spec = BUILDERS[category](rng, base, index)
    rows = scenario + _noise(rng, base, rng.randint(45, 60))
    rows.sort(key=lambda r: (r["ts"], r["tag"] != ""))

    log_lines = [json.dumps({"timestamp": _ts(r["ts"]), "host": r["host"], "message": r["message"]},
                            ensure_ascii=False) for r in rows]
    log_text = "\n".join(log_lines) + "\n"

    store = EventStore.from_bytes(log_text.encode(), f"{case_id}.jsonl")
    if len(store.events) != len(rows):
        raise AssertionError(f"{case_id}: event count mismatch")
    ids = defaultdict(list)
    for row, event in zip(rows, store.events):
        if row["tag"]:
            ids[row["tag"]].append(event.event_id)

    # Self-check: the labelled groups must be exactly what the shared helper derives.
    clusters = failure_clusters(store.events)
    specs_clusters = spec["clusters"]
    if len(clusters) != specs_clusters:
        raise AssertionError(f"{case_id}: expected {specs_clusters} failure groups, derived {len(clusters)}")
    derived_ids = {eid for group in clusters for eid in group["event_ids"]}
    intended = set(ids["cluster"]) | set(ids.get("cluster_other", []))
    if derived_ids != intended:
        raise AssertionError(f"{case_id}: derived cluster ids do not match the injected ones")

    expected = _resolve(spec, {"ids": ids})
    meta = {"case_id": case_id, "category": category, "log_file": f"{case_id}.jsonl", "goal": GOAL,
            "expected": expected, "events": len(rows),
            "design": _DESIGN[category]}
    return log_text, json.dumps(meta, ensure_ascii=False, indent=2) + "\n", meta


_DESIGN = {
    "bruteforce_then_success": "6-8 次同 IP/账号/主机失败后 15 分钟内同实体成功登录，属于应建立关联的阳性用例。",
    "bruteforce_no_success": "达到失败阈值但窗口后没有成功登录，结论应为失败簇存在、未观察到关联成功。",
    "success_other_account": "窗口后同 IP、同主机但另一账号登录，属于不应关联的干扰项。",
    "success_other_host": "窗口后同 IP、同账号但另一主机登录，属于不应关联的干扰项。",
    "success_outside_window": "同实体成功登录发生在失败窗口结束 15 分钟之后，超出关联窗口。",
    "benign_retries": "同一实体 2 分钟内仅 3 次输错后成功，低于 5 次阈值，属于良性重试。",
    "multi_cluster": "两个独立失败簇并存，只有第一个簇有后续成功，用于检查跨簇误配。",
}


def generate_all(out_dir: Path = CASES_DIR, seed: int = DEFAULT_SEED) -> dict:
    """Write every case file; return the manifest (also written to ``manifest.json``)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {name: 0 for name in CATEGORIES}
    plan = []
    for category in CATEGORIES:
        for _ in range(_CATEGORY_COUNTS[category]):
            plan.append(category)
    cases = []
    for index, category in enumerate(plan, start=1):
        case_id = f"ssh-{index:03d}"
        log_text, meta_text, meta = _build_case(case_id, category, seed, index)
        (out_dir / f"{case_id}.jsonl").write_text(log_text, encoding="utf-8", newline="\n")
        (out_dir / f"{case_id}.json").write_text(meta_text, encoding="utf-8", newline="\n")
        counts[category] += 1
        cases.append(meta)
    manifest = {"suite": "logfusion-agent-ssh-investigation", "version": 1, "seed": seed,
                "goal": GOAL, "total": len(cases), "counts": counts,
                "generator": "benchmarks/generate_cases.py",
                "note": "合成日志；标签仅存在于 .json 期望文件，工具只能看到 .jsonl"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    return manifest


_CATEGORY_COUNTS = {"bruteforce_then_success": 8, "bruteforce_no_success": 6,
                    "success_other_account": 6, "success_other_host": 6,
                    "success_outside_window": 5, "benign_retries": 6, "multi_cluster": 5}


def check(out_dir: Path = CASES_DIR, seed: int = DEFAULT_SEED) -> list[str]:
    """Regenerate in memory and report files that no longer match the committed suite."""
    problems = []
    for index, category in enumerate([c for c in CATEGORIES for _ in range(_CATEGORY_COUNTS[c])], start=1):
        case_id = f"ssh-{index:03d}"
        log_text, meta_text, _ = _build_case(case_id, category, seed, index)
        for suffix, text in ((".jsonl", log_text), (".json", meta_text)):
            path = out_dir / f"{case_id}{suffix}"
            if not path.exists():
                problems.append(f"missing {path.name}")
            elif path.read_text(encoding="utf-8") != text:
                problems.append(f"differs {path.name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 LogFusion-Agent SSH 评测用例")
    parser.add_argument("--out", type=Path, default=CASES_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true", help="只校验已提交用例是否与生成器一致")
    args = parser.parse_args()
    if args.check:
        problems = check(args.out, args.seed)
        print("\n".join(problems) if problems else "OK: 已提交用例与生成器一致")
        return 1 if problems else 0
    manifest = generate_all(args.out, args.seed)
    print(f"生成 {manifest['total']} 条用例 -> {args.out}")
    for category, count in manifest["counts"].items():
        print(f"  {category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
