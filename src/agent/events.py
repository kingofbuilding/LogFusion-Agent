from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .profiles import DEFAULT_PROFILE, LogProfile


def parse_time(value: str) -> datetime | None:
    """Normalize explicit-year timestamps to UTC; naive timestamps are treated as UTC.

    Yearless syslog dates deliberately remain unknown instead of guessing a year.
    """
    try:
        result = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class LogEvent:
    event_id: str
    source: str
    line: int
    timestamp: str
    host: str
    src_ip: str
    user: str
    event_type: str
    raw: str

    def to_dict(self) -> dict:
        return asdict(self)


def _extract(raw: str, metadata: dict, source: str, line: int,
             profile: LogProfile = DEFAULT_PROFILE) -> LogEvent:
    stamp = str(metadata.get("timestamp", metadata.get("time", "")) or "")
    match = re.search(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", raw)
    if not stamp and match:
        stamp = match.group()
    parsed = parse_time(stamp)
    stamp = parsed.isoformat() if parsed else ""
    # Support ISO and conventional yearless syslog host fields.
    host_match = re.match(r"(?:\S+T\S+|\d{4}-\d{2}-\d{2} \S+|[A-Z][a-z]{2}\s+\d+\s+\S+)\s+(\S+)\s+\S+(?:\[\d+\])?:", raw)
    host = str(metadata.get("host", metadata.get("hostname", "")) or (host_match.group(1) if host_match else ""))
    ip_match = re.search(r"\bfrom\s+([0-9a-fA-F:.]+)", raw)
    ip = str(metadata.get("src_ip", "") or (ip_match.group(1) if ip_match else ""))
    try:
        ip = str(ipaddress.ip_address(ip)) if ip else ""
    except ValueError:
        ip = ""
    user = str(metadata.get("user", metadata.get("username", "")) or "")
    if not user:
        user = profile.extract_user(raw)
    lower = raw.lower()
    # Labels and externally supplied classifications are never used as answers. The dialect's own
    # rules decide the event type; see src/agent/profiles.py.
    kind = profile.classify(lower)
    event_id = "E-" + hashlib.sha256(f"{source}\0{line}\0{raw}".encode()).hexdigest()[:16]
    return LogEvent(event_id, source, line, stamp, host, ip, user, kind, raw)


class EventStore:
    """Full uploaded stream, including events with low or unknown detector scores."""

    def __init__(self, events: list[LogEvent], profile: LogProfile = DEFAULT_PROFILE):
        self.events = events
        self.by_id = {e.event_id: e for e in events}
        self.profile = profile
        if len(self.by_id) != len(events):
            raise ValueError("Duplicate event IDs")

    @classmethod
    def from_bytes(cls, data: bytes, source: str = "upload.log", max_events: int = 100_000,
                   profile: LogProfile = DEFAULT_PROFILE) -> "EventStore":
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("单次调查最多支持 20 MiB 日志")
        text = data.decode("utf-8-sig")
        suffix = Path(source).suffix.lower()
        rows: list[tuple[int, object]]
        if suffix == ".csv":
            rows = list(enumerate(csv.DictReader(io.StringIO(text)), 2))
        elif suffix == ".json":
            payload = json.loads(text)
            if not isinstance(payload, list):
                raise ValueError("JSON 输入必须是日志对象数组")
            rows = list(enumerate(payload, 1))
        else:
            rows = [(i, json.loads(s) if suffix == ".jsonl" else s)
                    for i, s in enumerate(text.splitlines(), 1) if s.strip()]
        if len(rows) > max_events:
            raise ValueError(f"单次调查最多支持 {max_events} 条日志；请缩小输入范围")
        events = []
        for line, row in rows:
            metadata = row if isinstance(row, dict) else {}
            if isinstance(row, dict):
                # Explicit projection prevents attack_label / ground truth leakage.
                raw = next((str(row[k]) for k in ("message", "log_text", "raw", "content") if row.get(k)), "")
                if not raw:
                    raise ValueError(f"第 {line} 条日志缺少 message/log_text/raw/content 字段")
            elif isinstance(row, str):
                raw = row
            else:
                raise ValueError(f"第 {line} 条日志必须是字符串或对象")
            if len(raw) > 32_768:
                raise ValueError(f"第 {line} 条日志过长（最大 32768 字符）")
            events.append(_extract(raw, metadata, Path(source).name, line, profile))
        return cls(events, profile)

    @classmethod
    def from_path(cls, path: str | Path, profile: LogProfile = DEFAULT_PROFILE) -> "EventStore":
        path = Path(path)
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("单次调查最多支持 20 MiB 日志")
        return cls.from_bytes(path.read_bytes(), path.name, profile=profile)

    def coverage(self) -> dict:
        times = sorted(e.timestamp for e in self.events if e.timestamp)
        return {"events": len(self.events), "timestamped_events": len(times),
                "missing_timestamps": len(self.events) - len(times),
                "start": times[0] if times else "", "end": times[-1] if times else "",
                "timezone_policy": "Naive timestamps treated as UTC; yearless dates unknown"}
