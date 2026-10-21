from __future__ import annotations

import inspect
import json
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Callable

from .events import EventStore, parse_time

ROOT = Path(__file__).resolve().parents[2]


def failure_clusters(events, window_minutes: int = 5, min_failures: int = 5) -> list[dict]:
    """One maximum-density bounded window per (IP, user, host), with exact citations."""
    groups = defaultdict(list)
    for e in events:
        if e.event_type == "auth_failure" and e.src_ip and e.user and e.host and e.timestamp:
            groups[(e.src_ip, e.user, e.host)].append(e)
    results = []
    for (ip, user, host), rows in groups.items():
        rows.sort(key=lambda e: e.timestamp)
        left, best_left, best_right = 0, 0, -1
        for right, e in enumerate(rows):
            while parse_time(e.timestamp) - parse_time(rows[left].timestamp) > timedelta(minutes=window_minutes):
                left += 1
            if right - left > best_right - best_left:
                best_left, best_right = left, right
        best = rows[best_left:best_right + 1]
        if len(best) >= min_failures:
            results.append({"src_ip": ip, "user": user, "host": host, "count": len(best),
                            "start": best[0].timestamp, "end": best[-1].timestamp,
                            "event_ids": [e.event_id for e in best]})
    return sorted(results, key=lambda g: (-g["count"], g["start"], g["src_ip"]))


