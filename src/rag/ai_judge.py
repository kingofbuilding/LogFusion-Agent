from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.utils import Config, Logger

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


@dataclass
class JudgeResult:
    """One AI-assisted judgment result."""

    verdict: str
    confidence: str
    reason: str
    advice: str
    consistency: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "ai_verdict": self.verdict,
            "ai_confidence": self.confidence,
            "ai_reason": self.reason,
            "ai_advice": self.advice,
            "ai_consistency": self.consistency,
        }


class AIJudge:
    """AI helper for per-log Q&A and incident report generation."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        load_dotenv()

        self.use_llm = bool(config.get("ai_judge.use_llm", False))
        self.provider = str(config.get("ai_judge.provider", "deepseek") or "deepseek")
        self.profile_name = str(config.get("ai_judge.active_profile", config.get("ai_judge.default_profile", "default")) or "default")
        self.model = str(config.get("ai_judge.model", config.get("rag.llm.model", "deepseek-chat")))
        self.temperature = float(config.get("ai_judge.temperature", 0.2))
        self.max_tokens = int(config.get("ai_judge.max_tokens", 300))
        self.qa_max_tokens = int(config.get("ai_judge.qa_max_tokens", max(self.max_tokens, 3000)))
        self.report_max_tokens = int(config.get("ai_judge.report_max_tokens", max(self.max_tokens, 8000)))
        self.request_timeout = float(config.get("ai_judge.request_timeout", 45))

        self.client: Optional[OpenAI] = None
        self.mode = "rule"
        self.mode_reason = "LLM \u672a\u542f\u7528"
        if self.use_llm:
            self.client, self.mode_reason = self._build_openai_client()
            if self.client is not None:
                self.mode = "llm"
                self.mode_reason = f"LLM \u5df2\u542f\u7528: model={self.model}"
            else:
                self.mode = "rule"
                self.logger.warning(f"LLM \u521d\u59cb\u5316\u5931\u8d25\uff0c\u56de\u9000\u89c4\u5219\u6a21\u5f0f: {self.mode_reason}")

    def _resolve_api_key(self) -> str:
        return (
            str(self.config.get("ai_judge.api_key", "")).strip()
            or os.getenv("AI_JUDGE_API_KEY", "").strip()
            or os.getenv("DEEPSEEK_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )

    def _resolve_base_url(self) -> str:
        base_url = (
            str(self.config.get("ai_judge.base_url", "")).strip()
            or os.getenv("AI_JUDGE_BASE_URL", "").strip()
            or os.getenv("DEEPSEEK_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
        )
        if not base_url and self.model.lower().startswith("deepseek"):
            base_url = "https://api.deepseek.com"
        return base_url

    def _build_openai_client(self):
        if OpenAI is None:
            return None, "\u672a\u5b89\u88c5 openai SDK\uff0c\u8bf7\u5148\u5b89\u88c5 openai \u5305"

        api_key = self._resolve_api_key()
        base_url = self._resolve_base_url()
        if not api_key:
            return None, "\u7f3a\u5c11 API Key\uff0c\u8bf7\u914d\u7f6e AI_JUDGE_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY"

        try:
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url), "ok"
            return OpenAI(api_key=api_key), "ok"
        except Exception as exc:  # pragma: no cover
            return None, f"\u521d\u59cb\u5316\u5ba2\u6237\u7aef\u5931\u8d25: {exc}"

    @staticmethod
    def _mask_secret(value: str) -> str:
        text = str(value or '').strip()
        if not text:
            return ''
        if len(text) <= 8:
            return '*' * len(text)
        return f"{text[:4]}{'*' * max(4, len(text) - 8)}{text[-4:]}"

    def get_runtime_status(self) -> Dict[str, str]:
        api_key = self._resolve_api_key()
        base_url = self._resolve_base_url()
        key_source = 'config' if str(self.config.get('ai_judge.api_key', '')).strip() else 'env' if api_key else 'missing'
        return {
            "mode": self.mode,
            "reason": self.mode_reason,
            "use_llm": str(self.use_llm),
            "provider": self.provider,
            "profile": self.profile_name,
            "model": self.model,
            "base_url": base_url,
            "base_url_display": base_url or '-',
            "api_key_masked": self._mask_secret(api_key),
            "key_source": key_source,
            "qa_max_tokens": str(self.qa_max_tokens),
            "report_max_tokens": str(self.report_max_tokens),
            "request_timeout": str(self.request_timeout),
        }

    def test_connection(self) -> Dict[str, str]:
        api_key = self._resolve_api_key()
        base_url = self._resolve_base_url()
        if not self.use_llm:
            return {
                'success': 'false',
                'message': 'LLM 未启用，当前为规则模式。',
                'provider': self.provider,
                'profile': self.profile_name,
                'model': self.model,
                'base_url': base_url,
            }
        if self.client is None:
            return {
                'success': 'false',
                'message': self.mode_reason,
                'provider': self.provider,
                'profile': self.profile_name,
                'model': self.model,
                'base_url': base_url,
            }
        try:
            test_kwargs = {
                "model": self.model,
                "max_tokens": 8,
                "timeout": min(self.request_timeout, 15),
                "messages": [
                    {"role": "system", "content": "Reply with OK only."},
                    {"role": "user", "content": "OK"},
                ],
            }
            if self.temperature is not None:
                test_kwargs["temperature"] = self.temperature
            resp = self.client.chat.completions.create(**test_kwargs)
            text = (resp.choices[0].message.content or '').strip()
            return {
                'success': 'true',
                'message': text or '连接成功',
                'provider': self.provider,
                'profile': self.profile_name,
                'model': self.model,
                'base_url': base_url,
            }
        except Exception as exc:
            self.logger.warning(f"LLM 连通性测试失败: {exc}")
            return {
                'success': 'false',
                'message': str(exc),
                'provider': self.provider,
                'profile': self.profile_name,
                'model': self.model,
                'base_url': base_url,
            }

    @staticmethod
    def _consistency_label(stat: float, temp: float, sem: float, threshold: float = 0.6) -> str:
        votes = [stat >= threshold, temp >= threshold, sem >= threshold]
        cnt = sum(votes)
        if cnt == 3:
            return "\u9ad8\u4e00\u81f4"
        if cnt == 2:
            return "\u90e8\u5206\u4e00\u81f4"
        if cnt == 1:
            return "\u4f4e\u4e00\u81f4"
        return "\u4e0d\u4e00\u81f4"

    def _rule_judge(
        self,
        stat_score: float,
        temporal_score: float,
        semantic_score: float,
        fusion_score: float,
        template_text: str = "",
    ) -> JudgeResult:
        consistency = self._consistency_label(stat_score, temporal_score, semantic_score)

        if fusion_score >= 0.85 and consistency in {"\u9ad8\u4e00\u81f4", "\u90e8\u5206\u4e00\u81f4"}:
            verdict = "\u9ad8\u98ce\u9669\u5b89\u5168\u4e8b\u4ef6"
            confidence = "\u9ad8"
            reason = "\u591a\u89c6\u56fe\u5bf9\u8be5\u65e5\u5fd7\u8fbe\u6210\u8f83\u9ad8\u4e00\u81f4\u6027\uff0c\u878d\u5408\u7ed3\u679c\u663e\u793a\u5b58\u5728\u660e\u663e\u5b89\u5168\u98ce\u9669\u3002"
            advice = "\u5efa\u8bae\u7acb\u5373\u6838\u67e5\u6e90 IP\u3001\u76f8\u5173\u8d26\u53f7\u4e0e\u53d7\u5f71\u54cd\u8d44\u4ea7\uff0c\u5fc5\u8981\u65f6\u5148\u884c\u9694\u79bb\u6216\u963b\u65ad\u3002"
        elif fusion_score >= 0.65:
            verdict = "\u53ef\u7591\u5b89\u5168\u4e8b\u4ef6"
            confidence = "\u4e2d\u9ad8"
            reason = "\u878d\u5408\u5206\u6570\u8f83\u9ad8\uff0c\u81f3\u5c11\u6709\u4e24\u8def\u4fe1\u53f7\u8868\u73b0\u5f02\u5e38\uff0c\u5177\u5907\u8f83\u5f3a\u590d\u6838\u4ef7\u503c\u3002"
            advice = "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u3001\u6765\u6e90\u5730\u5740\u3001\u65f6\u95f4\u7a97\u53e3\u548c\u540e\u7eed\u52a8\u4f5c\u8fdb\u884c\u8fdb\u4e00\u6b65\u7814\u5224\u3002"
        elif fusion_score >= 0.45:
            verdict = "\u8f7b\u5ea6\u53ef\u7591"
            confidence = "\u4e2d"
            reason = "\u5f53\u524d\u7ed3\u679c\u5b58\u5728\u4e00\u5b9a\u98ce\u9669\u8ff9\u8c61\uff0c\u4f46\u591a\u89c6\u56fe\u4e00\u81f4\u6027\u5c1a\u4e0d\u5145\u5206\u3002"
            advice = "\u5efa\u8bae\u4fdd\u7559\u6837\u672c\u5e76\u7ed3\u5408\u76f8\u90bb\u65e5\u5fd7\u3001\u5386\u53f2\u57fa\u7ebf\u4e0e\u6848\u4f8b\u5e93\u7ed3\u679c\u7ee7\u7eed\u89c2\u5bdf\u3002"
        else:
            verdict = "\u4f4e\u98ce\u9669\u6216\u6b63\u5e38"
            confidence = "\u4f4e"
            reason = "\u5f53\u524d\u591a\u89c6\u56fe\u672a\u5f62\u6210\u660e\u663e\u5f02\u5e38\u5171\u8bc6\uff0c\u6574\u4f53\u98ce\u9669\u8f83\u4f4e\u3002"
            advice = "\u53ef\u5148\u5f52\u6863\u89c2\u5bdf\uff0c\u5982\u540e\u7eed\u51fa\u73b0\u5173\u8054\u544a\u8b66\u518d\u56de\u6eaf\u590d\u6838\u3002"

        t = (template_text or "").lower()
        if "failed password" in t or "invalid user" in t or "user unknown" in t:
            reason += " \u65e5\u5fd7\u4e2d\u51fa\u73b0\u8ba4\u8bc1\u5931\u8d25\u3001\u65e0\u6548\u7528\u6237\u6216\u8d26\u53f7\u63a2\u6d4b\u8ff9\u8c61\u3002"
        elif "accepted password" in t or "accepted publickey" in t:
            reason += " \u65e5\u5fd7\u4e2d\u51fa\u73b0\u6210\u529f\u767b\u5f55\u884c\u4e3a\uff0c\u5e94\u91cd\u70b9\u6838\u67e5\u8d26\u53f7\u5f52\u5c5e\u3001\u6765\u6e90\u5730\u5740\u4e0e\u540e\u7eed\u52a8\u4f5c\u3002"
        elif "permission denied" in t or "unauthorized" in t or "forbidden" in t:
            reason += " \u65e5\u5fd7\u4e2d\u5b58\u5728\u62d2\u7edd\u8bbf\u95ee\u6216\u672a\u6388\u6743\u8bbf\u95ee\u7ebf\u7d22\u3002"
        elif "sudo" in t or "type=execve" in t or "audit(" in t:
            reason += " \u65e5\u5fd7\u4e2d\u5b58\u5728\u63d0\u6743\u547d\u4ee4\u3001\u5ba1\u8ba1\u6267\u884c\u6216\u9ad8\u6743\u9650\u64cd\u4f5c\u75d5\u8ff9\u3002"
        elif "wpscan" in t or "ah01630" in t or "wp-login" in t:
            reason += " \u65e5\u5fd7\u4e2d\u5b58\u5728 Web \u626b\u63cf\u3001\u540e\u53f0\u63a2\u6d4b\u6216\u53d7\u9650\u8d44\u6e90\u8bbf\u95ee\u884c\u4e3a\u3002"

        return JudgeResult(verdict, confidence, reason, advice, consistency)

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def _llm_judge(
        self,
        stat_score: float,
        temporal_score: float,
        semantic_score: float,
        fusion_score: float,
        template_text: str = "",
    ) -> JudgeResult:
        if self.client is None:
            return self._rule_judge(stat_score, temporal_score, semantic_score, fusion_score, template_text)

        prompt = (
            "\u8bf7\u6839\u636e\u4ee5\u4e0b\u591a\u89c6\u56fe\u5206\u6570\u548c\u65e5\u5fd7\u5185\u5bb9\uff0c\u5bf9\u8fd9\u6761\u65e5\u5fd7\u505a\u5b89\u5168\u7814\u5224\uff0c\u5e76\u4e14\u53ea\u8f93\u51fa\u5408\u6cd5 JSON\u3002"
            "JSON \u53ea\u5141\u8bb8\u5305\u542b\u8fd9\u4e94\u4e2a\u952e\uff1averdict\u3001confidence\u3001reason\u3001advice\u3001consistency\u3002"
            "\u8981\u6c42\uff1a"
            "1. verdict \u7528\u7b80\u6d01\u4e2d\u6587\uff1b"
            "2. confidence \u53ea\u80fd\u662f \u9ad8 / \u4e2d\u9ad8 / \u4e2d / \u4f4e\uff1b"
            "3. consistency \u53ea\u80fd\u662f \u9ad8\u4e00\u81f4 / \u90e8\u5206\u4e00\u81f4 / \u4f4e\u4e00\u81f4 / \u4e0d\u4e00\u81f4\uff1b"
            "4. reason \u63a7\u5236\u5728 120 \u5b57\u4ee5\u5185\uff1b"
            "5. advice \u63a7\u5236\u5728 80 \u5b57\u4ee5\u5185\u3002\n\n"
            f"stat_score={stat_score:.4f}\n"
            f"temporal_score={temporal_score:.4f}\n"
            f"semantic_score={semantic_score:.4f}\n"
            f"fusion_score={fusion_score:.4f}\n"
            f"template_text={template_text[:500]}"
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.request_timeout,
                messages=[
                    {"role": "system", "content": "你是严谨的安全日志分析专家，只输出合法 JSON，不要加解释。"},
                    {"role": "user", "content": prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            obj = self._extract_json(text)
            if obj:
                return JudgeResult(
                    verdict=str(obj.get("verdict", "AI \u7814\u5224\u7ed3\u679c")),
                    confidence=str(obj.get("confidence", "\u4e2d")),
                    reason=str(obj.get("reason", ""))[:600],
                    advice=str(obj.get("advice", ""))[:300],
                    consistency=str(obj.get("consistency", self._consistency_label(stat_score, temporal_score, semantic_score))),
                )
            return JudgeResult(
                verdict="AI \u7814\u5224\u7ed3\u679c",
                confidence="\u4e2d",
                reason=text[:600] if text else "LLM \u672a\u8fd4\u56de\u53ef\u89e3\u6790 JSON\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u56de\u7b54\u6458\u8981\u3002",
                advice="\u5efa\u8bae\u7ed3\u5408\u89c4\u5219\u7ed3\u679c\u548c\u6848\u4f8b\u8bc1\u636e\u7ee7\u7eed\u590d\u6838\u3002",
                consistency=self._consistency_label(stat_score, temporal_score, semantic_score),
            )
        except Exception as exc:  # pragma: no cover
            self.logger.warning(f"LLM \u7814\u5224\u8bf7\u6c42\u5931\u8d25\uff0c\u56de\u9000\u89c4\u5219\u6a21\u5f0f: {exc}")
            return self._rule_judge(stat_score, temporal_score, semantic_score, fusion_score, template_text)

    def judge_one(
        self,
        stat_score: float,
        temporal_score: float,
        semantic_score: float,
        fusion_score: float,
        template_text: str = "",
    ) -> Dict[str, str]:
        if self.mode == "llm":
            return self._llm_judge(stat_score, temporal_score, semantic_score, fusion_score, template_text).to_dict()
        return self._rule_judge(stat_score, temporal_score, semantic_score, fusion_score, template_text).to_dict()

    def judge_batch(
        self,
        stat_scores: List[float],
        temporal_scores: List[float],
        semantic_scores: List[float],
        fusion_scores: List[float],
        template_texts: List[str],
    ) -> List[Dict[str, str]]:
        results = []
        for s, t, m, f, txt in zip(stat_scores, temporal_scores, semantic_scores, fusion_scores, template_texts):
            results.append(self.judge_one(float(s), float(t), float(m), float(f), str(txt)))
        return results

    def ask_about_log(self, log_text: str, question: str, context: Optional[Dict] = None) -> str:
        if self.client is None:
            return f"LLM \u5f53\u524d\u4e0d\u53ef\u7528\uff1a{self.mode_reason}"

        ctx = context or {}
        prompt = (
            "\u8bf7\u57fa\u4e8e\u7ed9\u5b9a\u65e5\u5fd7\u548c\u4e0a\u4e0b\u6587\uff0c\u7528\u4e2d\u6587\u76f4\u63a5\u56de\u7b54\u7528\u6237\u95ee\u9898\u3002\n"
            "\u56de\u7b54\u5c3d\u91cf\u6309\u4ee5\u4e0b\u987a\u5e8f\u7ec4\u7ec7\uff1a\n"
            "1. \u98ce\u9669\u5224\u65ad\n"
            "2. \u5173\u952e\u8bc1\u636e\n"
            "3. \u5904\u7f6e\u5efa\u8bae\n"
            "如果信息不足，请明确指出不确定点。\n"
            "RAG 只作为辅助证据：只能引用 context.incident_context.rag_cases 中的高置信案例；若该字段为空或只有 rag_evidence_note，请说明相似案例证据不足，不要把候选参考当成事实依据。\n\n"
            f"log={str(log_text)[:1200]}\n"
            f"context={json.dumps(ctx, ensure_ascii=False)}\n"
            f"question={str(question)[:1000]}"
        )
        try:
            effective_temperature = 1.0 if self.provider == 'custom' and 'kimi' in self.model.lower() else self.temperature
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=effective_temperature,
                max_tokens=self.qa_max_tokens,
                timeout=self.request_timeout,
                messages=[
                    {"role": "system", "content": "你是严谨、克制的安全分析助手，请直接给出中文结论，不要输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
            )
            message = resp.choices[0].message
            text = (getattr(message, 'content', None) or '').strip()
            if not text:
                text = (getattr(message, 'reasoning_content', None) or '').strip()
            finish_reason = getattr(resp.choices[0], 'finish_reason', '')
            if text:
                if str(finish_reason).lower() == 'length':
                    return f"{text}\n\n[提示] 模型输出达到长度上限，回答可能未完整结束；请提高 qa_max_tokens 后重新提交。"
                return text
            return "服务返回空响应，请检查模型是否支持当前问答格式，或尝试缩短问题内容后重试。"
        except Exception as exc:  # pragma: no cover
            self.logger.warning(f"LLM \u95ee\u7b54\u8bf7\u6c42\u5931\u8d25: {exc}")
            return f"LLM \u8bf7\u6c42\u5931\u8d25\uff1a{exc}"

    def generate_incident_report(self, incident: Dict) -> str:
        if self.client is None:
            return f"LLM \u5f53\u524d\u4e0d\u53ef\u7528\uff1a{self.mode_reason}"

        incident = incident or {}
        prompt = (
            "\u8bf7\u6839\u636e\u7ed9\u5b9a\u4e8b\u4ef6\u5bf9\u8c61\uff0c\u8f93\u51fa\u4e00\u4efd\u4e2d\u6587\u5b89\u5168\u4e8b\u4ef6\u7814\u5224\u62a5\u544a\u3002\n"
            "\u62a5\u544a\u5fc5\u987b\u5305\u542b\u4ee5\u4e0b 8 \u4e2a\u90e8\u5206\uff1a\n"
            "1. \u4e8b\u4ef6\u6982\u8ff0\n"
            "2. \u98ce\u9669\u7ed3\u8bba\n"
            "3. \u4e3b\u8981\u5224\u65ad\u4f9d\u636e\n"
            "4. \u5173\u952e\u65e5\u5fd7\u4e0e\u7ebf\u7d22\n"
            "5. \u76f8\u4f3c\u5386\u53f2\u6848\u4f8b\n"
            "6. \u653b\u51fb\u9636\u6bb5\u5206\u6790\n"
            "7. \u5904\u7f6e\u5efa\u8bae\n"
            "8. \u590d\u6838\u91cd\u70b9\u4e0e\u540e\u7eed\u52a8\u4f5c\n\n"
            "\u8981\u6c42\uff1a\n"
            "- \u76f4\u63a5\u8f93\u51fa\u62a5\u544a\u6b63\u6587\uff0c\u4e0d\u8981 JSON\uff1b\n"
            "- 只能引用 rag_cases 中已通过高置信门控的相似案例作为证据；\n"
            "- 如果 rag_cases 为空，或只有 rag_evidence_note，请明确说明相似案例证据不足，不得把候选参考当作事实依据；\n"
            "- \u7ed3\u8bba\u8981\u514b\u5236\uff0c\u4e0d\u8981\u5938\u5927\uff1b\n"
            "- \u62a5\u544a\u9002\u5408\u76f4\u63a5\u5c55\u793a\u7ed9\u5b89\u5168\u5206\u6790\u4eba\u5458\u3002\n\n"
            f"event_data={json.dumps(incident, ensure_ascii=False)}"
        )
        try:
            effective_temperature = 1.0 if self.provider == 'custom' and 'kimi' in self.model.lower() else self.temperature
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=effective_temperature,
                max_tokens=self.report_max_tokens,
                timeout=self.request_timeout,
                messages=[
                    {"role": "system", "content": "你是严谨的安全事件研判助手，只输出中文报告正文。"},
                    {"role": "user", "content": prompt},
                ],
            )
            message = resp.choices[0].message
            text = (getattr(message, 'content', None) or '').strip()
            if not text:
                text = (getattr(message, 'reasoning_content', None) or '').strip()
            finish_reason = getattr(resp.choices[0], 'finish_reason', '')
            if text:
                if str(finish_reason).lower() == 'length':
                    return f"{text}\n\n[提示] 模型输出达到长度上限，报告可能未完整结束；请提高 report_max_tokens 后重新生成。"
                return text
            return "服务返回空响应，请检查模型是否支持当前报告格式，或减少输入内容后重试。"
        except Exception as exc:  # pragma: no cover
            self.logger.warning(f"\u4e8b\u4ef6\u7ea7 LLM \u62a5\u544a\u751f\u6210\u5931\u8d25: {exc}")
            return f"LLM \u8bf7\u6c42\u5931\u8d25\uff1a{exc}"
