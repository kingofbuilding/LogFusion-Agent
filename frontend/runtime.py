from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import streamlit as st

from frontend.helpers import (
    build_sequence_timestamps,
    build_sequences,
    compact_log_preview,
    interpret_template_security,
    localize_advice,
    localize_attack_type,
    localize_case_group,
    localize_text,
    make_template_readable,
    pick_log_text_from_df,
    rag_hit_to_security_category,
    risk_level,
)
from src.fusion.ensemble import EnsemblePredictor
from src.fusion.log_domain import detect_log_domains
from src.fusion.semantic_text import build_sequence_raw_texts_from_logs, build_sequence_semantic_texts_from_logs
from src.fusion.three_view_service import ThreeViewScoringService
from src.rag.ai_judge import AIJudge
from src.rag.attack_case_base import AttackCaseRAG
from src.utils import Config


def _mask_secret(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if len(text) <= 8:
        return '*' * len(text)
    return f"{text[:4]}{'*' * max(4, len(text) - 8)}{text[-4:]}"


def _to_bool_series(series: pd.Series, default: bool = False) -> pd.Series:
    def _coerce(value: object) -> bool:
        if pd.isna(value):
            return default
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "y", "高", "可用"}:
                return True
            if text in {"false", "0", "no", "n", "", "none", "nan", "不可用"}:
                return False
        return bool(value)

    return series.map(_coerce).astype(bool)


def resolve_ai_judge_config(config_dict: dict, llm_cfg: Dict[str, str] | None = None) -> Dict[str, object]:
    llm_cfg = dict(llm_cfg or {})
    root = dict(config_dict or {})
    ai_cfg = dict(root.get('ai_judge', {}) or {})
    profiles = dict(ai_cfg.get('profiles', {}) or {})
    default_profile = str(ai_cfg.get('default_profile', '') or '').strip()
    if not default_profile:
        default_profile = 'default'

    if default_profile not in profiles:
        profiles[default_profile] = {
            'provider': str(ai_cfg.get('provider', 'deepseek') or 'deepseek'),
            'model': str(ai_cfg.get('model', root.get('rag', {}).get('llm', {}).get('model', 'deepseek-chat')) or 'deepseek-chat'),
            'base_url': str(ai_cfg.get('base_url', '') or ''),
            'api_key': str(ai_cfg.get('api_key', '') or ''),
            'temperature': float(ai_cfg.get('temperature', 0.2) or 0.2),
            'max_tokens': int(ai_cfg.get('max_tokens', 300) or 300),
            'request_timeout': float(ai_cfg.get('request_timeout', 45) or 45),
        }

    selected_profile_name = str(llm_cfg.get('profile', default_profile) or default_profile).strip() or default_profile
    profile_payload = dict(profiles.get(selected_profile_name, profiles.get(default_profile, {})) or {})
    use_override = bool(llm_cfg.get('override', False))
    provider = str((llm_cfg.get('provider') if use_override else None) or profile_payload.get('provider', ai_cfg.get('provider', 'deepseek')) or 'deepseek').strip()
    model = str((llm_cfg.get('model') if use_override else None) or profile_payload.get('model', ai_cfg.get('model', root.get('rag', {}).get('llm', {}).get('model', 'deepseek-chat'))) or '').strip()
    base_url = str((llm_cfg.get('base_url') if use_override else None) or profile_payload.get('base_url', ai_cfg.get('base_url', '')) or '').strip()
    api_key = str((llm_cfg.get('api_key') if use_override else None) or profile_payload.get('api_key', ai_cfg.get('api_key', '')) or '').strip()

    merged = dict(ai_cfg)
    merged['provider'] = provider
    merged['default_profile'] = default_profile
    merged['profiles'] = profiles
    merged['active_profile'] = selected_profile_name
    merged['use_llm'] = bool(llm_cfg.get('use_llm', ai_cfg.get('use_llm', False)))
    merged['model'] = model
    merged['base_url'] = base_url
    merged['api_key'] = api_key
    merged['temperature'] = float(profile_payload.get('temperature', ai_cfg.get('temperature', 0.2)) or 0.2)
    merged['max_tokens'] = int(profile_payload.get('max_tokens', ai_cfg.get('max_tokens', 300)) or 300)
    merged['qa_max_tokens'] = int(profile_payload.get('qa_max_tokens', ai_cfg.get('qa_max_tokens', max(merged['max_tokens'], 3000))) or max(merged['max_tokens'], 3000))
    merged['report_max_tokens'] = int(profile_payload.get('report_max_tokens', ai_cfg.get('report_max_tokens', max(merged['max_tokens'], 8000))) or max(merged['max_tokens'], 8000))
    merged['request_timeout'] = float(profile_payload.get('request_timeout', ai_cfg.get('request_timeout', 45)) or 45)
    return merged


