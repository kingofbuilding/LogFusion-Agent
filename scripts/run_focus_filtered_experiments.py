from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASETS = ["fox", "harrison", "santos"]
PROFILE = "web_linux_auth_focus"
REPORT_DIR = ROOT / "reports" / "main_experiment_focus"
MIGRATION_DIR = REPORT_DIR / "migration_fox_harrison_to_santos"
RAG_DIR = REPORT_DIR / "rag"
OUTPUT_REPORT_DIR = ROOT / "outputs" / "reports"
BACKUP_DIR = ROOT / "tmp" / "focus_filtered_model_backup"
MODEL_FILES = [
    ROOT / "models" / "bilstm" / "best_model.pth",
    ROOT / "models" / "isolation_forest" / "iforest_model.joblib",
    ROOT / "models" / "xgboost" / "xgboost_fusion.joblib",
]


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


def _restore_models() -> None:
    if not BACKUP_DIR.exists():
        return
    for path in MODEL_FILES:
        if path.exists():
            path.unlink()
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


def _load_profile() -> Dict[str, List[str]]:
    import yaml
    cfg = yaml.safe_load((ROOT / 'configs' / 'config.yaml').read_text(encoding='utf-8'))
    profile = cfg['data']['source_filter_profiles'][PROFILE]
    return {
        'include_patterns': [str(x) for x in profile.get('include_patterns', [])],
        'exclude_patterns': [str(x) for x in profile.get('exclude_patterns', [])],
    }


def _load_labels(ds: str) -> pd.DataFrame:
    rows = []
    labels_root = ROOT / 'data' / 'raw' / ds / 'labels'
    for label_file in sorted(labels_root.rglob('*.log')):
        source_file = str(Path('gather') / label_file.relative_to(labels_root)).replace('\\', '/')
        with open(label_file, 'r', encoding='utf-8', errors='ignore') as f:
            for raw in f:
                raw = str(raw).strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                line_num = obj.get('line')
                if line_num is None:
                    continue
                rows.append({
                    'source_file': source_file,
                    'source_line_num': int(line_num),
                    'label': 1 if len(obj.get('labels') or []) else 0,
                })
    return pd.DataFrame(rows)


def _apply_filter(df: pd.DataFrame, profile: Dict[str, List[str]]) -> pd.DataFrame:
    src = df['source_file'].astype(str)
    include = pd.Series(False, index=df.index)
    for pat in profile['include_patterns']:
        include = include | src.str.contains(pat, regex=True, na=False)
    exclude = pd.Series(False, index=df.index)
    for pat in profile['exclude_patterns']:
        exclude = exclude | src.str.contains(pat, regex=True, na=False)
    return df[include & ~exclude].copy()


def build_filter_summary() -> List[Dict[str, object]]:
    profile = _load_profile()
    rows = []
    source_rows = []
    for ds in DATASETS:
        parsed = pd.read_csv(ROOT / 'data' / 'processed' / ds / f'{ds}_parsed.csv', usecols=['source_file', 'source_line_num'])
        labels = _load_labels(ds)
        merged = parsed.merge(labels, on=['source_file', 'source_line_num'], how='left')
        merged['label'] = merged['label'].fillna(0).astype(int)
        filtered = _apply_filter(merged, profile)
        rows.append({
            'dataset': ds,
            'rows_before': int(len(merged)),
            'rows_after': int(len(filtered)),
            'keep_ratio': float(len(filtered) / len(merged)) if len(merged) else 0.0,
            'positive_before': int(merged['label'].sum()),
            'positive_after': int(filtered['label'].sum()),
            'sources_before': int(merged['source_file'].nunique()),
            'sources_after': int(filtered['source_file'].nunique()),
        })
        grouped = filtered.groupby('source_file')['label'].agg(['count', 'sum']).reset_index()
        for _, row in grouped.iterrows():
            source_rows.append({
                'dataset': ds,
                'source_file': str(row['source_file']),
                'row_count': int(row['count']),
                'positive_count': int(row['sum']),
            })
    with open(REPORT_DIR / 'filter_summary.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(REPORT_DIR / 'filter_source_breakdown.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(source_rows[0].keys()))
        writer.writeheader()
        writer.writerows(source_rows)
    return rows


