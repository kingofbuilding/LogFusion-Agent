from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from run_protocol_compare_random_window import (  # noqa: E402
    _evaluate_score_family,
    _predict_saved_sequence_model,
    _train_bilstm,
    _train_gru,
    _train_iforest,
)
from run_truncated_ordered_split import (  # noqa: E402
    DATASETS,
    SPLIT_RATIO_PRESETS,
    SPLIT_VARIANT_NAMES,
    _clone_config,
    _parse_datasets,
    _resolve_split_ratio,
)
from src.data_processing.truncated_protocol import (  # noqa: E402
    TRUNCATED_PROTOCOL_ID,
    TRUNCATED_SPLIT_MODE,
    build_truncated_ordered_splits,
    validate_protocol_dataframe,
)
from src.fusion.evaluate_views import _compute_stat_subscores  # noqa: E402
from src.fusion.three_view_service import ThreeViewScoringService  # noqa: E402
from src.fusion.xgboost_fusion import XGBoostFusion  # noqa: E402
from src.models.gru_classifier import GRUClassifier  # noqa: E402
from src.utils import Config, Logger, set_random_seed  # noqa: E402


def _fit_predict_classifier(model, x_train, y_train, x_val, x_test):
    model.fit(np.asarray(x_train, dtype=float), np.asarray(y_train, dtype=int))
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_val)[:, 1], model.predict_proba(x_test)[:, 1]
    if hasattr(model, "decision_function"):
        val_score = np.asarray(model.decision_function(x_val), dtype=float)
        test_score = np.asarray(model.decision_function(x_test), dtype=float)
        lo = float(np.min(val_score))
        hi = float(np.max(val_score))
        if hi - lo <= 1e-12:
            return np.zeros_like(val_score, dtype=float), np.zeros_like(test_score, dtype=float)
        return (
            np.clip((val_score - lo) / (hi - lo + 1e-8), 0.0, 1.0),
            np.clip((test_score - lo) / (hi - lo + 1e-8), 0.0, 1.0),
        )
    return model.predict(x_val).astype(float), model.predict(x_test).astype(float)


def _class_weight(y_train):
    y = np.asarray(y_train).astype(int)
    pos = int(np.sum(y == 1))
    neg = int(np.sum(y == 0))
    if pos <= 0 or neg <= 0:
        return None
    return "balanced"


