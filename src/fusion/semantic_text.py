from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

import numpy as np


SEMANTIC_NOISE_PATTERNS = [
    (r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b", " <time> "),
    (r"\b\d{4}\.\d{2}\.\d{2}\b", " <date> "),
    (r"\b\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}(?:\.\d+)?\b", " <time> "),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", " <ip> "),
    (r"\bblk_-?\d+\b", " <block> "),
    (r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", " <id> "),
    (r"\b(?:0x)?[0-9a-f]{8,}\b", " <hex> "),
    (r"\b[a-z]+[a-z0-9]*(?:[-_:][a-z0-9]+){1,}\b", " <tag> "),
    (r"\b\d+(?:[-_.]\d+){2,}\b", " <composite> "),
    (r"\b\d+(?:\.\d+){2,}\b", " <version> "),
    (r"\b\d+\b", " <num> "),
]


def distill_log_text(text: str, min_tokens: int = 3) -> str:
    """Remove high-cardinality noise while keeping event intent words."""
    value = str(text or "").strip().lower()
    if not value:
        return "empty log event"

    for pattern, repl in SEMANTIC_NOISE_PATTERNS:
        value = re.sub(pattern, repl, value)

    value = re.sub(r"[^a-z0-9_<>\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return "empty log event"
    if len(value.split()) < int(min_tokens):
        return f"event {value}"
    return value


def build_sequence_semantic_texts_from_logs(
    log_texts: Sequence[str],
    sequence_length: int,
    start_indices: Optional[Iterable[int]] = None,
    max_steps: int = 6,
    deduplicate_adjacent: bool = True,
    min_tokens: int = 3,
) -> List[str]:
    """Build semantic summaries from distilled raw logs instead of Drain templates."""
    texts = [str(x or "") for x in log_texts]
    if sequence_length <= 0 or len(texts) < sequence_length:
        return []

    if start_indices is None:
        start_indices = range(0, len(texts) - sequence_length + 1)

    max_steps = max(1, int(max_steps))
    out: List[str] = []
    for start in start_indices:
        start = int(start)
        tail = texts[start + max(0, sequence_length - max_steps) : start + sequence_length]
        parts: List[str] = []
        last = None
        for raw in tail:
            distilled = distill_log_text(raw, min_tokens=min_tokens)
            if deduplicate_adjacent and distilled == last:
                continue
            parts.append(distilled)
            last = distilled
        out.append(" [SEQ] ".join(parts) if parts else "empty sequence")
    return out



def build_sequence_raw_texts_from_logs(
    log_texts: Sequence[str],
    sequence_length: int,
    start_indices: Optional[Iterable[int]] = None,
    max_steps: int = 12,
) -> List[str]:
    """Build compact raw sequence contexts for behavior-statistical features."""
    texts = [str(x or "").strip() for x in log_texts]
    if sequence_length <= 0 or len(texts) < sequence_length:
        return []

    if start_indices is None:
        start_indices = range(0, len(texts) - sequence_length + 1)

    max_steps = max(1, int(max_steps))
    out: List[str] = []
    for start in start_indices:
        start = int(start)
        tail = texts[start + max(0, sequence_length - max_steps) : start + sequence_length]
        parts = [re.sub(r"\s+", " ", item).strip() for item in tail if str(item).strip()]
        out.append(" [SEQ] ".join(parts) if parts else "empty sequence")
    return out


def build_sequence_semantic_texts(
    x_seq: np.ndarray,
    template_mapping: dict[int, str],
    max_steps: int = 6,
    deduplicate_adjacent: bool = True,
) -> List[str]:
    """Backward-compatible template-based semantic summary builder."""
    arr = np.asarray(x_seq)
    if arr.ndim != 2 or arr.size == 0:
        return []

    max_steps = max(1, int(max_steps))
    texts: List[str] = []
    for row in arr:
        tids = [int(x) for x in row[-max_steps:]]
        parts: List[str] = []
        last = None
        for tid in tids:
            text = str(template_mapping.get(tid, f"TEMPLATE_{tid}")).strip()
            if not text:
                continue
            if deduplicate_adjacent and text == last:
                continue
            parts.append(text)
            last = text
        texts.append(" [SEQ] ".join(parts) if parts else "empty sequence")
    return texts
