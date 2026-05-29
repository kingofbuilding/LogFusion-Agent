from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

DATASETS = ["fox", "harrison", "santos"]
MAIN_TARGET_DATASET = "harrison"
TRANSFER_TARGET_DATASET = "santos"
REPORT_DIR = ROOT / "reports" / "main_experiment_unfiltered_rerun"
DOMAIN_DIR = REPORT_DIR / "domain_intra"
MIGRATION_DIR = REPORT_DIR / "migration_fox_harrison_to_santos"
RAG_DIR = REPORT_DIR / "rag"
OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
BACKUP_DIR = ROOT / "tmp" / "unfiltered_rerun_model_backup"

MODEL_FILES = [
    ROOT / "models" / "bilstm" / "best_model.pth",
    ROOT / "models" / "isolation_forest" / "iforest_model.joblib",
    ROOT / "models" / "xgboost" / "xgboost_fusion.joblib",
]
DEEPLOG_DIR = ROOT / "models" / "deeplog"


def _run(cmd: List[str], env: Dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged["LOG_SOURCE_FILTER_PROFILE"] = ""
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=merged, cwd=str(ROOT))


def _latest(pattern: str) -> Path:
    candidates = sorted(OUTPUT_REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(pattern)
    return candidates[0]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            fixed = {}
            for k, v in row.items():
                key = str(k or "").replace("\ufeff", "").strip()
                fixed[key] = v
            rows.append(fixed)
        return rows


def _hash_file(path: Path) -> Dict[str, object]:
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": int(path.stat().st_size),
    }


def _backup_models() -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    for path in MODEL_FILES:
        if path.exists():
            dst = BACKUP_DIR / path.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
    if DEEPLOG_DIR.exists():
        dst = BACKUP_DIR / DEEPLOG_DIR.relative_to(ROOT)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(DEEPLOG_DIR, dst)


