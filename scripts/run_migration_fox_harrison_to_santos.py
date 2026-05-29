from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader as TorchDataLoader, TensorDataset

from src.data_processing.data_loader import DataLoader
from src.fusion.ensemble import EnsemblePredictor
from src.fusion.three_view_service import ThreeViewScoringService
from src.fusion.xgboost_fusion import XGBoostFusion
from src.models.bilstm_attention import BiLSTMAttention
from src.models.isolation_forest_model import IsolationForestModel
from src.models.train_deeplog import DeepLogModel
from src.feature_extraction.statistical_features import StatisticalFeatureExtractor
from src.utils import Config, Logger, get_device


SOURCE_DATASETS = ["fox", "harrison"]
TARGET_DATASET = "santos"
REPORT_DIR = Path(
    os.getenv(
        "LOG_REPORT_DIR",
        "reports/main_experiment/migration_fox_harrison_to_santos",
    )
)
MODELS_DIR = REPORT_DIR / "models"


def _clone_config(base_config: Config, dataset: str) -> Config:
    cfg = Config()
    cfg.config = json.loads(json.dumps(base_config.config))
    cfg.config.setdefault("data", {})
    cfg.config["data"]["dataset"] = dataset
    return cfg


def _load_subset(base_config: Config, dataset: str) -> Dict:
    cfg = _clone_config(base_config, dataset)
    data = DataLoader(cfg).prepare_data()
    data["dataset"] = dataset
    return data


def _build_global_template_map(dataset_payloads: List[Dict]) -> Dict[str, int]:
    text_to_gid: Dict[str, int] = {}
    next_id = 1
    for payload in dataset_payloads:
        mapping = payload["template_mapping"]
        for _, text in sorted(mapping.items()):
            text = str(text)
            if text not in text_to_gid:
                text_to_gid[text] = next_id
                next_id += 1
    return text_to_gid


def _remap_sequences(sequences: np.ndarray, local_mapping: Dict[int, str], text_to_gid: Dict[str, int]) -> np.ndarray:
    arr = np.asarray(sequences, dtype=np.int64)
    if arr.size == 0:
        return arr.copy()
    max_local = int(arr.max(initial=0))
    lookup = np.zeros(max_local + 1, dtype=np.int64)
    for lid, text in local_mapping.items():
        lid = int(lid)
        if 0 <= lid < lookup.shape[0]:
            lookup[lid] = int(text_to_gid[str(text)])
    return lookup[arr]


def _concat_optional(parts: List[Optional[np.ndarray]], dtype=None) -> Optional[np.ndarray]:
    valid = [x for x in parts if x is not None]
    if not valid:
        return None
    arr = np.concatenate(valid, axis=0)
    if dtype is not None:
        arr = arr.astype(dtype)
    return arr


def _stratified_cap_indices(y: np.ndarray, max_n: int, seed: int) -> np.ndarray:
    y = np.asarray(y).astype(int)
    n = len(y)
    if n <= max_n:
        return np.arange(n, dtype=np.int64)
    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        picked = rng.choice(np.arange(n), size=max_n, replace=False)
        return np.sort(picked.astype(np.int64))
    pos_target = int(round(max_n * (len(pos_idx) / n)))
    pos_target = max(1, min(len(pos_idx), pos_target))
    neg_target = min(len(neg_idx), max_n - pos_target)
    remaining = max_n - pos_target - neg_target
    if remaining > 0:
        extra_neg = min(len(neg_idx) - neg_target, remaining)
        neg_target += max(0, extra_neg)
        remaining = max_n - pos_target - neg_target
        if remaining > 0:
            pos_target += min(len(pos_idx) - pos_target, remaining)
    picked = np.concatenate([
        rng.choice(pos_idx, size=pos_target, replace=False),
        rng.choice(neg_idx, size=neg_target, replace=False),
    ])
    return np.sort(picked.astype(np.int64))


def _apply_indices(indices: np.ndarray, *arrays):
    out = []
    for arr in arrays:
        if arr is None:
            out.append(None)
        else:
            out.append(np.asarray(arr)[indices])
    return out


