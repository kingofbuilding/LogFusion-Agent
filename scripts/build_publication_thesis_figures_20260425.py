from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import PercentFormatter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
THESIS_DIR = PROJECT_ROOT / "reports" / "final_thesis_package"
FIG_DIR = THESIS_DIR / "figures_publication_20260425"

MAIN_RESULT_CSV = PROJECT_ROOT / "outputs" / "reports" / "full_data_truncated_ordered_uniform_65_15_20" / "view_eval_truncated_ordered_pre_split_full_data_uniform_65_15_20_20260425_135427.csv"
CORE_TABLE_CSV = THESIS_DIR / "table_65_15_20_core_views_20260425.csv"
ALL_TABLE_CSV = THESIS_DIR / "table_65_15_20_all_views_20260425.csv"
PROTOCOL_SUMMARY_CSV = PROJECT_ROOT / "outputs" / "reports" / "full_data_truncated_ordered_uniform_65_15_20" / "protocol_compare_ordered_random_truncated_summary_full_data_uniform_65_15_20_20260425_135427.csv"
PROTOCOL_FULL_CSV = PROJECT_ROOT / "outputs" / "reports" / "full_data_truncated_ordered_uniform_65_15_20" / "protocol_compare_ordered_random_truncated_full_data_uniform_65_15_20_20260425_135427.csv"

DATASET_ORDER = ["harrison", "santos", "fox"]
COLORS = {
    "blue": "#2563EB",
    "green": "#16A34A",
    "orange": "#F97316",
    "amber": "#F59E0B",
    "purple": "#7C3AED",
    "pink": "#DB2777",
    "red": "#DC2626",
    "slate": "#64748B",
    "light_slate": "#CBD5E1",
    "ordered": "#94A3B8",
    "random": "#F59E0B",
    "truncated": "#2563EB",
    "train": "#2563EB",
    "val": "#10B981",
    "test": "#EF4444",
}
MODEL_LABELS = {
    "statistical_view": "Statistical view",
    "temporal_view": "BiLSTM temporal view",
    "gru_temporal_view": "GRU temporal baseline",
    "semantic_view": "Semantic view",
    "mean_fusion_all": "Mean fusion",
    "xgboost_fusion_retrained": "XGBoost fusion",
    "xgboost_fusion_stat_parts_xgb": "Stat-parts fusion",
    "xgboost_fusion_stat_parts_plus_legacy_xgb": "Stat-parts + legacy",
}


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    sns.set_theme(style="whitegrid", rc={"axes.edgecolor": "#CBD5E1", "grid.color": "#E2E8F0"})


def clean_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8, alpha=0.8)
    ax.grid(axis="x", visible=False)


def save_all_formats(fig, base_name: str) -> dict[str, str]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for suffix in ("png", "svg", "pdf"):
        path = FIG_DIR / f"{base_name}.{suffix}"
        try:
            fig.savefig(path, bbox_inches="tight", facecolor="white")
        except PermissionError:
            if path.exists():
                outputs[suffix] = rel(path)
                continue
            raise
        outputs[suffix] = rel(path)
    plt.close(fig)
    return outputs


def add_labels(ax, fmt: str = "{:.3f}", dy: float = 0.01) -> None:
    for patch in ax.patches:
        height = patch.get_height()
        width = patch.get_width()
        if np.isnan(height) or height <= 0 or width <= 0:
            continue
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            height + dy,
            fmt.format(height),
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="#334155",
        )


def load_sources() -> dict[str, pd.DataFrame]:
    return {
        "main": pd.read_csv(MAIN_RESULT_CSV),
        "core": pd.read_csv(CORE_TABLE_CSV),
        "all": pd.read_csv(ALL_TABLE_CSV),
        "protocol_summary": pd.read_csv(PROTOCOL_SUMMARY_CSV),
        "protocol_full": pd.read_csv(PROTOCOL_FULL_CSV),
    }


def best_by_dataset(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset, sub in df.groupby("dataset"):
        rows.append(sub.sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).iloc[0])
    return pd.DataFrame(rows).set_index("dataset").loc[DATASET_ORDER].reset_index()


