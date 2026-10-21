from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import upstream_detector, upstream_retriever
from .engine import InvestigationAgent
from .events import EventStore
from .planner import LLMPlanner
from .tools import InvestigationTools, ROOT


def main():
    parser = argparse.ArgumentParser(description="LogFusion-Agent：证据驱动的安全日志调查")
    parser.add_argument("--input", type=Path, help="UTF-8 .log/.txt/.jsonl/.json/.csv")
    parser.add_argument("--demo", action="store_true", help="使用合成 SSH 场景，无需模型权重或密钥")
    parser.add_argument("--mode", choices=["rule", "llm"], default="rule")
    parser.add_argument("--goal", default="调查是否存在 SSH 暴力破解、后续成功登录及可疑账户活动")
    parser.add_argument("--with-detector", action="store_true", help="调用原项目已训练融合模型")
    parser.add_argument("--vector-rag", action="store_true", help="调用原项目已构建向量索引")
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--max-seconds", type=float, default=90)
    parser.add_argument("--max-tokens", type=int, default=24_000)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/investigations")
    args = parser.parse_args()
    if args.demo == bool(args.input):
        parser.error("选择 --demo 或 --input，两者只能选一个")
    try:
        store = EventStore.from_path(ROOT / "data/demo/ssh_investigation.jsonl" if args.demo else args.input)
        planner = LLMPlanner.from_env(timeout=min(20, args.max_seconds)) if args.mode == "llm" else None
        tools = InvestigationTools(store, detector=upstream_detector() if args.with_detector else None,
                                   retriever=upstream_retriever() if args.vector_rag else None)
        result = InvestigationAgent(store, planner=planner, tools=tools, max_steps=args.max_steps,
                                   max_seconds=args.max_seconds, max_tokens=args.max_tokens).run(
            args.goal, on_step=lambda t: print(f"[{t['step']}] {t['tool']} {'ERROR' if t.get('error') else 'OK'}"))
        target = result.save(args.output)
        print(f"Mode: {result.mode}; status: {result.status}; stop: {result.stop_reason}")
        print(f"Findings: {len(result.findings)}; evidence: {len(result.evidence)}; tokens: {result.tokens_used}")
        print(f"Report: {target / 'report.md'}")
        return 0 if result.status == "completed" else 2
    except (ValueError, OSError, ImportError) as exc:
        # Configuration errors are sanitized; never print client credentials or raw SDK responses.
        print(f"Unable to start investigation: {type(exc).__name__}. Check input, optional dependencies, model files and environment configuration.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
