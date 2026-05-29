"""
多视图融合评估脚本：
1. 单视图效果评估
2. 简单融合效果评估
3. XGBoost 融合效果评估
4. 视图消融实验
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.data_processing.data_loader import DataLoader
from src.fusion.ensemble import EnsemblePredictor
from src.fusion.three_view_service import ThreeViewScoringService
from src.fusion.xgboost_fusion import XGBoostFusion
from src.utils import Config, Logger


from src.feature_extraction.statistical_features import StatisticalFeatureExtractor, trim_statistical_window


def _quantile_normalize(arr: np.ndarray, lo_q: float = 0.10, hi_q: float = 0.90) -> np.ndarray:
    arr = np.asarray(arr, dtype=float).reshape(-1)
    if arr.size == 0:
        return arr
    lo = float(np.quantile(arr, lo_q))
    hi = float(np.quantile(arr, hi_q))
    if hi - lo <= 1e-12:
        mn = float(arr.min())
        mx = float(arr.max())
        if mx - mn <= 1e-12:
            return np.zeros_like(arr, dtype=float)
        return np.clip((arr - mn) / (mx - mn + 1e-8), 0.0, 1.0)
    return np.clip((arr - lo) / (hi - lo + 1e-8), 0.0, 1.0)


def _build_dns_subscore(seq_raw_texts):
    texts = [str(x or '') for x in seq_raw_texts]
    n = len(texts)
    if n == 0:
        return np.zeros((0,), dtype=float)
    out = np.zeros((n,), dtype=float)
    for i, text in enumerate(texts):
        lowered = text.lower()
        parts = [p.strip() for p in lowered.split('[seq]') if p.strip()]
        step_count = max(len(parts), 1)
        query = sum('query[' in p or 'query ' in p for p in parts) / step_count
        forwarded = sum('forwarded ' in p for p in parts) / step_count
        refused = sum('refused' in p or 'servfail' in p or 'nxdomain' in p for p in parts) / step_count
        long_token = 0.0
        for p in parts:
            tokens = [tok for tok in re.findall(r"[a-z0-9_.-]+", p) if tok]
            if any(len(tok) >= 24 for tok in tokens):
                long_token += 1.0
        long_token /= step_count
        mix = 1.0 if (query > 0 and ('reply ' in lowered or 'forwarded ' in lowered)) else 0.0
        out[i] = np.clip(np.mean([query, forwarded, refused, long_token, mix]), 0.0, 1.0)
    return out


def _compute_stat_subscores(cfg: Config, x_seq, seq_timestamps, seq_texts, seq_raw_texts):
    stat_len = int(cfg.get('data.statistical_sequence_length', cfg.get('data.sequence_length', 50)))
    x_stat, t_stat = trim_statistical_window(x_seq, seq_timestamps, stat_len)
    extractor = StatisticalFeatureExtractor(cfg)
    bundle = extractor.extract_all_features(
        x_stat,
        seq_timestamps=t_stat,
        seq_texts=seq_texts,
        seq_raw_texts=seq_raw_texts,
    )

    def _flat(name):
        arr = bundle.get(name)
        if arr is None:
            return np.zeros((len(x_stat),), dtype=float)
        return np.asarray(arr, dtype=float).reshape(len(x_stat), -1)

    dist_terms = []
    for key in ['normalized_entropy', 'switch_rate', 'template_count', 'dominant_ratio', 'variance', 'time_burstiness']:
        arr = _flat(key)
        if arr.size == 0:
            continue
        vec = arr[:, 0] if arr.ndim == 2 else arr.reshape(-1)
        if key == 'template_count':
            vec = _quantile_normalize(vec)
        elif key == 'dominant_ratio':
            vec = np.clip(1.0 - vec, 0.0, 1.0)
        elif key in ('variance', 'time_burstiness'):
            vec = _quantile_normalize(np.log1p(np.clip(vec, 0.0, None)))
        else:
            vec = np.clip(vec, 0.0, 1.0)
        dist_terms.append(vec)
    time_interval = bundle.get('time_interval')
    if time_interval is not None:
        tia = np.asarray(time_interval, dtype=float)
        if tia.ndim == 2 and tia.shape[1] >= 1:
            dist_terms.append(_quantile_normalize(np.log1p(np.clip(tia[:, 0], 0.0, None))))
    stat_dist = np.mean(np.column_stack(dist_terms), axis=1) if dist_terms else np.zeros((len(x_stat),), dtype=float)

    auth_terms = []
    for key in ['auth_failure_ratio', 'auth_success_ratio', 'auth_failure_density', 'success_after_fail_chain', 'session_after_fail_chain', 'failed_login_per_user']:
        arr = bundle.get(key)
        if arr is not None:
            auth_terms.append(np.clip(np.asarray(arr, dtype=float).reshape(-1), 0.0, 1.0))
    stat_auth = np.mean(np.column_stack(auth_terms), axis=1) if auth_terms else np.zeros((len(x_stat),), dtype=float)

    web_terms = []
    for key in ['web_probe_ratio', 'suspicious_keyword_ratio', 'unique_uri_per_ip', 'requests_per_ip']:
        arr = bundle.get(key)
        if arr is not None:
            web_terms.append(np.clip(np.asarray(arr, dtype=float).reshape(-1), 0.0, 1.0))
    stat_web = np.mean(np.column_stack(web_terms), axis=1) if web_terms else np.zeros((len(x_stat),), dtype=float)

    dns_source = seq_raw_texts if seq_raw_texts is not None else seq_texts
    if dns_source is None:
        dns_source = []
    stat_dns = _build_dns_subscore(dns_source)

    return {
        'stat_dist_score': np.clip(stat_dist, 0.0, 1.0),
        'stat_auth_score': np.clip(stat_auth, 0.0, 1.0),
        'stat_web_score': np.clip(stat_web, 0.0, 1.0),
        'stat_dns_score': np.clip(stat_dns, 0.0, 1.0),
    }


def _clone_config(base_config: Config, dataset: str) -> Config:
    cfg = Config()
    cfg.config = deepcopy(base_config.config)
    cfg.config.setdefault("data", {})
    cfg.config["data"]["dataset"] = dataset
    return cfg


def _search_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    best_thr = 0.5
    best_f1 = -1.0
    best_recall = -1.0
    for thr in np.linspace(0.05, 0.95, 181):
        y_pred = (y_score >= float(thr)).astype(int)
        cur_f1 = f1_score(y_true, y_pred, zero_division=0)
        cur_recall = recall_score(y_true, y_pred, zero_division=0)
        if cur_f1 > best_f1 or (abs(cur_f1 - best_f1) <= 1e-12 and cur_recall > best_recall):
            best_f1 = float(cur_f1)
            best_recall = float(cur_recall)
            best_thr = float(thr)
    return best_thr


def _calc_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    y_pred = (y_score >= float(threshold)).astype(int)
    metrics = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
        "score_mean": float(np.mean(y_score)),
        "score_std": float(np.std(y_score)),
    }
    if len(np.unique(y_true)) > 1:
        metrics["auc"] = float(roc_auc_score(y_true, y_score))
        metrics["pr_auc"] = float(average_precision_score(y_true, y_score))
    else:
        metrics["auc"] = 0.0
        metrics["pr_auc"] = 0.0
    metrics.update(_calc_ranking_metrics(y_true, y_score))
    return metrics




def _calc_ranking_metrics(y_true: np.ndarray, y_score: np.ndarray, ks: Tuple[int, ...] = (10, 20, 50)) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    total_pos = int(np.sum(y_true))
    order = np.argsort(-y_score)
    y_sorted = y_true[order]

    out: Dict[str, float] = {"positive_count": float(total_pos)}
    for k in ks:
        topk = y_sorted[: min(int(k), len(y_sorted))]
        hit_count = int(np.sum(topk))
        out[f"top{k}_hits"] = float(hit_count)
        out[f"precision_at_{k}"] = float(hit_count / len(topk)) if len(topk) else 0.0
        out[f"recall_at_{k}"] = float(hit_count / total_pos) if total_pos > 0 else 0.0
    return out

def _evaluate_score_family(
    name: str,
    dataset: str,
    y_train: np.ndarray,
    train_score: np.ndarray,
    y_val: np.ndarray,
    val_score: np.ndarray,
    y_test: np.ndarray,
    test_score: np.ndarray,
    group: str,
    split_metadata: Dict[str, object] | None = None,
) -> Dict[str, float]:
    threshold = _search_best_threshold(y_val, val_score)
    row = {
        "dataset": dataset,
        "experiment_group": group,
        "model_name": name,
        "train_samples": int(len(y_train)),
        "val_samples": int(len(y_val)),
        "test_samples": int(len(y_test)),
        "train_anomaly_ratio": float(np.mean(y_train)),
        "val_anomaly_ratio": float(np.mean(y_val)),
        "test_anomaly_ratio": float(np.mean(y_test)),
        "split_mode": str((split_metadata or {}).get("split_mode", "unknown")),
        "threshold_source": "val",
        "test_used_for_selection": False,
    }
    row.update(_calc_metrics(y_test, test_score, threshold))
    return row


def _train_subset_xgb(
    config: Config,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    x_test: np.ndarray,
) -> Tuple[np.ndarray, float]:
    fusion = XGBoostFusion(config)
    fusion.train(x_train, y_train, x_val, y_val)
    val_prob = fusion.predict_proba(x_val)
    test_prob = fusion.predict_proba(x_test)
    threshold = _search_best_threshold(y_val, val_prob)
    return test_prob, threshold


def evaluate_dataset(base_config: Config, dataset: str, logger) -> List[Dict[str, float]]:
    cfg = _clone_config(base_config, dataset)
    data = DataLoader(cfg).prepare_data()
    x_train = data["X_train"]
    x_val = data.get("X_val")
    x_test = data["X_test"]
    y_train = data["y_train"]
    y_val = data.get("y_val")
    y_test = data["y_test"]
    t_train = data.get("T_train")
    t_val = data.get("T_val")
    t_test = data.get("T_test")
    semantic_train = data.get("S_train")
    semantic_val = data.get("S_val")
    semantic_test = data.get("S_test")
    raw_train = data.get("R_train")
    raw_val = data.get("R_val")
    raw_test = data.get("R_test")
    split_metadata = data.get("split_metadata", {})

    if y_train is None or y_test is None or y_val is None or len(y_val) == 0:
        raise ValueError(f"dataset={dataset} 缺少 train/val/test 标签，无法做 leakage-safe 监督评估")

    scorer = ThreeViewScoringService(cfg)
    train_scores = scorer.score(
        x_train,
        semantic_train,
        seq_timestamps=t_train,
        raw_seq_texts=raw_train,
    )
    val_scores = scorer.score(
        x_val,
        semantic_val,
        seq_timestamps=t_val,
        raw_seq_texts=raw_val,
    )
    test_scores = scorer.score(
        x_test,
        semantic_test,
        seq_timestamps=t_test,
        raw_seq_texts=raw_test,
    )

    stat_train = np.asarray(train_scores["stat_scores"], dtype=float)
    temp_train = np.asarray(train_scores["temporal_scores"], dtype=float)
    sem_train = np.asarray(train_scores["semantic_scores"], dtype=float)
    stat_val = np.asarray(val_scores["stat_scores"], dtype=float)
    temp_val = np.asarray(val_scores["temporal_scores"], dtype=float)
    sem_val = np.asarray(val_scores["semantic_scores"], dtype=float)
    stat_test = np.asarray(test_scores["stat_scores"], dtype=float)
    temp_test = np.asarray(test_scores["temporal_scores"], dtype=float)
    sem_test = np.asarray(test_scores["semantic_scores"], dtype=float)

    rows: List[Dict[str, float]] = []
    rows.append(_evaluate_score_family("statistical_view", dataset, y_train, stat_train, y_val, stat_val, y_test, stat_test, "single_view", split_metadata))
    rows.append(_evaluate_score_family("temporal_view", dataset, y_train, temp_train, y_val, temp_val, y_test, temp_test, "single_view", split_metadata))
    rows.append(_evaluate_score_family("semantic_view", dataset, y_train, sem_train, y_val, sem_val, y_test, sem_test, "single_view", split_metadata))

    mean_all_train = (stat_train + temp_train + sem_train) / 3.0
    mean_all_val = (stat_val + temp_val + sem_val) / 3.0
    mean_all_test = (stat_test + temp_test + sem_test) / 3.0
    rows.append(_evaluate_score_family("mean_fusion_all", dataset, y_train, mean_all_train, y_val, mean_all_val, y_test, mean_all_test, "fusion", split_metadata))

    subset_specs = [
        ("ablation_stat_temporal_mean", (stat_train + temp_train) / 2.0, (stat_val + temp_val) / 2.0, (stat_test + temp_test) / 2.0),
        ("ablation_stat_semantic_mean", (stat_train + sem_train) / 2.0, (stat_val + sem_val) / 2.0, (stat_test + sem_test) / 2.0),
        ("ablation_temporal_semantic_mean", (temp_train + sem_train) / 2.0, (temp_val + sem_val) / 2.0, (temp_test + sem_test) / 2.0),
    ]
    for name, train_score, val_score, test_score in subset_specs:
        rows.append(_evaluate_score_family(name, dataset, y_train, train_score, y_val, val_score, y_test, test_score, "ablation_mean", split_metadata))

    stat_sub_train = _compute_stat_subscores(cfg, x_train, t_train, semantic_train, raw_train)
    stat_sub_val = _compute_stat_subscores(cfg, x_val, t_val, semantic_val, raw_val)
    stat_sub_test = _compute_stat_subscores(cfg, x_test, t_test, semantic_test, raw_test)

    x_meta_train = np.column_stack([stat_train, temp_train, sem_train])
    x_meta_val = np.column_stack([stat_val, temp_val, sem_val])
    x_meta_test = np.column_stack([stat_test, temp_test, sem_test])

    x_meta_train_stat_parts = np.column_stack([
        temp_train,
        sem_train,
        stat_sub_train['stat_dist_score'],
        stat_sub_train['stat_auth_score'],
        stat_sub_train['stat_web_score'],
        stat_sub_train['stat_dns_score'],
    ])
    x_meta_val_stat_parts = np.column_stack([
        temp_val,
        sem_val,
        stat_sub_val['stat_dist_score'],
        stat_sub_val['stat_auth_score'],
        stat_sub_val['stat_web_score'],
        stat_sub_val['stat_dns_score'],
    ])
    x_meta_test_stat_parts = np.column_stack([
        temp_test,
        sem_test,
        stat_sub_test['stat_dist_score'],
        stat_sub_test['stat_auth_score'],
        stat_sub_test['stat_web_score'],
        stat_sub_test['stat_dns_score'],
    ])

    x_meta_train_stat_parts_plus_legacy = np.column_stack([
        stat_train,
        temp_train,
        sem_train,
        stat_sub_train['stat_dist_score'],
        stat_sub_train['stat_auth_score'],
        stat_sub_train['stat_web_score'],
        stat_sub_train['stat_dns_score'],
    ])
    x_meta_val_stat_parts_plus_legacy = np.column_stack([
        stat_val,
        temp_val,
        sem_val,
        stat_sub_val['stat_dist_score'],
        stat_sub_val['stat_auth_score'],
        stat_sub_val['stat_web_score'],
        stat_sub_val['stat_dns_score'],
    ])
    x_meta_test_stat_parts_plus_legacy = np.column_stack([
        stat_test,
        temp_test,
        sem_test,
        stat_sub_test['stat_dist_score'],
        stat_sub_test['stat_auth_score'],
        stat_sub_test['stat_web_score'],
        stat_sub_test['stat_dns_score'],
    ])

    try:
        ensemble = EnsemblePredictor(cfg)
        xgb_train_prob = ensemble.fusion.predict_proba(x_meta_train)
        xgb_test_prob = ensemble.fusion.predict_proba(x_meta_test)
        xgb_val_prob = ensemble.fusion.predict_proba(x_meta_val)
        rows.append(
            _evaluate_score_family(
                "xgboost_fusion_saved_model",
                dataset,
                y_train,
                xgb_train_prob,
                y_val,
                xgb_val_prob,
                y_test,
                xgb_test_prob,
                "fusion",
                split_metadata,
            )
        )
    except Exception as exc:
        logger.warning(f"dataset={dataset} 无法加载已训练 XGBoost 融合模型: {exc}")

    ablation_xgb_specs = [
        ("ablation_stat_temporal_xgb", np.column_stack([stat_train, temp_train]), np.column_stack([stat_val, temp_val]), np.column_stack([stat_test, temp_test])),
        ("ablation_stat_semantic_xgb", np.column_stack([stat_train, sem_train]), np.column_stack([stat_val, sem_val]), np.column_stack([stat_test, sem_test])),
        ("ablation_temporal_semantic_xgb", np.column_stack([temp_train, sem_train]), np.column_stack([temp_val, sem_val]), np.column_stack([temp_test, sem_test])),
        ("xgboost_fusion_retrained", x_meta_train, x_meta_val, x_meta_test),
        ("xgboost_fusion_stat_parts_xgb", x_meta_train_stat_parts, x_meta_val_stat_parts, x_meta_test_stat_parts),
        ("xgboost_fusion_stat_parts_plus_legacy_xgb", x_meta_train_stat_parts_plus_legacy, x_meta_val_stat_parts_plus_legacy, x_meta_test_stat_parts_plus_legacy),
    ]
    for name, sub_train, sub_val, sub_test in ablation_xgb_specs:
        try:
            test_prob, threshold = _train_subset_xgb(cfg, sub_train, y_train, sub_val, y_val, sub_test)
            row = {
                "dataset": dataset,
                "experiment_group": "ablation_xgb" if "ablation" in name else "fusion",
                "model_name": name,
                "train_samples": int(len(y_train)),
                "val_samples": int(len(y_val)),
                "test_samples": int(len(y_test)),
                "train_anomaly_ratio": float(np.mean(y_train)),
                "val_anomaly_ratio": float(np.mean(y_val)),
                "test_anomaly_ratio": float(np.mean(y_test)),
                "split_mode": str(split_metadata.get("split_mode", "unknown")),
                "threshold_source": "val",
                "test_used_for_selection": False,
            }
            row.update(_calc_metrics(y_test, test_prob, threshold))
            rows.append(row)
        except Exception as exc:
            logger.warning(f"dataset={dataset} {name} 训练失败: {exc}")

    return rows


def save_results(config: Config, datasets: Iterable[str], rows: List[Dict[str, float]]) -> Tuple[Path, Path]:
    out_dir = Path(config.get("paths.outputs.reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_tag = "_".join(datasets)
    csv_path = out_dir / f"view_eval_{dataset_tag}_{ts}.csv"
    json_path = out_dir / f"view_eval_{dataset_tag}_{ts}.json"

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = {
        "datasets": list(datasets),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": int(len(df)),
        "best_by_dataset": {},
    }
    if not df.empty:
        for dataset, sub in df.groupby("dataset"):
            best = sub.sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).head(1)
            summary["best_by_dataset"][dataset] = best.to_dict(orient="records")[0]
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def main(datasets: Iterable[str] | None = None):
    config = Config()
    logger = Logger.get_logger("evaluate_views", config)
    if not datasets:
        datasets = [str(config.get("data.dataset", "hdfs"))]

    all_rows: List[Dict[str, float]] = []
    for dataset in datasets:
        logger.info(f"开始评估数据集: {dataset}")
        rows = evaluate_dataset(config, str(dataset), logger)
        all_rows.extend(rows)

    csv_path, json_path = save_results(config, [str(x) for x in datasets], all_rows)
    print("=" * 70)
    print("多视图评估完成")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
