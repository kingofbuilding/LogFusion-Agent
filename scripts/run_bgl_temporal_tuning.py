from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.models.temporal_public import score_temporal_public, train_temporal_public_model
from benchmarks.public_logs.preprocess_bgl import run_bgl_preprocess
from benchmarks.public_logs.split_utils import keep_only_normal_train, split_bgl_ordered, summarize_split
from src.utils import Config, Logger, set_random_seed

DEFAULT_SCORE_MODE = "deeplog_true_prob_topk_mean"
PHASE_A_AGGREGATE_K = [3, 5, 8]
PHASE_A_TOP_K = [3, 5, 10]
PHASE_B_WINDOW_SIZE = [20, 40, 60]
PHASE_C_EPOCHS = [6, 10]
BASELINE_F1 = 0.2311


def _build_base_frames(config: Config, logger):
    seq_df = run_bgl_preprocess(config)
    split = split_bgl_ordered(
        seq_df,
        float(config.get("benchmarks.public_logs.train_ratio", 0.6)),
        float(config.get("benchmarks.public_logs.val_ratio", 0.2)),
    )
    train_df = keep_only_normal_train(split.train)
    val_df = split.val.reset_index(drop=True)
    test_df = split.test.reset_index(drop=True)

    max_train_samples = int(config.get("benchmarks.public_logs.max_train_samples", 0))
    max_val_samples = int(config.get("benchmarks.public_logs.max_val_samples", 0))
    max_test_samples = int(config.get("benchmarks.public_logs.max_test_samples", 0))
    if max_train_samples > 0:
        train_df = train_df.iloc[:max_train_samples].copy().reset_index(drop=True)
    if max_val_samples > 0:
        val_df = val_df.iloc[:max_val_samples].copy().reset_index(drop=True)
    if max_test_samples > 0:
        test_df = test_df.iloc[:max_test_samples].copy().reset_index(drop=True)

    logger.info(
        "[bgl_temporal_tuning] split summary train=%s val=%s test=%s",
        summarize_split(train_df),
        summarize_split(val_df),
        summarize_split(test_df),
    )
    return train_df, val_df, test_df


def _run_single_combo(
    base_config_path: str,
    train_df,
    val_df,
    test_df,
    *,
    aggregate_k: int,
    top_k: int,
    window_size: int,
    epochs: int,
    score_mode: str = DEFAULT_SCORE_MODE,
) -> dict:
    config = Config(base_config_path)
    config.update_config(
        {
            "benchmarks.public_logs.temporal_topk_aggregate_k": int(aggregate_k),
            "benchmarks.public_logs.temporal_top_k": int(top_k),
            "benchmarks.public_logs.temporal_window_size": int(window_size),
            "models.public_temporal.epochs": int(epochs),
        },
        persist=False,
    )
    logger = Logger.get_logger(
        f"bgl_temporal_tuning_k{aggregate_k}_top{top_k}_w{window_size}_e{epochs}",
        config,
    )
    logger.info(
        "[bgl_temporal_tuning] start score_mode=%s aggregate_k=%s top_k=%s window_size=%s epochs=%s",
        score_mode,
        aggregate_k,
        top_k,
        window_size,
        epochs,
    )
    model, actual_window_size, device, train_normal = train_temporal_public_model(train_df, val_df, test_df, config)
    metrics, result = score_temporal_public(
        model,
        actual_window_size,
        device,
        train_normal,
        val_df,
        test_df,
        config,
        score_mode=score_mode,
    )
    return {
        "score_mode": score_mode,
        "aggregate_k": int(aggregate_k),
        "temporal_top_k": int(top_k),
        "window_size": int(actual_window_size),
        "epochs": int(epochs),
        "Precision": float(metrics.get("precision", 0.0)),
        "Recall": float(metrics.get("recall", 0.0)),
        "F1": float(metrics.get("f1", 0.0)),
        "AUC": float(metrics.get("auc", 0.0)),
        "PR-AUC": float(metrics.get("pr_auc", 0.0)),
        "threshold": float(metrics.get("threshold", result.threshold)),
        "status": result.status,
        "notes": result.notes,
        "backend": result.backend,
    }


