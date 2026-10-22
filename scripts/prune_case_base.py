"""Prune low-quality auto-generated cases from the RAG case base.

Rules (each independently justified, applied only to auto_labeled_template cases):
  1. semantic-density  : >= 2 `<*>` placeholders means the template carries no matchable content
  2. baseline-template : template_count >= 5000 is mainstream traffic, not an attack pattern
                         (AUTO-0001/0002 swept in 71k/44k dnsmasq lines via one labelled row)
  3. cross-dedup       : templates that normalise to the same string across datasets are kept once

The 48 built-in hand-written cases are never touched.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/rag/attack_cases.jsonl"
MAX_PLACEHOLDERS = 1
MAX_TEMPLATE_COUNT = 5000
NORMALISERS = [(re.compile(r"<(NUM|IP|HEXID|NODEID|TIMESTAMP)>"), "<v>"),
               (re.compile(r"<\*>"), "<v>")]


def normalise(template: str) -> str:
    text = template
    for pattern, replacement in NORMALISERS:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="写回清洗结果（默认只打印报告）")
    args = parser.parse_args()

    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    auto = [c for c in cases if c.get("case_origin") == "auto_labeled_template"]
    built = [c for c in cases if c.get("case_origin") != "auto_labeled_template"]

    kept, dropped = [], []
    seen: dict[str, dict] = {}
    for case in auto:
        template = case.get("template", "")
        stars = template.count("<*>")
        count = int(case.get("template_count", 0))
        reasons = []
        if stars >= 2:
            reasons.append(f"语义密度不足（<*>×{stars}）")
        if count >= MAX_TEMPLATE_COUNT:
            reasons.append(f"主流量基线（template_count={count}）")
        norm = normalise(template)
        if norm in seen:
            reasons.append(f"与 {seen[norm]['case_id']} 跨库重复")
        if reasons:
            dropped.append((case, reasons))
        else:
            seen[norm] = case
            kept.append(case)

    print(f"自动案例 {len(auto)} 条：保留 {len(kept)}，淘汰 {len(dropped)}；内置 {len(built)} 条不动")
    print("\n-- 保留 --")
    for c in kept:
        print(f"  {c['case_id']}  {c.get('template', '')[:80]}")
    print("\n-- 淘汰 --")
    for c, reasons in dropped:
        print(f"  {c['case_id']}  {'；'.join(reasons)}")
        print(f"      {c.get('template', '')[:80]}")

    if args.apply:
        backup = CASES.with_suffix(".jsonl.bak-20261022")
        shutil.copy2(CASES, backup)
        kept_full = built + kept
        with CASES.open("w", encoding="utf-8") as f:
            for c in kept_full:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"\n已写回 {CASES}（{len(kept_full)} 条）；备份在 {backup.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