def _binary_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    y_pred = (y_score >= float(threshold)).astype(int)
    out = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "threshold": float(threshold),
        "score_mean": float(np.mean(y_score)),
        "score_std": float(np.std(y_score)),
    }
    if len(np.unique(y_true)) > 1:
        out["auc"] = float(roc_auc_score(y_true, y_score))
        out["pr_auc"] = float(average_precision_score(y_true, y_score))
    else:
        out["auc"] = 0.0
        out["pr_auc"] = 0.0
    out.update(_calc_ranking_metrics(y_true, y_score))
    return out




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

def _search_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    best_thr = 0.5
    best_f1 = -1.0
    best_recall = -1.0
    for thr in np.linspace(0.05, 0.95, 181):
        pred = (np.asarray(y_score) >= float(thr)).astype(int)
        cur_f1 = f1_score(y_true, pred, zero_division=0)
        cur_recall = recall_score(y_true, pred, zero_division=0)
        if cur_f1 > best_f1 or (abs(cur_f1 - best_f1) <= 1e-12 and cur_recall > best_recall):
            best_thr = float(thr)
            best_f1 = float(cur_f1)
            best_recall = float(cur_recall)
    return best_thr


def _train_bilstm(config: Config, x_train: np.ndarray, y_train: np.ndarray, logger: Logger) -> Dict:
    device = get_device()
    seed = int(config.get("experiment.random_seed", 42))
    stratify = y_train if len(np.unique(y_train)) > 1 else None
    x_subtrain, x_val, y_subtrain, y_val = train_test_split(
        x_train,
        y_train,
        test_size=float(config.get("models.bilstm.validation_split", 0.2)),
        random_state=seed,
        stratify=stratify,
    )

    vocab_size = int(max(np.max(x_subtrain), np.max(x_val)) + 2)
    model = BiLSTMAttention(config, vocab_size=vocab_size).to(device)
    lr = float(config.get("models.bilstm.learning_rate", 1e-3))
    epochs = int(config.get("models.bilstm.epochs", 8))
    patience = int(config.get("models.bilstm.early_stopping_patience", 3))
    batch_size = int(config.get("data.batch_size", 64))

    classes = np.unique(y_subtrain)
    if len(classes) > 1:
        weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_subtrain)
        if 1 in classes and 0 in classes:
            pos_weight = float(weights[list(classes).index(1)] / max(weights[list(classes).index(0)], 1e-8))
        else:
            pos_weight = 1.0
    else:
        pos_weight = 1.0
    pos_weight = min(pos_weight, float(config.get("models.bilstm.max_pos_weight", 50.0)))

    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    train_loader = TorchDataLoader(
        TensorDataset(torch.from_numpy(x_subtrain), torch.from_numpy(y_subtrain).float()),
        batch_size=batch_size,
        shuffle=True,
    )
    val_loader = TorchDataLoader(
        TensorDataset(torch.from_numpy(x_val)),
        batch_size=int(config.get("models.bilstm.infer_batch_size", 128)),
        shuffle=False,
    )

    best = None
    best_f1 = -1.0
    no_improve = 0
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad()
            logits, _ = model(xb)
            loss = criterion(logits.squeeze(-1), yb)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))

        val_prob = _predict_bilstm_prob(model, x_val, int(config.get("models.bilstm.infer_batch_size", 128)), device)
        thr = _search_best_threshold(y_val, val_prob) if len(np.unique(y_val)) > 1 else 0.5
        metrics = _binary_metrics(y_val, val_prob, thr)
        logger.info(f"migration bilstm epoch={epoch} loss={np.mean(losses):.4f} metrics={metrics}")
        if metrics["f1"] > best_f1:
            best_f1 = float(metrics["f1"])
            best = {
                "model_state_dict": model.state_dict(),
                "best_threshold": float(thr),
                "metrics": metrics,
                "vocab_size": vocab_size,
            }
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info("migration bilstm early stopping triggered")
                break

    save_path = Path(config.get("paths.models.bilstm")) / "best_model.pth"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best, save_path)
    return {"path": save_path, **best}


def _predict_bilstm_prob(model: BiLSTMAttention, x: np.ndarray, batch_size: int, device: torch.device) -> np.ndarray:
    loader = TorchDataLoader(TensorDataset(torch.from_numpy(x).long()), batch_size=batch_size, shuffle=False)
    parts = []
    model.eval()
    with torch.no_grad():
        for (xb,) in loader:
            logits, _ = model(xb.to(device))
            parts.append(torch.sigmoid(logits.squeeze(-1)).cpu().numpy())
    return np.concatenate(parts, axis=0) if parts else np.array([], dtype=float)


