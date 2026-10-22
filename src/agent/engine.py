from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .events import EventStore, parse_time
from .judgment import JudgmentValidationError
from .planner import RulePlanner
from .tools import InvestigationTools, ToolArgumentError, failure_clusters

# Tools still allowed once the agent enters wrap-up mode: consolidate and finish, no new exploration.
WRAP_UP_TOOLS = {"build_timeline", "retrieve_cases", "update_hypothesis", "finish_investigation"}
# Wrap-up is terminal: one integration turn plus one finishing turn, then the run is closed. Without
# this cap a planner that never calls finish_investigation can consume the whole remaining budget and
# the completeness gate is never consulted, because the gate only runs on a finish request.
WRAP_UP_TURNS = 2


@dataclass
class Finding:
    kind: str
    statement: str
    evidence_ids: list[str]
    interpretation: str


@dataclass
class InvestigationResult:
    run_id: str
    goal: str
    mode: str
    status: str
    stop_reason: str
    coverage: dict
    findings: list[Finding]
    evidence: list[dict]
    case_references: list[dict]
    trace: list[dict]
    limitations: list[str]
    elapsed_seconds: float
    tokens_used: int
    judgment: dict = field(default_factory=lambda: {"status": "not_requested"})
    plan: list[dict] = field(default_factory=list)
    gate_triggers: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)

    def to_markdown(self):
        def safe(value):
            # Escape untrusted log/user text instead of rendering it as Markdown/HTML.
            text = str(value).replace("\n", " ").replace("\r", " ")
            for c in "\\`*_{}[]()<>#|!":
                text = text.replace(c, "\\" + c)
            return text
        lines = ["# LogFusion-Agent 调查报告", "", f"调查编号：{self.run_id}",
                 f"目标：{safe(self.goal)}", f"模式：{self.mode}；状态：{self.status}；停止原因：{self.stop_reason}",
                 f"输入日志：{self.coverage['events']} 条；已查看证据：{len(self.evidence)} 条", ""]
        if self.plan:
            lines += ["## 调查计划与假设", ""]
            for item in self.plan:
                lines.append(f"- [{item['id']}] {safe(item['statement'])} — 状态：{item['status']}")
            lines.append("")
        lines += ["## 调查发现", ""]
        for f in self.findings:
            lines += [f"- {safe(f.statement)}", f"  - 判断性质：{safe(f.interpretation)}",
                      "  - 原始证据：" + ", ".join(f.evidence_ids)]
        lines += ["", "## LLM 综合研判", "", f"状态：{self.judgment['status']}"]
        if self.judgment.get("status") == "completed":
            content = self.judgment["content"]
            lines.append(f"后端：{safe(self.judgment.get('backend', ''))}；模型：{safe(self.judgment.get('model', ''))}")
            if self.judgment.get("backend") == "simulated_llm":
                lines.append("这是模拟模型的完整链路演示，未调用真实 LLM，不代表模型研判质量。")
            lines += [f"评估：{content['assessment']}", "引用检查仅验证结构与 ID 有效性，不证明自然语言判断正确。", ""]
            for claim in content["claims"]:
                label = "观察" if claim["kind"] == "observation" else "推断"
                lines += [f"- {label}：{safe(claim['statement'])}",
                          "  - 原始证据：" + ", ".join(claim["evidence_ids"]),
                          "  - 参考案例：" + ", ".join(safe(c) for c in claim["case_ids"])]
            lines += ["", "### 建议（未自动执行）", ""]
            for action in content["recommendations"]:
                lines += [f"- {safe(action['action'])}：{safe(action['rationale'])}",
                          "  - 原始证据：" + ", ".join(action["evidence_ids"]),
                          "  - 参考案例：" + ", ".join(safe(c) for c in action["case_ids"])]
            lines += ["", "### 待确认事项", "", *["- " + safe(s) for s in content["uncertainties"]]]
        elif self.judgment.get("reason"):
            lines.append("原因：" + safe(self.judgment["reason"]))
        lines += ["", "## 证据时间线", ""]
        for e in sorted(self.evidence, key=lambda e: (not bool(e["timestamp"]), e["timestamp"], e["line"])):
            lines.append(f"- [{e['event_id']}] {safe(e['timestamp'] or '时间未知')} · {safe(e['source'])}:{e['line']} · {safe(e['raw'])}")
        lines += ["", "## 参考案例（不构成本次事件的事实证据）", ""]
        for case in self.case_references:
            lines.append(f"- {safe(case['case_id'])}：{safe(case['title'])}")
        lines += ["", "## 不确定性与边界", "", *[f"- {safe(s)}" for s in self.limitations],
                  "", "## 工具执行记录", ""]
        for t in self.trace:
            reason = f"（理由：{safe(t['rationale'])}）" if t.get("rationale") else ""
            lines.append(f"- {t['step']}. {t['tool']}{reason}：{'失败' if t.get('error') else '完成'}")
        return "\n".join(lines) + "\n"

    def save(self, directory: str | Path):
        target = Path(directory) / self.run_id
        target.mkdir(parents=True, exist_ok=False)
        (target / "investigation.json").write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        (target / "report.md").write_text(self.to_markdown(), encoding="utf-8")
        return target


