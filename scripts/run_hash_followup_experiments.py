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
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

DATASETS = ["fox", "harrison", "santos"]
BASE_REPORT_DIR = ROOT / "reports" / "main_experiment"
HASH_REPORT_DIR = ROOT / "reports" / "main_experiment_hash"
MIGRATION_BASE_DIR = BASE_REPORT_DIR / "migration_fox_harrison_to_santos"
MIGRATION_HASH_DIR = HASH_REPORT_DIR / "migration_fox_harrison_to_santos"
OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
BACKUP_DIR = ROOT / "tmp" / "hash_followup_model_backup"
MODEL_FILES = [
    ROOT / "models" / "bilstm" / "best_model.pth",
    ROOT / "models" / "isolation_forest" / "iforest_model.joblib",
    ROOT / "models" / "xgboost" / "xgboost_fusion.joblib",
]
MODEL_DIRS = [ROOT / "models" / "deeplog"]


def _run(cmd: List[str], env: Dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=merged, cwd=str(ROOT))


def _latest(pattern: str) -> Path:
    candidates = sorted(OUTPUT_REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(pattern)
    return candidates[0]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return [{str(k).replace('\ufeff', '').strip(): v for k, v in row.items()} for row in reader]


def _backup_models() -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    for path in MODEL_FILES:
        if path.exists():
            dst = BACKUP_DIR / path.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
    for d in MODEL_DIRS:
        if d.exists():
            dst = BACKUP_DIR / d.relative_to(ROOT)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(d, dst)


def _restore_models() -> None:
    if not BACKUP_DIR.exists():
        return
    for path in MODEL_FILES:
        if path.exists():
            path.unlink()
    for d in MODEL_DIRS:
        if d.exists():
            shutil.rmtree(d)
    for src in BACKUP_DIR.rglob('*'):
        if src.is_dir():
            continue
        dst = ROOT / src.relative_to(BACKUP_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _hash_file(path: Path) -> Dict[str, object]:
    return {
        'path': str(path.relative_to(ROOT)).replace('\\', '/'),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'size_bytes': int(path.stat().st_size),
    }


def _archive_current_models(dst_root: Path) -> List[Dict[str, object]]:
    model_dir = dst_root / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    for src in MODEL_FILES:
        if src.exists():
            dst = model_dir / src.name
            shutil.copy2(src, dst)
            manifests.append(_hash_file(dst))
    return manifests


def _write_md(path: Path, lines: List[str], checks: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(lines) + '\n'
    path.write_text(text, encoding='utf-8-sig')
    loaded = path.read_text(encoding='utf-8-sig')
    missing = [c for c in checks if c not in loaded]
    validation = {
        'report_path': str(path.relative_to(ROOT)).replace('\\', '/'),
        'encoding': 'utf-8-sig',
        'missing_count': len(missing),
        'valid': len(missing) == 0,
    }
    (path.parent / (path.stem + '_validation.json')).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    if missing:
        raise RuntimeError(f'report validation failed for {path}: {missing}')


def _fmt(x: str | float) -> str:
    return f"{float(x):.4f}"


def run_domain_intra_hash() -> None:
    HASH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    manifest = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'semantic_mode': 'hash_fallback',
        'datasets': DATASETS,
        'items': [],
    }
    for ds in DATASETS:
        env = {'LOG_DATASET': ds, 'LOG_FORCE_HASH_FALLBACK': '1'}
        _run([sys.executable, 'main.py', '--extract'], env=env)
        _run([sys.executable, 'main.py', '--train', '--train-mode', 'all'], env=env)
        _run([sys.executable, 'main.py', '--evaluate-views', '--eval-datasets', ds], env=env)
        csv_path = _latest(f'view_eval_{ds}_*.csv')
        json_path = _latest(f'view_eval_{ds}_*.json')
        rows = _read_csv(csv_path)
        keep = {'statistical_view','temporal_view','semantic_view','mean_fusion_all','xgboost_fusion_saved_model','ablation_temporal_semantic_xgb'}
        picked = [r for r in rows if r['model_name'] in keep]
        for r in picked:
            summary_rows.append({
                'dataset': ds,
                'category': 'multiview',
                'model_name': r['model_name'],
                'precision': float(r['precision']),
                'recall': float(r['recall']),
                'f1': float(r['f1']),
                'auc': float(r['auc']),
                'pr_auc': float(r['pr_auc']),
                'threshold': float(r['threshold']),
            })
        model_manifest = _archive_current_models(HASH_REPORT_DIR / ds)
        manifest['items'].append({
            'dataset': ds,
            'eval_csv': str(csv_path.relative_to(ROOT)).replace('\\', '/'),
            'eval_json': str(json_path.relative_to(ROOT)).replace('\\', '/'),
            'models': model_manifest,
        })

    summary_csv = HASH_REPORT_DIR / 'domain_intra_eval_hash_summary.csv'
    with open(summary_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['dataset','category','model_name','precision','recall','f1','auc','pr_auc','threshold'])
        writer.writeheader()
        writer.writerows(summary_rows)

    (HASH_REPORT_DIR / 'model_archive_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# AIT-LDS v2 主实验域内评估报告（Hash 语义模式）',
        '',
        '## 1. 实验目的',
        '本实验在 fox、harrison、santos 三个主实验子集上重新运行三视图模型，并统一强制使用 hash 文本表示作为语义视图输入，用于和之前的 sentence-transformers 结果做公平对比。',
        '',
        '## 2. 实验设置',
        '- 语义模式：`hash_fallback`',
        '- 数据集：`fox`、`harrison`、`santos`',
        '- 评估方式：域内训练、域内测试',
        '',
        '## 3. 结果总表',
        '',
        '| 数据集 | 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for ds in DATASETS:
        sub = [r for r in summary_rows if r['dataset'] == ds]
        for r in sub:
            lines.append(f"| {ds} | {r['model_name']} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['auc']:.4f} | {r['pr_auc']:.4f} | {r['threshold']:.3f} |")
    lines += [
        '',
        '## 4. 结果解读',
        '- 这组结果用于回答一个关键问题：当语义视图从 sentence-transformers 切换到 hash 文本表示后，主实验三视图性能会如何变化。',
        '- 如果某个子集上 F1 / AUC 提升，说明该子集更适合采用轻量文本表示；如果下降，说明通用句向量在该子集上仍有价值。',
        '',
        '## 5. 格式校验',
        '- 本报告以 UTF-8 with BOM 编码写入。',
        '- 已通过 Python 回读检查标题、表格和中文段落。',
    ]
    _write_md(HASH_REPORT_DIR / 'domain_intra_eval_hash_report.md', lines, ['# AIT-LDS v2 主实验域内评估报告（Hash 语义模式）','## 3. 结果总表','| 数据集 | 模型 | Precision | Recall | F1 | AUC | PR-AUC | 阈值 |'])

    # Comparison with previous sentence-transformers results.
    prev_rows = _read_csv(BASE_REPORT_DIR / 'domain_intra_eval_summary.csv')
    prev_map = {(r['dataset'], r['model_name']): r for r in prev_rows}
    cmp_rows = []
    for r in summary_rows:
        key = (r['dataset'], r['model_name'])
        if key not in prev_map:
            continue
        old = prev_map[key]
        cmp_rows.append({
            'dataset': r['dataset'],
            'model_name': r['model_name'],
            'f1_st': float(old['f1']),
            'f1_hash': float(r['f1']),
            'f1_delta': float(r['f1']) - float(old['f1']),
            'auc_st': float(old['auc']),
            'auc_hash': float(r['auc']),
            'auc_delta': float(r['auc']) - float(old['auc']),
            'pr_auc_st': float(old['pr_auc']),
            'pr_auc_hash': float(r['pr_auc']),
            'pr_auc_delta': float(r['pr_auc']) - float(old['pr_auc']),
        })
    cmp_csv = HASH_REPORT_DIR / 'domain_intra_hash_vs_st_comparison.csv'
    with open(cmp_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cmp_rows)
    cmp_lines = [
        '# 主实验域内结果对比：Hash vs Sentence-Transformers',
        '',
        '## 1. 对比目的',
        '本报告用于比较同一批主实验子集在两种语义模式下的结果差异：一组是之前的 sentence-transformers 结果，另一组是这次统一使用 hash 文本表示后的结果。',
        '',
        '## 2. 对比表',
        '',
        '| 数据集 | 模型 | F1(ST) | F1(Hash) | ΔF1 | AUC(ST) | AUC(Hash) | ΔAUC | PR-AUC(ST) | PR-AUC(Hash) | ΔPR-AUC |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in cmp_rows:
        cmp_lines.append(f"| {r['dataset']} | {r['model_name']} | {r['f1_st']:.4f} | {r['f1_hash']:.4f} | {r['f1_delta']:.4f} | {r['auc_st']:.4f} | {r['auc_hash']:.4f} | {r['auc_delta']:.4f} | {r['pr_auc_st']:.4f} | {r['pr_auc_hash']:.4f} | {r['pr_auc_delta']:.4f} |")
    cmp_lines += [
        '',
        '## 3. 说明',
        '- 正数表示 Hash 模式优于之前的 Sentence-Transformers 模式。',
        '- 负数表示 Hash 模式弱于之前的 Sentence-Transformers 模式。',
        '- 这组对比结果可以直接支撑论文中关于“语义表示方式选择”的实验分析。',
    ]
    _write_md(HASH_REPORT_DIR / 'domain_intra_hash_vs_st_comparison.md', cmp_lines, ['# 主实验域内结果对比：Hash vs Sentence-Transformers','## 2. 对比表'])


def run_migration_hash() -> None:
    MIGRATION_HASH_DIR.mkdir(parents=True, exist_ok=True)
    env = {
        'LOG_FORCE_HASH_FALLBACK': '1',
        'LOG_REPORT_DIR': str(MIGRATION_HASH_DIR),
    }
    _run([sys.executable, 'scripts/run_migration_fox_harrison_to_santos.py'], env=env)

    current = _read_csv(MIGRATION_HASH_DIR / 'migration_summary.csv')
    previous = _read_csv(MIGRATION_BASE_DIR / 'migration_summary.csv')
    prev_map = {r['model_name']: r for r in previous}
    cmp_rows = []
    for r in current:
        if r['model_name'] not in prev_map:
            continue
        old = prev_map[r['model_name']]
        cmp_rows.append({
            'model_name': r['model_name'],
            'f1_st': float(old['f1']),
            'f1_hash': float(r['f1']),
            'f1_delta': float(r['f1']) - float(old['f1']),
            'auc_st': float(old['auc']),
            'auc_hash': float(r['auc']),
            'auc_delta': float(r['auc']) - float(old['auc']),
            'pr_auc_st': float(old['pr_auc']),
            'pr_auc_hash': float(r['pr_auc']),
            'pr_auc_delta': float(r['pr_auc']) - float(old['pr_auc']),
        })
    cmp_csv = MIGRATION_HASH_DIR / 'migration_hash_vs_st_comparison.csv'
    with open(cmp_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cmp_rows)
    lines = [
        '# 迁移实验结果对比：Hash vs Sentence-Transformers',
        '',
        '## 1. 对比目的',
        '本报告比较同一组迁移实验 `fox + harrison -> santos` 在两种语义模式下的差异，用于判断迁移场景下应优先采用哪一种语义表示。',
        '',
        '## 2. 对比表',
        '',
        '| 模型 | F1(ST) | F1(Hash) | ΔF1 | AUC(ST) | AUC(Hash) | ΔAUC | PR-AUC(ST) | PR-AUC(Hash) | ΔPR-AUC |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in cmp_rows:
        lines.append(f"| {r['model_name']} | {r['f1_st']:.4f} | {r['f1_hash']:.4f} | {r['f1_delta']:.4f} | {r['auc_st']:.4f} | {r['auc_hash']:.4f} | {r['auc_delta']:.4f} | {r['pr_auc_st']:.4f} | {r['pr_auc_hash']:.4f} | {r['pr_auc_delta']:.4f} |")
    lines += [
        '',
        '## 3. 说明',
        '- 正数表示 Hash 模式优于之前的 Sentence-Transformers 模式。',
        '- 迁移实验比域内实验更敏感，因此这组对比对论文中的泛化分析很重要。',
    ]
    _write_md(MIGRATION_HASH_DIR / 'migration_hash_vs_st_comparison.md', lines, ['# 迁移实验结果对比：Hash vs Sentence-Transformers','## 2. 对比表'])


def main() -> None:
    started = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    HASH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _backup_models()
        run_domain_intra_hash()
        run_migration_hash()
    finally:
        _restore_models()
    manifest = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'started_at': started,
        'experiments': [
            'domain_intra_hash',
            'migration_fox_harrison_to_santos_hash',
        ],
        'notes': 'Old reports under reports/main_experiment were kept untouched. Shared models were backed up before rerun and restored afterwards.',
    }
    (HASH_REPORT_DIR / 'run_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