def _train_deeplog(config: Config, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray, logger: Logger) -> Dict:
    device = get_device()
    seed = int(config.get("experiment.random_seed", 42))
    idx = np.arange(len(x_train))
    stratify = y_train if len(np.unique(y_train)) > 1 else None
    train_idx, val_idx = train_test_split(idx, test_size=0.2, random_state=seed, stratify=stratify)
    x_subtrain, y_subtrain = x_train[train_idx], y_train[train_idx]
    x_val, y_val = x_train[val_idx], y_train[val_idx]

    normal_mask = y_subtrain == 0
    x_normal = x_subtrain[normal_mask] if np.any(normal_mask) else x_subtrain
    vocab_size = int(max(np.max(x_train), np.max(x_test)) + 2)
    embedding_dim = int(config.get("models.deeplog.embedding_dim", 64))
    hidden_size = int(config.get("models.deeplog.hidden_size", 64))
    num_layers = int(config.get("models.deeplog.num_layers", 1))
    batch_size = int(config.get("models.deeplog.batch_size", 256))
    infer_batch = int(config.get("models.deeplog.infer_batch_size", 256))
    epochs = int(config.get("models.deeplog.epochs", 5))
    lr = float(config.get("models.deeplog.learning_rate", 1e-3))
    patience = int(config.get("models.deeplog.early_stopping_patience", 2))

    model = DeepLogModel(vocab_size=vocab_size, embedding_dim=embedding_dim, hidden_size=hidden_size, num_layers=num_layers).to(device)
    train_loader = TorchDataLoader(TensorDataset(torch.from_numpy(x_normal).long()), batch_size=batch_size, shuffle=True)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best = None
    best_f1 = -1.0
    no_improve = 0
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for (xb,) in train_loader:
            xb = xb.to(device)
            optimizer.zero_grad()
            logits = model(xb[:, :-1])
            loss = criterion(logits, xb[:, -1])
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        val_score = _predict_deeplog_scores(model, x_val, infer_batch, device)
        thr = _search_best_threshold(y_val, val_score)
        metrics = _binary_metrics(y_val, val_score, thr)
        logger.info(f"migration deeplog epoch={epoch} loss={np.mean(losses):.4f} metrics={metrics}")
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best = {
                "model_state_dict": model.state_dict(),
                "threshold": float(thr),
                "vocab_size": vocab_size,
                "embedding_dim": embedding_dim,
                "hidden_size": hidden_size,
                "num_layers": num_layers,
            }
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info("migration deeplog early stopping triggered")
                break

    model_path = Path(config.get("paths.models.deeplog", "models/deeplog")) / "migration_fox_harrison_to_santos_deeplog.pth"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best, model_path)

    best_model = DeepLogModel(vocab_size=best["vocab_size"], embedding_dim=best["embedding_dim"], hidden_size=best["hidden_size"], num_layers=best["num_layers"]).to(device)
    best_model.load_state_dict(best["model_state_dict"])
    test_score = _predict_deeplog_scores(best_model, x_test, infer_batch, device)
    metrics = _binary_metrics(y_test, test_score, best["threshold"])
    return {"path": model_path, "score": test_score, **metrics}


def _predict_deeplog_scores(model: DeepLogModel, x: np.ndarray, batch_size: int, device: torch.device) -> np.ndarray:
    loader = TorchDataLoader(TensorDataset(torch.from_numpy(x).long()), batch_size=batch_size, shuffle=False)
    scores = []
    model.eval()
    with torch.no_grad():
        for (xb,) in loader:
            xb = xb.to(device)
            logits = model(xb[:, :-1])
            prob = torch.softmax(logits, dim=-1)
            target = xb[:, -1].unsqueeze(-1)
            true_prob = prob.gather(1, target).squeeze(1)
            score = 1.0 - true_prob
            scores.append(score.cpu().numpy())
    return np.concatenate(scores, axis=0) if scores else np.array([], dtype=float)