def _classifier_specs(y_train, feature_set_name):
    class_weight = _class_weight(y_train)
    base_linear_svc = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LinearSVC(class_weight=class_weight, C=1.0, max_iter=5000, random_state=42),
    )
    suffix = feature_set_name
    return [
        (
            f"lr_fusion_{suffix}",
            make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                LogisticRegression(class_weight=class_weight, max_iter=2000, solver="lbfgs", random_state=42),
            ),
        ),
        (
            f"linear_svm_fusion_{suffix}",
            CalibratedClassifierCV(base_linear_svc, cv=3, method="sigmoid"),
        ),
        (
            f"random_forest_fusion_{suffix}",
            make_pipeline(
                SimpleImputer(strategy="median"),
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_leaf=5,
                    class_weight=class_weight,
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ),
        (
            f"extra_trees_fusion_{suffix}",
            make_pipeline(
                SimpleImputer(strategy="median"),
                ExtraTreesClassifier(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_leaf=5,
                    class_weight=class_weight,
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ),
        (
            f"gradient_boosting_fusion_{suffix}",
            make_pipeline(
                SimpleImputer(strategy="median"),
                GradientBoostingClassifier(
                    n_estimators=150,
                    learning_rate=0.05,
                    max_depth=3,
                    random_state=42,
                ),
            ),
        ),
    ]


def _predict_xgboost(cfg, x_train, y_train, x_val, y_val, x_test):
    fusion = XGBoostFusion(cfg)
    fusion.train(x_train, y_train, x_val, y_val)
    return fusion.predict_proba(x_val), fusion.predict_proba(x_test)


def _build_fusion_features(cfg, bundle, scores):
    stat = np.asarray(scores["stat_scores"], dtype=float)
    temp = np.asarray(scores["temporal_scores"], dtype=float)
    sem = np.asarray(scores["semantic_scores"], dtype=float)
    stat_sub = _compute_stat_subscores(cfg, bundle["X"], bundle["T"], bundle["S"], bundle["R"])
    return np.column_stack([
        stat,
        temp,
        sem,
        stat_sub["stat_dist_score"],
        stat_sub["stat_auth_score"],
        stat_sub["stat_web_score"],
        stat_sub["stat_dns_score"],
    ])


def _evaluate_dataset(base_config, dataset, model_root, logger, full_data, ratio_override, split_variant):
    cfg = _clone_config(base_config, dataset, model_root)
    cfg.config.setdefault("data", {})["split_mode"] = TRUNCATED_SPLIT_MODE
    bundles = build_truncated_ordered_splits(
        cfg,
        dataset,
        full_data=full_data,
        ratio_override=ratio_override,
        split_variant=split_variant,
    )

    for key in ("bilstm", "gru", "isolation_forest", "xgboost"):
        Path(cfg.get(f"paths.models.{key}")).mkdir(parents=True, exist_ok=True)

    _train_iforest(cfg, bundles["train"])
    _train_bilstm(cfg, bundles["train"], bundles["val"], bundles["test"])
    _train_gru(cfg, bundles["train"], bundles["val"], bundles["test"])

    scorer = ThreeViewScoringService(cfg)
    train_scores = scorer.score(
        bundles["train"]["X"],
        bundles["train"]["S"],
        seq_timestamps=bundles["train"]["T"],
        raw_seq_texts=bundles["train"]["R"],
    )
    val_scores = scorer.score(
        bundles["val"]["X"],
        bundles["val"]["S"],
        seq_timestamps=bundles["val"]["T"],
        raw_seq_texts=bundles["val"]["R"],
    )
    test_scores = scorer.score(
        bundles["test"]["X"],
        bundles["test"]["S"],
        seq_timestamps=bundles["test"]["T"],
        raw_seq_texts=bundles["test"]["R"],
    )

    x_train = _build_fusion_features(cfg, bundles["train"], train_scores)
    x_val = _build_fusion_features(cfg, bundles["val"], val_scores)
    x_test = _build_fusion_features(cfg, bundles["test"], test_scores)
    y_train = np.asarray(bundles["train"]["y"], dtype=int)
    y_val = np.asarray(bundles["val"]["y"], dtype=int)
    split_metadata = bundles["metadata"]

    rows = []
    stat_train, temp_train, sem_train = x_train[:, 0], x_train[:, 1], x_train[:, 2]
    stat_val, temp_val, sem_val = x_val[:, 0], x_val[:, 1], x_val[:, 2]
    stat_test, temp_test, sem_test = x_test[:, 0], x_test[:, 1], x_test[:, 2]
    gru_train = _predict_saved_sequence_model(cfg, bundles["train"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")
    gru_val = _predict_saved_sequence_model(cfg, bundles["val"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")
    gru_test = _predict_saved_sequence_model(cfg, bundles["test"]["X"], GRUClassifier, "paths.models.gru", "models.gru.infer_batch_size")

    base_scores = [
        ("statistical_view", "single_view", stat_train, stat_val, stat_test),
        ("temporal_view", "single_view", temp_train, temp_val, temp_test),
        ("gru_temporal_view", "single_view", gru_train, gru_val, gru_test),
        ("semantic_view", "single_view", sem_train, sem_val, sem_test),
        ("mean_fusion_all", "fusion_baseline", (stat_train + temp_train + sem_train) / 3.0, (stat_val + temp_val + sem_val) / 3.0, (stat_test + temp_test + sem_test) / 3.0),
    ]
    for name, group, train_score, val_score, test_score in base_scores:
        rows.append(_evaluate_score_family(name, dataset, group, bundles, train_score, val_score, test_score, split_metadata))

    feature_sets = [
        ("base_3view", [0, 1, 2]),
        ("stat_parts", [1, 2, 3, 4, 5, 6]),
        ("stat_parts_plus_legacy", [0, 1, 2, 3, 4, 5, 6]),
    ]
    for feature_set_name, columns in feature_sets:
        cur_x_train = x_train[:, columns]
        cur_x_val = x_val[:, columns]
        cur_x_test = x_test[:, columns]
        for name, model in _classifier_specs(y_train, feature_set_name):
            logger.info("train supervised baseline dataset=%s model=%s shape=%s", dataset, name, cur_x_train.shape)
            val_prob, test_prob = _fit_predict_classifier(model, cur_x_train, y_train, cur_x_val, cur_x_test)
            rows.append(_evaluate_score_family(name, dataset, "supervised_fusion_baseline", bundles, np.zeros_like(y_train, dtype=float), val_prob, test_prob, split_metadata))

        val_prob, test_prob = _predict_xgboost(cfg, cur_x_train, y_train, cur_x_val, y_val, cur_x_test)
        rows.append(_evaluate_score_family(f"xgboost_fusion_{feature_set_name}", dataset, "supervised_fusion_baseline", bundles, np.zeros_like(y_train, dtype=float), val_prob, test_prob, split_metadata))

    for row in rows:
        for key, value in split_metadata.items():
            if key not in row and isinstance(value, (str, int, float, bool)):
                row[key] = value
    return rows


def _write_markdown(df, out_path):
    core = df[["dataset", "model_name", "precision", "recall", "f1", "auc", "pr_auc", "threshold"]].copy()
    core = core.sort_values(["dataset", "f1"], ascending=[True, False])
    lines = [
        "# 监督式融合基线对比（uniform 65/15/20）",
        "",
        "## 实验说明",
        "",
        "- 协议：`truncated_ordered_pre_split`",
        "- 数据规模：full-data",
        "- 切分比例：`65% / 15% / 20%`",
        "- 输入特征：统计视图风险分、时序视图风险分、语义视图风险分、分布/认证/Web/DNS 统计子分数。",
        "- 阈值：统一在验证集搜索最优 F1，测试集仅用于最终评估。",
        "",
        "## 全部模型结果",
        "",
        core.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 各数据集最佳监督式融合模型",
        "",
    ]
    fusion = df[df["experiment_group"].eq("supervised_fusion_baseline")].copy()
    best = fusion.sort_values(["dataset", "f1", "recall", "auc"], ascending=[True, False, False, False]).groupby("dataset", as_index=False).head(1)
    lines.append(best[["dataset", "model_name", "precision", "recall", "f1", "auc", "pr_auc"]].to_markdown(index=False, floatfmt=".4f"))
    lines.extend([
        "",
        "## 结论",
        "",
        "监督式融合基线用于评价本文在有标注安全日志场景下的模型选择是否合理。若 XGBoost 或树模型融合在多个数据集上优于 LR、SVM 和简单平均，说明多视图风险分数之间存在非线性关系，学习型融合层具有必要性；若线性模型在个别数据集接近最优，则说明该数据集上的视图分数边界较清晰，可作为模型复杂度分析的补充依据。",
        "",
    ])
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run supervised fusion baselines on truncated ordered splits")
    parser.add_argument("--full-data", action="store_true")
    parser.add_argument("--datasets", default="")
    parser.add_argument("--split-ratio", default="65/15/20", choices=sorted(SPLIT_RATIO_PRESETS))
    args = parser.parse_args()

    base_config = Config()
    logger = Logger.get_logger("supervised_fusion_baselines", base_config)
    set_random_seed(int(base_config.get("experiment.random_seed", 42)))

    selected_datasets = _parse_datasets(args.datasets)
    ratio_override, split_variant = _resolve_split_ratio(args.split_ratio, False)
    suffix = "_full_data" if args.full_data else ""
    if split_variant != "dataset_specific":
        suffix += f"_{SPLIT_VARIANT_NAMES[args.split_ratio]}" if args.split_ratio in SPLIT_VARIANT_NAMES else f"_{split_variant}"

    out_dir = PROJECT_ROOT / "outputs" / "reports" / f"supervised_fusion_baselines_{split_variant}"
    model_root = PROJECT_ROOT / "outputs" / "strict_retrain" / f"supervised_fusion_baselines_{split_variant}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_root.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for dataset in selected_datasets:
        logger.info("start supervised fusion baselines dataset=%s", dataset)
        all_rows.extend(_evaluate_dataset(base_config, dataset, model_root, logger, args.full_data, ratio_override, split_variant))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"supervised_fusion_baselines_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.csv"
    json_path = out_dir / f"supervised_fusion_baselines_{TRUNCATED_SPLIT_MODE}{suffix}_{ts}.json"
    md_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"supervised_fusion_baselines_uniform_65_15_20_{ts}.md"
    thesis_csv_path = PROJECT_ROOT / "reports" / "final_thesis_package" / f"supervised_fusion_baselines_uniform_65_15_20_{ts}.csv"

    df = pd.DataFrame(all_rows)
    validate_protocol_dataframe(df)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_csv(thesis_csv_path, index=False, encoding="utf-8-sig")
    _write_markdown(df, md_path)
    summary = {
        "protocol_id": TRUNCATED_PROTOCOL_ID,
        "split_mode": TRUNCATED_SPLIT_MODE,
        "split_variant": split_variant,
        "datasets": selected_datasets,
        "csv": str(csv_path.relative_to(PROJECT_ROOT)),
        "thesis_csv": str(thesis_csv_path.relative_to(PROJECT_ROOT)),
        "markdown": str(md_path.relative_to(PROJECT_ROOT)),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