def build_split_scheme_sensitivity() -> dict[str, str]:
    df = pd.DataFrame(
        [
            {"scheme": "dataset-specific", "macro_f1": 0.8417, "min_f1": 0.7483},
            {"scheme": "60/20/20", "macro_f1": 0.8338, "min_f1": 0.7483},
            {"scheme": "60/15/25", "macro_f1": 0.8584, "min_f1": 0.7799},
            {"scheme": "65/20/15", "macro_f1": 0.8514, "min_f1": 0.6646},
            {"scheme": "65/15/20", "macro_f1": 0.9055, "min_f1": 0.8309},
        ]
    )
    df["y"] = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(7.4, 4.1))
    for _, row in df.iterrows():
        color = COLORS["red"] if row["scheme"] == "65/15/20" else COLORS["light_slate"]
        ax.hlines(row["y"], row["min_f1"], row["macro_f1"], color=color, linewidth=2.4, alpha=0.9)
    ax.scatter(df["min_f1"], df["y"], s=70, color=COLORS["orange"], label="Minimum F1", zorder=3)
    ax.scatter(df["macro_f1"], df["y"], s=80, color=COLORS["blue"], label="Macro-F1", zorder=3)
    best = df[df["scheme"] == "65/15/20"].iloc[0]
    ax.scatter([best["macro_f1"]], [best["y"]], s=150, facecolors="none", edgecolors=COLORS["red"], linewidths=2.2, zorder=4)
    for _, row in df.iterrows():
        ax.text(row["macro_f1"] + 0.008, row["y"], f'{row["macro_f1"]:.3f}', va="center", fontsize=9, color="#334155")
    ax.set_yticks(df["y"])
    ax.set_yticklabels(df["scheme"])
    ax.set_xlim(0.62, 0.95)
    ax.set_xlabel("Score")
    ax.set_title("Split-ratio sensitivity: average and worst-case F1", pad=18)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    clean_axes(ax)
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.8, alpha=0.8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save_all_formats(fig, "fig5_1_split_scheme_sensitivity_20260425")


def build_split_anomaly_distribution(main: pd.DataFrame) -> dict[str, str]:
    meta = main[["dataset", "train_anomaly_ratio", "val_anomaly_ratio", "test_anomaly_ratio"]].drop_duplicates()
    rows = []
    for _, row in meta.iterrows():
        for split in ("train", "val", "test"):
            rows.append({"dataset": row["dataset"], "split": split, "ratio": row[f"{split}_anomaly_ratio"]})
    plot_df = pd.DataFrame(rows)
    plot_df["dataset"] = pd.Categorical(plot_df["dataset"], DATASET_ORDER, ordered=True)
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    sns.barplot(
        data=plot_df,
        x="dataset",
        y="ratio",
        hue="split",
        palette={"train": COLORS["train"], "val": COLORS["val"], "test": COLORS["test"]},
        ax=ax,
    )
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, max(plot_df["ratio"]) * 1.28)
    ax.set_xlabel("Dataset")
    ax.set_ylabel("Anomaly ratio")
    ax.set_title("Train / validation / test anomaly ratios under 65/15/20", pad=20)
    ax.legend(frameon=False, ncol=3, title="", loc="upper center", bbox_to_anchor=(0.5, -0.14))
    add_labels(ax, fmt="{:.1%}", dy=0.006)
    clean_axes(ax)
    fig.tight_layout()
    return save_all_formats(fig, "fig5_2_split_anomaly_distribution_20260425")


