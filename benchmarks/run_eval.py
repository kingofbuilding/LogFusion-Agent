"""Run the labelled SSH suite and report per-category metrics.

Usage:
    python -m benchmarks.run_eval                              # rule playbook, offline
    python -m benchmarks.run_eval --groups rule,simulated       # + simulated synthesis chain
    python -m benchmarks.run_eval --groups upstream             # upstream detector, one-shot
    python -m benchmarks.run_eval --groups llm --repeats 3 --limit 20
    python -m benchmarks.run_eval --groups agent+upstream --limit 20

Groups:
    rule            fixed SSH playbook, no model                 (plan group B)
    simulated       playbook + local deterministic judgment      (chain demo, not model quality)
    llm             LLM tool calling + LLM synthesis             (plan group C)
    upstream        migrated upstream detector, one-shot         (plan group A)
    agent+upstream  LLM agent + upstream detector + vector RAG   (plan group D)

Groups A and D need the migrated artifacts under ``models/`` and ``data/vectors/``; see
docs/EVAL_REPORT.md for provenance and the limitations of the hash-embedding RAG index.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.agent.engine import InvestigationAgent, is_empty_observation
from src.agent.events import EventStore
from src.agent.planner import RulePlanner
from src.agent.tools import ROOT

CASES_DIR = ROOT / "benchmarks/cases"
RESULTS_DIR = ROOT / "benchmarks/results"


def git_sha() -> str:
    """Read HEAD without spawning git, so results record exactly which code produced them."""
    head = ROOT / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith("ref: "):
            ref = ROOT / ".git" / text[5:]
            return ref.read_text(encoding="utf-8").strip() if ref.exists() else ""
        return text
    except OSError:
        return ""

GROUPS = ("rule", "simulated", "llm", "upstream", "agent+upstream")

PER_GROUP_BUDGET = {"rule": {"max_steps": 16, "max_seconds": 60, "max_tokens": 24_000},
                    "simulated": {"max_steps": 16, "max_seconds": 60, "max_tokens": 24_000},
                    # 16 steps is the schema-fixed budget; C0 (12 steps, old schema) is kept only
                    # as historical evidence in docs/EVAL_REPORT.md.
                    "llm": {"max_steps": 16, "max_seconds": 120, "max_tokens": 130_000},
                    # Group A performs a single detector call; the loop budget is unused.
                    "upstream": {"max_steps": 1, "max_seconds": 1, "max_tokens": 1},
                    # Same 16-step budget as the schema-fixed C run so only the tool set differs.
                    "agent+upstream": {"max_steps": 16, "max_seconds": 120, "max_tokens": 130_000}}


def derived_verdict(findings) -> str:
    """The conclusion layer is rule-based in every group; groups differ only in evidence gathered."""
    if any(f.kind == "success_after_failures" for f in findings):
        return "correlated_success"
    if any(f.kind in ("suspected_bruteforce", "suspected_distributed_spray",
                      "suspected_account_stuffing", "suspected_low_and_slow") for f in findings):
        return "no_correlated_success"
    return "insufficient_evidence"


def _judgment_evidence(judgment: dict) -> set[str]:
    if judgment.get("status") != "completed":
        return set()
    content = judgment["content"]
    ids = {eid for claim in content["claims"] for eid in claim["evidence_ids"]}
    ids |= {eid for action in content["recommendations"] for eid in action["evidence_ids"]}
    return ids


def _rationale_rate(trace) -> float | None:
    """Share of action steps that state why they were taken."""
    actions = [item for item in trace if item.get("stage") not in ("plan", "gate", "wrap_up")
               and item.get("tool") != "synthesize_judgment"]
    if not actions:
        return None
    return round(sum(bool(item.get("rationale")) for item in actions) / len(actions), 4)


def score_case(meta: dict, result) -> dict:
    expected = meta["expected"]
    must_find = expected["must_find_event_ids"]
    observed = {event["event_id"] for event in result.evidence}
    cited = {eid for finding in result.findings for eid in finding.evidence_ids}
    linked = {eid for finding in result.findings if finding.kind == "success_after_failures"
              for eid in finding.evidence_ids}
    judgment_ids = _judgment_evidence(result.judgment)

    def recall(ids, pool):
        return round(len(set(ids) & pool) / len(ids), 4) if ids else None

    actual = derived_verdict(result.findings)
    hits = set(must_find) & observed
    return {
        "case_id": meta["case_id"],
        "category": meta["category"],
        "verdict_expected": expected["verdict"],
        "verdict_actual": actual,
        "verdict_ok": actual == expected["verdict"],
        "evidence_recall": recall(must_find, observed),
        # Probe-level precision: how much of what the agent looked at is actually labelled.
        # Coarse window evidence scores low here even when recall is 1.0.
        "evidence_precision": round(len(hits) / len(observed), 4) if must_find and observed else None,
        "link_recall": recall(expected.get("must_link_event_ids") or [], linked),
        # Real-log cases only declare evidence and verdict; missing keys mean "not applicable".
        "false_links": sorted(set(expected.get("must_not_link_event_ids") or []) & cited),
        "judgment_decoy_citations": sorted(set(expected.get("must_not_link_event_ids") or []) & judgment_ids),
        "pair_violations": [pair for pair in expected.get("must_not_pair") or []
                            if any(set(pair) <= set(f.evidence_ids) for f in result.findings
                                   if f.kind == "success_after_failures")],
        "evidence_count": len(observed),
        "tool_steps": len([t for t in result.trace if t.get("stage") not in ("plan", "gate", "wrap_up", "hint")
                           and t["tool"] != "synthesize_judgment"]),
        "tool_errors": sum(bool(t.get("error")) for t in result.trace),
        "tool_error_types": sorted({t["error"] for t in result.trace if t.get("error")}),
        "tokens": result.tokens_used,
        "tokens_cached": getattr(result, "tokens_cached", 0),
        "empty_calls": sum(1 for t in result.trace
                           if not t.get("error") and t.get("stage") not in ("plan", "gate", "wrap_up", "hint")
                           and is_empty_observation(t.get("result"))),
        "elapsed": result.elapsed_seconds,
        "status": result.status,
        "stop_reason": result.stop_reason,
        "judgment_status": result.judgment.get("status", "not_requested"),
        "claims": len(result.judgment["content"]["claims"]) if result.judgment.get("status") == "completed" else 0,
        "gate_triggers": getattr(result, "gate_triggers", 0),
        "gate_terminal_refusals": sum(1 for t in result.trace
                                      if t["tool"] == "completeness_gate" and t.get("terminal")),
        "rationale_rate": _rationale_rate(result.trace),
        "hypothesis_rate": (round(sum(1 for item in result.plan if item["status"] != "open") / len(result.plan), 4)
                            if getattr(result, "plan", None) else None),
    }


def _mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 4) if values else None


def summarize(rows: list[dict]) -> dict:
    def mislinks(row):
        return row.get("false_links") or []

    def decoys(row):
        return row.get("judgment_decoy_citations") or row.get("judgment_false_links") or []

    summary = {"cases": len(rows),
               "verdict_accuracy": _mean([r["verdict_ok"] for r in rows]),
               "evidence_recall": _mean([r["evidence_recall"] for r in rows]),
               "evidence_precision": _mean([r.get("evidence_precision") for r in rows]),
               "link_recall": _mean([r["link_recall"] for r in rows]),
               "mislink_cases": sum(bool(mislinks(r)) for r in rows),
               "judgment_mislink_cases": sum(bool(decoys(r)) for r in rows),
               "pair_violations": sum(bool(r["pair_violations"]) for r in rows),
               "mean_tool_steps": _mean([r["tool_steps"] for r in rows]),
               "mean_tokens": _mean([r["tokens"] for r in rows]),
               "mean_tokens_cached": _mean([r.get("tokens_cached", 0) for r in rows]),
               "mean_empty_calls": _mean([r.get("empty_calls", 0) for r in rows]),
               "tool_error_rate": _mean([bool(r.get("tool_errors", 0)) for r in rows]),
               "tool_error_types": {name: sum(name in r.get("tool_error_types", []) for r in rows)
                                    for name in sorted({e for r in rows for e in r.get("tool_error_types", [])})},
               "stop_reasons": {reason: sum(r.get("stop_reason") == reason for r in rows)
                                for reason in sorted({r.get("stop_reason", "unknown") for r in rows})},
               "completed_rate": _mean([r["status"] == "completed" for r in rows]),
               "partial_rate": _mean([r["status"] == "completed_partial" for r in rows]),
               "completion_rate": _mean([r["status"] in ("completed", "completed_partial") for r in rows]),
               "mean_gate_triggers": _mean([r.get("gate_triggers", 0) for r in rows]),
               "mean_gate_terminal_refusals": _mean([r.get("gate_terminal_refusals", 0) for r in rows]),
               "rationale_rate": _mean([r.get("rationale_rate") for r in rows]),
               "hypothesis_rate": _mean([r.get("hypothesis_rate") for r in rows]),
               "judgment_completed_rate": _mean([r["judgment_status"] == "completed" for r in rows])}
    summary["by_category"] = {}
    by_category: dict[str, list[dict]] = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)
    for category, items in by_category.items():
        summary["by_category"][category] = {
            "cases": len(items),
            "verdict_accuracy": _mean([r["verdict_ok"] for r in items]),
            "evidence_recall": _mean([r["evidence_recall"] for r in items]),
            "evidence_precision": _mean([r.get("evidence_precision") for r in items]),
            "link_recall": _mean([r["link_recall"] for r in items]),
            "mislink_cases": sum(bool(mislinks(r)) for r in items),
            "evidence_count": _mean([r["evidence_count"] for r in items]),
            "mean_tool_steps": _mean([r["tool_steps"] for r in items]),
            "mean_tokens": _mean([r["tokens"] for r in items]),
            "completed_rate": _mean([r["status"] == "completed" for r in items]),
            "completion_rate": _mean([r["status"] in ("completed", "completed_partial") for r in items])}
    return summary


def _upstream_tools(shared: dict):
    """Lazily build the migrated upstream detector and vector retriever once per run."""
    if "detector" not in shared:
        from src.agent.adapters import upstream_detector, upstream_retriever
        shared["detector"] = upstream_detector()
        shared["retriever"] = upstream_retriever()
    return shared["detector"], shared["retriever"]


def _build_agent(group: str, store: EventStore, shared: dict, token_override: int = 0):
    from src.agent.demo import SimulatedJudgment
    from src.agent.judgment import LLMJudgment
    from src.agent.planner import LLMPlanner
    from src.agent.tools import InvestigationTools

    budget = dict(PER_GROUP_BUDGET[group])
    if token_override:
        budget["max_tokens"] = token_override
    if group in ("agent+upstream", "upstream"):
        detector, retriever = _upstream_tools(shared)
        tools = InvestigationTools(store, detector=detector, retriever=retriever)
        if group == "upstream":
            from benchmarks.oneshot import run_upstream_once
            return ("oneshot", run_upstream_once, tools)
    else:
        tools = InvestigationTools(store)
    if group == "rule":
        return InvestigationAgent(store, planner=RulePlanner(), tools=tools, **budget)
    if group == "simulated":
        return InvestigationAgent(store, planner=RulePlanner(), tools=tools, reviewer=SimulatedJudgment(), **budget)
    if "llm" not in shared:
        planner = LLMPlanner.from_env(timeout=20)
        shared["llm"] = planner
        shared["judge"] = LLMJudgment(planner.client, planner.model, planner.request_options)
    return InvestigationAgent(store, planner=shared["llm"], tools=tools, reviewer=shared["judge"], **budget)


def _run_once(agent, goal: str):
    if isinstance(agent, tuple) and agent[0] == "oneshot":
        _, run_upstream_once, tools = agent
        return run_upstream_once(tools.store, tools.detector, tools.retriever, goal=goal)
    return agent.run(goal)


def _exception_row(meta: dict, exc: Exception) -> dict:
    return {"case_id": meta["case_id"], "category": meta["category"],
            "verdict_expected": meta["expected"]["verdict"], "verdict_actual": "",
            "verdict_ok": False, "evidence_recall": None, "evidence_precision": None,
            "link_recall": None, "false_links": [], "judgment_decoy_citations": [],
            "pair_violations": [], "evidence_count": 0, "tool_steps": 0, "tool_errors": 0,
            "tool_error_types": [], "tokens": 0, "elapsed": 0.0, "status": "exception",
            "stop_reason": type(exc).__name__, "judgment_status": "not_requested", "claims": 0,
            "gate_triggers": 0, "rationale_rate": None, "hypothesis_rate": None}


def run_group(group: str, cases: list[dict], repeats: int, progress=print, cases_dir: Path = CASES_DIR,
              token_override: int = 0) -> dict:
    shared: dict = {}
    rows = []
    streak = 0
    aborted = ""
    for meta in cases:
        store = EventStore.from_path(cases_dir / meta["log_file"])
        for attempt in range(1, repeats + 1):
            # Fresh tools/agent per attempt: the engine resets per-run state, and rebuilding also
            # guarantees no evidence dictionary is shared between cases.
            try:
                agent = _build_agent(group, store, shared, token_override)
                result = _run_once(agent, meta["goal"])
            except Exception as exc:  # provider outage must not silently become a "wrong verdict"
                rows.append(_exception_row(meta, exc))
                streak += 1
                progress(f"  {meta['case_id']} #{attempt} EXCEPTION {type(exc).__name__}")
                if streak >= 3:
                    aborted = f"连续 {streak} 次调用失败（{type(exc).__name__}），已中止批次"
                    break
                continue
            row = score_case(meta, result)
            row["attempt"] = attempt
            rows.append(row)
            # A provider outage shows up as an engine-level error, not an exception.
            provider_failure = row["status"] == "error" and row["stop_reason"].startswith("planner_error")
            streak = streak + 1 if provider_failure else 0
            progress(f"  {meta['case_id']} #{attempt} {row['status']}/{row['stop_reason']} "
                     f"verdict={'ok' if row['verdict_ok'] else 'MISS'} "
                     f"recall={row['evidence_recall']} prec={row['evidence_precision']} "
                     f"steps={row['tool_steps']} tokens={row['tokens']}")
            if streak >= 3:
                aborted = f"连续 {streak} 次模型调用失败（{row['stop_reason']}），已中止批次"
                break
        if aborted:
            break
    data = {"group": group, "repeats": repeats, "cases": rows, "summary": summarize(rows)}
    if aborted:
        data["aborted"] = aborted
    return data


def markdown_table(group: str, summary: dict) -> str:
    def fmt(value, digits=2):
        return "—" if value is None else f"{value:.{digits}f}"

    lines = [f"### 组 {group}（{summary['cases']} 次运行）", "",
             "| 类别 | 用例数 | 结论正确率 | 证据召回 | 证据精度 | 关联召回 | 误关联用例 | 平均步数 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for category, row in summary["by_category"].items():
        lines.append(f"| {category} | {row['cases']} | {fmt(row['verdict_accuracy'])} | "
                     f"{fmt(row['evidence_recall'])} | {fmt(row['evidence_precision'])} | "
                     f"{fmt(row['link_recall'])} | {row['mislink_cases']} | {fmt(row['mean_tool_steps'], 1)} |")
    lines += ["", f"总体：结论正确率 {fmt(summary['verdict_accuracy'])}，证据召回 {fmt(summary['evidence_recall'])}，"
                  f"证据精度 {fmt(summary['evidence_precision'])}，关联召回 {fmt(summary['link_recall'])}，"
                  f"误关联 {summary['mislink_cases']} 例，平均 {fmt(summary['mean_tool_steps'], 1)} 步，"
                  f"平均 {fmt(summary['mean_tokens'], 0)} tokens（缓存命中 {fmt(summary['mean_tokens_cached'], 0)}），"
                  f"空结果调用 {fmt(summary['mean_empty_calls'], 1)} 次/次，"
                  f"完成率 {fmt(summary['completion_rate'])}（完全完成 {fmt(summary['completed_rate'])}，部分完成 {fmt(summary['partial_rate'])}），"
                  f"闸门 {fmt(summary['mean_gate_triggers'], 1)} 次/次（终局拒绝 {fmt(summary['mean_gate_terminal_refusals'], 1)}），"
                  f"理由覆盖 {fmt(summary['rationale_rate'])}，"
                  f"假设结论率 {fmt(summary['hypothesis_rate'])}，"
                  f"工具报错率 {fmt(summary['tool_error_rate'])}，停止原因 {summary['stop_reasons']}，"
                  f"错误类型 {summary['tool_error_types']}。", ""]
    return "\n".join(lines)


def main() -> int:
    # The upstream detector logs every model load at INFO; keep evaluation output readable.
    import logging
    logging.disable(logging.INFO)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="运行 LogFusion-Agent SSH 评测")
    parser.add_argument("--groups", default="rule")
    parser.add_argument("--repeats", type=int, default=1, help="每条用例重复次数（LLM 建议 3）")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条用例（0 为全部）")
    parser.add_argument("--max-tokens", type=int, default=0,
                        help="覆盖该组的 token 预算（0 为默认；真实调用前先用 --estimate 估价）")
    parser.add_argument("--estimate", action="store_true",
                        help="只估算 token 与费用，不发出任何请求")
    parser.add_argument("--case-ids", default="", help="逗号分隔的用例 ID")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR,
                        help="用例目录；规则失效用例在 benchmarks/cases_hard")
    args = parser.parse_args()

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    unknown = set(groups) - set(GROUPS)
    if unknown:
        parser.error(f"未知分组: {sorted(unknown)}；可选 {list(GROUPS)}")
    if args.repeats < 1:
        parser.error("--repeats 至少为 1")

    cases_dir = args.cases_dir
    case_glob = {"cases_hard": "hard-*.json", "cases_real": "real-*.json"}.get(cases_dir.name, "ssh-*.json")
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob(case_glob))]
    if not metas:
        print(f"未找到用例：{cases_dir}；请先运行 python -m benchmarks.generate_cases 或 generate_hard_cases")
        return 2
    if args.case_ids:
        wanted = {c.strip() for c in args.case_ids.split(",") if c.strip()}
        metas = [m for m in metas if m["case_id"] in wanted]
    if args.limit:
        metas = metas[:args.limit]
    if not metas:
        print("过滤后没有用例")
        return 2

    print(f"用例 {len(metas)} 条；分组 {groups}；重复 {args.repeats} 次；代码 {git_sha()[:12]}；预算 {PER_GROUP_BUDGET}")

    if args.estimate:
        # Cost estimate only; no request is made. The 0.8 factor is the observed ratio between
        # spent tokens and the configured budget on recorded LLM runs (models usually wrap up early).
        rate = 2.6 / 1e6          # input 2 CNY/M * 0.9 + output 8 CNY/M * 0.1
        total = 0.0
        for group in groups:
            budget = dict(PER_GROUP_BUDGET[group])
            if args.max_tokens:
                budget["max_tokens"] = args.max_tokens
            cap = budget["max_tokens"]
            per_case = cap * 0.8 if group in ("llm", "agent+upstream") else 0.0
            tok = len(metas) * args.repeats * per_case
            total += tok
            print(f"  {group:15s} 预算 {cap:>7,}/条 → {tok/1e6:5.2f}M token ≈ {tok*rate:5.2f} 元")
        print(f"  合计约 {total/1e6:.2f}M token ≈ {total*rate:.2f} 元"
              f"（按输入 2 元/M、输出 8 元/M、输出占 10% 估算；前缀命中缓存时更低）")
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {"suite": str(cases_dir.relative_to(ROOT)) if cases_dir.is_relative_to(ROOT) else str(cases_dir),
               "stamp": stamp, "repeats": args.repeats,
               "git_sha": git_sha(), "budgets": PER_GROUP_BUDGET, "groups": {}}
    for group in groups:
        print(f"\n== 组 {group} ==")
        data = run_group(group, metas, args.repeats, cases_dir=cases_dir,
                         token_override=args.max_tokens)
        payload["groups"][group] = data
        print(markdown_table(group, data["summary"]))
        if data.get("aborted"):
            # Do not publish a summary that mostly measures a provider outage.
            print(f"批次中止：{data['aborted']}；未写入结果文件。")
            return 2
    # Include the suite name: two runs started in the same second used to overwrite each other.
    target = args.out / f"eval_{cases_dir.name}_{'_'.join(groups)}_{stamp}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