def build_ai_judge_admin_snapshot(config_dict: dict, llm_cfg: Dict[str, str] | None = None) -> Dict[str, object]:
    resolved = resolve_ai_judge_config(config_dict, llm_cfg)
    return {
        'provider': str(resolved.get('provider', '')),
        'default_profile': str(resolved.get('default_profile', '')),
        'active_profile': str(resolved.get('active_profile', '')),
        'use_llm': bool(resolved.get('use_llm', False)),
        'model': str(resolved.get('model', '')),
        'base_url': str(resolved.get('base_url', '')),
        'api_key_masked': _mask_secret(str(resolved.get('api_key', ''))),
        'temperature': float(resolved.get('temperature', 0.2) or 0.2),
        'max_tokens': int(resolved.get('max_tokens', 300) or 300),
        'qa_max_tokens': int(resolved.get('qa_max_tokens', 3000) or 3000),
        'report_max_tokens': int(resolved.get('report_max_tokens', 8000) or 8000),
        'request_timeout': float(resolved.get('request_timeout', 45) or 45),
        'profile_names': list(dict(resolved.get('profiles', {}) or {}).keys()),
    }


@st.cache_resource(show_spinner=False)
def load_runtime(config_dict: dict):
    cfg = Config()
    cfg.config = config_dict
    scorer = ThreeViewScoringService(cfg)
    rag = AttackCaseRAG(cfg)
    try:
        rag.load_index_if_exists()
    except Exception:
        pass
    fusion = None
    try:
        fusion = EnsemblePredictor(cfg)
    except Exception:
        fusion = None
    return scorer, fusion, rag


@st.cache_resource(show_spinner=False)
def load_ai_judge(config_dict: dict, llm_cfg: Dict[str, str]):
    cfg = Config()
    cfg.config = dict(config_dict or {})
    cfg.config['ai_judge'] = resolve_ai_judge_config(cfg.config, llm_cfg)
    return AIJudge(cfg)


def _rag_cache_signature(config: Config) -> str:
    cache_version = "rag-v6-zh-localize"
    index_path = Path(config.get("rag.case_base.index_file", "data/vectors/rag_attack_cases.npz"))
    case_path = Path(config.get("rag.case_base.file", "data/rag/attack_cases.jsonl"))
    try:
        index_mtime = float(index_path.stat().st_mtime) if index_path.exists() else 0.0
    except Exception:
        index_mtime = 0.0
    try:
        case_mtime = float(case_path.stat().st_mtime) if case_path.exists() else 0.0
    except Exception:
        case_mtime = 0.0
    try:
        resolved_index = str(index_path.resolve())
    except Exception:
        resolved_index = str(index_path)
    try:
        resolved_case = str(case_path.resolve())
    except Exception:
        resolved_case = str(case_path)
    return f"{cache_version}|{resolved_index}|{index_mtime}|{resolved_case}|{case_mtime}"


def _get_rag_top1_cache(config: Config) -> Dict[str, Dict]:
    try:
        bucket = st.session_state.setdefault("_rag_top1_cache_bucket", {})
    except Exception:
        return {}

    sig = _rag_cache_signature(config)
    if bucket.get("_sig") != sig:
        bucket.clear()
        bucket["_sig"] = sig
        bucket["items"] = {}
    if "items" not in bucket or not isinstance(bucket["items"], dict):
        bucket["items"] = {}
    return bucket["items"]