def build_protocol_best_f1_compare(summary: pd.DataFrame) -> dict[str, str]:
    best = summary.sort_values(["dataset", "truncated_f1"], ascending=[True, False]).groupby("dataset").head(1)
    rows = []
    for _, row in best.iterrows():
        for protocol, col in (("ordered", "ordered_f1"), ("random", "random_f1"), ("truncated", "truncated_f1")):
            rows.append({"dataset": row["dataset"], "protocol": protocol, "f1": row[col]})
    plot_df = pd.DataFrame(rows)
    plot_df["dataset"] = pd.Categorical(plot_df["dataset"], DATASET_ORDER, ordered=True)
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    sns.barplot(data=plot_df, x="dataset", y="f1", hue="protocol", palette={k: COLORS[k] for k in ("ordered", "random", "truncated")}, ax=ax)
    ax.set_ylim(0, 1.10)
    ax.set_xlabel("Dataset")
    ax.set_ylabel("Best F1")
    ax.set_title("Protocol comparison by best F1", pad=20)
    ax.legend(frameon=False, ncol=3, title="", loc="upper center", bbox_to_anchor=(0.5, -0.14))
    add_labels(ax, fmt="{:.3f}", dy=0.014)
    clean_axes(ax)
    fig.tight_layout()
    return save_all_formats(fig, "fig5_3_protocol_best_f1_compare_20260425")


def build_core_model_heatmap(core: pd.DataFrame) -> dict[str, str]:
    models = [
        "statistical_view",
        "temporal_view",
        "semantic_view",
        "mean_fusion_all",
        "xgboost_fusion_retrained",
        "xgboost_fusion_stat_parts_xgb",
        "xgboost_fusion_stat_parts_plus_legacy_xgb",
    ]
    keep = core[core["model_name"].isin(models)].copy()
    pivot = keep.pivot(index="model_name", columns="dataset", values="f1").loc[models, DATASET_ORDER]
    pivot["macro"] = pivot.mean(axis=1)
    pivot.index = [MODEL_LABELS.get(idx, idx) for idx in pivot.index]
    fig, ax = plt.subplots(figsize=(8.4, 4.7))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".3f",
        cmap="YlGnBu",
        vmin=0.1,
        vmax=1.0,
        linewidths=0.8,
        linecolor="white",
        cbar_kws={"label": "F1"},
        ax=ax,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title("Core model F1 heatmap under 65/15/20")
    fig.tight_layout()
    return save_all_formats(fig, "fig5_4_core_model_f1_heatmap_20260425")


def build_fusion_variant_compare(core: pd.DataFrame) -> dict[str, str]:
    models = [
        "xgboost_fusion_retrained",
        "xgboost_fusion_stat_parts_xgb",
        "xgboost_fusion_stat_parts_plus_legacy_xgb",
    ]
    keep = core[core["model_name"].isin(models)].copy()
    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    palette = [COLORS["slate"], COLORS["blue"], COLORS["purple"]]
    label_offsets = {
        "xgboost_fusion_retrained": -0.018,
        "xgboost_fusion_stat_parts_xgb": 0.014,
        "xgboost_fusion_stat_parts_plus_legacy_xgb": 0.028,
    }
    for color, model in zip(palette, models):
        sub = keep[keep["model_name"] == model].set_index("dataset").loc[DATASET_ORDER]
        y = sub["f1"].to_numpy()
        ax.plot(DATASET_ORDER, y, marker="o", linewidth=2.2, markersize=6, color=color, label=MODEL_LABELS[model])
        for x, value in zip(DATASET_ORDER, y):
            ax.text(x, value + label_offsets[model], f"{value:.3f}", ha="center", va="bottom", fontsize=8.2, color=color)
    ax.set_ylim(0.54, 1.04)
    ax.set_xlabel("Dataset")
    ax.set_ylabel("F1")
    ax.set_title("Fusion variant comparison", pad=18)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    clean_axes(ax)
    fig.tight_layout()
    return save_all_formats(fig, "fig5_5_fusion_variant_f1_compare_20260425")


def build_best_model_metric_balance(core: pd.DataFrame) -> dict[str, str]:
    best = best_by_dataset(core).set_index("dataset").loc[DATASET_ORDER]
    metrics = [
        ("Precision", "precision", COLORS["blue"]),
        ("Recall", "recall", COLORS["orange"]),
        ("F1", "f1", COLORS["green"]),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.9))
    x = np.arange(len(DATASET_ORDER))
    width = 0.23
    offsets = [-width, 0, width]
    for offset, (label, column, color) in zip(offsets, metrics):
        values = best[column].to_numpy(dtype=float)
        bars = ax.bar(x + offset, values, width=width * 0.92, color=color, label=label)
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.012,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8.0,
                color="#334155",
            )
    ax.set_xticks(x)
    ax.set_xticklabels(DATASET_ORDER)
    ax.set_ylim(0, 1.10)
    ax.set_xlabel("Dataset")
    ax.set_ylabel("Score")
    ax.set_title("Precision / recall / F1 balance of best models", pad=18)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3)
    clean_axes(ax)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8, alpha=0.8)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return save_all_formats(fig, "fig5_6_best_model_metric_balance_20260425")