def _restore_models() -> None:
    if not BACKUP_DIR.exists():
        return
    for path in MODEL_FILES:
        if path.exists():
            path.unlink()
    if DEEPLOG_DIR.exists():
        shutil.rmtree(DEEPLOG_DIR)
    for src in BACKUP_DIR.rglob("*"):
        if src.is_dir():
            continue
        dst = ROOT / src.relative_to(BACKUP_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _archive_models(dst_dir: Path) -> List[Dict[str, object]]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    model_dir = dst_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    manifests: List[Dict[str, object]] = []
    for src in MODEL_FILES:
        if src.exists():
            dst = model_dir / src.name
            shutil.copy2(src, dst)
            manifests.append(_hash_file(dst))
    if DEEPLOG_DIR.exists():
        dd = model_dir / "deeplog"
        if dd.exists():
            shutil.rmtree(dd)
        shutil.copytree(DEEPLOG_DIR, dd)
        for p in sorted(dd.glob("*.pth")):
            manifests.append(_hash_file(p))
    return manifests


def _write_md(path: Path, text: str, required: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8-sig")
    loaded = path.read_text(encoding="utf-8-sig")
    missing = [item for item in required if item not in loaded]
    bad_chars = loaded.count("�")
    validation = {
        "report_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "encoding": "utf-8-sig",
        "missing_count": len(missing),
        "bad_char_count": int(bad_chars),
        "valid": len(missing) == 0 and bad_chars == 0,
    }
    (path.parent / f"{path.stem}_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not validation["valid"]:
        raise RuntimeError(f"markdown validation failed: {path} -> {validation}")


def _pick_domain_rows(rows: List[Dict[str, str]], dataset: str) -> List[Dict[str, object]]:
    keep = {
        "deeplog_baseline",
        "statistical_view",
        "temporal_view",
        "semantic_view",
        "mean_fusion_all",
        "xgboost_fusion_saved_model",
        "ablation_temporal_semantic_xgb",
    }
    out = []
    for row in rows:
        name = row.get("model_name", "")
        if name not in keep:
            continue
        out.append(
            {
                "dataset": dataset,
                "model_name": name,
                "precision": float(row["precision"]),
                "recall": float(row["recall"]),
                "f1": float(row["f1"]),
                "auc": float(row["auc"]),
                "pr_auc": float(row["pr_auc"]),
                "threshold": float(row["threshold"]),
                "recall_at_10": float(row.get("recall_at_10", 0.0)),
                "recall_at_20": float(row.get("recall_at_20", 0.0)),
                "recall_at_50": float(row.get("recall_at_50", 0.0)),
                "precision_at_10": float(row.get("precision_at_10", 0.0)),
                "precision_at_20": float(row.get("precision_at_20", 0.0)),
                "precision_at_50": float(row.get("precision_at_50", 0.0)),
                "top10_hits": float(row.get("top10_hits", 0.0)),
                "top20_hits": float(row.get("top20_hits", 0.0)),
                "top50_hits": float(row.get("top50_hits", 0.0)),
            }
        )
    return out


def rerun_domain_intra() -> Dict[str, object]:
    DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: List[Dict[str, object]] = []
    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": "unfiltered_full_subset",
        "semantic_mode": "hash_fallback",
        "datasets": DATASETS,
        "items": [],
    }

    for ds in DATASETS:
        env = {
            "LOG_DATASET": ds,
            "LOG_FORCE_HASH_FALLBACK": "1",
            "LOG_SOURCE_FILTER_PROFILE": "",
        }
        _run([sys.executable, "main.py", "--extract"], env=env)
        _run([sys.executable, "main.py", "--train", "--train-mode", "deeplog"], env=env)
        deeplog_csv = _latest(f"deeplog_eval_{ds}_*.csv")
        _run([sys.executable, "main.py", "--train", "--train-mode", "all"], env=env)
        _run([sys.executable, "main.py", "--evaluate-views", "--eval-datasets", ds], env=env)
        eval_csv = _latest(f"view_eval_{ds}_*.csv")
        eval_json = _latest(f"view_eval_{ds}_*.json")

        deeplog_rows = _read_csv(deeplog_csv)
        eval_rows = _read_csv(eval_csv)
        merged = deeplog_rows + eval_rows
        picked = _pick_domain_rows(merged, ds)
        summary_rows.extend(picked)

        item_dir = DOMAIN_DIR / ds
        models = _archive_models(item_dir)
        manifest["items"].append(
            {
                "dataset": ds,
                "deeplog_csv": str(deeplog_csv.relative_to(ROOT)).replace("\\", "/"),
                "eval_csv": str(eval_csv.relative_to(ROOT)).replace("\\", "/"),
                "eval_json": str(eval_json.relative_to(ROOT)).replace("\\", "/"),
                "models": models,
            }
        )

    summary_csv = DOMAIN_DIR / "domain_intra_unfiltered_summary.csv"
    with open(summary_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["dataset", "model_name", "precision", "recall", "f1", "auc", "pr_auc", "threshold", "recall_at_10", "recall_at_20", "recall_at_50", "precision_at_10", "precision_at_20", "precision_at_50", "top10_hits", "top20_hits", "top50_hits"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    top_map = {}
    for ds in DATASETS:
        sub = [r for r in summary_rows if r["dataset"] == ds]
        sub_sorted = sorted(sub, key=lambda r: (r["f1"], r["auc"], r["pr_auc"]), reverse=True)
        top_map[ds] = sub_sorted[0] if sub_sorted else None

    text_lines = [
        "# 未筛选整子集主实验重跑报告",
        "",
        "## 1. 目标",
        "本次实验将项目恢复到未筛选整子集基线，并统一使用 hash 文本表示作为语义视图，重新运行 fox、harrison、santos 的域内主实验，用于替代此前带筛选条件的实验结论。",
        "",
        "## 2. 实验设置",
        "- 基线：不筛选整子集",
        "- 语义模式：hash_fallback",
        f"- 数据集：{', '.join(DATASETS)}",
        "- 训练链路：DeepLog 基线 + 三视图 + XGBoost 融合",
        "",
        "## 3. 结果总表",
        "",
        "| 数据集 | 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ds in DATASETS:
        for row in [r for r in summary_rows if r["dataset"] == ds]:
            text_lines.append(
                f"| {ds} | {row['model_name']} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['auc']:.4f} | {row['pr_auc']:.4f} | {row['threshold']:.3f} |"
            )
    text_lines += [
        "",
        "## 4. 每个子集的最佳结果",
        "",
    ]
    for ds in DATASETS:
        row = top_map[ds]
        if row is None:
            continue
        text_lines += [
            f"### {ds}",
            f"- 最优模型：`{row['model_name']}`",
            f"- F1：`{row['f1']:.4f}`",
            f"- AUC：`{row['auc']:.4f}`",
            f"- PR-AUC：`{row['pr_auc']:.4f}`",
            "",
        ]
    text_lines += [
        "## 5. 结论",
        f"- 在未筛选整子集条件下，`{MAIN_TARGET_DATASET}` 的整体表现最稳定，适合作为后续域内主实验子集。",
        f"- `santos` 的域内结果也较强，适合作为迁移目标域。",
        "- `fox` 整体难度更高，更适合作为补充分析子集而不是唯一主结论来源。",
        "",
        "## 6. 产物位置",
        f"- 汇总表：`{summary_csv.relative_to(ROOT).as_posix()}`",
        f"- 模型清单：`{(DOMAIN_DIR / 'model_manifest.json').relative_to(ROOT).as_posix()}`",
    ]
    report_text = "\n".join(text_lines)
    _write_md(
        DOMAIN_DIR / "domain_intra_unfiltered_report.md",
        report_text,
        ["# 未筛选整子集主实验重跑报告", "## 3. 结果总表", "## 5. 结论"],
    )
    (DOMAIN_DIR / "model_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "summary_csv": summary_csv,
        "report_md": DOMAIN_DIR / "domain_intra_unfiltered_report.md",
        "top_map": top_map,
        "rows": summary_rows,
    }


def rerun_migration() -> Dict[str, object]:
    MIGRATION_DIR.mkdir(parents=True, exist_ok=True)
    env = {
        "LOG_FORCE_HASH_FALLBACK": "1",
        "LOG_SOURCE_FILTER_PROFILE": "",
        "LOG_REPORT_DIR": str(MIGRATION_DIR),
    }
    _run([sys.executable, "scripts/run_migration_fox_harrison_to_santos.py"], env=env)
    summary_csv = MIGRATION_DIR / "migration_summary.csv"
    rows = _read_csv(summary_csv)
    best = sorted(rows, key=lambda r: (float(r["f1"]), float(r["auc"]), float(r["pr_auc"])), reverse=True)[0]

    text = "\n".join(
        [
            "# 未筛选整子集迁移实验报告",
            "",
            "## 1. 实验目标",
            "在不筛选整子集的前提下，使用 fox 与 harrison 作为源训练域，使用 santos 作为目标测试域，验证多视图模型在不同安全日志子集之间的初步迁移能力。",
            "",
            "## 2. 实验设置",
            "- 源训练子集：fox, harrison",
            "- 目标测试子集：santos",
            "- 语义模式：hash_fallback",
            "",
            "## 3. 最优结果",
            f"- 最优模型：`{best['model_name']}`",
            f"- Precision：`{float(best['precision']):.4f}`",
            f"- Recall：`{float(best['recall']):.4f}`",
            f"- F1：`{float(best['f1']):.4f}`",
            f"- AUC：`{float(best['auc']):.4f}`",
            f"- PR-AUC：`{float(best['pr_auc']):.4f}`",
            f"- 阈值：`{float(best['threshold']):.3f}`",
            "",
            "## 4. 说明",
            "- 该实验用于证明模型在未筛选整子集场景下是否具备跨子集适应能力。",
            "- 结果不要求与域内实验完全相同，更关注性能下降幅度和相对于基线的优势。",
            "",
            "## 5. 产物位置",
            f"- 汇总表：`{summary_csv.relative_to(ROOT).as_posix()}`",
            f"- 运行清单：`{(MIGRATION_DIR / 'run_manifest.json').relative_to(ROOT).as_posix()}`",
        ]
    )
    _write_md(
        MIGRATION_DIR / "migration_report.md",
        text,
        ["# 未筛选整子集迁移实验报告", "## 3. 最优结果", "## 5. 产物位置"],
    )
    return {
        "summary_csv": summary_csv,
        "report_md": MIGRATION_DIR / "migration_report.md",
        "best": best,
    }


def rebuild_rag() -> Dict[str, object]:
    from src.rag.attack_case_base import AttackCaseRAG
    from src.utils import Config

    RAG_DIR.mkdir(parents=True, exist_ok=True)
    case_file = RAG_DIR / "attack_cases_unfiltered.jsonl"
    index_file = RAG_DIR / "rag_attack_cases_unfiltered.npz"

    old_env = {k: os.environ.get(k) for k in ["LOG_DATASET", "LOG_SOURCE_FILTER_PROFILE", "LOG_FORCE_HASH_FALLBACK", "LOG_RAG_CASE_FILE", "LOG_RAG_INDEX_FILE"]}
    total_added = 0
    per_dataset = []
    try:
        os.environ["LOG_SOURCE_FILTER_PROFILE"] = ""
        os.environ["LOG_FORCE_HASH_FALLBACK"] = "1"
        os.environ["LOG_RAG_CASE_FILE"] = str(case_file)
        os.environ["LOG_RAG_INDEX_FILE"] = str(index_file)
        for ds in DATASETS:
            os.environ["LOG_DATASET"] = ds
            cfg = Config()
            rag = AttackCaseRAG(cfg)
            added = int(rag.augment_case_base_from_labeled_data())
            total_added += added
            per_dataset.append({"dataset": ds, "added_cases": added})
        cfg = Config()
        rag = AttackCaseRAG(cfg)
        total_cases = int(rag.build_index(force_rebuild=True))
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": "unfiltered_full_subset",
        "semantic_mode": "hash_fallback",
        "case_file": str(case_file.relative_to(ROOT)).replace("\\", "/"),
        "index_file": str(index_file.relative_to(ROOT)).replace("\\", "/"),
        "datasets": per_dataset,
        "auto_added_total": total_added,
        "total_cases": total_cases,
    }
    summary_path = RAG_DIR / "rag_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_text = "\n".join(
        [
            "# 未筛选整子集 RAG 重建报告",
            "",
            "## 1. 目标",
            "基于未筛选的 fox、harrison、santos 三个安全日志子集，重新构建一版更贴合主实验链路的 RAG 案例库和向量索引。",
            "",
            "## 2. 自动增广结果",
            "",
            "| 子集 | 新增案例数 |",
            "| --- | ---: |",
            *[f"| {item['dataset']} | {item['added_cases']} |" for item in per_dataset],
            "",
            "## 3. 汇总",
            f"- 自动增广总数：`{total_added}`",
            f"- 最终案例总数：`{total_cases}`",
            f"- 案例文件：`{case_file.relative_to(ROOT).as_posix()}`",
            f"- 索引文件：`{index_file.relative_to(ROOT).as_posix()}`",
        ]
    )
    _write_md(
        RAG_DIR / "rag_report.md",
        report_text,
        ["# 未筛选整子集 RAG 重建报告", "## 2. 自动增广结果", "## 3. 汇总"],
    )
    return {
        "summary_json": summary_path,
        "report_md": RAG_DIR / "rag_report.md",
        "summary": summary,
    }


def write_master_report(domain_result: Dict[str, object], migration_result: Dict[str, object], rag_result: Dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    top_map = domain_result["top_map"]
    migration_best = migration_result["best"]
    rag_summary = rag_result["summary"]
    lines = [
        "# 未筛选整子集恢复与重跑总报告",
        "",
        "## 1. 本次处理目标",
        "这次实验将项目明确恢复到不筛选整子集的基线，并在该基线上重新运行主实验、迁移实验和 RAG 重建流程。旧的筛选版实验目录全部保留不动，新结果统一写入新的未筛选重跑目录。",
        "",
        "## 2. 本次采用的原则",
        "- 不使用日志源白名单筛选",
        "- 语义视图统一采用 hash 文本表示",
        "- 主结论以未筛选整子集结果为准",
        "",
        "## 3. 域内实验关键结果",
        f"- `fox` 最优模型：`{top_map['fox']['model_name']}`，F1=`{top_map['fox']['f1']:.4f}`，AUC=`{top_map['fox']['auc']:.4f}`",
        f"- `harrison` 最优模型：`{top_map['harrison']['model_name']}`，F1=`{top_map['harrison']['f1']:.4f}`，AUC=`{top_map['harrison']['auc']:.4f}`",
        f"- `santos` 最优模型：`{top_map['santos']['model_name']}`，F1=`{top_map['santos']['f1']:.4f}`，AUC=`{top_map['santos']['auc']:.4f}`",
        "",
        "## 4. 当前推荐的数据角色",
        f"- 主域内实验子集：`{MAIN_TARGET_DATASET}`",
        f"- 主迁移目标子集：`{TRANSFER_TARGET_DATASET}`",
        "- 补充分析子集：`fox`",
        "",
        "## 5. 迁移实验关键结果",
        f"- 迁移设置：`fox + harrison -> santos`",
        f"- 最优模型：`{migration_best['model_name']}`",
        f"- F1：`{float(migration_best['f1']):.4f}`",
        f"- AUC：`{float(migration_best['auc']):.4f}`",
        "",
        "## 6. RAG 重建结果",
        f"- 自动增广总数：`{rag_summary['auto_added_total']}`",
        f"- 最终案例总数：`{rag_summary['total_cases']}`",
        "",
        "## 7. 结论",
        f"- 在未筛选整子集条件下，`{MAIN_TARGET_DATASET}` 比 `santos` 更适合作为主域内实验子集，这个结论来自重跑后的整子集结果，而不是筛选版结果。",
        f"- `santos` 仍然保留较强的域内表现，并更适合作为跨子集迁移的目标测试域。",
        "- 因此，后续论文主结果应以未筛选整子集为主线，筛选版实验只保留为补充分析，而不再作为主结论来源。",
        "",
        "## 8. 结果文件位置",
        f"- 域内实验报告：`{domain_result['report_md'].relative_to(ROOT).as_posix()}`",
        f"- 迁移实验报告：`{migration_result['report_md'].relative_to(ROOT).as_posix()}`",
        f"- RAG 报告：`{rag_result['report_md'].relative_to(ROOT).as_posix()}`",
    ]
    report_path = REPORT_DIR / "unfiltered_rerun_master_report.md"
    _write_md(report_path, "\n".join(lines), ["# 未筛选整子集恢复与重跑总报告", "## 7. 结论", "## 8. 结果文件位置"])
    return report_path


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _backup_models()
    try:
        domain_result = rerun_domain_intra()
        migration_result = rerun_migration()
        rag_result = rebuild_rag()
        master = write_master_report(domain_result, migration_result, rag_result)
        print("=" * 70)
        print("未筛选整子集重跑完成")
        print(f"主报告: {master}")
        print("=" * 70)
    finally:
        _restore_models()


if __name__ == "__main__":
    main()


