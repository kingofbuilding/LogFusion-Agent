"""Generate cases where the fixed SSH playbook is structurally blind.

The standard suite (``generate_cases.py``) is aligned with the evidence rules, so it cannot show a
benefit for an investigator that looks beyond "5 failures in 5 minutes from one entity". These hard
cases keep the same logging format and label discipline but are built so that no
(IP, user, host) triple ever reaches the failure threshold:

    distributed_spray        one failure per IP across many IPs, then a success from one of them
    low_and_slow             4 failures per 10-minute window for three windows, then a success
    many_accounts_one_ip     one failure per account from a single IP, then a success
    spray_then_other_host    distributed spray against one host, success on another host

Consequences:
- The rule conclusion layer still reports ``insufficient_evidence`` for every case; that is the
  point. Verdict accuracy is therefore uninformative here and the metric is **key evidence recall**.
- The generator asserts that ``failure_clusters`` returns no group for each case, which is exactly
  the blind spot being tested.

Usage:
    python -m benchmarks.generate_hard_cases
    python -m benchmarks.generate_hard_cases --check
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from benchmarks.generate_cases import GOAL, _accepted, _failed, _noise, _row, _ts
from src.agent.events import EventStore
from src.agent.tools import failure_clusters

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks/cases_hard"
DEFAULT_SEED = 20260210
SPRAY_NET = "203.0.113."
CATEGORY_COUNTS = {"distributed_spray": 3, "low_and_slow": 3, "many_accounts_one_ip": 3,
                   "spray_then_other_host": 3}

_DESIGN = {
    "distributed_spray": "20 个不同 IP 各失败 1 次后同一账号成功登录；任一 (IP,账号,主机) 都达不到 5 次阈值。",
    "low_and_slow": "同一实体每 10 分钟错 4 次、连续三个窗口后成功；任一 5 分钟窗口内最多 4 次。",
    "many_accounts_one_ip": "同一 IP 在 2 分钟内对 15 个账号各失败 1 次后其中一个账号成功登录，属于撞库形态。",
    "spray_then_other_host": "分布式喷洒发生在 web-01，成功登录落在 db-01，跨主机且无实体达到阈值。",
}


def _distributed_spray(rng, base):
    rows = [_failed(rng, base + timedelta(seconds=7 * i), "web-01", "alice", f"{SPRAY_NET}{10 + i}", "spray")
            for i in range(20)]
    rows.append(_accepted(rng, base + timedelta(minutes=4), "web-01", "alice", f"{SPRAY_NET}10", "success"))
    return rows, ["spray", "success"]


def _low_and_slow(rng, base):
    rows = []
    for window in range(3):
        start = base + timedelta(minutes=10 * window)
        rows += [_failed(rng, start + timedelta(seconds=30 * i), "web-01", "bob", f"{SPRAY_NET}77", "failures")
                 for i in range(4)]
    rows.append(_accepted(rng, base + timedelta(minutes=26), "web-01", "bob", f"{SPRAY_NET}77", "success"))
    return rows, ["failures", "success"]


def _many_accounts_one_ip(rng, base):
    rows = [_failed(rng, base + timedelta(seconds=6 * i), "bastion-01", f"user{i:02d}", f"{SPRAY_NET}42", "failures")
            for i in range(15)]
    rows.append(_accepted(rng, base + timedelta(minutes=3), "bastion-01", "user00", f"{SPRAY_NET}42", "success"))
    return rows, ["failures", "success"]


def _spray_then_other_host(rng, base):
    rows = [_failed(rng, base + timedelta(seconds=8 * i), "web-01", "carol", f"{SPRAY_NET}{100 + i}", "spray")
            for i in range(20)]
    rows.append(_accepted(rng, base + timedelta(minutes=4), "db-01", "carol", f"{SPRAY_NET}103", "success"))
    return rows, ["spray", "success"]


BUILDERS = {"distributed_spray": _distributed_spray, "low_and_slow": _low_and_slow,
            "many_accounts_one_ip": _many_accounts_one_ip, "spray_then_other_host": _spray_then_other_host}


def _build_case(case_id: str, category: str, seed: int, index: int):
    rng = random.Random(f"{seed}:{case_id}")
    base = datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc) + timedelta(hours=6 * index)
    scenario, tags = BUILDERS[category](rng, base)
    rows = scenario + _noise(rng, base, rng.randint(42, 48))
    rows.sort(key=lambda r: (r["ts"], r["tag"] != ""))

    log_text = "\n".join(json.dumps({"timestamp": _ts(r["ts"]), "host": r["host"], "message": r["message"]},
                                    ensure_ascii=False) for r in rows) + "\n"
    store = EventStore.from_bytes(log_text.encode(), f"{case_id}.jsonl")

    ids = defaultdict(list)
    for row, event in zip(rows, store.events):
        if row["tag"]:
            ids[row["tag"]].append(event.event_id)

    # The blind spot must actually exist: no entity may reach the 5-in-5-minutes threshold.
    clusters = failure_clusters(store.events)
    if clusters:
        raise AssertionError(f"{case_id}: playbook would detect {len(clusters)} cluster(s); case is not a blind spot")

    must_find = [eid for tag in tags for eid in ids[tag]]
    meta = {"case_id": case_id, "category": category, "log_file": f"{case_id}.jsonl", "goal": GOAL,
            "expected": {"verdict": "insufficient_evidence", "must_find_event_ids": must_find,
                         "must_link_event_ids": [], "must_not_link_event_ids": [], "must_not_pair": []},
            "incident_present": True,
            "design": _DESIGN[category],
            "note": "规则结论层无法表达此类事件；判分只看关键证据召回，不看 verdict。"}
    return log_text, json.dumps(meta, ensure_ascii=False, indent=2) + "\n", meta


def generate_all(out_dir: Path = CASES_DIR, seed: int = DEFAULT_SEED) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = [category for category, count in CATEGORY_COUNTS.items() for _ in range(count)]
    counts = {category: 0 for category in CATEGORY_COUNTS}
    cases = []
    for index, category in enumerate(plan, start=1):
        case_id = f"hard-{index:03d}"
        log_text, meta_text, meta = _build_case(case_id, category, seed, index)
        (out_dir / f"{case_id}.jsonl").write_text(log_text, encoding="utf-8", newline="\n")
        (out_dir / f"{case_id}.json").write_text(meta_text, encoding="utf-8", newline="\n")
        counts[category] += 1
        cases.append(meta)
    manifest = {"suite": "logfusion-agent-hard-cases", "version": 1, "seed": seed, "goal": GOAL,
                "total": len(cases), "counts": counts, "generator": "benchmarks/generate_hard_cases.py",
                "note": "规则剧本结构性失效的用例；verdict 恒为 insufficient_evidence，指标为关键证据召回"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    return manifest


def check(out_dir: Path = CASES_DIR, seed: int = DEFAULT_SEED) -> list[str]:
    problems = []
    for index, category in enumerate([c for c, n in CATEGORY_COUNTS.items() for _ in range(n)], start=1):
        case_id = f"hard-{index:03d}"
        log_text, meta_text, _ = _build_case(case_id, category, seed, index)
        for suffix, text in ((".jsonl", log_text), (".json", meta_text)):
            path = out_dir / f"{case_id}{suffix}"
            if not path.exists():
                problems.append(f"missing {path.name}")
            elif path.read_text(encoding="utf-8") != text:
                problems.append(f"differs {path.name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="生成规则剧本失效的 SSH 用例")
    parser.add_argument("--out", type=Path, default=CASES_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check(args.out, args.seed)
        print("\n".join(problems) if problems else "OK: 硬用例与生成器一致")
        return 1 if problems else 0
    manifest = generate_all(args.out, args.seed)
    print(f"生成 {manifest['total']} 条硬用例 -> {args.out}")
    for category, count in manifest["counts"].items():
        print(f"  {category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