def _select_rag_query_key(template_text: str, raw_log_text: str) -> str:
    raw = str(raw_log_text or '').strip()
    template = str(template_text or '').strip()
    if not raw:
        return template
    q = raw.lower()
    security_markers = [
        'sshd', 'accepted password', 'accepted publickey', 'failed password', 'user unknown',
        'session opened for user', 'pam_unix(sshd:session)', 'prompt injection', 'security_alert',
        'ai-agent', 'wpscan', 'ah01630', 'ah00687', 'audit(', 'type=execve', 'sudo', 'openvpn',
        'peer connection initiated', 'tls error', 'union select', '<script', 'multipart/form-data',
    ]
    if any(marker in q for marker in security_markers):
        return raw
    return template or raw


def _get_rag_panel_cache(config: Config) -> Dict[str, pd.DataFrame]:
    try:
        bucket = st.session_state.setdefault("_rag_panel_cache_bucket", {})
    except Exception:
        return {}
    sig = _rag_cache_signature(config)
    if bucket.get("_sig") != sig:
        bucket.clear()
        bucket["_sig"] = sig
        bucket["items"] = {}
    if "items" not in bucket or not isinstance(bucket["items"], dict):
        bucket["items"] = {}
    return bucket["items"]


def run_pipeline(config: Config, src_df: pd.DataFrame, seq_len: int, threshold: float):
    work = src_df.copy()
    raw_log_values = pick_log_text_from_df(work)
    if isinstance(raw_log_values, pd.Series):
        raw_log_series = raw_log_values.reset_index(drop=True).astype(str)
    else:
        raw_log_values = list(raw_log_values or [])
        if len(raw_log_values) == len(work):
            raw_log_series = pd.Series(raw_log_values, dtype="string")
        else:
            fallback = work["template"].astype(str).tolist() if "template" in work.columns else [""] * len(work)
            raw_log_series = pd.Series(fallback, dtype="string")
    to_num = pd.to_numeric(work["template_id"], errors="coerce")
    if to_num.isna().any():
        codes, _ = pd.factorize(work["template"].astype(str), sort=False)
        work["template_id"] = (codes + 1).astype(int)
    else:
        work["template_id"] = to_num.astype(int)

    x_seq, ends = build_sequences(work["template_id"].values, seq_len)
    if len(x_seq) == 0:
        return pd.DataFrame(), x_seq

    scorer, fusion, _ = load_runtime(config.config)
    end_template_series = work.iloc[ends]["template"].astype(str)
    semantic_source = (
        raw_log_series.astype(str).tolist()
        if len(raw_log_series) == len(work)
        else work["template"].astype(str).tolist()
    )
    semantic_inputs = build_sequence_semantic_texts_from_logs(
        semantic_source,
        sequence_length=seq_len,
        start_indices=np.arange(len(x_seq), dtype=np.int64),
        max_steps=int(config.get("features.semantic.sequence_context_window", 6)),
        min_tokens=int(config.get("features.semantic.distillation.min_tokens", 3)),
    )
    raw_inputs = build_sequence_raw_texts_from_logs(
        semantic_source,
        sequence_length=seq_len,
        start_indices=np.arange(len(x_seq), dtype=np.int64),
        max_steps=int(config.get("features.statistical_behavior_context_window", 12)),
    )
    seq_ts = build_sequence_timestamps(work, seq_len)
    scores = scorer.score(x_seq, semantic_inputs, seq_timestamps=seq_ts, raw_seq_texts=np.asarray(raw_inputs, dtype=object))

    stat_s = scores["stat_scores"]
    temp_s = scores["temporal_scores"]
    sem_s = scores["semantic_scores"]
    domains = np.asarray(detect_log_domains(semantic_inputs), dtype=object)

    risk_s = stat_s
    fusion_tag = "iforest_only"
    if fusion is not None:
        _, risk_s = fusion.predict_meta(scores["meta_features"])
        fusion_tag = "xgboost_fusion"

    default_threshold = float(config.get("frontend.controls.default_threshold", 0.5))
    apply_domain_thresholds = bool(config.get("frontend.controls.apply_domain_thresholds", True))
    domain_thresholds = dict(config.get("frontend.controls.domain_thresholds", {}))
    auto_threshold_mode = apply_domain_thresholds and abs(float(threshold) - default_threshold) <= 1e-9
    effective_thresholds = (
        np.array([float(domain_thresholds.get(str(domain), threshold)) for domain in domains], dtype=float)
        if auto_threshold_mode
        else np.full(len(x_seq), float(threshold), dtype=float)
    )

    out = pd.DataFrame(
        {
            "seq_index": np.arange(len(x_seq)),
            "line_num": work.iloc[ends]["line_num"].values if "line_num" in work.columns else ends + 1,
            "template_id": work.iloc[ends]["template_id"].values,
            "template": end_template_series.values,
            "semantic_text": np.asarray(semantic_inputs, dtype=object),
            "log_text": raw_log_series.iloc[ends].astype(str).values if len(raw_log_series) == len(work) else "",
            "log_domain": domains,
            "recommended_threshold": effective_thresholds,
            "threshold_mode": "domain_auto" if auto_threshold_mode else "manual",
            "stat_score": stat_s,
            "temporal_score": temp_s,
            "semantic_score": sem_s,
            "stat_dist_score": scores.get("stat_dist_scores", np.zeros(len(x_seq), dtype=float)),
            "stat_auth_score": scores.get("stat_auth_scores", np.zeros(len(x_seq), dtype=float)),
            "stat_web_score": scores.get("stat_web_scores", np.zeros(len(x_seq), dtype=float)),
            "stat_dns_score": scores.get("stat_dns_scores", np.zeros(len(x_seq), dtype=float)),
            "risk_score": risk_s,
            "fusion_model": fusion_tag,
        }
    )
    out["is_alert"] = out["risk_score"] >= out["recommended_threshold"]
    return out, x_seq