def _window(rows, minutes, key):
    """Densest bounded window: return (slice, number of distinct ``key`` values inside it)."""
    rows = sorted(rows, key=lambda e: e.timestamp)
    best, best_count = [], 0
    for i in range(len(rows)):
        seen = set()
        for j in range(i, len(rows)):
            if parse_time(rows[j].timestamp) - parse_time(rows[i].timestamp) > timedelta(minutes=minutes):
                break
            seen.add(key(rows[j]))
            if len(seen) > best_count:
                best, best_count = rows[i:j + 1], len(seen)
    return best, best_count


def _max_window_count(rows, minutes):
    rows = sorted(rows, key=lambda e: e.timestamp)
    best, left = 0, 0
    for right, event in enumerate(rows):
        while parse_time(event.timestamp) - parse_time(rows[left].timestamp) > timedelta(minutes=minutes):
            left += 1
        best = max(best, right - left + 1)
    return best


def _pattern_findings(events, findings, cited):
    """Patterns the 5-in-5-minutes entity rule cannot express: spray, stuffing, low-and-slow."""
    failures = [e for e in events if e.event_type == "auth_failure" and e.timestamp and e.src_ip and e.user and e.host]
    successes = [e for e in events if e.event_type == "auth_success" and e.timestamp]

    by_account = defaultdict(list)
    for event in failures:
        by_account[(event.user, event.host)].append(event)
    for (user, host), rows in by_account.items():
        window, distinct_ips = _window(rows, 10, lambda e: e.src_ip)
        if distinct_ips < 8:
            continue
        ids = [e.event_id for e in window]
        findings.append(Finding(
            "suspected_distributed_spray",
            f"账号 {user} 在 {host} 上 10 分钟内被 {distinct_ips} 个不同来源 IP 尝试登录，疑似分布式喷洒。",
            ids, "跨来源聚合推断；多个合法客户端同时使用错误密码也可能产生类似形态"))
        end = parse_time(window[-1].timestamp)
        for success in [e for e in successes if e.user == user and e.host == host
                        and end < parse_time(e.timestamp) <= end + timedelta(minutes=15)][:3]:
            if success.event_id in cited:
                continue
            cited.add(success.event_id)
            findings.append(Finding(
                "success_after_failures",
                f"账号 {user} 在 {host} 上的分布式失败窗口结束后 15 分钟内出现成功登录。",
                [*ids, success.event_id], "同账号、同主机的时间关联；无法确认成功登录与哪一次失败尝试相关"))

    by_source = defaultdict(list)
    for event in failures:
        by_source[(event.src_ip, event.host)].append(event)
    for (src_ip, host), rows in by_source.items():
        window, distinct_users = _window(rows, 10, lambda e: e.user)
        if distinct_users < 8:
            continue
        ids = [e.event_id for e in window]
        users = sorted({e.user for e in window})
        findings.append(Finding(
            "suspected_account_stuffing",
            f"来源 {src_ip} 在 {host} 上 10 分钟内对 {distinct_users} 个不同账号尝试登录，疑似撞库。",
            ids, "跨账号聚合推断；也可能是一台共享主机的多个合法用户同时输错密码"))
        end = parse_time(window[-1].timestamp)
        for success in [e for e in successes if e.src_ip == src_ip and e.host == host and e.user in users
                        and end < parse_time(e.timestamp) <= end + timedelta(minutes=15)][:3]:
            if success.event_id in cited:
                continue
            cited.add(success.event_id)
            findings.append(Finding(
                "success_after_failures",
                f"来源 {src_ip} 的撞库窗口结束后 15 分钟内，其中一个被尝试账号在 {host} 上登录成功。",
                [*ids, success.event_id], "同来源、同主机的时间关联；登录成功不等于凭据来自撞库"))

    by_entity = defaultdict(list)
    for event in failures:
        by_entity[(event.src_ip, event.user, event.host)].append(event)
    for (src_ip, user, host), rows in by_entity.items():
        window, count = _window(rows, 30, lambda e: e.line)
        if count < 10 or _max_window_count(rows, 5) >= 5:
            continue
        ids = [e.event_id for e in window]
        findings.append(Finding(
            "suspected_low_and_slow",
            f"来源 {src_ip} 对 {host} 上账号 {user} 在 30 分钟内累计 {count} 次失败，任意 5 分钟窗口均不足 5 次，疑似低速爆破。",
            ids, "长窗口聚合推断；自动化任务使用过期凭据也可能产生类似形态"))
        end = parse_time(window[-1].timestamp)
        for success in [e for e in successes if (e.src_ip, e.user, e.host) == (src_ip, user, host)
                        and end < parse_time(e.timestamp) <= end + timedelta(minutes=15)][:3]:
            if success.event_id in cited:
                continue
            cited.add(success.event_id)
            findings.append(Finding(
                "success_after_failures",
                f"来源 {src_ip} 对账号 {user} 的低速失败窗口结束后 15 分钟内出现同实体成功登录。",
                [*ids, success.event_id], "同实体、长时间窗的时间关联；尚未确认凭据是否泄漏"))


