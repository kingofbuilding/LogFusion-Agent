"""Build evaluation cases from the real AIT-LDS testbed logs and their line-level labels.

Unlike `generate_cases.py` (synthetic), these cases are cut from the shipped testbed logs:
- a case is a contiguous window around one attack activity, with surrounding normal traffic kept;
- labels come from `data/raw/<dataset>/labels/<log path>` (one JSON object per labelled line);
- expected evidence is derived from the labelled lines, never hand-written.

Source layout (predecessor repo):
    data/raw/<dataset>/gather/<log path>     raw log lines
    data/raw/<dataset>/labels/<log path>     {"line": N, "labels": [...], "rules": {...}}

Usage:
    python -m benchmarks.build_real_cases                 # build the default suite
    python -m benchmarks.build_real_cases --check         # verify committed cases match
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmarks/cases_real"
RAW_ROOT = Path(r"D:\毕业设计\log_analysis_system_complete\data\raw")
GOAL = "调查这批真实日志中是否存在入侵活动，并指出具体证据"

# Log paths worth cutting cases from: they carry security-relevant events (auth, audit, vpn, web).
# dnsmasq is deliberately excluded: it is 300k+ lines of mostly-fixed traffic and would dominate.
TARGETS = [
    ("harrison", "intranet_server/logs/auth.log", "privilege_escalation"),
    ("harrison", "intranet_server/logs/audit/audit.log", "privilege_escalation"),
    ("harrison", "vpn/logs/openvpn.log", "vpn_access"),
    ("santos", "intranet_server/logs/auth.log", "privilege_escalation"),
    ("santos", "intranet_server/logs/audit/audit.log", "privilege_escalation"),
    ("santos", "vpn/logs/openvpn.log", "vpn_access"),
    ("fox", "intranet_server/logs/auth.log", "privilege_escalation"),
    ("fox", "intranet_server/logs/audit/audit.log", "privilege_escalation"),
    ("fox", "vpn/logs/openvpn.log", "vpn_access"),
]

# Keep normal traffic on both sides so the case is not a single-attack excerpt.
CONTEXT_BEFORE = 120
CONTEXT_AFTER = 120
MAX_LINES = 900


def _label_path(dataset: str, rel: str) -> Path:
    return RAW_ROOT / dataset / "labels" / Path(rel)


def _raw_path(dataset: str, rel: str) -> Path:
    return RAW_ROOT / dataset / "gather" / Path(rel)


def _load_labels(dataset: str, rel: str) -> dict[int, list[str]]:
    path = _label_path(dataset, rel)
    if not path.exists():
        return {}
    labels: dict[int, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        labels[int(row["line"])] = sorted(row.get("labels") or [])
    return labels


def _read_lines(dataset: str, rel: str) -> list[str]:
    path = _raw_path(dataset, rel)
    if not path.exists():
        raise FileNotFoundError(f"缺少原始日志：{path}")
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _event_id(dataset: str, rel: str, line_no: int, text: str) -> str:
    digest = hashlib.sha256(f"{dataset}\0{rel}\0{line_no}\0{text}".encode()).hexdigest()[:16]
    return "E-" + digest


def _activity_blocks(labelled: list[int], gap: int = 40) -> list[tuple[int, int]]:
    """Group labelled line numbers into contiguous activities (tolerating small gaps)."""
    blocks: list[tuple[int, int]] = []
    for line_no in sorted(labelled):
        if blocks and line_no - blocks[-1][1] <= gap:
            blocks[-1] = (blocks[-1][0], line_no)
        else:
            blocks.append((line_no, line_no))
    return blocks


def build_case(dataset: str, rel: str, category: str, start: int, end: int,
               labels: dict[int, list[str]], lines: list[str], index: int) -> tuple[str, dict]:
    lo = max(1, start - CONTEXT_BEFORE)
    hi = min(len(lines), end + CONTEXT_AFTER)
    if hi - lo + 1 > MAX_LINES:
        hi = lo + MAX_LINES - 1
    case_id = f"real-{index:03d}"
    rows, evidence = [], []
    tags: dict[str, int] = defaultdict(int)
    for line_no in range(lo, hi + 1):
        text = lines[line_no - 1]
        event_id = _event_id(dataset, rel, line_no, text)
        rows.append({"timestamp": "", "host": _host_from(rel), "message": text})
        if line_no in labels:
            evidence.append(event_id)
            for tag in labels[line_no]:
                tags[tag] += 1
    has_incident = bool(evidence)
    meta = {
        "case_id": case_id,
        "category": category,
        "dataset": dataset,
        "source_log": rel,
        "log_file": f"{case_id}.jsonl",
        "goal": GOAL,
        "expected": {
            "incident_present": has_incident,
            "must_find_event_ids": evidence,
            "verdict": "suspicious" if has_incident else "insufficient_evidence",
        },
        "line_range": [lo, hi],
        "labelled_lines": end - start + 1,
        "attack_tags": dict(sorted(tags.items())),
        "note": "真实 AIT-LDS 测试床日志切片；标签来自官方逐行标注，期望证据由标注推导。",
    }
    return case_id, {"meta": meta, "rows": rows}


def _host_from(rel: str) -> str:
    return rel.split("/")[0] or "unknown"


def generate_all(out_dir: Path = CASES_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    index = 0
    for dataset, rel, category in TARGETS:
        labels = _load_labels(dataset, rel)
        if not labels:
            continue
        lines = _read_lines(dataset, rel)
        for start, end in _activity_blocks(list(labels)):
            index += 1
            case_id, payload = build_case(dataset, rel, category, start, end, labels, lines, index)
            meta = payload["meta"]
            (out_dir / f"{case_id}.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in payload["rows"]) + "\n",
                encoding="utf-8", newline="\n")
            (out_dir / f"{case_id}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            cases.append(meta)
    manifest = {
        "suite": "logfusion-agent-real-ait-lds",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(cases),
        "counts": dict(sorted(__import__("collections").Counter(c["category"] for c in cases).items())),
        "datasets": sorted({c["dataset"] for c in cases}),
        "generator": "benchmarks/build_real_cases.py",
        "note": "真实日志切片 + 官方行级标注；无合成内容。期望证据 = 标注行的 event_id。",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    return manifest


def check(out_dir: Path = CASES_DIR) -> list[str]:
    problems = []
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for case_file in sorted(out_dir.glob("real-*.json")):
        meta = json.loads(case_file.read_text(encoding="utf-8"))
        for key in ("case_id", "category", "log_file", "expected", "line_range"):
            if key not in meta:
                problems.append(f"{case_file.name}: missing {key}")
        log = out_dir / meta["log_file"]
        if not log.exists():
            problems.append(f"{case_file.name}: missing {meta['log_file']}")
            continue
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != meta["line_range"][1] - meta["line_range"][0] + 1:
            problems.append(f"{case_file.name}: line count mismatch")
    if len(list(out_dir.glob("real-*.json"))) != manifest["total"]:
        problems.append("manifest total does not match case count")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="用真实 AIT-LDS 日志构建评测用例")
    parser.add_argument("--out", type=Path, default=CASES_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check(args.out)
        print("\n".join(problems) if problems else "OK: 真实用例与生成器一致")
        return 1 if problems else 0
    if not RAW_ROOT.exists():
        print(f"未找到原始日志根目录：{RAW_ROOT}")
        return 2
    manifest = generate_all(args.out)
    print(f"生成 {manifest['total']} 条真实用例 -> {args.out}")
    print("  数据集:", ", ".join(manifest["datasets"]))
    for category, count in manifest["counts"].items():
        print(f"  {category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