def write_report(config: Config, source_name: str, result_df: pd.DataFrame):
    report_dir = Path(config.get("paths.outputs.reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{source_name}_{ts}"

    csv_path = report_dir / f"{base}_result.csv"
    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    detail_col = "细粒度主分类" if "细粒度主分类" in result_df.columns else ("安全分类" if "安全分类" in result_df.columns else None)
    risk_col = "风险层级" if "风险层级" in result_df.columns else ("风险等级" if "风险等级" in result_df.columns else None)
    advice_col = "建议处置" if "建议处置" in result_df.columns else ("处置建议" if "处置建议" in result_df.columns else None)

    alert_df = result_df[result_df["is_alert"]].copy().sort_values("risk_score", ascending=False)
    top_alerts = alert_df.head(20).copy()

    if detail_col and not alert_df.empty:
        top_categories_df = (
            alert_df[detail_col].astype(str).value_counts().head(10).rename_axis("category").reset_index(name="count")
        )
        top_categories = top_categories_df.to_dict(orient="records")
    else:
        top_categories_df = pd.DataFrame(columns=["category", "count"])
        top_categories = []

    if risk_col and not alert_df.empty:
        risk_levels_df = (
            alert_df[risk_col].astype(str).value_counts().rename_axis("level").reset_index(name="count")
        )
        risk_levels = risk_levels_df.to_dict(orient="records")
    else:
        risk_levels = []

    top_alert_cols = [c for c in ["line_num", risk_col, detail_col, "template", advice_col, "risk_score"] if c and c in top_alerts.columns]
    top_alert_records = top_alerts[top_alert_cols].to_dict(orient="records") if top_alert_cols else []

    summary = {
        "source": source_name,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sample_count": int(len(result_df)),
        "alert_count": int(result_df["is_alert"].sum()),
        "alert_ratio": float(result_df["is_alert"].mean()) if len(result_df) else 0.0,
        "risk_mean": float(result_df["risk_score"].mean()) if len(result_df) else 0.0,
        "risk_max": float(result_df["risk_score"].max()) if len(result_df) else 0.0,
        "fusion_model": str(result_df["fusion_model"].iloc[0]) if len(result_df) and "fusion_model" in result_df.columns else "none",
        "top_categories": top_categories,
        "risk_levels": risk_levels,
        "top_alerts": top_alert_records,
    }
    json_path = report_dir / f"{base}_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    top_category_name = top_categories[0]["category"] if top_categories else "暂无明显集中类别"
    top_category_count = int(top_categories[0]["count"]) if top_categories else 0
    severe_count = int((result_df[risk_col] == "严重").sum()) if risk_col and risk_col in result_df.columns else 0
    brief = (
        f"本次检测共处理 {len(result_df)} 条样本，识别告警 {int(result_df['is_alert'].sum())} 条，"
        f"最高风险分为 {float(result_df['risk_score'].max()) if len(result_df) else 0.0:.4f}。"
        f"当前最集中的类别为「{top_category_name}」，共 {top_category_count} 条；其中「严重」级别告警 {severe_count} 条。"
    )

    top_alert_export = top_alerts.copy()
    if "risk_score" in top_alert_export.columns:
        top_alert_export["risk_score"] = top_alert_export["risk_score"].map(lambda x: f"{float(x):.4f}")
    if top_alert_export.empty or not top_alert_cols:
        top_alert_md = "暂无告警明细。"
        top_alert_html = "<p>暂无告警明细。</p>"
    else:
        top_alert_md = top_alert_export[top_alert_cols].to_markdown(index=False)
        top_alert_html = top_alert_export[top_alert_cols].to_html(index=False, classes="alert-table", border=0)

    if top_categories:
        category_md_lines = [f"- {item['category']}：{int(item['count'])} 条" for item in top_categories]
        category_html_rows = ''.join([f"<tr><td>{item['category']}</td><td>{int(item['count'])}</td></tr>" for item in top_categories])
    else:
        category_md_lines = ["- 暂无类别统计。"]
        category_html_rows = "<tr><td colspan='2'>暂无类别统计</td></tr>"

    md_lines = [
        "# 批次诊断报告",
        "",
        "## 基本概况",
        f"- 数据来源：{source_name}",
        f"- 生成时间：{summary['time']}",
        f"- 样本总数：{summary['sample_count']}",
        f"- 告警数量：{summary['alert_count']}",
        f"- 告警占比：{summary['alert_ratio']:.2%}",
        f"- 平均风险分：{summary['risk_mean']:.4f}",
        f"- 最高风险分：{summary['risk_max']:.4f}",
        f"- 融合模型：{summary['fusion_model']}",
        "",
        "## AI 批量简报",
        brief,
        "",
        "## 高危类别分布 Top 10",
        *category_md_lines,
        "",
        "## 高危明细 Top 20",
        top_alert_md,
        "",
        "## 导出文件说明",
        "- `_result.csv`：本次检测的完整明细结果。",
        "- `_summary.json`：本次检测的摘要与 Top 告警信息。",
        "- `*_diagnosis_report.md/html`：适合答辩展示和产品演示的批次诊断报告。",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path = report_dir / f"{base}_diagnosis_report.md"
    md_path.write_text(md_text, encoding="utf-8")

    html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>批次诊断报告</title>
  <style>
    body {{ font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; margin: 32px; color: #0f172a; background: #f8fafc; }}
    .page {{ max-width: 1100px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 20px; padding: 28px 32px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05); }}
    h1 {{ margin: 0 0 12px; font-size: 28px; }}
    h2 {{ margin-top: 28px; font-size: 20px; border-left: 4px solid #dc2626; padding-left: 10px; }}
    .brief {{ background: linear-gradient(135deg, #eff6ff 0%, #fff7ed 100%); border: 1px solid #dbeafe; border-radius: 16px; padding: 18px 20px; line-height: 1.9; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }}
    .metric {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px 16px; }}
    .metric .label {{ font-size: 12px; color: #64748b; margin-bottom: 8px; }}
    .metric .value {{ font-size: 28px; font-weight: 700; color: #111827; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ background: #f8fafc; color: #334155; font-weight: 600; }}
    .note {{ color: #475569; line-height: 1.8; }}
  </style>
</head>
<body>
  <div class="page">
    <h1>批次诊断报告</h1>
    <p class="note">数据来源：{source_name} | 生成时间：{summary['time']}</p>
    <div class="metrics">
      <div class="metric"><div class="label">样本总数</div><div class="value">{summary['sample_count']}</div></div>
      <div class="metric"><div class="label">告警数量</div><div class="value">{summary['alert_count']}</div></div>
      <div class="metric"><div class="label">平均风险分</div><div class="value">{summary['risk_mean']:.4f}</div></div>
      <div class="metric"><div class="label">最高风险分</div><div class="value">{summary['risk_max']:.4f}</div></div>
    </div>

    <h2>AI 批量简报</h2>
    <div class="brief">{brief}</div>

    <h2>高危类别分布 Top 10</h2>
    <table>
      <thead><tr><th>类别</th><th>数量</th></tr></thead>
      <tbody>{category_html_rows}</tbody>
    </table>

    <h2>高危明细 Top 20</h2>
    {top_alert_html}

    <h2>导出文件说明</h2>
    <div class="note">
      <p>1. <code>_result.csv</code> 保存完整检测结果明细。</p>
      <p>2. <code>_summary.json</code> 保存本次检测的摘要与 Top 告警。</p>
      <p>3. Markdown / HTML 版报告适合演示与答辩使用。</p>
    </div>
  </div>
</body>
</html>
"""
    html_path = report_dir / f"{base}_diagnosis_report.html"
    html_path.write_text(html_text, encoding="utf-8")
    return csv_path, json_path, md_path, html_path

def build_view_df(config: Config, result_df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    view_df = result_df.copy()
    if "log_text" not in view_df.columns:
        view_df["log_text"] = ""

    raw_series = view_df["log_text"].astype(str)
    view_df["日志原文"] = np.where(raw_series.str.strip() != "", raw_series, view_df["template"].astype(str))
    view_df["日志预览"] = view_df["日志原文"].apply(compact_log_preview)
    if "recommended_threshold" in view_df.columns:
        view_df["is_alert"] = view_df["risk_score"] >= view_df["recommended_threshold"].astype(float)
    else:
        view_df["is_alert"] = view_df["risk_score"] >= float(threshold)
    view_df["日志域"] = view_df["log_domain"] if "log_domain" in view_df.columns else "generic"
    view_df["推荐阈值"] = view_df["recommended_threshold"] if "recommended_threshold" in view_df.columns else float(threshold)
    view_df["模板原文"] = view_df["template"].astype(str)
    # 模板解读与主分类保持同源，优先读取原始日志。
    view_df["风险层级"] = view_df["risk_score"].apply(risk_level)

    raw_log_col = "日志原文"
    category_col = "安全分类"
    advice_col = "建议处置"
    source_col = "分类来源"
    security_source = view_df[raw_log_col].where(view_df[raw_log_col].astype(str).str.strip() != "", view_df["template"].astype(str))
    view_df["模板解读"] = security_source.apply(make_template_readable)
    mapped = security_source.apply(interpret_template_security)
    view_df[category_col] = mapped.apply(lambda x: x[0])
    view_df[advice_col] = mapped.apply(lambda x: x[2])
    view_df[source_col] = "原始日志优先规则"

    view_df["RAG辅助分类"] = ""
    view_df["RAG辅助建议"] = ""
    view_df["RAG案例分组"] = ""
    view_df["RAG案例标题"] = ""
    view_df["RAG相似度"] = np.nan
    view_df["RAG向量相似度"] = np.nan
    view_df["RAG排序分"] = np.nan
    view_df["RAG证据可用"] = False
    view_df["rag_cases"] = None
    view_df["攻击大类"] = ""
    view_df["攻击子类"] = ""

    assist_mask = view_df["is_alert"]
    if assist_mask.any():
        _, _, rag = load_runtime(config.config)
        rag_cache = _get_rag_top1_cache(config)
        view_df["_rag_query_key"] = view_df.apply(
            lambda row: _select_rag_query_key(row.get("template", ""), row.get(raw_log_col, "")),
            axis=1,
        )
        unique_query_keys = (
            view_df.loc[assist_mask, "_rag_query_key"]
            .astype(str)
            .dropna()
            .drop_duplicates()
            .tolist()
        )
        top1_map: Dict[str, Dict] = {}

        for query_key in unique_query_keys:
            query_text = str(query_key or "").strip()
            if not query_text:
                continue
            cache_key = query_text
            if cache_key in rag_cache:
                cached = rag_cache.get(cache_key) or {}
                if cached:
                    top1_map[query_text] = cached
                continue

            try:
                hits = rag.retrieve(query_text, top_k=3, auto_build=False, apply_threshold=False)
            except Exception:
                hits = []

            if not hits:
                rag_cache[cache_key] = {}
                continue

            evidence_hit = next((item for item in hits if bool(item.get("evidence_usable", False))), None)
            hit = evidence_hit or hits[0]
            rag_cases = []
            for item in hits[:3]:
                evidence_usable = bool(item.get("evidence_usable", False))
                rag_cases.append(
                    {
                        "title": localize_text(str(item.get("title", ""))),
                        "case_group": localize_case_group(str(item.get("case_group", ""))),
                        "attack_type": localize_attack_type(str(item.get("attack_type", ""))),
                        "advice": localize_advice(str(item.get("advice", ""))),
                        "raw_score": round(float(item.get("raw_score", item.get("score", 0.0))), 4),
                        "score": round(float(item.get("score", 0.0)), 4),
                        "lexical_boost": round(float(item.get("lexical_boost", 0.0)), 4),
                        "evidence_usable": evidence_usable,
                        "confidence_level": str(item.get("confidence_level", "high" if evidence_usable else "candidate")),
                    }
                )
            fill = {
                "RAG\u8f85\u52a9\u5206\u7c7b": rag_hit_to_security_category(evidence_hit) if evidence_hit else "",
                "RAG\u8f85\u52a9\u5efa\u8bae": localize_advice(str(evidence_hit.get("advice", ""))) if evidence_hit else "",
                "RAG\u6848\u4f8b\u5206\u7ec4": localize_case_group(str(evidence_hit.get("case_group", ""))) if evidence_hit else "",
                "RAG\u6848\u4f8b\u6807\u9898": localize_text(str(evidence_hit.get("title", ""))) if evidence_hit else "",
                "RAG\u76f8\u4f3c\u5ea6": round(float(hit.get("score", 0.0)), 4),
                "RAG\u5411\u91cf\u76f8\u4f3c\u5ea6": round(float(hit.get("raw_score", hit.get("score", 0.0))), 4),
                "RAG\u6392\u5e8f\u5206": round(float(hit.get("score", 0.0)), 4),
                "RAG证据可用": bool(evidence_hit),
                "rag_cases": rag_cases,
            }
            rag_cache[cache_key] = fill
            top1_map[query_text] = fill

        if top1_map:
            rag_df = pd.DataFrame.from_dict(top1_map, orient="index")
            rag_df.index.name = "_rag_query_key"
            rag_df = rag_df.reset_index()
            view_df = view_df.merge(rag_df, on="_rag_query_key", how="left", suffixes=("", "_rag"))

            rag_text_cols = [
                "RAG\u8f85\u52a9\u5206\u7c7b",
                "RAG\u8f85\u52a9\u5efa\u8bae",
                "RAG\u6848\u4f8b\u5206\u7ec4",
                "RAG\u6848\u4f8b\u6807\u9898",
                "rag_cases",
            ]
            for col in rag_text_cols:
                rag_col = f"{col}_rag"
                if rag_col in view_df.columns:
                    if col == "rag_cases":
                        view_df[col] = view_df[col].where(view_df[col].notna(), view_df[rag_col])
                    else:
                        base_series = view_df[col].astype(object)
                        base_series = base_series.where(base_series.astype(str).str.strip().ne(""), np.nan)
                        view_df[col] = base_series.combine_first(view_df[rag_col])
                    view_df = view_df.drop(columns=[rag_col])

            for rag_score_col in ["RAG\u76f8\u4f3c\u5ea6", "RAG\u5411\u91cf\u76f8\u4f3c\u5ea6", "RAG\u6392\u5e8f\u5206"]:
                if f"{rag_score_col}_rag" in view_df.columns:
                    view_df[rag_score_col] = view_df[rag_score_col].fillna(view_df[f"{rag_score_col}_rag"])
                    view_df = view_df.drop(columns=[f"{rag_score_col}_rag"])
            if "RAG证据可用_rag" in view_df.columns:
                base_evidence = _to_bool_series(view_df["RAG证据可用"], default=False)
                rag_evidence = _to_bool_series(view_df["RAG证据可用_rag"], default=False)
                view_df["RAG证据可用"] = base_evidence | rag_evidence
                view_df = view_df.drop(columns=["RAG证据可用_rag"])

            rag_display_threshold = float(config.get("rag.retrieval.ui_candidate_min_raw_score", 0.4))
            rag_score_series = pd.to_numeric(view_df["RAG向量相似度"], errors="coerce").fillna(0.0)
            low_confidence_mask = rag_score_series.lt(rag_display_threshold)
            if low_confidence_mask.any():
                for col in ["RAG\u8f85\u52a9\u5206\u7c7b", "RAG\u8f85\u52a9\u5efa\u8bae", "RAG\u6848\u4f8b\u5206\u7ec4", "RAG\u6848\u4f8b\u6807\u9898"]:
                    if col in view_df.columns:
                        view_df.loc[low_confidence_mask, col] = ""
                if "rag_cases" in view_df.columns:
                    view_df.loc[low_confidence_mask, "rag_cases"] = None

            rag_category_col = "RAG\u8f85\u52a9\u5206\u7c7b"
            rag_advice_col = "RAG\u8f85\u52a9\u5efa\u8bae"
            rag_score_col = "RAG\u76f8\u4f3c\u5ea6"
            rag_title_col = "RAG\u6848\u4f8b\u6807\u9898"
            rag_cat_series = view_df[rag_category_col].fillna("").astype(str).str.strip()
            split_parts = rag_cat_series.str.split("/", n=1, expand=True)
            if split_parts.shape[1] >= 1:
                view_df["攻击大类"] = split_parts[0].fillna("").astype(str).str.strip()
            if split_parts.shape[1] >= 2:
                view_df["攻击子类"] = split_parts[1].fillna("").astype(str).str.strip()
            generic_category_mask = view_df[category_col].astype(str).str.strip().isin(["\u5176\u4ed6\u53ef\u7591\u884c\u4e3a"])
            generic_advice_mask = view_df[advice_col].astype(str).str.contains("\u4eba\u5de5\u590d\u6838", na=False)
            rag_ready_mask = (
                rag_cat_series.ne("")
                & view_df[rag_advice_col].astype(str).str.strip().ne("")
                & _to_bool_series(view_df["RAG证据可用"], default=False)
            )
            upgrade_mask = generic_category_mask & generic_advice_mask & rag_ready_mask
            if upgrade_mask.any():
                promoted_detail = view_df.loc[upgrade_mask, rag_title_col].fillna("").astype(str).str.strip()
                fallback_detail = view_df.get("攻击子类", pd.Series("", index=view_df.index)).loc[upgrade_mask].fillna("").astype(str).str.strip()
                promoted_detail = promoted_detail.where(promoted_detail.ne(""), fallback_detail)
                promoted_detail = promoted_detail.where(promoted_detail.ne(""), view_df.loc[upgrade_mask, category_col].astype(str))
                view_df.loc[upgrade_mask, "细粒度主分类"] = promoted_detail.astype(str)
                view_df.loc[upgrade_mask, category_col] = rag_cat_series.loc[upgrade_mask].astype(str)
                view_df.loc[upgrade_mask, advice_col] = view_df.loc[upgrade_mask, rag_advice_col].astype(str)
                view_df.loc[upgrade_mask, source_col] = "\u89c4\u5219+RAG\u589e\u5f3a"

    if "_rag_query_key" in view_df.columns:
        view_df = view_df.drop(columns=["_rag_query_key"])

    if "细粒度主分类" not in view_df.columns:
        view_df["细粒度主分类"] = view_df[category_col].astype(str)
    detail_series = view_df["细粒度主分类"].fillna("").astype(str).str.strip()
    detail_series = detail_series.where(detail_series.ne(""), view_df[category_col].astype(str))
    view_df["细粒度主分类"] = detail_series
    if "攻击大类" not in view_df.columns:
        view_df["攻击大类"] = ""
    if "攻击子类" not in view_df.columns:
        view_df["攻击子类"] = ""

    return view_df

