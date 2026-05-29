from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.data_processing.data_loader import DataLoader
from src.rag.attack_case_base import AttackCaseRAG
from src.utils import Config


REPORT_DIR = ROOT / "reports" / "main_experiment_unfiltered_rerun" / "rag"
CASE_FILE = REPORT_DIR / "attack_cases_unfiltered.jsonl"
INDEX_FILE = REPORT_DIR / "rag_attack_cases_unfiltered.npz"


def _load_labeled_anomaly_templates(dataset_name: str, min_template_count: int = 5) -> pd.DataFrame:
    config = Config()
    config.config.setdefault("data", {})
    config.config["data"]["dataset"] = dataset_name
    config.config["data"]["source_filter_profile"] = ""

    loader = DataLoader(config)
    parsed_df = loader.load_parsed_data()
    labels_df = loader.load_labels()
    if labels_df is None:
        raise RuntimeError(f"labels not found for dataset={dataset_name}")

    work = parsed_df.copy()
    if {"source_file", "source_line_num", "label"}.issubset(labels_df.columns):
        if "source_line_num" not in work.columns:
            work["source_line_num"] = work["line_num"]
        work = work.merge(
            labels_df[["source_file", "source_line_num", "label"]],
            on=["source_file", "source_line_num"],
            how="left",
        )
    elif {"line_num", "label"}.issubset(labels_df.columns):
        work = work.merge(labels_df[["line_num", "label"]], on="line_num", how="left")
    else:
        raise RuntimeError(f"unsupported label schema for dataset={dataset_name}")

    work["label"] = work["label"].fillna(0).astype(int)
    anomaly_df = work[work["label"] == 1].copy()
    grouped = (
        anomaly_df.groupby(["source_file", "template_id", "template"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    grouped = grouped[grouped["count"] >= int(min_template_count)].copy()
    return grouped


def _query_text(row: pd.Series) -> str:
    return (
        f"source={str(row['source_file'])}; "
        f"count={int(row['count'])}; "
        f"template={str(row['template'])}"
    )


def _evaluate_dataset(dataset_name: str, rag: AttackCaseRAG, min_template_count: int = 5) -> Dict:
    grouped = _load_labeled_anomaly_templates(dataset_name, min_template_count=min_template_count)
    eval_rows: List[Dict] = []

    for _, row in grouped.iterrows():
        case_group, _, attack_type, _, _ = rag._infer_case_meta(
            str(row["template"]), source_file=str(row["source_file"])
        )
        if attack_type == "Unknown" and case_group == "unknown":
            continue

        retrieved = rag.retrieve(_query_text(row), top_k=5, auto_build=False)
        if not retrieved:
            eval_rows.append(
                {
                    "dataset": dataset_name,
                    "source_file": str(row["source_file"]),
                    "template": str(row["template"]),
                    "count": int(row["count"]),
                    "expected_case_group": case_group,
                    "expected_attack_type": attack_type,
                    "top1_case_hit": 0,
                    "top3_case_hit": 0,
                    "top5_case_hit": 0,
                    "top1_group_hit": 0,
                    "top3_group_hit": 0,
                    "top5_group_hit": 0,
                    "top1_title": "",
                    "top1_attack_type": "",
                    "top1_score": 0.0,
                }
            )
            continue

        top1 = retrieved[:1]
        top3 = retrieved[:3]
        top5 = retrieved[:5]

        def has_attack_type(hits: List[Dict], expected: str) -> int:
            return int(any(str(hit.get("attack_type", "")) == expected for hit in hits))

        def has_case_group(hits: List[Dict], expected: str) -> int:
            return int(any(str(hit.get("case_group", "")) == expected for hit in hits))

        eval_rows.append(
            {
                "dataset": dataset_name,
                "source_file": str(row["source_file"]),
                "template": str(row["template"]),
                "count": int(row["count"]),
                "expected_case_group": case_group,
                "expected_attack_type": attack_type,
                "top1_case_hit": has_attack_type(top1, attack_type),
                "top3_case_hit": has_attack_type(top3, attack_type),
                "top5_case_hit": has_attack_type(top5, attack_type),
                "top1_group_hit": has_case_group(top1, case_group),
                "top3_group_hit": has_case_group(top3, case_group),
                "top5_group_hit": has_case_group(top5, case_group),
                "top1_title": str(top1[0].get("title", "")),
                "top1_attack_type": str(top1[0].get("attack_type", "")),
                "top1_score": float(top1[0].get("score", 0.0)),
            }
        )

    detail_df = pd.DataFrame(eval_rows)
    if detail_df.empty:
        raise RuntimeError(f"no evaluable anomaly templates for dataset={dataset_name}")

    summary = {
        "dataset": dataset_name,
        "samples": int(len(detail_df)),
        "min_template_count": int(min_template_count),
        "top1_case_hit_rate": float(detail_df["top1_case_hit"].mean()),
        "top3_case_hit_rate": float(detail_df["top3_case_hit"].mean()),
        "top5_case_hit_rate": float(detail_df["top5_case_hit"].mean()),
        "top1_group_hit_rate": float(detail_df["top1_group_hit"].mean()),
        "top3_group_hit_rate": float(detail_df["top3_group_hit"].mean()),
        "top5_group_hit_rate": float(detail_df["top5_group_hit"].mean()),
        "avg_top1_score": float(detail_df["top1_score"].mean()),
    }
    return {"summary": summary, "detail": detail_df}


def _write_markdown(summary_df: pd.DataFrame, report_path: Path, detail_paths: Dict[str, Path]) -> None:
    lines = [
        "# RAG Top-K Case Hit 评估报告",
        "",
        "## 1. 实验目的",
        "",
        "本实验用于评估当前 RAG 案例库在真实异常模板检索场景中的命中能力，重点考察前 1/3/5 个返回案例中是否包含与目标异常模板同类的安全案例。",
        "",
        "## 2. 命中定义",
        "",
        "- `Top-K case hit`：前 K 个返回案例中，是否至少有 1 条与目标模板的 `attack_type` 一致。",
        "- `Top-K group hit`：前 K 个返回案例中，是否至少有 1 条与目标模板的 `case_group` 一致。",
        "- 目标标签并非人工额外标注，而是沿用 RAG 自动增广阶段相同的 `_infer_case_meta` 规则，从带标签异常模板推断得到。",
        "",
        "## 3. 结果汇总",
        "",
        "| 数据集 | 样本数 | Top-1 case hit | Top-3 case hit | Top-5 case hit | Top-1 group hit | Top-3 group hit | Top-5 group hit | 平均Top-1分数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for _, row in summary_df.iterrows():
        lines.append(
            f"| {row['dataset']} | {int(row['samples'])} | "
            f"{row['top1_case_hit_rate']:.4f} | {row['top3_case_hit_rate']:.4f} | {row['top5_case_hit_rate']:.4f} | "
            f"{row['top1_group_hit_rate']:.4f} | {row['top3_group_hit_rate']:.4f} | {row['top5_group_hit_rate']:.4f} | "
            f"{row['avg_top1_score']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 4. 结果解读",
            "",
            "- `Top-1 case hit` 更适合衡量检索结果是否能在第一条就给出正确参考案例。",
            "- `Top-3 / Top-5 case hit` 更适合衡量 RAG 在辅助研判时的可用性，因为运维人员通常会结合前几条相似案例综合判断。",
            "- `group hit` 是更宽松的命中标准，用于观察案例库在大类层面的覆盖情况。",
            "",
            "## 5. 明细文件",
            "",
        ]
    )

    for ds, path in detail_paths.items():
        lines.append(f"- `{ds}` 明细：`{path}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _validate_markdown(report_path: Path, validation_path: Path) -> None:
    text = report_path.read_text(encoding="utf-8-sig")
    validation = {
        "valid": all(x in text for x in ["# RAG Top-K Case Hit 评估报告", "## 3. 结果汇总", "| 数据集 | 样本数 |"]),
        "encoding": "utf-8-sig",
        "bad_char_count": text.count("\ufffd"),
        "missing_count": 0,
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    os.environ["LOG_SOURCE_FILTER_PROFILE"] = ""
    config = Config()
    config.config.setdefault("rag", {})
    config.config.setdefault("data", {})
    config.config.setdefault("features", {})
    config.config['features'].setdefault('semantic', {})
    config.config["data"]["source_filter_profile"] = ""
    config.config['features']['semantic']['force_hash_fallback'] = True

    rag = AttackCaseRAG(config)
    rag.case_file = CASE_FILE
    rag.index_file = INDEX_FILE
    if not rag.load_index_if_exists():
        raise RuntimeError(f"RAG index missing: {INDEX_FILE}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    detail_paths: Dict[str, Path] = {}
    summaries: List[Dict] = []

    for dataset_name in ["harrison", "santos"]:
        result = _evaluate_dataset(dataset_name, rag, min_template_count=5)
        detail_path = REPORT_DIR / f"rag_case_hit_detail_{dataset_name}.csv"
        result["detail"].to_csv(detail_path, index=False, encoding="utf-8-sig")
        detail_paths[dataset_name] = detail_path
        summaries.append(result["summary"])

    summary_df = pd.DataFrame(summaries)
    summary_path = REPORT_DIR / "rag_case_hit_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    report_path = REPORT_DIR / "rag_case_hit_report.md"
    _write_markdown(summary_df, report_path, detail_paths)
    _validate_markdown(report_path, REPORT_DIR / "rag_case_hit_report_validation.json")

    (REPORT_DIR / "rag_case_hit_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"saved summary: {summary_path}")
    print(f"saved report: {report_path}")


if __name__ == "__main__":
    main()
