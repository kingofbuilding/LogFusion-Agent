"""Replay recorded investigations and measure what each turn would have cost.

This is an offline instrument: it reads ``investigation.json`` files (no model calls, no API key),
rebuilds the exact messages that ``LLMPlanner.choose`` would send, and compares three history
policies on identical traces:

* ``full``    — every observation replayed in full (pre-optimisation behaviour)
* ``fold``    — older observations replaced by shape-preserving locator projections (default)
* ``compact`` — older calls collapsed into a single ledger message (experimental)

Token counts are estimates from a mixed CJK/latin heuristic calibrated to within ~4% of recorded
``tokens_used`` on the runs shipped with this repository. Character counts are exact. Quote the
ratio, not the absolute token number.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.planner import SYSTEM_PROMPT, FINISH_SCHEMA, build_messages  # noqa: E402
from src.agent.tools import TOOL_SCHEMAS  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")


def est_tokens(text: str) -> float:
    """Rough token count: ~1.5 chars per token for Chinese, ~3.9 for the rest."""
    cjk = len(CJK.findall(text))
    return cjk / 1.5 + (len(text) - cjk) / 3.9


def fixed_overhead() -> float:
    """System prompt plus every tool schema, sent on each call regardless of history."""
    return est_tokens(SYSTEM_PROMPT) + est_tokens(json.dumps([*TOOL_SCHEMAS.values(), FINISH_SCHEMA],
                                                             ensure_ascii=False))


def replay(goal: str, trace: list, mode: str) -> dict:
    """Sum the payload of every call in the trace under one history policy."""
    chars = tokens = 0.0
    curve = []
    for k in range(1, len(trace) + 1):
        messages = build_messages(goal, trace[:k], fold=(mode != "full"), compact=(mode == "compact"))
        payload = json.dumps(messages, ensure_ascii=False)
        chars += len(payload)
        tokens += est_tokens(payload)
        curve.append(tokens)
    return {"chars": chars, "tokens": tokens, "calls": len(trace), "curve": curve}


def empty_calls(trace: list) -> int:
    """Successful calls that returned no rows: they cost a full replay and buy nothing."""
    total = 0
    for step in trace:
        result = step.get("result") or {}
        if step.get("error") or not isinstance(result, dict):
            continue
        for key in ("events", "groups", "cases"):
            if isinstance(result.get(key), list):
                total += 0 if result[key] else 1
                break
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glob", default="outputs/investigations/*/investigation.json")
    parser.add_argument("--out", type=Path, default=None, help="把逐条结果写到 JSON")
    args = parser.parse_args()

    paths = sorted(glob.glob(args.glob))
    if not paths:
        print(f"没有找到轨迹：{args.glob}")
        return 1

    overhead = fixed_overhead()
    rows = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        trace = [t for t in data.get("trace", []) if t.get("stage") not in ("gate", "wrap_up", "hint")]
        if not trace:
            continue
        full = replay(data["goal"], trace, "full")
        fold = replay(data["goal"], trace, "fold")
        compact = replay(data["goal"], trace, "compact")
        rows.append({
            "run": data.get("run_id", Path(path).parent.name),
            "mode": data.get("mode"),
            "steps": len(trace),
            "recorded_tokens": data.get("tokens_used", 0),
            "full_chars": int(full["chars"]), "fold_chars": int(fold["chars"]),
            "compact_chars": int(compact["chars"]),
            "full_tokens": round(full["tokens"]), "fold_tokens": round(fold["tokens"]),
            "compact_tokens": round(compact["tokens"]),
            "fold_cut": round(1 - fold["tokens"] / full["tokens"], 4) if full["tokens"] else 0.0,
            "compact_cut": round(1 - compact["tokens"] / full["tokens"], 4) if full["tokens"] else 0.0,
            "empty_calls": empty_calls(trace),
            "curve_full": [round(x) for x in full["curve"]],
            "curve_fold": [round(x) for x in fold["curve"]],
            "curve_compact": [round(x) for x in compact["curve"]],
        })

    if not rows:
        print("没有可复放的轨迹")
        return 1

    print(f"固定开销（system + 8 个 schema）≈ {overhead:.0f} tokens/次\n")
    head = (f"{'轨迹':<20}{'步数':>4}{'原token':>9}{'折叠后':>9}{'降':>7}"
            f"{'台账后':>9}{'降':>7}{'空结果':>7}")
    print(head)
    print("-" * len(head))
    for r in rows:
        print(f"{r['run']:<20}{r['steps']:>4}{r['full_tokens']:>9}{r['fold_tokens']:>9}"
              f"{r['fold_cut']*100:>6.1f}%{r['compact_tokens']:>9}{r['compact_cut']*100:>6.1f}%"
              f"{r['empty_calls']:>7}")

    def total(key):
        return sum(r[key] for r in rows)

    print("-" * len(head))
    print(f"{'合计/' + str(len(rows)) + ' 条':<18}{total('steps'):>4}{total('full_tokens'):>9}"
          f"{total('fold_tokens'):>9}{(1-total('fold_tokens')/total('full_tokens'))*100:>6.1f}%"
          f"{total('compact_tokens'):>9}"
          f"{(1-total('compact_tokens')/total('full_tokens'))*100:>6.1f}%{total('empty_calls'):>7}")

    longest = max(rows, key=lambda r: r["steps"])
    print(f"\n最长轨迹 {longest['run']}（{longest['steps']} 步）单次调用累计成本：")
    print("  原  ：" + " → ".join(str(x) for x in longest["curve_full"]))
    print("  折叠：" + " → ".join(str(x) for x in longest["curve_fold"]))
    print("  台账：" + " → ".join(str(x) for x in longest["curve_compact"]))

    long_rows = [r for r in rows if r["steps"] >= 10]
    if long_rows:
        print(f"\n≥10 步的 {len(long_rows)} 条轨迹：折叠平均降 "
              f"{(1-sum(r['fold_tokens'] for r in long_rows)/sum(r['full_tokens'] for r in long_rows))*100:.1f}%，"
              f"台账平均降 "
              f"{(1-sum(r['compact_tokens'] for r in long_rows)/sum(r['full_tokens'] for r in long_rows))*100:.1f}%")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"fixed_overhead": round(overhead), "runs": rows},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
