from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from torch.utils.data import DataLoader as TorchDataLoader, TensorDataset

from src.data_processing.data_loader import DataLoader
from src.utils import Config, Logger, get_device


class DeepLogModel(nn.Module):
    def __init__(self, vocab_size: int, embedding_dim: int = 64, hidden_size: int = 64, num_layers: int = 1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.lstm = nn.LSTM(embedding_dim, hidden_size, num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(x)
        out, _ = self.lstm(emb)
        last = out[:, -1, :]
        return self.fc(last)


def _metrics(y_true: np.ndarray, y_score: np.ndarray, thr: float) -> dict:
    y_pred = (y_score >= float(thr)).astype(int)
    out = {
        'precision': float(precision_score(y_true, y_pred, zero_division=0)),
        'recall': float(recall_score(y_true, y_pred, zero_division=0)),
        'f1': float(f1_score(y_true, y_pred, zero_division=0)),
        'threshold': float(thr),
        'score_mean': float(np.mean(y_score)),
        'score_std': float(np.std(y_score)),
    }
    if len(np.unique(y_true)) > 1:
        out['auc'] = float(roc_auc_score(y_true, y_score))
        out['pr_auc'] = float(average_precision_score(y_true, y_score))
    else:
        out['auc'] = 0.0
        out['pr_auc'] = 0.0
    return out


def _search_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    best_thr, best_f1, best_recall = 0.5, -1.0, -1.0
    for thr in np.linspace(0.05, 0.95, 181):
        pred = (y_score >= thr).astype(int)
        cur_f1 = f1_score(y_true, pred, zero_division=0)
        cur_recall = recall_score(y_true, pred, zero_division=0)
        if cur_f1 > best_f1 or (abs(cur_f1 - best_f1) <= 1e-12 and cur_recall > best_recall):
            best_thr = float(thr)
            best_f1 = float(cur_f1)
            best_recall = float(cur_recall)
    return best_thr


def _predict_scores(model: DeepLogModel, x: np.ndarray, batch_size: int, device: torch.device) -> np.ndarray:
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


def main() -> None:
    config = Config()
    logger = Logger.get_logger('train_deeplog', config)
    device = get_device()
    dataset = str(config.get('data.dataset', 'hdfs')).lower()

    data = DataLoader(config).prepare_data()
    x_train = np.asarray(data['X_train'], dtype=np.int64)
    x_val = np.asarray(data.get('X_val'), dtype=np.int64)
    x_test = np.asarray(data['X_test'], dtype=np.int64)
    y_train_raw = data['y_train']
    y_val_raw = data.get('y_val')
    y_test_raw = data['y_test']

    if y_train_raw is None or y_test_raw is None:
        raise ValueError(f'dataset={dataset} 缺少标签，无法训练 DeepLog 基线')

    y_train = np.asarray(y_train_raw, dtype=np.int64)
    y_val = np.asarray(y_val_raw, dtype=np.int64) if y_val_raw is not None and len(y_val_raw) else np.asarray([], dtype=np.int64)
    y_test = np.asarray(y_test_raw, dtype=np.int64)

    max_train = int(config.get('experiment.max_train_samples', 24000))
    max_val = int(config.get('experiment.max_val_samples', config.get('experiment.max_test_samples', 6000)))
    max_test = int(config.get('experiment.max_test_samples', 6000))
    x_train, y_train = x_train[:max_train], y_train[:max_train]
    x_val, y_val = x_val[:max_val], y_val[:max_val]
    x_test, y_test = x_test[:max_test], y_test[:max_test]

    if len(x_val) == 0 or len(y_val) == 0:
        raise ValueError(f'dataset={dataset} 缺少验证集，请使用 ordered_pre_split + val_ratio 配置重跑')

    x_subtrain, y_subtrain = x_train, y_train

    normal_mask = (y_subtrain == 0)
    x_normal = x_subtrain[normal_mask]
    if len(x_normal) == 0:
        logger.warning('训练集中无正常样本，回退为使用全部样本训练 DeepLog')
        x_normal = x_subtrain

    vocab_size = int(max(np.max(x_train), np.max(x_test)) + 2)
    model = DeepLogModel(
        vocab_size=vocab_size,
        embedding_dim=int(config.get('models.deeplog.embedding_dim', 64)),
        hidden_size=int(config.get('models.deeplog.hidden_size', 64)),
        num_layers=int(config.get('models.deeplog.num_layers', 1)),
    ).to(device)

    batch_size = int(config.get('models.deeplog.batch_size', 256))
    infer_batch = int(config.get('models.deeplog.infer_batch_size', 256))
    epochs = int(config.get('models.deeplog.epochs', 5))
    lr = float(config.get('models.deeplog.learning_rate', 1e-3))
    patience = int(config.get('models.deeplog.early_stopping_patience', 2))

    train_loader = TorchDataLoader(
        TensorDataset(torch.from_numpy(x_normal).long()), batch_size=batch_size, shuffle=True
    )
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

        val_score = _predict_scores(model, x_val, infer_batch, device)
        thr = _search_best_threshold(y_val, val_score)
        metrics = _metrics(y_val, val_score, thr)
        logger.info(f'dataset={dataset} epoch={epoch} loss={np.mean(losses):.4f} metrics={metrics}')
        if metrics['f1'] > best_f1:
            best_f1 = metrics['f1']
            best = {
                'model_state_dict': model.state_dict(),
                'threshold': float(thr),
                'metrics': metrics,
                'vocab_size': vocab_size,
                'embedding_dim': int(config.get('models.deeplog.embedding_dim', 64)),
                'hidden_size': int(config.get('models.deeplog.hidden_size', 64)),
                'num_layers': int(config.get('models.deeplog.num_layers', 1)),
                'dataset': dataset,
            }
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info('DeepLog early stopping triggered')
                break

    if best is None:
        raise RuntimeError('DeepLog training failed to produce checkpoint')

    save_dir = Path(config.get('paths.models.deeplog', 'models/deeplog'))
    save_dir.mkdir(parents=True, exist_ok=True)
    model_path = save_dir / f'{dataset}_deeplog.pth'
    torch.save(best, model_path)

    best_model = DeepLogModel(
        vocab_size=best['vocab_size'],
        embedding_dim=best['embedding_dim'],
        hidden_size=best['hidden_size'],
        num_layers=best['num_layers'],
    ).to(device)
    best_model.load_state_dict(best['model_state_dict'])
    test_score = _predict_scores(best_model, x_test, infer_batch, device)
    result = {
        'dataset': dataset,
        'model_name': 'deeplog_baseline',
        'train_samples': int(len(x_train)),
        'val_samples': int(len(x_val)),
        'test_samples': int(len(x_test)),
        'train_anomaly_ratio': float(np.mean(y_train)),
        'val_anomaly_ratio': float(np.mean(y_val)) if len(y_val) else None,
        'test_anomaly_ratio': float(np.mean(y_test)),
        'split_mode': str(data.get('split_metadata', {}).get('split_mode', 'unknown')),
        'threshold_source': 'val',
        'test_used_for_selection': False,
        **_metrics(y_test, test_score, best['threshold']),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'model_path': str(model_path).replace('\\', '/'),
        'vocab_size': int(best['vocab_size']),
    }

    out_dir = Path(config.get('paths.outputs.reports'))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = out_dir / f'deeplog_eval_{dataset}_{ts}.csv'
    json_path = out_dir / f'deeplog_eval_{dataset}_{ts}.json'
    pd.DataFrame([result]).to_csv(csv_path, index=False, encoding='utf-8-sig')
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    print('=' * 70)
    print('DeepLog 基线训练与评估完成')
    print(f'模型: {model_path}')
    print(f'CSV: {csv_path}')
    print(f'JSON: {json_path}')
    print('=' * 70)


if __name__ == '__main__':
    main()