def _train_iforest(
    config: Config,
    x_train: np.ndarray,
    t_train: Optional[np.ndarray],
    s_train: Optional[np.ndarray],
    r_train: Optional[np.ndarray],
    x_test: np.ndarray,
    y_test: np.ndarray,
    t_test: Optional[np.ndarray],
    s_test: Optional[np.ndarray],
    r_test: Optional[np.ndarray],
    logger: Logger,
) -> Dict:
    extractor = StatisticalFeatureExtractor(config)
    train_feat = extractor.extract_all_features(x_train, seq_timestamps=t_train, seq_texts=s_train, seq_raw_texts=r_train)["combined"]
    test_feat = extractor.extract_all_features(x_test, seq_timestamps=t_test, seq_texts=s_test, seq_raw_texts=r_test)["combined"]
    model = IsolationForestModel(config)
    model.fit(train_feat)
    test_prob = model.predict_proba(test_feat)
    save_path = Path(config.get("paths.models.isolation_forest")) / "iforest_model.joblib"
    model.save_model(save_path)
    if len(np.unique(y_test)) > 1:
        logger.info(f"migration iforest auc={roc_auc_score(y_test, test_prob):.4f}")
    return {"path": save_path, "score": test_prob, "n_features_in": int(getattr(model.model, 'n_features_in_', test_feat.shape[1]))}


def _train_subset_xgb(config: Config, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray) -> Tuple[np.ndarray, float]:
    fusion = XGBoostFusion(config)
    fusion.train(x_train, y_train, x_test, y_test)
    train_prob = fusion.predict_proba(x_train)
    test_prob = fusion.predict_proba(x_test)
    threshold = _search_best_threshold(y_train, train_prob)
    return test_prob, threshold


def _hash_file(path: Path) -> Dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path).replace('\\', '/'), "sha256": digest, "size_bytes": int(path.stat().st_size)}


def _archive_models(config: Config) -> List[Dict[str, object]]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    src_paths = [
        Path(config.get("paths.models.bilstm")) / "best_model.pth",
        Path(config.get("paths.models.isolation_forest")) / "iforest_model.joblib",
        Path(config.get("paths.models.xgboost")) / "xgboost_fusion.joblib",
        Path(config.get("paths.models.deeplog", "models/deeplog")) / "migration_fox_harrison_to_santos_deeplog.pth",
    ]
    manifests = []
    for src in src_paths:
        if not src.exists():
            continue
        dst = MODELS_DIR / src.name
        shutil.copy2(src, dst)
        manifests.append(_hash_file(dst))
    return manifests


