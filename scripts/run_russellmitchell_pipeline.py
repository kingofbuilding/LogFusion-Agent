from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import joblib
import torch


ROOT = Path(__file__).resolve().parents[1]
TRACKED_DIR = ROOT / "reports" / "russellmitchell"
TRACKED_MODELS_DIR = TRACKED_DIR / "models"
DATASET = "russellmitchell"


def run_cmd(cmd: List[str], env: dict) -> None:
    print("\n" + "=" * 88)
    print("RUN:", " ".join(cmd))
    print("=" * 88)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def latest_file(pattern: str) -> Path:
    files = sorted(ROOT.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matched: {pattern}")
    return files[-1]


def resolve_eval_artifact(kind: str) -> Path:
    pattern = f"outputs/reports/view_eval_{DATASET}_*.{kind}"
    files = sorted(ROOT.glob(pattern))
    if files:
        return files[-1]
    tracked = TRACKED_DIR / f"view_eval_latest.{kind}"
    if tracked.exists():
        return tracked
    raise FileNotFoundError(f"No evaluation artifact found for: {kind}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_models_manifest(local_model_paths: dict[str, Path]) -> Path:
    TRACKED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in TRACKED_MODELS_DIR.glob("*"):
        if stale.suffix in {".pth", ".joblib"} and stale.is_file():
            stale.unlink()
    previous = {}
    previous_path = TRACKED_MODELS_DIR / "model_manifest.json"
    if previous_path.exists():
        try:
            previous_obj = json.loads(previous_path.read_text(encoding="utf-8"))
            previous = {item.get("name"): item for item in previous_obj.get("models", [])}
        except Exception:
            previous = {}
    rows: list[dict] = []
    for name, path in local_model_paths.items():
        item = {
            "name": name,
            "local_path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else "",
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
        if path.exists() and path.suffix == ".pth":
            ckpt = torch.load(path, map_location="cpu")
            item["metadata"] = {
                "best_threshold": float(ckpt.get("best_threshold", 0.0)),
                "vocab_size": int(ckpt.get("vocab_size", 0)),
                "metrics": ckpt.get("metrics", {}),
            }
        elif path.exists() and path.suffix == ".joblib":
            obj = joblib.load(path)
            if isinstance(obj, dict) and "model" in obj:
                model = obj["model"]
                item["metadata"] = {
                    "use_cross_features": bool(obj.get("use_cross_features", False)),
                    "n_features_in": int(getattr(model, "n_features_in_", 0)),
                    "n_estimators": int(getattr(model, "n_estimators", 0)),
                }
            else:
                item["metadata"] = {
                    "n_features_in": int(getattr(obj, "n_features_in_", 0)),
                    "n_estimators": int(getattr(obj, "n_estimators", 0)),
                }
        elif name in previous:
            prev = previous[name]
            item["sha256"] = prev.get("sha256", "")
            item["size_bytes"] = prev.get("size_bytes", 0)
            if prev.get("metadata") is not None:
                item["metadata"] = prev.get("metadata")
            item["reference_only"] = True
        rows.append(item)

    manifest = {
        "note": "二进制模型文件不提交到仓库；这里提供本地模型路径、SHA256、大小和关键元数据，便于本地复现实验后比对。",
        "models": rows,
    }
    out_path = TRACKED_MODELS_DIR / "model_manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = TRACKED_MODELS_DIR / "README.md"
    readme.write_text(
        "# 可见模型说明\n\n"
        "由于仓库不支持提交二进制模型文件，这里只保存模型清单、哈希和关键元数据。\n\n"
        "请在本地运行 `python scripts/run_russellmitchell_pipeline.py` 后，使用 `models/` 下生成的模型文件，"
        "并对照 `model_manifest.json` 校验 SHA256 与大小是否一致。\n",
        encoding="utf-8",
    )
    return out_path


def build_report(eval_csv: Path, eval_json: Path, manifest_path: Path) -> Path:
    df = pd.read_csv(eval_csv)
    summary = json.loads(eval_json.read_text(encoding="utf-8"))
    best = summary["best_by_dataset"][DATASET]
    ranking = df[["model_name", "precision", "recall", "f1", "auc", "pr_auc", "threshold"]].sort_values("f1", ascending=False)

    table_lines = [
        "| 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in ranking.iterrows():
        table_lines.append(
            f"| {row['model_name']} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['auc']:.4f} | {row['pr_auc']:.4f} | {row['threshold']:.3f} |"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_lines = []
    for item in manifest["local_artifacts"]:
        artifact_lines.append(f"- `{item['path']}`：{'存在' if item['exists'] else '缺失'}")
    table_block = "\n".join(table_lines)
    artifacts_block = "\n".join(artifact_lines)

    text = f"""# russellmitchell 全流程复现实验报告

## 1. 结论先看
- 本次重新跑的是 **AIT-LDS v2 / russellmitchell** 全流程。
- 关键结果已经额外保存到 **GitHub 可见目录**：`reports/russellmitchell/`。
- 同时保留本地运行产物目录结构：`data/raw/`、`data/processed/`、`data/vectors/`、`models/`、`outputs/`。
- 仓库不提交二进制模型文件，但已把模型 SHA256、大小和关键元数据同步保存到 **GitHub 可见目录**：`reports/russellmitchell/models/`。

## 2. 为什么这次结果要另存到 GitHub 可见目录
前面的做法只把结果写进本地运行目录，而这些目录通常会被 `.gitignore` 排除，因此虽然本地跑过，GitHub 仓库里看不到。为避免“跑过但仓库里没有结果”的问题，这次把**评估 CSV/JSON、运行清单、中文报告**同步保存到 `reports/russellmitchell/`。

## 3. 最优结果
- 最优模型：`{best['model_name']}`
- Precision：**{best['precision']:.4f}**
- Recall：**{best['recall']:.4f}**
- F1：**{best['f1']:.4f}**
- AUC：**{best['auc']:.4f}**
- PR-AUC：**{best['pr_auc']:.4f}**
- 最优阈值：**{best['threshold']:.3f}**

## 4. 多视图评估结果（按 F1 从高到低）
{table_block}

## 5. 对你之前结果偏低的解释
如果你之前跑出来的指标明显更低，常见原因包括：
1. 运行时没有沿用同一份已训练模型，而是重新训练了不同随机划分/不同阶段结果；
2. 本地产物目录没有持久化保存，导致“看起来跑过，但后来模型/中间结果没了”；
3. 语义特征在当前环境下回退到了哈希向量模式，而不是在线下载的 sentence-transformers；
4. 评估时使用的输入数据范围不同，例如是否只抽取带标签镜像日志。

## 6. 本次保留的本地产物
{artifacts_block}

## 7. GitHub 可见结果目录
- `reports/russellmitchell/view_eval_latest.csv`
- `reports/russellmitchell/view_eval_latest.json`
- `reports/russellmitchell/run_manifest.json`
- `reports/russellmitchell/实验报告.md`
- `reports/russellmitchell/models/model_manifest.json`
- `reports/russellmitchell/models/README.md`

## 8. 运行说明
本次运行时间：{manifest['generated_at_utc']} UTC。
命令清单见 `reports/russellmitchell/run_manifest.json`。
"""

    report_path = TRACKED_DIR / "实验报告.md"
    report_path.write_text(text, encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="重新跑 russellmitchell 全流程并生成可见结果归档")
    parser.add_argument("--skip-pipeline", action="store_true", help="跳过训练/评估，仅根据现有本地产物刷新可见归档")
    args = parser.parse_args()

    TRACKED_DIR.mkdir(parents=True, exist_ok=True)
    TRACKED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOG_DATASET"] = DATASET

    commands = [
        ["python", "src/data_processing/prepare_ait_lds.py", "--subset", DATASET],
        ["python", "main.py", "--parse"],
        ["python", "main.py", "--extract"],
        ["python", "main.py", "--train", "--train-mode", "bilstm"],
        ["python", "main.py", "--train", "--train-mode", "iforest"],
        ["python", "main.py", "--train", "--train-mode", "xgboost"],
        ["python", "main.py", "--evaluate-views", "--eval-datasets", DATASET],
        ["python", "main.py", "--build-rag", "--rag-force"],
    ]

    if not args.skip_pipeline:
        for cmd in commands:
            run_cmd(cmd, env)

    eval_csv = resolve_eval_artifact("csv")
    eval_json = resolve_eval_artifact("json")
    tracked_csv = TRACKED_DIR / "view_eval_latest.csv"
    tracked_json = TRACKED_DIR / "view_eval_latest.json"
    if eval_csv.resolve() != tracked_csv.resolve():
        shutil.copy2(eval_csv, tracked_csv)
    if eval_json.resolve() != tracked_json.resolve():
        shutil.copy2(eval_json, tracked_json)
    local_model_paths = {
        "bilstm": ROOT / "models/bilstm/best_model.pth",
        "iforest": ROOT / "models/isolation_forest/iforest_model.joblib",
        "xgboost": ROOT / "models/xgboost/xgboost_fusion.joblib",
    }
    model_manifest_path = build_models_manifest(local_model_paths)

    local_artifacts = [
        ROOT / "data/raw/russellmitchell",
        ROOT / "data/processed/russellmitchell/russellmitchell_parsed.csv",
        ROOT / "data/vectors/rag_attack_cases.npz",
        ROOT / "models/bilstm/best_model.pth",
        ROOT / "models/isolation_forest/iforest_model.joblib",
        ROOT / "models/xgboost/xgboost_fusion.joblib",
        model_manifest_path,
        TRACKED_MODELS_DIR / "README.md",
        eval_csv,
        eval_json,
    ]

    summary = json.loads((TRACKED_DIR / "view_eval_latest.json").read_text(encoding="utf-8"))
    manifest = {
        "dataset": DATASET,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "commands": [" ".join(cmd) for cmd in commands],
        "best_by_dataset": summary.get("best_by_dataset", {}).get(DATASET, {}),
        "local_artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "type": "dir" if path.is_dir() else "file",
            }
            for path in local_artifacts
        ],
    }
    manifest_path = TRACKED_DIR / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = build_report(TRACKED_DIR / "view_eval_latest.csv", TRACKED_DIR / "view_eval_latest.json", manifest_path)
    print("\nSaved visible artifacts:")
    print("-", TRACKED_DIR / "view_eval_latest.csv")
    print("-", TRACKED_DIR / "view_eval_latest.json")
    print("-", manifest_path)
    print("-", report_path)


if __name__ == "__main__":
    main()