def grounded_findings(tools: InvestigationTools) -> list[Finding]:
    """Conclusions are derived from observed evidence; the planner cannot invent them."""
    events = [tools.store.by_id[eid] for eid in tools.evidence]
    # Discovery tool aggregation may use another threshold. Report uses the documented 5/5 default.
    groups = failure_clusters(events)
    findings = []
    cited = set()
    for group in groups[:10]:
        ids = group["event_ids"]
        prefix = f"来源 {group['src_ip']} 对 {group['host']} 上账号 {group['user']}"
        findings.append(Finding("suspected_bruteforce", f"{prefix}在 5 分钟窗口内出现 {group['count']} 次认证失败，疑似暴力破解。",
                                ids, "规则推断；合法重试或自动化配置错误也可能产生类似行为"))
        end = parse_time(group["end"])
        successes = [e for e in events if e.event_type == "auth_success" and e.timestamp
                     and (e.src_ip, e.user, e.host) == (group["src_ip"], group["user"], group["host"])
                     and end < parse_time(e.timestamp) <= end + timedelta(minutes=15)]
        for success in successes[:3]:
            if success.event_id in cited:
                continue
            cited.add(success.event_id)
            findings.append(Finding("success_after_failures", f"{prefix}的失败窗口结束后 15 分钟内出现成功登录。",
                                    [*ids, success.event_id], "时间与实体关联；尚不能确认凭据被盗或登录未经授权"))
            later = [e for e in events if e.timestamp and e.user == success.user and e.host == success.host
                     and e.event_type in ("privileged_command", "account_change")
                     and parse_time(success.timestamp) <= parse_time(e.timestamp) <= parse_time(success.timestamp) + timedelta(minutes=15)]
            if later:
                findings.append(Finding("post_login_activity", f"该成功登录后 15 分钟内，同账号、同主机出现特权命令或账户变更记录。",
                                        [success.event_id, *[e.event_id for e in later[:20]]],
                                        "上下文关联；缺少会话 ID 时不能确认由同一登录会话执行，也不直接证明恶意提权"))
    _pattern_findings(events, findings, cited)
    if not findings:
        findings.append(Finding("insufficient_evidence", "已查看证据尚不足以建立 SSH 集中失败与后续登录的关联链。", [],
                                "证据不足；不能据此认定日志正常或不存在入侵"))
    if any(eid not in tools.evidence for f in findings for eid in f.evidence_ids):
        raise ValueError("Finding contains unknown evidence citation")
    return findings