def run_domain_intra() -> List[Dict[str, object]]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    manifest = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source_filter_profile': PROFILE,
        'semantic_mode': 'hash_fallback',
        'datasets': DATASETS,
        'items': [],
    }
    keep = {
        'statistical_view',
        'temporal_view',
        'semantic_view',
        'mean_fusion_all',
        'xgboost_fusion_saved_model',
        'ablation_temporal_semantic_xgb',
    }
    for ds in DATASETS:
        env = {
            'LOG_DATASET': ds,
            'LOG_FORCE_HASH_FALLBACK': '1',
            'LOG_SOURCE_FILTER_PROFILE': PROFILE,
        }
        _run([sys.executable, 'main.py', '--extract'], env=env)
        _run([sys.executable, 'main.py', '--train', '--train-mode', 'all'], env=env)
        _run([sys.executable, 'main.py', '--evaluate-views', '--eval-datasets', ds], env=env)
        csv_path = _latest(f'view_eval_{ds}_*.csv')
        json_path = _latest(f'view_eval_{ds}_*.json')
        rows = _read_csv(csv_path)
        picked = [r for r in rows if r['model_name'] in keep]
        for r in picked:
            summary_rows.append({
                'dataset': ds,
                'model_name': r['model_name'],
                'precision': float(r['precision']),
                'recall': float(r['recall']),
                'f1': float(r['f1']),
                'auc': float(r['auc']),
                'pr_auc': float(r['pr_auc']),
                'threshold': float(r['threshold']),
            })
        models = _archive_current_models(REPORT_DIR / ds)
        manifest['items'].append({
            'dataset': ds,
            'eval_csv': str(csv_path.relative_to(ROOT)).replace('\\', '/'),
            'eval_json': str(json_path.relative_to(ROOT)).replace('\\', '/'),
            'models': models,
        })
    with open(REPORT_DIR / 'domain_intra_eval_focus_summary.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    (REPORT_DIR / 'model_archive_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary_rows


def build_domain_comparison(current_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    prev_rows = _read_csv(ROOT / 'reports' / 'main_experiment_hash' / 'domain_intra_eval_hash_summary.csv')
    prev_map = {(r['dataset'], r['model_name']): r for r in prev_rows}
    cmp_rows = []
    for r in current_rows:
        key = (r['dataset'], r['model_name'])
        old = prev_map.get(key)
        if not old:
            continue
        cmp_rows.append({
            'dataset': r['dataset'],
            'model_name': r['model_name'],
            'f1_unfiltered': float(old['f1']),
            'f1_filtered': float(r['f1']),
            'f1_delta': float(r['f1']) - float(old['f1']),
            'auc_unfiltered': float(old['auc']),
            'auc_filtered': float(r['auc']),
            'auc_delta': float(r['auc']) - float(old['auc']),
            'pr_auc_unfiltered': float(old['pr_auc']),
            'pr_auc_filtered': float(r['pr_auc']),
            'pr_auc_delta': float(r['pr_auc']) - float(old['pr_auc']),
        })
    with open(REPORT_DIR / 'domain_intra_focus_vs_unfiltered_hash.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cmp_rows)
    return cmp_rows


def run_migration() -> Dict[str, object]:
    env = {
        'LOG_FORCE_HASH_FALLBACK': '1',
        'LOG_SOURCE_FILTER_PROFILE': PROFILE,
        'LOG_REPORT_DIR': str(MIGRATION_DIR),
    }
    _run([sys.executable, 'scripts/run_migration_fox_harrison_to_santos.py'], env=env)
    rows = _read_csv(MIGRATION_DIR / 'migration_summary.csv')
    best = max(rows, key=lambda r: float(r['f1']))
    prev_rows = _read_csv(ROOT / 'reports' / 'main_experiment_hash' / 'migration_fox_harrison_to_santos' / 'migration_summary.csv')
    prev_map = {r['model_name']: r for r in prev_rows}
    cmp_rows = []
    for r in rows:
        old = prev_map.get(r['model_name'])
        if not old:
            continue
        cmp_rows.append({
            'model_name': r['model_name'],
            'f1_unfiltered': float(old['f1']),
            'f1_filtered': float(r['f1']),
            'f1_delta': float(r['f1']) - float(old['f1']),
            'auc_unfiltered': float(old['auc']),
            'auc_filtered': float(r['auc']),
            'auc_delta': float(r['auc']) - float(old['auc']),
            'pr_auc_unfiltered': float(old['pr_auc']),
            'pr_auc_filtered': float(r['pr_auc']),
            'pr_auc_delta': float(r['pr_auc']) - float(old['pr_auc']),
        })
    with open(MIGRATION_DIR / 'migration_focus_vs_unfiltered_hash.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cmp_rows)
    return {
        'rows': rows,
        'best': best,
        'comparison_rows': cmp_rows,
    }


def rebuild_rag() -> Dict[str, object]:
    case_file = RAG_DIR / 'attack_cases_focus.jsonl'
    index_file = RAG_DIR / 'rag_attack_cases_focus.npz'
    if case_file.exists():
        case_file.unlink()
    if index_file.exists():
        index_file.unlink()
    for ds in DATASETS:
        env = {
            'LOG_DATASET': ds,
            'LOG_SOURCE_FILTER_PROFILE': PROFILE,
            'LOG_FORCE_HASH_FALLBACK': '1',
            'LOG_RAG_CASE_FILE': str(case_file),
            'LOG_RAG_INDEX_FILE': str(index_file),
        }
        _run([sys.executable, 'main.py', '--build-rag', '--rag-force'], env=env)
    from src.utils import Config
    from src.rag.attack_case_base import AttackCaseRAG
    old_env = {k: os.environ.get(k) for k in ['LOG_DATASET', 'LOG_SOURCE_FILTER_PROFILE', 'LOG_FORCE_HASH_FALLBACK', 'LOG_RAG_CASE_FILE', 'LOG_RAG_INDEX_FILE']}
    try:
        os.environ['LOG_DATASET'] = DATASETS[-1]
        os.environ['LOG_SOURCE_FILTER_PROFILE'] = PROFILE
        os.environ['LOG_FORCE_HASH_FALLBACK'] = '1'
        os.environ['LOG_RAG_CASE_FILE'] = str(case_file)
        os.environ['LOG_RAG_INDEX_FILE'] = str(index_file)
        rag = AttackCaseRAG(Config())
        cases = rag.load_cases()
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    group_counts = Counter(str(c.get('case_group', 'unknown')) for c in cases)
    auto_cases = [c for c in cases if str(c.get('case_id', '')).startswith('AUTO-')]
    summary = {
        'case_file': str(case_file.relative_to(ROOT)).replace('\\', '/'),
        'index_file': str(index_file.relative_to(ROOT)).replace('\\', '/'),
        'total_cases': len(cases),
        'auto_cases': len(auto_cases),
        'group_counts': dict(group_counts),
        'sample_titles': [str(c.get('title', '')) for c in cases[:12]],
    }
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    (RAG_DIR / 'rag_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def build_final_report(filter_rows, domain_rows, domain_cmp_rows, migration_info, rag_summary) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    best_by_dataset = {}
    for ds in DATASETS:
        sub = [r for r in domain_rows if r['dataset'] == ds]
        best_by_dataset[ds] = max(sub, key=lambda r: float(r['f1']))

    lines = [
        '# AIT-LDS v2 ????????',
        '',
        '## 1. ????',
        '?????????????????????????? `Apache/Web + Linux ?????? + SSH/auth/????` ????????? `fox / harrison / santos` ???????????????????????????????? RAG ????',
        '',
        '## 2. ??????????',
        f'- ?????`{PROFILE}`',
        '- ????????`/apache2/`?`/auth.log`?`/audit/audit.log`?`/openvpn.log`',
        '- ????????`attacker_0/logs/attacks.log`',
        '- ???AIT-LDS v2 ????????????? `syslog/messages` ?????? `audit.log` ? `openvpn.log` ????? Linux ??????????????????',
        '',
        '## 3. ???????',
        '',
        '| ??? | ????? | ????? | ???? | ?????? | ?????? | ????? | ????? |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in filter_rows:
        lines.append(f"| {r['dataset']} | {r['rows_before']} | {r['rows_after']} | {r['keep_ratio']:.4f} | {r['positive_before']} | {r['positive_after']} | {r['sources_before']} | {r['sources_after']} |")
    lines += [
        '',
        '## 4. ??????????? + Hash ???',
        '',
        '| ??? | ???? | Precision | Recall | F1 | AUC | PR-AUC | ?? |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for ds in DATASETS:
        r = best_by_dataset[ds]
        lines.append(f"| {ds} | {r['model_name']} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['auc']:.4f} | {r['pr_auc']:.4f} | {r['threshold']:.3f} |")
    lines += [
        '',
        '## 5. ?????????? + Hash ???????',
        '',
        '| ??? | ?? | F1(???) | F1(???) | ?F1 | AUC(???) | AUC(???) | ?AUC |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for r in domain_cmp_rows:
        if r['model_name'] not in {'xgboost_fusion_saved_model', 'ablation_temporal_semantic_xgb'}:
            continue
        lines.append(f"| {r['dataset']} | {r['model_name']} | {r['f1_unfiltered']:.4f} | {r['f1_filtered']:.4f} | {r['f1_delta']:.4f} | {r['auc_unfiltered']:.4f} | {r['auc_filtered']:.4f} | {r['auc_delta']:.4f} |")
    lines += [
        '',
        '## 6. ???????fox + harrison ?? -> santos ???',
        '',
        '| ???? | Precision | Recall | F1 | AUC | PR-AUC | ?? |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    best_m = migration_info['best']
    lines.append(f"| {best_m['model_name']} | {float(best_m['precision']):.4f} | {float(best_m['recall']):.4f} | {float(best_m['f1']):.4f} | {float(best_m['auc']):.4f} | {float(best_m['pr_auc']):.4f} | {float(best_m['threshold']):.3f} |")
    lines += [
        '',
        '| ?? | F1(???) | F1(???) | ?F1 | AUC(???) | AUC(???) | ?AUC |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for r in migration_info['comparison_rows']:
        if r['model_name'] not in {'xgboost_fusion_saved_model', 'ablation_temporal_semantic_xgb', 'DeepLog'}:
            continue
        lines.append(f"| {r['model_name']} | {r['f1_unfiltered']:.4f} | {r['f1_filtered']:.4f} | {r['f1_delta']:.4f} | {r['auc_unfiltered']:.4f} | {r['auc_filtered']:.4f} | {r['auc_delta']:.4f} |")
    lines += [
        '',
        '## 7. RAG ???????',
        f"- ??????`{rag_summary['case_file']}`",
        f"- ???????`{rag_summary['index_file']}`",
        f"- ?????`{rag_summary['total_cases']}`",
        f"- ????????`{rag_summary['auto_cases']}`",
        f"- ??????`{json.dumps(rag_summary['group_counts'], ensure_ascii=False)}`",
        '',
        '???????',
    ]
    for title in rag_summary['sample_titles'][:10]:
        lines.append(f'- {title}')
    lines += [
        '',
        '## 8. ??',
        '- ????????????????????????????????? Web / Linux ???? / SSH-auth ??????',
        '- ??????`santos` ?????? Web ??????????????`fox` ? `harrison` ???? Linux ???????????????',
        '- ????????????????????????????????? dnsmasq ??????????',
        '- ????? RAG ????????????????????????????????????????',
        '',
        '## 9. ????',
        f'- ?????`{(REPORT_DIR / "filter_summary.csv").relative_to(ROOT).as_posix()}`',
        f'- ?????`{(REPORT_DIR / "domain_intra_eval_focus_summary.csv").relative_to(ROOT).as_posix()}`',
        f'- ?????`{(REPORT_DIR / "domain_intra_focus_vs_unfiltered_hash.csv").relative_to(ROOT).as_posix()}`',
        f'- ?????`{(MIGRATION_DIR / "migration_summary.csv").relative_to(ROOT).as_posix()}`',
        f'- ?????`{(MIGRATION_DIR / "migration_focus_vs_unfiltered_hash.csv").relative_to(ROOT).as_posix()}`',
        f'- RAG ???`{(RAG_DIR / "rag_summary.json").relative_to(ROOT).as_posix()}`',
    ]
    _write_md(REPORT_DIR / 'focus_filtered_experiment_report.md', lines, ['# AIT-LDS v2 ????????', '## 3. ???????', '## 7. RAG ???????'])


if __name__ == '__main__':
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _backup_models()
    try:
        filter_rows = build_filter_summary()
        domain_rows = run_domain_intra()
        domain_cmp_rows = build_domain_comparison(domain_rows)
        migration_info = run_migration()
        rag_summary = rebuild_rag()
        build_final_report(filter_rows, domain_rows, domain_cmp_rows, migration_info, rag_summary)
        print('focus filtered experiments completed')
    finally:
        _restore_models()