class InvestigationTools:
    """Read-only, allowlisted tools. No shell, SQL execution or arbitrary file access."""

    def __init__(self, store: EventStore, case_file: Path | None = None,
                 detector: Callable | None = None, retriever: Callable | None = None):
        self.store = store
        self.case_file = case_file or ROOT / "data/agent/reference_cases.jsonl"
        self.detector = detector
        self.retriever = retriever
        self.evidence: dict[str, dict] = {}
        self.case_references: dict[str, dict] = {}
        self.observations: list[dict] = []

    def _records(self, events, limit=50):
        result = [e.to_dict() for e in list(events)[:limit]]
        self.evidence.update({e["event_id"]: e for e in result})
        return result

    def detect_anomalies(self, limit: int = 30) -> dict:
        if self.detector is not None:
            result = self.detector(self.store, limit)
            for row in result.get("scores", []):
                if row.get("event_id") not in self.store.by_id:
                    raise ValueError("Detector returned unknown event ID")
                self._records([self.store.by_id[row["event_id"]]])
            return result
        selected = [e for e in self.store.events if e.event_type != "other"]
        return {"backend": "rule_signals", "model_loaded": False,
                "notice": "规则候选信号，不是三视图模型评分或攻击概率。", "total": len(selected),
                "events": self._records(selected, limit), "coverage": self.store.coverage()}

    def aggregate_events(self, window_minutes: int = 5, min_failures: int = 5, max_groups: int = 3) -> dict:
        if not 1 <= window_minutes <= 60 or not 2 <= min_failures <= 100:
            raise ValueError("window_minutes must be 1..60; min_failures must be 2..100")
        groups = failure_clusters(self.store.events, window_minutes, min_failures)
        # Bound response and citations even for very large failure bursts.
        selected = groups[:max_groups]
        for g in selected:
            g["evidence_truncated"] = len(g["event_ids"]) > 100
            g["event_ids"] = g["event_ids"][:100]
            self._records([self.store.by_id[eid] for eid in g["event_ids"]], 100)
        result = {"groups": selected, "total_groups": len(groups), "truncated": len(groups) > max_groups,
                  "window_minutes": window_minutes, "min_failures": min_failures,
                  "notice": "按同 IP、同账号、同主机和显式时间聚合；缺失字段的记录不参与关联。"}
        self.observations.append({"tool": "aggregate_events", **result})
        return result

    def search_logs(self, src_ip: str = "", user: str = "", host: str = "", event_type: str = "",
                    start: str = "", end: str = "", limit: int = 50) -> dict:
        begin, finish = parse_time(start) if start else None, parse_time(end) if end else None
        if (start and not begin) or (end and not finish) or (begin and finish and begin > finish):
            raise ValueError("Invalid explicit-year ISO time range")
        matches = []
        for e in self.store.events:
            if any(value and getattr(e, key) != value for key, value in
                   (("src_ip", src_ip), ("user", user), ("host", host), ("event_type", event_type))):
                continue
            t = parse_time(e.timestamp)
            if (begin or finish) and not t:
                continue
            if (begin and t < begin) or (finish and t > finish):
                continue
            matches.append(e)
        matches.sort(key=lambda e: (not bool(e.timestamp), e.timestamp, e.line))
        return {"total": len(matches), "truncated": len(matches) > limit,
                "events": self._records(matches, limit)}

    def get_event_context(self, event_id: str, before_minutes: int = 5, after_minutes: int = 15,
                          limit: int = 50) -> dict:
        event = self.store.by_id.get(event_id)
        if event is None:
            raise ValueError("Unknown event_id")
        if event_id not in self.evidence:
            raise ValueError("Inspect the event using another tool first")
        if not 0 <= before_minutes <= 60 or not 0 <= after_minutes <= 60:
            raise ValueError("Context must be between 0 and 60 minutes")
        time = parse_time(event.timestamp)
        if not time or not event.host or not event.user:
            return {"events": [], "notice": "缺少时间、主机或账号，无法可靠关联上下文。"}
        return self.search_logs(host=event.host, user=event.user,
                                start=(time - timedelta(minutes=before_minutes)).isoformat(),
                                end=(time + timedelta(minutes=after_minutes)).isoformat(), limit=limit)

    def retrieve_cases(self, query: str = "SSH failed password accepted sudo", top_k: int = 3) -> dict:
        if len(query) > 1000:
            raise ValueError("Query too long")
        if self.retriever is not None:
            hits = self.retriever(query, top_k)
            backend = "upstream_vector_rag"
        else:
            cases = [json.loads(line) for line in self.case_file.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
            ranked = []
            for case in cases:
                text = " ".join(str(case.get(k, "")) for k in ("title", "content", "technique"))
                overlap = tokens & set(re.findall(r"[a-z0-9]+", text.lower()))
                if overlap:
                    ranked.append({**case, "score": len(overlap) / max(1, len(tokens))})
            hits = sorted(ranked, key=lambda c: -c["score"])[:top_k]
            backend = "lexical_case_search"
        projected = [{k: h.get(k, "") for k in ("case_id", "title", "content", "technique", "advice_cn", "score")}
                     for h in hits[:top_k]]
        self.case_references.update({c["case_id"]: c for c in projected if c["case_id"]})
        return {"backend": backend, "cases": projected,
                "notice": "案例仅供解释与调查参考，不能证明本次攻击发生；相似度不是概率。"}

    def build_timeline(self, limit: int = 100) -> dict:
        events = sorted(self.evidence.values(), key=lambda e: (not bool(e["timestamp"]), e["timestamp"], e["line"]))
        return {"events": events[:limit], "total": len(events), "truncated": len(events) > limit,
                "notice": "只展示已查询的原始证据；时间未知的记录排在末尾。"}

    def call(self, name: str, arguments: dict) -> dict:
        if name not in TOOL_SCHEMAS or not isinstance(arguments, dict):
            raise ValueError("Unknown tool or invalid arguments")
        fn = getattr(self, name)
        inspect.signature(fn).bind(**arguments)
        properties = TOOL_SCHEMAS[name]["function"]["parameters"]["properties"]
        for key, value in arguments.items():
            expected = properties[key]["type"]
            if (expected == "string" and not isinstance(value, str)) or (
                expected == "integer" and (not isinstance(value, int) or isinstance(value, bool))):
                raise ValueError(f"Invalid type for {key}")
            if key in ("limit", "max_groups", "top_k") and not 1 <= value <= (10 if key in ("max_groups", "top_k") else 100):
                raise ValueError(f"{key} outside allowed range")
        return fn(**arguments)


def _schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": {
                k: {"type": t} for k, t in properties.items()}, "required": list(required),
                "additionalProperties": False}}}


TOOL_SCHEMAS = {s["function"]["name"]: s for s in [
    _schema("detect_anomalies", "Identify candidate signals; backend explicitly says rule or model.", {"limit": "integer"}),
    _schema("aggregate_events", "Group SSH failures in a bounded time window by IP/user/host; start here to investigate brute force.",
            {"window_minutes": "integer", "min_failures": "integer", "max_groups": "integer"}),
    _schema("search_logs", "Search full logs, including low-risk successes. Exact filters; ISO times.",
            {"src_ip": "string", "user": "string", "host": "string", "event_type": "string",
             "start": "string", "end": "string", "limit": "integer"}),
    _schema("get_event_context", "Read same-host, same-user context around an observed event. Does not prove session attribution.",
            {"event_id": "string", "before_minutes": "integer", "after_minutes": "integer", "limit": "integer"}, ["event_id"]),
    _schema("retrieve_cases", "Retrieve reference cases, never factual evidence of this incident.", {"query": "string", "top_k": "integer"}),
    _schema("build_timeline", "Build timeline from already observed original evidence.", {"limit": "integer"}),
]}
