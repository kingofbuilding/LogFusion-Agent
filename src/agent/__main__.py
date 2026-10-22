from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import upstream_detector, upstream_retriever
from .engine import InvestigationAgent
from .events import EventStore
from .planner import LLMPlanner
from .judgment import LLMJudgment
from .demo import SimulatedJudgment
from .tools import InvestigationTools, ROOT

# Three inputs, three different trajectories: the same agent, not three scripts.
DEMO_SUITE = [
    ("经典暴力破解", ROOT / "data/demo/ssh_investigation.jsonl",
     "聚合出失败簇 → 查后续成功登录 → 查上下文 → 出报告",
     "同样的固定剧本，用来对比"),
    ("分布式喷洒", ROOT / "benchmarks/cases_hard/hard-001.jsonl",
     "聚合无簇 → 结束（规则剧本没有自适应分支）",
     "聚合无簇 → 按账号汇总发现跨 IP 失败 → 查后续成功登录"),
    ("良性重试", ROOT / "benchmarks/cases/ssh-032.jsonl",
     "聚合无簇 → 确认低于阈值 → 提前结束，不做无谓查询",
     "同上，不应出现无谓查询"),
]


def _agent_for(args, store):
    llm = LLMPlanner.from_env(timeout=min(20, args.max_seconds)) if args.mode == "llm" or args.llm_judge else None
    planner = llm if args.mode == "llm" else None
    reviewer = LLMJudgment(llm.client, llm.model, llm.request_options) if llm else None
    if args.mode == "simulated":
        reviewer = SimulatedJudgment()
    tools = InvestigationTools(store, detector=upstream_detector() if args.with_detector else None,
                               retriever=upstream_retriever() if args.vector_rag else None)
    return InvestigationAgent(store, planner=planner, tools=tools, max_steps=args.max_steps,
                              max_seconds=args.max_seconds, max_tokens=args.max_tokens, reviewer=reviewer)


def run_suite(args) -> int:
    """Run the three showcase inputs and print the trajectory each one takes."""
    print(f"模式：{args.mode}；预算：{args.max_steps} 步 / {args.max_tokens} tokens\n")
    rows = []
    for name, path, rule_expected, llm_expected in DEMO_SUITE:
        expected = llm_expected if args.mode == "llm" else rule_expected
        if not path.exists():
            print(f"跳过 {name}：缺少 {path}")
            continue
        store = EventStore.from_path(path)
        result = _agent_for(args, store).run(args.goal)
        target = result.save(args.output)
        statuses = ", ".join(f"{item['id']}={item['status']}" for item in result.plan) or "无计划"
        print(f"=== {name} ===（预期：{expected}）")
        print(f"状态：{result.status}/{result.stop_reason}；发现：{', '.join(f.kind for f in result.findings)}")
        print(f"假设：{statuses}；完整性闸门：{result.gate_triggers} 次；tokens：{result.tokens_used}")
        for entry in result.trace:
            if entry["tool"] in ("plan", "completeness_gate"):
                continue
            reason = f" — {entry['rationale']}" if entry.get("rationale") else ""
            print(f"  {entry['step']}. {entry['tool']}{reason}")
        print(f"报告：{target / 'report.md'}\n")
        rows.append((name, result, expected))
    if args.mode != "llm":
        print("提示：规则模式展示的是基线轨迹；用 --mode llm 可看到模型自行改用 group_by / 检测器。\n")
    if rows:
        print("=== 轨迹对比 ===")
        for name, result, expected in rows:
            actions = [t for t in result.trace if t.get("stage") not in ("plan", "gate", "wrap_up")]
            completed = "是" if result.status in ("completed", "completed_partial") else "否"
            print(f"- {name}：{len(actions)} 步，状态 {result.status}，出报告 {completed}，闸门 {result.gate_triggers} 次")
    return 0


def main():
    parser = argparse.ArgumentParser(description="LogFusion-Agent：证据驱动的安全日志调查")
    parser.add_argument("--input", type=Path, help="UTF-8 .log/.txt/.jsonl/.json/.csv")
    parser.add_argument("--demo", action="store_true", help="使用合成 SSH 场景，无需模型权重或密钥")
    parser.add_argument("--demo-suite", action="store_true", help="依次运行三种输入，展示不同轨迹")
    parser.add_argument("--mode", choices=["rule", "llm", "simulated"], default="rule",
                        help="simulated 为零网络模拟研判，不代表真实 LLM")
    parser.add_argument("--llm-judge", action="store_true", help="规则调查后调用 LLM 综合研判；llm 模式自动启用")
    parser.add_argument("--goal", default="调查是否存在 SSH 暴力破解、后续成功登录及可疑账户活动")
    parser.add_argument("--with-detector", action="store_true", help="调用原项目已训练融合模型")
    parser.add_argument("--vector-rag", action="store_true", help="调用原项目已构建向量索引")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--max-seconds", type=float, default=90)
    parser.add_argument("--max-tokens", type=int, default=24_000)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/investigations")
    args = parser.parse_args()
    if args.demo_suite:
        if args.input:
            parser.error("--demo-suite 与 --input 不能同时使用")
        return run_suite(args)
    if args.demo == bool(args.input):
        parser.error("选择 --demo 或 --input，两者只能选一个")
    if args.mode == "simulated" and args.llm_judge:
        parser.error("模拟模式不能与 --llm-judge 同时使用")
    try:
        store = EventStore.from_path(ROOT / "data/demo/ssh_investigation.jsonl" if args.demo else args.input)
        agent = _agent_for(args, store)
        result = agent.run(
            args.goal, on_step=lambda t: print(f"[{t['step']}] {t['tool']} {'ERROR' if t.get('error') else 'OK'}"))
        target = result.save(args.output)
        print(f"Mode: {result.mode}; status: {result.status}; stop: {result.stop_reason}")
        print(f"Findings: {len(result.findings)}; evidence: {len(result.evidence)}; tokens: {result.tokens_used}")
        print(f"LLM judgment: {result.judgment['status']}")
        print(f"Report: {target / 'report.md'}")
        return 0 if result.status in ("completed", "completed_partial") else 2
    except (ValueError, OSError, ImportError) as exc:
        # Configuration errors are sanitized; never print client credentials or raw SDK responses.
        print(f"Unable to start investigation: {type(exc).__name__}. Check input, optional dependencies, model files and environment configuration.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