def build_temporal_baseline_compare(all_df: pd.DataFrame) -> dict[str, str]:
    models = [
        "temporal_view",
        "gru_temporal_view",
        "xgboost_fusion_retrained",
        "xgboost_fusion_stat_parts_xgb",
        "xgboost_fusion_stat_parts_plus_legacy_xgb",
    ]
    keep = all_df[all_df["model_name"].isin(models)].copy()
    keep["model_label"] = keep["model_name"].map(MODEL_LABELS)
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.4), sharex=True)
    palette = {
        "BiLSTM temporal view": COLORS["slate"],
        "GRU temporal baseline": COLORS["amber"],
        "XGBoost fusion": COLORS["blue"],
        "Stat-parts fusion": COLORS["green"],
        "Stat-parts + legacy": COLORS["purple"],
    }
    model_labels = [MODEL_LABELS[m] for m in models]
    y_positions = np.arange(len(model_labels))
    for i, (ax, dataset) in enumerate(zip(axes, DATASET_ORDER)):
        sub = keep[keep["dataset"] == dataset].set_index("model_label").loc[model_labels].reset_index()
        values = sub["f1"].to_numpy()
        colors = [palette[label] for label in model_labels]
        ax.scatter(values, y_positions, s=82, color=colors, zorder=3)
        for y, value in zip(y_positions, values):
            ax.text(value + 0.012, y, f"{value:.3f}", va="center", fontsize=8.0, color="#334155")
        ax.set_title(dataset, pad=12)
        ax.set_xlim(0.15, 1.04)
        ax.set_ylim(-0.6, len(model_labels) - 0.4)
        ax.invert_yaxis()
        ax.set_xlabel("F1")
        ax.set_yticks(y_positions)
        if i == 0:
            ax.set_yticklabels(model_labels)
        else:
            ax.set_yticklabels([])
        ax.set_ylabel("")
        clean_axes(ax)
        ax.grid(axis="x", color="#E2E8F0", linewidth=0.8, alpha=0.8)
        ax.grid(axis="y", visible=False)
    fig.suptitle("Temporal baselines and fusion models", y=1.03, fontsize=13)
    fig.tight_layout(w_pad=2.2)
    return save_all_formats(fig, "fig5_7_temporal_baseline_fusion_compare_20260425")


