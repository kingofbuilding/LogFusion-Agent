"""Explicitly simulated synthesis for showing the full pipeline without API credentials."""
from __future__ import annotations

import json
from types import SimpleNamespace

from .judgment import LLMJudgment


class _SimulatedCompletions:
    def create(self, **kwargs):
        context = json.loads(kwargs["messages"][-1]["content"])
        references = [case["case_id"] for case in context["reference_cases"][:1]]
        claims = [{"kind": "hypothesis", "statement": f["statement"],
                   "evidence_ids": f["evidence_ids"], "case_ids": references}
                  for f in context["rule_findings"] if f["evidence_ids"]][:8]
        payload = {"assessment": "suspicious" if claims else "insufficient_evidence", "claims": claims,
                   "recommendations": [{"action": "人工核对成功登录的授权情况，并补充会话审计记录。",
                                        "rationale": "现有日志可提示关联，但无法单独确认是否未经授权。",
                                        "evidence_ids": claims[-1]["evidence_ids"] if claims else [],
                                        "case_ids": references}],
                   "uncertainties": ["这是模拟模型的链路演示，不代表真实 LLM 研判质量。",
                                     "同账号和同主机的特权命令不能证明属于同一登录会话。",
                                     "缺少授权核对与完整会话审计，无法确认入侵成功。"]}
        return SimpleNamespace(usage=SimpleNamespace(total_tokens=0), choices=[SimpleNamespace(
            message=SimpleNamespace(tool_calls=[SimpleNamespace(function=SimpleNamespace(
                name="publish_judgment", arguments=json.dumps(payload, ensure_ascii=False)))]))])


class SimulatedJudgment(LLMJudgment):
    def __init__(self):
        super().__init__(SimpleNamespace(chat=SimpleNamespace(completions=_SimulatedCompletions())), "local-simulation")

    def synthesize(self, *args, **kwargs):
        result = super().synthesize(*args, **kwargs)
        result["backend"] = "simulated_llm"
        return result