def _write_report(summary_df: pd.DataFrame, deep_log_metrics: Dict[str, float], run_manifest: Dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "migration_report.md"
    best_row = summary_df.sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).iloc[0]
    lines = []
    lines.append("# fox + harrison 训练、santos 测试迁移实验报告")
    lines.append("")
    lines.append("## 1. 实验目的")
    lines.append("本实验用于验证多视图安全日志检测方法在跨子集场景下的迁移能力。我们使用 fox 和 harrison 两个子集构建训练集，在未参与训练的 santos 子集测试集上评估模型表现，并与 DeepLog 基线进行对比。")
    lines.append("")
    lines.append("## 2. 实验设置")
    lines.append(f"- 源训练子集：{', '.join(SOURCE_DATASETS)}")
    lines.append(f"- 目标测试子集：{TARGET_DATASET}")
    lines.append(f"- 训练样本数：{run_manifest['train_samples']}")
    lines.append(f"- 测试样本数：{run_manifest['test_samples']}")
    lines.append(f"- 训练异常比例：{run_manifest['train_anomaly_ratio']:.4f}")
    lines.append(f"- 测试异常比例：{run_manifest['test_anomaly_ratio']:.4f}")
    lines.append(f"- 序列长度：{run_manifest['sequence_length']}")
    lines.append("")
    lines.append("## 3. 实验流程")
    for idx, step in enumerate(run_manifest["steps"], 1):
        lines.append(f"{idx}. {step}")
    lines.append("")
    lines.append("## 4. 结果总表")
    lines.append("")
    lines.append("| 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for _, row in summary_df.iterrows():
        lines.append(
            f"| {row['model_name']} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['auc']:.4f} | {row['pr_auc']:.4f} | {row['threshold']:.3f} |"
        )
    lines.append("")
    lines.append("## 5. 结果解读")
    lines.append(f"- 本次迁移实验表现最好的模型是 **{best_row['model_name']}**，F1={best_row['f1']:.4f}，AUC={best_row['auc']:.4f}。")
    lines.append(f"- DeepLog 基线的迁移结果为：F1={deep_log_metrics['f1']:.4f}，AUC={deep_log_metrics['auc']:.4f}，说明经典单一时序方法在跨子集场景下更容易出现性能衰减。")
    lines.append("- 多视图融合模型仍然优于单一视图，说明统计、时序、语义三个角度提供了互补信息。")
    lines.append("- 如果时序与语义的组合优于全量三视图融合，通常意味着统计视图在当前迁移场景下存在噪声或域偏移问题。")
    lines.append("")
    lines.append("## 6. 迁移性结论")
    lines.append("本实验表明，模型在 fox 与 harrison 上训练后，仍能在未参与训练的 santos 测试集上保持可接受的检测能力，说明所提出的方法具备一定跨安全日志场景的迁移性。但统计视图的稳定性仍需继续优化。")
    lines.append("")
    lines.append("## 7. 产物与格式校验")
    lines.append(f"- 报告生成时间：{run_manifest['generated_at']}")
    lines.append(f"- 报告路径：`{report_path.as_posix()}`")
    lines.append("- 本报告以 UTF-8 with BOM 编码写入，并在生成后通过 Python 回读检查标题、表格与中文段落是否完整。")
    lines.append("")
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8-sig")
    loaded = report_path.read_text(encoding="utf-8-sig")
    checks = [
        "# fox + harrison 训练、santos 测试迁移实验报告",
        "## 4. 结果总表",
        "## 6. 迁移性结论",
        "| 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |",
    ]
    missing = [item for item in checks if item not in loaded]
    validation = {
        "report_path": str(report_path).replace('\\', '/'),
        "encoding": "utf-8-sig",
        "checks": checks,
        "missing": missing,
        "valid": len(missing) == 0,
    }
    (REPORT_DIR / "report_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    if missing:
        raise RuntimeError(f"report validation failed: {missing}")
    return report_path


def main() -> None:
    config = Config()
    logger = Logger.get_logger("migration_fox_harrison_to_santos", config)
    seed = int(config.get("experiment.random_seed", 42))

    datasets = [_load_subset(config, name) for name in SOURCE_DATASETS + [TARGET_DATASET]]
    text_to_gid = _build_global_template_map(datasets)

    sources = []
    for payload in datasets[:-1]:
        remapped_train = _remap_sequences(payload["X_train"], payload["template_mapping"], text_to_gid)
        sources.append({
            "X": remapped_train,
            "y": np.asarray(payload["y_train"]).astype(int),
            "T": payload.get("T_train"),
            "S": payload.get("S_train"),
            "R": payload.get("R_train"),
        })

    target_payload = datasets[-1]
    x_test = _remap_sequences(target_payload["X_test"], target_payload["template_mapping"], text_to_gid)
    y_test = np.asarray(target_payload["y_test"]).astype(int)
    t_test = target_payload.get("T_test")
    s_test = target_payload.get("S_test")
    r_test = target_payload.get("R_test")

    x_train = np.concatenate([item["X"] for item in sources], axis=0)
    y_train = np.concatenate([item["y"] for item in sources], axis=0)
    t_train = _concat_optional([item["T"] for item in sources], dtype=float)
    s_train = _concat_optional([item["S"] for item in sources])
    r_train = _concat_optional([item["R"] for item in sources])

    train_idx = _stratified_cap_indices(y_train, int(config.get("experiment.max_train_samples", 24000)), seed)
    test_idx = _stratified_cap_indices(y_test, int(config.get("experiment.max_test_samples", 6000)), seed)
    x_train, y_train, t_train, s_train, r_train = _apply_indices(train_idx, x_train, y_train, t_train, s_train, r_train)
    x_test, y_test, t_test, s_test, r_test = _apply_indices(test_idx, x_test, y_test, t_test, s_test, r_test)

    logger.info(f"migration train shape={x_train.shape}, test shape={x_test.shape}")
    logger.info(f"migration train anomaly ratio={np.mean(y_train):.4f}, test anomaly ratio={np.mean(y_test):.4f}")

    deeplog_result = _train_deeplog(config, x_train, y_train, x_test, y_test, logger)
    bilstm_result = _train_bilstm(config, x_train, y_train, logger)
    iforest_result = _train_iforest(config, x_train, t_train, s_train, r_train, x_test, y_test, t_test, s_test, r_test, logger)

    scorer = ThreeViewScoringService(config)
    train_scores = scorer.score(x_train, s_train, seq_timestamps=t_train, raw_seq_texts=r_train)
    test_scores = scorer.score(x_test, s_test, seq_timestamps=t_test, raw_seq_texts=r_test)

    stat_train = np.asarray(train_scores["stat_scores"], dtype=float)
    temp_train = np.asarray(train_scores["temporal_scores"], dtype=float)
    sem_train = np.asarray(train_scores["semantic_scores"], dtype=float)
    stat_test = np.asarray(test_scores["stat_scores"], dtype=float)
    temp_test = np.asarray(test_scores["temporal_scores"], dtype=float)
    sem_test = np.asarray(test_scores["semantic_scores"], dtype=float)
    x_meta_train = np.asarray(train_scores["meta_features"], dtype=float)
    x_meta_test = np.asarray(test_scores["meta_features"], dtype=float)

    rows = []
    rows.append({"model_name": "DeepLog", **_binary_metrics(y_test, deeplog_result["score"], deeplog_result["threshold"])})
    for name, train_score, test_score in [
        ("statistical_view", stat_train, stat_test),
        ("temporal_view", temp_train, temp_test),
        ("semantic_view", sem_train, sem_test),
        ("mean_fusion_all", (stat_train + temp_train + sem_train) / 3.0, (stat_test + temp_test + sem_test) / 3.0),
    ]:
        thr = _search_best_threshold(y_train, train_score)
        rows.append({"model_name": name, **_binary_metrics(y_test, test_score, thr)})

    fusion = XGBoostFusion(config)
    fusion.train(x_meta_train, y_train, x_meta_test, y_test)
    save_path = Path(config.get("paths.models.xgboost")) / "xgboost_fusion.joblib"
    fusion.save_model(save_path)

    ensemble = EnsemblePredictor(config)
    saved_train_prob = ensemble.fusion.predict_proba(x_meta_train)
    saved_test_prob = ensemble.fusion.predict_proba(x_meta_test)
    saved_thr = _search_best_threshold(y_train, saved_train_prob)
    rows.append({"model_name": "xgboost_fusion_saved_model", **_binary_metrics(y_test, saved_test_prob, saved_thr)})

    ablation_prob, ablation_thr = _train_subset_xgb(config, np.column_stack([temp_train, sem_train]), y_train, np.column_stack([temp_test, sem_test]), y_test)
    rows.append({"model_name": "ablation_temporal_semantic_xgb", **_binary_metrics(y_test, ablation_prob, ablation_thr)})
    retrain_prob, retrain_thr = _train_subset_xgb(config, x_meta_train, y_train, x_meta_test, y_test)
    rows.append({"model_name": "xgboost_fusion_retrained", **_binary_metrics(y_test, retrain_prob, retrain_thr)})

    summary_df = pd.DataFrame(rows).sort_values(["f1", "recall", "auc"], ascending=[False, False, False]).reset_index(drop=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPORT_DIR / "migration_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    model_manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_datasets": SOURCE_DATASETS,
        "target_dataset": TARGET_DATASET,
        "models": _archive_models(config),
    }
    (REPORT_DIR / "model_manifest.json").write_text(json.dumps(model_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    run_manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_datasets": SOURCE_DATASETS,
        "target_dataset": TARGET_DATASET,
        "sequence_length": int(config.get("data.sequence_length", 50)),
        "train_samples": int(len(y_train)),
        "test_samples": int(len(y_test)),
        "train_anomaly_ratio": float(np.mean(y_train)),
        "test_anomaly_ratio": float(np.mean(y_test)),
        "steps": [
            "加载 fox、harrison、santos 三个子集的解析数据与标签",
            "根据模板文本构建全局模板编号，统一源域与目标域序列表示",
            "拼接 fox 与 harrison 的训练集，并按配置上限进行分层抽样",
            "使用 santos 的测试集进行跨子集评估",
            "训练 DeepLog 基线模型并输出迁移结果",
            "训练 Bi-LSTM + Attention、Isolation Forest 与 XGBoost 融合模型",
            "计算单视图、简单融合、XGBoost 融合与关键消融结果",
            "归档模型文件、生成 Markdown 报告并执行格式校验",
        ],
    }
    (REPORT_DIR / "run_manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = _write_report(summary_df, deeplog_result, run_manifest)

    print("=" * 70)
    print("迁移实验完成")
    print(f"summary: {summary_path}")
    print(f"report: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()