class InvestigationAgent:
    def __init__(self, store: EventStore, planner=None, tools=None,
                 max_steps: int = 16, max_seconds: float = 90, max_tokens: int = 24_000, reviewer=None,
                 completeness_gate: bool = True):
        if not 1 <= max_steps <= 40 or not 1 <= max_seconds <= 600 or not 1 <= max_tokens <= 200_000:
            raise ValueError("Invalid investigation budget")
        self.store = store
        self.planner = planner or RulePlanner()
        self.tools = tools or InvestigationTools(store)
        self.reviewer = reviewer
        self.max_steps, self.max_seconds, self.max_tokens = max_steps, max_seconds, max_tokens
        self.completeness_gate = completeness_gate

    def _coverage_gaps(self, trace, plan) -> list[str]:
        """What the investigation already knows it has not checked before declaring it is done."""
        gaps = []
        if not self.tools.evidence:
            return ["尚未查看任何日志证据：先执行一次聚合或检索再结束"]
        events = [self.tools.store.by_id[eid] for eid in self.tools.evidence]
        clusters = failure_clusters(events)[:3]
        ends = [parse_time(group["end"]) for group in clusters]
        for group in clusters:
            searched = any(t["tool"] == "search_logs" and not t.get("error")
                           and t["arguments"].get("user") == group["user"]
                           and t["arguments"].get("host") == group["host"]
                           and t["arguments"].get("event_type") == "auth_success"
                           for t in trace)
            if not searched:
                gaps.append(f"失败簇 {group['src_ip']}/{group['user']}@{group['host']} 尚未查询后续成功登录")
        # Only successes that could complete a chain (same account and host, just after a cluster) are
        # required to have context; unrelated successes in the evidence are not a completeness gap.
        for event in events:
            if event.event_type != "auth_success" or not event.timestamp:
                continue
            relevant = any(
                (event.user, event.host) == (group["user"], group["host"])
                and 0 <= (parse_time(event.timestamp) - end).total_seconds() <= 15 * 60
                for group, end in zip(clusters, ends))
            if not relevant:
                continue
            checked = any(t["tool"] == "get_event_context" and t["arguments"].get("event_id") == event.event_id
                          for t in trace)
            if not checked:
                gaps.append(f"成功登录 {event.event_id} 尚未核对上下文")
        if plan and all(item["status"] == "open" for item in plan):
            gaps.append("计划中的假设都还没有结论（可用 update_hypothesis 标注）")
        return gaps[:4]

    def _unsearched_clusters(self, trace, hinted) -> list[tuple[str, str, str]]:
        """Failure clusters whose follow-up success login has not been searched yet."""
        events = [self.tools.store.by_id[eid] for eid in self.tools.evidence]
        missing = []
        for group in failure_clusters(events)[:3]:
            key = (group["src_ip"], group["user"], group["host"])
            if key in hinted:
                continue
            searched = any(t["tool"] == "search_logs" and not t.get("error")
                           and t["arguments"].get("user") == group["user"]
                           and t["arguments"].get("host") == group["host"]
                           and t["arguments"].get("event_type") == "auth_success"
                           for t in trace)
            if not searched:
                missing.append(key)
        return missing

    def run(self, goal: str, on_step=None, cancelled=None):
        if not goal.strip() or len(goal) > 2000:
            raise ValueError("调查目标须为 1..2000 字符")
        # Per-run evidence and cost state; avoid evidence leaking between investigations.
        if hasattr(self.tools, "reset"):
            self.tools.reset()
        else:  # custom tools in tests
            self.tools.evidence.clear()
            self.tools.case_references.clear()
            self.tools.observations.clear()
        self.planner.tokens_used = 0
        if self.reviewer:
            self.reviewer.tokens_used = 0
        trace, seen = [], set()
        # Plan first: two to four hypotheses the investigation will try to confirm or refute.
        plan: list[dict] = []
        if getattr(self.planner, "supports_plan", False) and not (cancelled and cancelled()):
            try:
                statements = self.planner.plan(goal) or []
            except Exception:
                statements = []  # a planning failure must not prevent the investigation
            plan = [{"id": f"H{i + 1}", "statement": str(text)[:200].strip(), "status": "open"}
                    for i, text in enumerate(list(statements)[:4]) if str(text).strip()]
        if plan:
            trace.append({"step": 0, "tool": "plan", "arguments": {}, "stage": "plan",
                          "result": {"hypotheses": plan}})
        started = time.monotonic()
        status, reason = "limited", "max_steps"
        # Reserve budget for the completion stages (case retrieval + synthesis) so an investigation
        # always ends with a report instead of dying as soon as the tool loop runs out of budget.
        reserve_tokens = min(30_000, self.max_tokens // 3)
        tool_token_limit = self.max_tokens - reserve_tokens
        reserve_steps = 2 if self.max_steps >= 6 else 0
        tool_step_limit = self.max_steps - reserve_steps
        # Wrap-up must start at least one model call before the tool-token hard limit. A fixed
        # percentage of the budget cannot guarantee that: a single turn can cost more than the gap,
        # so wrap-up would be entered and skipped in the same iteration. Reserve ~1.5 observed turns.
        wrap_up_steps = max(1, tool_step_limit - 2)
        repeated_calls = 0
        wrap_up = False
        wrap_up_turns = 0
        wrap_up_final = False
        wrap_up_restricted = 0
        gate_triggers = 0
        hinted_clusters: set[tuple[str, str, str]] = set()
        unresolved_gaps: list[str] = []

        def next_step():
            return max((item.get("step", 0) for item in trace), default=0) + 1

        def actions_done():
            return sum(1 for item in trace if item.get("stage") not in ("wrap_up", "plan", "gate", "hint"))

        for step in range(1, self.max_steps + 1):
            if cancelled and cancelled():
                status, reason = "cancelled", "user_cancelled"
                break
            if time.monotonic() - started >= self.max_seconds:
                reason = "time_budget"
                break
            # Reserve the cost of the next call (plus half a turn of slack) so wrap-up always gets
            # at least one turn before the tool-token hard limit. Never reserve more than half the
            # tool budget, otherwise a deliberately tiny budget would start in wrap-up.
            turns_done = max(1, sum(1 for item in trace
                                    if item.get("stage") not in ("plan", "gate", "wrap_up", "hint")))
            wrap_up_headroom = min(max(1_200, int(self.planner.tokens_used / turns_done * 1.5)),
                                   tool_token_limit // 2)
            if not wrap_up and (self.planner.tokens_used >= tool_token_limit - wrap_up_headroom
                                or actions_done() >= wrap_up_steps):
                wrap_up = True
                notice = {"step": step, "tool": "wrap_up", "arguments": {}, "stage": "wrap_up",
                          "result": {"mode": "wrap_up",
                                     "notice": "预算接近上限：停止探索。本轮先用 update_hypothesis 收束假设，"
                                               "可再用 build_timeline 整理证据，随后必须调用 "
                                               f"finish_investigation；{WRAP_UP_TURNS} 轮后强制收口。"}}
                trace.append(notice)
                if on_step:
                    on_step(notice)
            if wrap_up:
                wrap_up_turns += 1
                if wrap_up_turns > WRAP_UP_TURNS:
                    # Backstop for planners without forced-finish support: close, then audit below.
                    status, reason = "completed_partial", "wrap_up_terminal"
                    break
                # The last wrap-up turn is a forced finish request. That is what gives the gate
                # something real to inspect instead of closing the run behind its back.
                wrap_up_final = wrap_up_turns >= WRAP_UP_TURNS
            # Wrap-up may spend part of the completion reserve, but never all of it: the closing
            # judgment still needs room, and a runaway planner must not eat the whole budget.
            token_limit = (min(self.max_tokens, tool_token_limit + reserve_tokens // 2)
                           if wrap_up else tool_token_limit)
            if self.planner.tokens_used >= token_limit or (not wrap_up and actions_done() >= tool_step_limit):
                # Stop gathering and keep the reserved budget for completion. Wrap-up turns are funded
                # by that reserve; only the absolute max_tokens cap can cut them short.
                status, reason = ("completed_partial" if wrap_up else "completed"), "evidence_budget"
                break
            if self.planner.tokens_used >= self.max_tokens:
                reason = "token_budget"
                break
            try:
                if getattr(self.planner, "supports_wrap_up", False):
                    name, arguments = self.planner.choose(goal, trace, wrap_up=wrap_up,
                                                          final=wrap_up and wrap_up_final)
                else:
                    name, arguments = self.planner.choose(goal, trace)
                # The rationale is a planner annotation, not a tool argument.
                rationale = ""
                if isinstance(arguments, dict) and "rationale" in arguments:
                    rationale = str(arguments.pop("rationale"))[:300]
                if wrap_up_final and name != "finish_investigation":
                    # Some OpenAI-compatible providers ignore a forced tool_choice. The terminal turn
                    # accepts only a finish request, so record the ignored call and close through the
                    # gate instead of executing a tool that cannot change the outcome.
                    ignored = {"step": step, "tool": "wrap_up", "arguments": {}, "stage": "wrap_up",
                               "result": {"mode": "terminal", "ignored_tool_call": name,
                                          "notice": "终局只接受 finish_investigation；已忽略该调用并按结束处理。"}}
                    trace.append(ignored)
                    if on_step:
                        on_step(ignored)
                    name, arguments = "finish_investigation", {}
                # Check after an in-flight model call, before executing its requested tool.
                if self.planner.tokens_used >= self.max_tokens:
                    reason = "token_budget"
                    break
                if time.monotonic() - started >= self.max_seconds:
                    reason = "time_budget"
                    break
                if name == "finish_investigation":
                    if arguments:
                        raise ValueError("finish_investigation accepts no arguments")
                    # Completeness gate: a finish request must account for known clusters and
                    # successes. Outside wrap-up the run may be refused twice and keep investigating;
                    # inside wrap-up there is no turn left to act on the feedback, so a refusal ends
                    # the run as partial with the gaps on record.
                    gaps = [] if not self.completeness_gate else self._coverage_gaps(trace, plan)
                    if gaps and gate_triggers < 2:
                        gate_triggers += 1
                        notice = {"step": step, "tool": "completeness_gate", "arguments": {},
                                  "stage": "gate", "control": "CompletenessGate",
                                  "terminal": wrap_up,
                                  "result": {"missing": gaps,
                                             "notice": ("收尾阶段无法再补查：结束请求被拒绝，未覆盖项写入报告限制。"
                                                        if wrap_up else
                                                        "结束前请补齐以下检查；若确实无法检查，请说明原因后再结束。"),
                                             "type": "CompletenessGate"}}
                        trace.append(notice)
                        if on_step:
                            on_step(notice)
                        if wrap_up:
                            unresolved_gaps = gaps
                            status, reason = "completed_partial", "gate_unresolved"
                            break
                        continue
                    status, reason = "completed", "planner_finished"
                    break
                if wrap_up and name not in WRAP_UP_TOOLS:
                    wrap_up_restricted += 1
                    hint = {"step": step, "tool": name, "arguments": arguments, "control": "WrapUpRestricted",
                            "stage": "wrap_up",
                            "result": {"error": "收尾模式：探索类工具已关闭，请用 build_timeline 整理证据或 finish_investigation 结束。",
                                       "type": "WrapUpRestricted"}}
                    trace.append(hint)
                    if on_step:
                        on_step(hint)
                    if wrap_up_restricted >= 2:
                        status, reason = "completed_partial", "evidence_budget"
                        break
                    continue
                signature = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False)
                if signature in seen:
                    # Do not abort the investigation for a repeated call: tell the planner what went
                    # wrong and let it choose again, then wrap up if it keeps looping.
                    repeated_calls += 1
                    hint = {"step": step, "tool": name, "arguments": arguments, "error": "RepeatedCall",
                            "result": {"error": "This exact tool call already ran; its result is in the "
                                                "conversation. Choose a different tool or finish_investigation.",
                                       "type": "RepeatedCall"}}
                    trace.append(hint)
                    if on_step:
                        on_step(hint)
                    if repeated_calls >= 2:
                        status, reason = "completed_partial", "evidence_budget"
                        break
                    continue
                seen.add(signature)
            except Exception as exc:
                # A provider failure should end with a report when evidence already exists; only a
                # failure before any tool ran leaves nothing to report.
                # Do not persist SDK exceptions, which may contain headers or credentials.
                status = "completed_partial" if trace else "error"
                reason = "planner_error:" + type(exc).__name__
                break
            entry = {"step": step, "tool": name, "arguments": arguments}
            if rationale:
                entry["rationale"] = rationale
            try:
                entry["result"] = self.tools.call(name, arguments)
            except ToolArgumentError as exc:
                entry.update(error="ToolArgumentError", result={"error": str(exc), "type": "ToolArgumentError",
                             "retry_guidance": "Correct arguments using the schema; do not repeat the invalid call."})
            except Exception as exc:
                entry.update(error=type(exc).__name__, result={"error": "Tool failed or arguments invalid", "type": type(exc).__name__})
            if name == "update_hypothesis" and not entry.get("error"):
                updated = entry["result"]
                target = next((item for item in plan if item["id"] == updated.get("hypothesis_id")), None)
                if target is None:
                    entry.update(error="UnknownHypothesis",
                                 result={"error": "未知的假设 ID；请只更新计划中列出的假设。", "type": "UnknownHypothesis"})
                else:
                    target["status"] = updated["status"]
                    target["note"] = updated.get("note", "")
                    target["updated_at_step"] = step
            trace.append(entry)
            if on_step:
                on_step(entry)
            # Pull completeness checks forward: once a failure cluster is observed, the planner is
            # told to search that entity's follow-up logins now, not at finish time when the budget
            # is gone. Each entity is nudged once.
            if name == "aggregate_events" and not entry.get("error"):
                cluster_keys = self._unsearched_clusters(trace, hinted_clusters)
                if cluster_keys:
                    hinted_clusters.update(cluster_keys)
                    hint = {"step": next_step(), "tool": "required_action", "arguments": {},
                            "stage": "hint", "control": "RequiredAction",
                            "result": {"clusters": [f"{ip}/{user}@{host}" for ip, user, host in cluster_keys],
                                       "notice": "发现失败簇后先查询同实体、同主机的后继成功登录，再继续其他线索；"
                                                 "这是完整性检查要求，不是新发现。"}}
                    trace.append(hint)
                    if on_step:
                        on_step(hint)
            if sum(bool(t.get("error")) for t in trace) >= 3:
                # Repeated tool failures should degrade to a partial report, not kill the run.
                status, reason = "completed", "evidence_budget"
                break
        # Terminal audit. The gate normally runs when the planner asks to finish; a run that burns
        # its budget or its wrap-up turns never asks, so it would be published with no coverage check
        # at all. Audit the same gaps at the end and disclose them, so an unfinished investigation
        # cannot look complete just because it never called finish_investigation.
        if (self.completeness_gate and status in ("completed", "completed_partial")
                and reason not in ("planner_finished", "user_cancelled") and gate_triggers == 0):
            unresolved_gaps = self._coverage_gaps(trace, plan)
            if unresolved_gaps:
                gate_triggers += 1
                if status == "completed":
                    status = "completed_partial"
                notice = {"step": next_step(), "tool": "completeness_gate", "arguments": {},
                          "stage": "gate", "control": "CompletenessGate", "terminal": True,
                          "result": {"missing": unresolved_gaps, "terminal": True,
                                     "notice": "终局审计：调查在预算内结束，仍有未覆盖项；已写入报告限制。",
                                     "type": "CompletenessGate"}}
                trace.append(notice)
                if on_step:
                    on_step(notice)
        findings = grounded_findings(self.tools)
        judgment = {"status": "not_requested"}
        if self.reviewer:
            judgment = {"status": "skipped", "reason": "investigation_incomplete"}

            def budget_reason():
                if cancelled and cancelled():
                    return "user_cancelled"
                if time.monotonic() - started >= self.max_seconds:
                    return "time_budget"
                if self.planner.tokens_used + self.reviewer.tokens_used >= self.max_tokens:
                    return "token_budget"
                if len(trace) >= self.max_steps and actions_done() >= self.max_steps:
                    return "max_steps"
                return ""

            # The Agent owns the entire completion pipeline, including reference retrieval and synthesis.
            # A planner finishing early cannot publish a report without running these stages.
            if status in ("completed", "completed_partial"):
                stopped = budget_reason()
                if not stopped and not any(t["tool"] == "retrieve_cases" and not t.get("error") for t in trace):
                    entry = {"step": next_step(), "tool": "retrieve_cases",
                             "arguments": {"query": "SSH brute force failed password accepted sudo", "top_k": 3},
                             "stage": "agent_completion"}
                    try:
                        entry["result"] = self.tools.call(entry["tool"], entry["arguments"])
                    except Exception as exc:
                        entry.update(error=type(exc).__name__, result={"error": "Reference retrieval failed"})
                    trace.append(entry)
                    if on_step:
                        on_step(entry)
                    if entry.get("error"):
                        status, reason = "error", "completion_retrieval_failed"
                        judgment = {"status": "skipped", "reason": reason}
                if status in ("completed", "completed_partial"):
                    feedback = ""
                    for attempt in range(2):
                        stopped = budget_reason()
                        if stopped:
                            status = "cancelled" if stopped == "user_cancelled" else "limited"
                            reason = stopped
                            judgment = {"status": "skipped", "reason": stopped}
                            break
                        entry = {"step": next_step(), "tool": "synthesize_judgment",
                                 "arguments": {"attempt": attempt + 1}, "stage": "agent_completion"}
                        try:
                            judgment = self.reviewer.synthesize(
                                goal, self.tools.evidence, self.tools.case_references, findings, self.store.coverage(),
                                timeout=max(.1, min(20, self.max_seconds - (time.monotonic() - started))),
                                output_tokens=min(2400, self.max_tokens - self.planner.tokens_used - self.reviewer.tokens_used),
                                feedback=feedback)
                            # In-flight calls may exceed a soft budget; never publish their result as completed.
                            stopped = ""
                            if self.planner.tokens_used + self.reviewer.tokens_used >= self.max_tokens:
                                stopped = "token_budget"
                            elif time.monotonic() - started >= self.max_seconds:
                                stopped = "time_budget"
                            elif cancelled and cancelled():
                                stopped = "user_cancelled"
                            if stopped:
                                status = "cancelled" if stopped == "user_cancelled" else "limited"
                                reason = stopped
                                judgment = {"status": "discarded", "reason": stopped}
                            entry["result"] = {"status": judgment["status"],
                                               "validation": judgment.get("validation", "not_published")}
                        except JudgmentValidationError as exc:
                            feedback = str(exc)
                            entry.update(error="JudgmentValidationError", result={"error": feedback})
                            judgment = {"status": "rejected", "reason": feedback}
                        except Exception as exc:
                            entry.update(error=type(exc).__name__, result={"error": "Model synthesis failed"})
                            judgment = {"status": "failed", "reason": "model_error:" + type(exc).__name__}
                        trace.append(entry)
                        if on_step:
                            on_step(entry)
                        if judgment["status"] != "rejected":
                            break
                    if judgment["status"] in ("rejected", "failed"):
                        # The investigation itself completed; only the model's synthesis was withheld.
                        # Publish rules and evidence, and mark the run as partial rather than failed.
                        status, reason = "completed_partial", "judgment_" + judgment["status"]
        coverage = self.store.coverage()
        coverage["input_sha256"] = hashlib.sha256(json.dumps([e.to_dict() for e in self.store.events],
                                                              sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        limitations = ["第一版仅对 SSH 集中认证失败、后续成功登录、账户上下文，以及分布式喷洒/撞库/低速爆破的聚合形态生成结构化结论；其他调查目标尚不保证覆盖。",
                       "调查范围仅为当前上传日志，缺少的日志或未查询的记录不能当作不存在。",
                       "成功登录、sudo 和账户变更均可能是合法行为；确认入侵仍需授权记录、会话或审计证据。",
                       "关联默认要求同 IP、同账号、同主机；失败窗口 5 分钟至少 5 次，后续登录窗口 15 分钟；跨主机成功登录不关联。",
                       "同一实体仅检查最密集失败窗口，单次最多报告 10 组；不能视为穷尽调查。",
                       "无时区时间按 UTC 处理；缺失年份或时间的日志不参与时间关联。",
                       "LLM 模式会把调查目标和工具返回的部分日志发送至所配置的模型服务。"]
        if coverage["missing_timestamps"]:
            limitations.append(f"有 {coverage['missing_timestamps']} 条日志缺少可解析的完整时间。")
        if any(t.get("result", {}).get("truncated") or any(g.get("evidence_truncated") for g in t.get("result", {}).get("groups", [])) for t in trace):
            limitations.append("部分工具结果受数量限制发生截断；报告仅基于实际返回的证据。")
        if not any(f.kind == "success_after_failures" for f in findings):
            limitations.append("当前已查看证据未建立失败后成功登录链，不能排除其他时间、账号或主机上的入侵。")
        if reason == "evidence_budget":
            limitations.append("工具阶段在预留预算内提前收束，研判仅基于已查证据；未覆盖的日志不能视为不存在。")
        if reason == "wrap_up_terminal":
            limitations.append("收尾阶段未在限额内请求结束，已强制收口；此后未再执行任何检查，研判仅基于已查证据。")
        if reason == "gate_unresolved":
            limitations.append("结束请求被完整性闸门拒绝，且已无预算补查，报告作为部分完成发布。")
        if status == "completed_partial":
            limitations.append("状态为部分完成：报告已产出，但调查没有覆盖全部可能路径。")
        if gate_triggers:
            limitations.append(f"完整性闸门触发 {gate_triggers} 次：结束前被要求补齐未检查的覆盖项。")
        if unresolved_gaps:
            limitations.append("结束前仍未覆盖：" + "；".join(unresolved_gaps[:4]) + "。")
        if any(t.get("tool") == "detect_anomalies" and t.get("error") for t in trace):
            limitations.append("检测器不可用（日志条数不足或模型缺失），本次结论仅基于规则信号与日志检索。")
        if reason == "gate_unresolved":
            limitations.append("收尾阶段被完整性闸门拦下：未覆盖项见上，报告作为部分完成发布。")
        elif status != "completed":
            limitations.append("本次调查未正常完成，请结合停止原因检查预算或服务状态。")
        if self.reviewer:
            limitations.append("LLM 综合研判为辅助意见；引用检查验证结构与引用 ID，不保证文字与证据的语义一致性。")
            if judgment.get("preview", {}).get("events_truncated") or judgment.get("preview", {}).get("raw_truncated"):
                limitations.append("综合研判使用截断的证据预览；完整已查证据见时间线及 JSON。")
            if judgment.get("status") in ("rejected", "failed", "discarded"):
                limitations.append(f"本次综合研判未发布（{judgment['status']}），报告只保留规则发现与已查证据。")
        return InvestigationResult("INV-" + uuid4().hex[:12], goal, self.planner.mode, status, reason,
                                    coverage, findings, list(self.tools.evidence.values()),
                                    list(self.tools.case_references.values()), trace, limitations,
                                    round(time.monotonic() - started, 3),
                                    self.planner.tokens_used + (self.reviewer.tokens_used if self.reviewer else 0),
                                    judgment=judgment, plan=plan, gate_triggers=gate_triggers)