def _sort_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    ordered = df.sort_values(["F1", "PR-AUC", "Recall"], ascending=[False, False, False]).reset_index(drop=True)
    ordered["rank"] = ordered.index + 1
    ordered["f1_gain_vs_old_best"] = ordered["F1"] - BASELINE_F1
    return ordered


def _phase_best(df: pd.DataFrame) -> dict:
    if df.empty:
        raise RuntimeError("bgl temporal tuning produced no rows")
    row = df.iloc[0]
    return {
        "aggregate_k": int(row["aggregate_k"]),
        "temporal_top_k": int(row["temporal_top_k"]),
        "window_size": int(row["window_size"]),
        "epochs": int(row["epochs"]),
    }


def _write_outputs(output_dir: Path, ts: str, phase_a_df: pd.DataFrame, phase_b_df: pd.DataFrame, phase_c_df: pd.DataFrame, final_df: pd.DataFrame):
    summary_csv = output_dir / f"bgl_temporal_tuning_summary_{ts}.csv"
    summary_json = output_dir / f"bgl_temporal_tuning_summary_{ts}.json"
    report_md = PROJECT_ROOT / "reports" / f"bgl_temporal_tuning_summary_{ts}.md"
    phase_a_csv = output_dir / f"bgl_temporal_tuning_phase_a_{ts}.csv"
    phase_b_csv = output_dir / f"bgl_temporal_tuning_phase_b_{ts}.csv"
    phase_c_csv = output_dir / f"bgl_temporal_tuning_phase_c_{ts}.csv"

    phase_a_df.to_csv(phase_a_csv, index=False, encoding="utf-8-sig")
    phase_b_df.to_csv(phase_b_csv, index=False, encoding="utf-8-sig")
    phase_c_df.to_csv(phase_c_csv, index=False, encoding="utf-8-sig")
    final_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    best = final_df.iloc[0].to_dict()
    payload = {
        "generated_at": ts,
        "dataset": "BGL",
        "score_mode": DEFAULT_SCORE_MODE,
        "baseline_f1": BASELINE_F1,
        "sort_rule": ["F1 desc", "PR-AUC desc", "Recall desc"],
        "phase_a_grid": {
            "aggregate_k": PHASE_A_AGGREGATE_K,
            "temporal_top_k": PHASE_A_TOP_K,
            "window_size": [20],
            "epochs": [6],
        },
        "phase_b_grid": {
            "window_size": PHASE_B_WINDOW_SIZE,
            "epochs": [6],
        },
        "phase_c_grid": {
            "epochs": PHASE_C_EPOCHS,
        },
        "best_config": best,
        "top5": final_df.head(5).to_dict(orient="records"),
        "phase_outputs": {
            "phase_a_csv": str(phase_a_csv.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "phase_b_csv": str(phase_b_csv.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "phase_c_csv": str(phase_c_csv.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "summary_csv": str(summary_csv.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        },
    }
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    delta = float(best["F1"]) - BASELINE_F1
    lines = [
        "# BGL temporal tuning summary",
        "",
        f"- dataset: `BGL`",
        f"- score_mode: `{DEFAULT_SCORE_MODE}`",
        f"- sort rule: `F1 desc -> PR-AUC desc -> Recall desc`",
        f"- old best F1: `{BASELINE_F1:.4f}`",
        "",
        "## Best config",
        f"- aggregate_k: `{int(best['aggregate_k'])}`",
        f"- temporal_top_k: `{int(best['temporal_top_k'])}`",
        f"- window_size: `{int(best['window_size'])}`",
        f"- epochs: `{int(best['epochs'])}`",
        f"- F1: `{float(best['F1']):.4f}`",
        f"- Precision: `{float(best['Precision']):.4f}`",
        f"- Recall: `{float(best['Recall']):.4f}`",
        f"- AUC: `{float(best['AUC']):.4f}`",
        f"- PR-AUC: `{float(best['PR-AUC']):.4f}`",
        f"- threshold: `{float(best['threshold']):.3f}`",
        f"- delta vs old best: `{delta:+.4f}`",
        "",
        "## Full rerun recommendation",
    ]
    if delta > 0.01:
        lines.append("- 建议触发全量 temporal 重跑：小样本 sweep 已给出明显提升。")
    else:
        lines.append("- 暂不建议立即全量重跑：当前最优结果相对旧 best 仅为小幅波动。")
    lines.extend([
        "",
        "## Top 5",
    ])
    for _, row in final_df.head(5).iterrows():
        lines.append(
            f"- rank={int(row['rank'])}: aggregate_k={int(row['aggregate_k'])}, top_k={int(row['temporal_top_k'])}, "
            f"window={int(row['window_size'])}, epochs={int(row['epochs'])}, F1={float(row['F1']):.4f}, "
            f"PR-AUC={float(row['PR-AUC']):.4f}, Recall={float(row['Recall']):.4f}"
        )
    lines.extend([
        "",
        "## Artifacts",
        f"- summary csv: `{summary_csv.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- summary json: `{summary_json.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- phase A csv: `{phase_a_csv.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- phase B csv: `{phase_b_csv.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- phase C csv: `{phase_c_csv.relative_to(PROJECT_ROOT).as_posix()}`",
    ])
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_csv, summary_json, report_md


def main(config_path: str = "benchmarks/configs/bgl.yaml"):
    config = Config(config_path)
    logger = Logger.get_logger("bgl_temporal_tuning", config)
    set_random_seed(int(config.get("experiment.random_seed", 42)))
    train_df, val_df, test_df = _build_base_frames(config, logger)

    phase_a_rows = []
    for aggregate_k in PHASE_A_AGGREGATE_K:
        for top_k in PHASE_A_TOP_K:
            phase_a_rows.append(
                _run_single_combo(
                    config_path,
                    train_df,
                    val_df,
                    test_df,
                    aggregate_k=aggregate_k,
                    top_k=top_k,
                    window_size=20,
                    epochs=6,
                )
            )
    phase_a_df = _sort_results(pd.DataFrame(phase_a_rows))
    best_phase_a = _phase_best(phase_a_df)

    phase_b_rows = []
    for window_size in PHASE_B_WINDOW_SIZE:
        phase_b_rows.append(
            _run_single_combo(
                config_path,
                train_df,
                val_df,
                test_df,
                aggregate_k=best_phase_a["aggregate_k"],
                top_k=best_phase_a["temporal_top_k"],
                window_size=window_size,
                epochs=6,
            )
        )
    phase_b_df = _sort_results(pd.DataFrame(phase_b_rows))
    best_phase_b = _phase_best(phase_b_df)

    phase_c_rows = []
    for epochs in PHASE_C_EPOCHS:
        phase_c_rows.append(
            _run_single_combo(
                config_path,
                train_df,
                val_df,
                test_df,
                aggregate_k=best_phase_b["aggregate_k"],
                top_k=best_phase_b["temporal_top_k"],
                window_size=best_phase_b["window_size"],
                epochs=epochs,
            )
        )
    phase_c_df = _sort_results(pd.DataFrame(phase_c_rows))
    combined_df = _sort_results(pd.concat([phase_a_df, phase_b_df, phase_c_df], ignore_index=True))
    final_df = _sort_results(
        combined_df.drop_duplicates(
            subset=["score_mode", "aggregate_k", "temporal_top_k", "window_size", "epochs"],
            keep="first",
        )
    )

    output_dir = Path(config.get("paths.outputs.reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_csv, summary_json, report_md = _write_outputs(output_dir, ts, phase_a_df, phase_b_df, phase_c_df, final_df)
    logger.info("[bgl_temporal_tuning] summary csv=%s json=%s report=%s", summary_csv, summary_json, report_md)
    print(
        json.dumps(
            {
                "summary_csv": str(summary_csv),
                "summary_json": str(summary_json),
                "report_md": str(report_md),
                "best": final_df.iloc[0].to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary_csv, summary_json, report_md


if __name__ == "__main__":
    main()