def write_docs(outputs: dict[str, dict[str, str]]) -> None:
    placement = """# 第 5 章图表放置建议（20260425 主线）

当前主线：`full_data + truncated_ordered_pre_split_v1 + uniform_65_15_20`。

## 5.3 数据集与实验协议

1. 图 5-1：切分方案敏感性对比
   文件：`figures_publication_20260425/fig5_1_split_scheme_sensitivity_20260425.png`

2. 图 5-2：65/15/20 下 train/val/test 异常比例
   文件：`figures_publication_20260425/fig5_2_split_anomaly_distribution_20260425.png`

## 5.5 实验协议对比

3. 图 5-3：ordered、random、truncated 三协议最佳 F1 对比
   文件：`figures_publication_20260425/fig5_3_protocol_best_f1_compare_20260425.png`

## 5.6 多视图融合主结果

4. 图 5-4：核心模型 F1 热力图
   文件：`figures_publication_20260425/fig5_4_core_model_f1_heatmap_20260425.png`

## 5.7 融合与消融分析

5. 图 5-5：融合变体 F1 对比
   文件：`figures_publication_20260425/fig5_5_fusion_variant_f1_compare_20260425.png`

6. 图 5-6：最佳模型 Precision / Recall / F1 平衡
   文件：`figures_publication_20260425/fig5_6_best_model_metric_balance_20260425.png`

## 5.8 时序基线比较

7. 图 5-7：时序基线与融合模型对比
   文件：`figures_publication_20260425/fig5_7_temporal_baseline_fusion_compare_20260425.png`

说明：`gru_temporal_view` 只作为时序基线，不作为 AIT-LDS v2 核心视图。
"""
    captions = """# 第 5 章图题与说明（20260425 主线）

## 图 5-1 切分方案敏感性对比

该图比较了不同 train/val/test 切分比例下的 Macro-F1 与最低子集 F1。统一 `65/15/20` 同时取得最高平均性能与最高最低子集性能，说明该方案在统一实验口径下具有更好的整体稳定性。

## 图 5-2 统一 65/15/20 下的异常比例分布

该图展示 harrison、santos、fox 三个子集在训练集、验证集和测试集中的异常比例。结果表明，不同数据集的异常阶段分布存在差异，因此论文同时报告异常比例以增强协议可解释性。

## 图 5-3 不同协议下的最佳 F1 对比

该图比较 ordered、random 与 truncated ordered 三类协议的最佳 F1。本文选择截断时序协议作为主协议，是为了在保持时间顺序的同时保证测试阶段具有有效异常覆盖。

## 图 5-4 核心模型 F1 热力图

该图展示统计视图、时序视图、语义视图及多种融合模型在三个数据集上的 F1。相比单一视图，多视图融合模型在多数数据集上取得更高且更稳定的检测效果。

## 图 5-5 融合变体 F1 对比

该图比较基础 XGBoost 融合、统计子分融合以及统计子分加原始统计视图的增强融合方案。结果显示，统计子分融合能够提升多视图融合表达能力，但不同数据集上的最优融合形式略有差异。

## 图 5-6 最佳模型的 Precision / Recall / F1 平衡

该图展示每个数据集最佳模型的精确率、召回率和 F1。结果说明最终方案并非单纯依靠某一指标取胜，而是在误报控制与异常覆盖之间取得较好平衡。

## 图 5-7 时序基线与融合模型对比

该图比较 BiLSTM 时序视图、GRU 时序基线与多视图融合模型的 F1。结果表明，仅依赖时序模式难以充分刻画安全日志异常，多视图融合能显著增强检测效果。
"""
    (THESIS_DIR / "chapter5_figure_placement_plan_20260425.md").write_text(placement, encoding="utf-8")
    (THESIS_DIR / "chapter5_figure_captions_20260425.md").write_text(captions, encoding="utf-8")


def main() -> None:
    setup_style()
    sources = load_sources()
    outputs = {
        "split_scheme_sensitivity": build_split_scheme_sensitivity(),
        "split_anomaly_distribution": build_split_anomaly_distribution(sources["main"]),
        "protocol_best_f1_compare": build_protocol_best_f1_compare(sources["protocol_summary"]),
        "core_model_f1_heatmap": build_core_model_heatmap(sources["core"]),
        "fusion_variant_f1_compare": build_fusion_variant_compare(sources["core"]),
        "best_model_metric_balance": build_best_model_metric_balance(sources["core"]),
        "temporal_baseline_fusion_compare": build_temporal_baseline_compare(sources["all"]),
    }
    write_docs(outputs)
    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "protocol_id": "truncated_ordered_pre_split_v1",
        "split_mode": "truncated_ordered_pre_split",
        "sample_cap_mode": "full_data",
        "split_variant": "uniform_65_15_20",
        "style": "academic_clean",
        "sources": {
            "main_result_csv": rel(MAIN_RESULT_CSV),
            "core_table_csv": rel(CORE_TABLE_CSV),
            "all_table_csv": rel(ALL_TABLE_CSV),
            "protocol_summary_csv": rel(PROTOCOL_SUMMARY_CSV),
            "protocol_full_csv": rel(PROTOCOL_FULL_CSV),
        },
        "outputs": outputs,
        "docs": {
            "placement_plan": rel(THESIS_DIR / "chapter5_figure_placement_plan_20260425.md"),
            "captions": rel(THESIS_DIR / "chapter5_figure_captions_20260425.md"),
        },
    }
    manifest_path = THESIS_DIR / "publication_figures_manifest_20260425.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
