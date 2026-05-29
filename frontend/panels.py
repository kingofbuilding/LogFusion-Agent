from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import re
from typing import Any, Dict, List

import numpy as np
import yaml
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.helpers import (
    add_security_columns,
    compact_log_preview,
    localize_advice,
    localize_attack_type,
    localize_case_group,
    localize_text,
    make_template_readable,
    render_hero_and_kpis,
)
from frontend.runtime import (
    _get_rag_panel_cache,
    build_ai_judge_admin_snapshot,
    build_view_df,
    load_ai_judge,
    load_runtime,
    resolve_ai_judge_config,
    write_report,
)
from src.utils import Config


def _result_signature(result_df: pd.DataFrame, threshold: float) -> tuple:
    if result_df is None or result_df.empty:
        return (0, 0.0, 0.0, float(threshold))
    risk_series = result_df["risk_score"].astype(float) if "risk_score" in result_df.columns else pd.Series(dtype=float)
    seq_series = result_df["seq_index"].astype(float) if "seq_index" in result_df.columns else pd.Series(dtype=float)
    return (
        int(len(result_df)),
        round(float(risk_series.sum()) if not risk_series.empty else 0.0, 6),
        round(float(seq_series.max()) if not seq_series.empty else 0.0, 3),
        round(float(threshold), 4),
    )


def _view_signature(view_df: pd.DataFrame) -> tuple:
    if view_df is None or view_df.empty:
        return (0, 0, 0.0, 0.0)
    risk_series = view_df["risk_score"].astype(float) if "risk_score" in view_df.columns else pd.Series(dtype=float)
    alert_count = int(view_df["is_alert"].sum()) if "is_alert" in view_df.columns else 0
    return (
        int(len(view_df)),
        alert_count,
        round(float(risk_series.sum()) if not risk_series.empty else 0.0, 6),
        round(float(risk_series.max()) if not risk_series.empty else 0.0, 6),
    )


def _stable_widget_key(*parts: object) -> str:
    raw = "::".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _get_cached_view_df(config: Config, result_df: pd.DataFrame, threshold: float, source_name: str) -> pd.DataFrame:
    cache_key = f"view_df_cache::{source_name}"
    signature = _result_signature(result_df, threshold)
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and cached.get("signature") == signature and isinstance(cached.get("data"), pd.DataFrame):
        return cached["data"]
    view_df = build_view_df(config, result_df, threshold)
    st.session_state[cache_key] = {"signature": signature, "data": view_df}
    return view_df


def _get_cached_incidents(view_df: pd.DataFrame, source_name: str, max_groups: int = 40) -> pd.DataFrame:
    cache_key = f"incident_df_cache::{source_name}::{max_groups}"
    signature = _view_signature(view_df)
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and cached.get("signature") == signature and isinstance(cached.get("data"), pd.DataFrame):
        return cached["data"]
    incidents = build_incident_candidates(view_df, max_groups=max_groups)
    st.session_state[cache_key] = {"signature": signature, "data": incidents}
    return incidents


def render_attention_panel(config: Config, x_seq: np.ndarray, result_df: pd.DataFrame):
    if len(result_df) == 0 or len(x_seq) == 0:
        return
    scorer, _, _ = load_runtime(config.config)
    top_idx = result_df.sort_values("risk_score", ascending=False).head(1)["seq_index"].tolist()
    if not top_idx:
        return
    seq_index = int(top_idx[0])
    if seq_index >= len(x_seq):
        return
    attn = scorer.get_attention_weights(x_seq[seq_index])
    if attn is None:
        st.info("当前未获取到 Bi-LSTM Attention 权重。")
        return
    st.markdown("#### Attention 权重分析")
    heat_df = pd.DataFrame({"位置": np.arange(len(attn)), "权重": attn})
    fig = px.bar(heat_df, x="位置", y="权重", title="高危序列关注位置映射", color_discrete_sequence=["#3b82f6"])
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))


def render_overview(view_df: pd.DataFrame, threshold: float):
    alerts = int(view_df["is_alert"].sum())
    total = int(len(view_df))
    alert_ratio = alerts / max(1, total) * 100.0

    with st.container(border=True):
        st.markdown("#### 全局态势")
        st.caption("用最少的信息先判断当前批次日志是否需要立即进入处置。")
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        row1_left, row1_right = st.columns([1, 2], gap="large")
        with row1_left:
            gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=alert_ratio,
                    number={"suffix": "%", "font": {"size": 28, "color": "#0f172a", "family": "Inter, Microsoft YaHei"}},
                    title={"text": "告警占比", "font": {"size": 14, "color": "#475569"}},
                    gauge={
                        "axis": {
                            "range": [0, 100],
                            "tickwidth": 1,
                            "tickcolor": "#cbd5e1",
                            "tickfont": {"size": 10, "color": "#64748b"},
                            "tickmode": "array",
                            "tickvals": [0, 25, 50, 75, 100],
                        },
                        "bar": {"color": "#2563eb", "thickness": 0.58},
                        "bgcolor": "#ffffff",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, 5], "color": "#e0f2fe"},
                            {"range": [5, 15], "color": "#fef3c7"},
                            {"range": [15, 100], "color": "#fee2e2"},
                        ],
                        "threshold": {"line": {"color": "#ef4444", "width": 4}, "thickness": 0.8, "value": max(10, float(threshold) * 100)},
                    },
                )
            )
            gauge.update_layout(height=258, margin={"l": 18, "r": 18, "t": 34, "b": 12}, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(gauge, use_container_width=True)
            status_text = '低风险' if alert_ratio < 5 else '需关注' if alert_ratio < 15 else '高风险'
            status_class = 'badge-chip-success' if alert_ratio < 5 else 'badge-chip-warning' if alert_ratio < 15 else 'badge-chip-danger'
            st.markdown(f"<div style='margin-top:4px;'><span class='badge-chip {status_class}'>当前状态：{status_text}</span></div>", unsafe_allow_html=True)

        with row1_right:
            trend = view_df[["seq_index", "risk_score"]].copy().sort_values("seq_index")
            trend["rolling_mean"] = trend["risk_score"].rolling(window=60, min_periods=1).mean()
            head_trend = trend.head(min(3000, len(trend)))
            fig_trend = go.Figure()
            fig_trend.add_trace(
                go.Scatter(
                    x=head_trend["seq_index"],
                    y=head_trend["risk_score"],
                    mode="lines",
                    line={"color": "rgba(30,144,255,0)", "width": 0.1, "shape": "spline", "smoothing": 0.55},
                    fill="tozeroy",
                    fillcolor="rgba(112,161,255,0.22)",
                    name="风险分",
                    hovertemplate="序列 %{x}<br>风险分 %{y:.3f}<extra></extra>",
                )
            )
            fig_trend.add_trace(
                go.Scatter(
                    x=head_trend["seq_index"],
                    y=head_trend["rolling_mean"],
                    mode="lines",
                    name="短窗均值",
                    line={"color": "#2A5298", "width": 2.8, "shape": "spline", "smoothing": 0.55},
                    hovertemplate="序列 %{x}<br>短窗均值 %{y:.3f}<extra></extra>",
                )
            )
            fig_trend.add_hline(y=float(threshold), line_dash="dash", line_color="#ef4444", annotation_text="告警阈值", annotation_position="top right")
            fig_trend.update_layout(
                title={"text": "风险趋势", "font": {"size": 16, "color": "#1f2937"}},
                height=270,
                margin={"l": 8, "r": 10, "t": 42, "b": 12},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
                xaxis={"title": "序列位置", "showgrid": False, "zeroline": False, "color": "#64748b"},
                yaxis={"title": "风险分", "showgrid": True, "gridcolor": "rgba(148,163,184,0.16)", "zeroline": False, "color": "#64748b"},
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 风险构成")
        st.caption("从等级与安全类别两个视角，快速判断当前异常主要集中在哪里。")
        row2_left, row2_right = st.columns(2, gap="large")
        with row2_left:
            level_df = view_df["风险层级"].value_counts().reindex(["严重", "高危", "中危", "低风险"], fill_value=0)
            level_df = pd.DataFrame({"风险层级": level_df.index, "数量": level_df.values}).iloc[::-1]
            fig_level = go.Figure(
                go.Bar(
                    x=level_df["数量"],
                    y=level_df["风险层级"],
                    orientation="h",
                    text=level_df["数量"],
                    textposition="outside",
                    marker={
                        "color": ["#60A5FA", "#1E90FF", "#F59E0B", "#EF4444"],
                        "line": {"color": "rgba(255,255,255,0.9)", "width": 1.2},
                    },
                    hovertemplate="%{y}<br>数量 %{x}<extra></extra>",
                )
            )
            fig_level.update_layout(
                title={"text": "风险等级分布", "font": {"size": 16, "color": "#1f2937"}},
                height=280,
                margin={"l": 10, "r": 10, "t": 42, "b": 20},
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis={"title": "数量", "showgrid": True, "gridcolor": "rgba(148,163,184,0.16)", "zeroline": False, "color": "#64748b"},
                yaxis={"title": None, "showgrid": False, "color": "#64748b", "categoryorder": "array", "categoryarray": ["严重", "高危", "中危", "低风险"]},
            )
            st.plotly_chart(fig_level, use_container_width=True)

        with row2_right:
            alert_view = view_df[view_df["is_alert"]].copy()
            cat_df = (
                alert_view.groupby("安全分类", as_index=False)
                .size()
                .rename(columns={"size": "数量"})
                .sort_values("数量", ascending=False)
            )
            total_alerts = int(alert_view["is_alert"].sum()) if not alert_view.empty else 0
            color_pool = ["#2A5298", "#1E90FF", "#70A1FF", "#A4B0BE", "#6B7A8F", "#89A7D8"]
            fig_tree = go.Figure(
                go.Pie(
                    labels=cat_df["安全分类"],
                    values=cat_df["数量"],
                    hole=0.6,
                    sort=False,
                    marker={"colors": color_pool[: len(cat_df)]},
                    textinfo="percent",
                    textposition="inside",
                    insidetextorientation="horizontal",
                    hovertemplate="%{label}<br>告警数 %{value}<br>占比 %{percent}<extra></extra>",
                )
            )
            fig_tree.add_annotation(
                x=0.5,
                y=0.5,
                text=f"<b>{total_alerts}</b><br><span style='font-size:12px;color:#64748b'>总告警数</span>",
                showarrow=False,
                font={"size": 20, "color": "#0f172a"},
            )
            fig_tree.update_layout(
                title={"text": "安全分类构成", "font": {"size": 16, "color": "#1f2937"}},
                height=280,
                margin={"l": 18, "r": 18, "t": 42, "b": 18},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                legend={"orientation": "v", "x": 1.02, "xanchor": "left", "y": 0.5, "font": {"size": 11, "color": "#475569"}},
            )
            st.plotly_chart(fig_tree, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 告警集中度")
        st.caption("判断当前风险是零散分布，还是集中爆发在少数序列窗口内。")
        risk_series = view_df["risk_score"].astype(float).clip(lower=0.0) if "risk_score" in view_df.columns else pd.Series(dtype=float)
        alert_df = view_df[view_df["is_alert"]].copy() if "is_alert" in view_df.columns else pd.DataFrame()
        top_n = max(1, int(np.ceil(len(risk_series) * 0.1))) if len(risk_series) else 1
        top_share = float(risk_series.nlargest(top_n).sum() / risk_series.sum() * 100.0) if float(risk_series.sum()) > 0 else 0.0
        if alert_df.empty:
            max_run = 0
            coverage_ratio = 0.0
            concentration_label = "暂无告警"
        else:
            alert_seq = sorted(alert_df["seq_index"].astype(int).tolist()) if "seq_index" in alert_df.columns else list(range(len(alert_df)))
            max_run = 1
            current_run = 1
            for prev, curr in zip(alert_seq, alert_seq[1:]):
                if curr == prev + 1:
                    current_run += 1
                else:
                    max_run = max(max_run, current_run)
                    current_run = 1
            max_run = max(max_run, current_run)
            coverage_ratio = len(alert_df) / max(1, int(alert_seq[-1] - alert_seq[0] + 1)) * 100.0 if alert_seq else 0.0
            if max_run >= 20 or coverage_ratio >= 45:
                concentration_label = "高度集中"
            elif max_run >= 6 or coverage_ratio >= 20:
                concentration_label = "局部集中"
            else:
                concentration_label = "较分散"

        c1, c2, c3 = st.columns(3, gap="medium")
        c1.metric("Top 10% 风险贡献", f"{top_share:.1f}%")
        c2.metric("最长连续告警", f"{max_run} 条")
        c3.metric("分布判断", concentration_label)

        if "seq_index" in view_df.columns and not view_df.empty:
            plot_df = view_df[["seq_index", "risk_score", "is_alert"]].copy().sort_values("seq_index")
            bins = min(30, max(6, int(np.sqrt(len(plot_df)))))
            plot_df["序列窗口"] = pd.cut(plot_df["seq_index"], bins=bins, duplicates="drop")
            window_df = (
                plot_df.groupby("序列窗口", observed=True)
                .agg(告警数=("is_alert", "sum"), 平均风险=("risk_score", "mean"))
                .reset_index()
            )
            window_df["窗口"] = window_df["序列窗口"].astype(str)
            fig_cluster = go.Figure()
            fig_cluster.add_trace(go.Bar(x=window_df["窗口"], y=window_df["告警数"], name="告警数", marker_color="#ef4444", opacity=0.78))
            fig_cluster.add_trace(go.Scatter(x=window_df["窗口"], y=window_df["平均风险"], name="平均风险", yaxis="y2", mode="lines+markers", line={"color": "#2563eb", "width": 2}))
            fig_cluster.update_layout(
                height=300,
                margin={"l": 10, "r": 10, "t": 26, "b": 80},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend={"orientation": "h", "y": 1.08, "x": 1, "xanchor": "right"},
                xaxis={"title": "序列窗口", "tickangle": -28},
                yaxis={"title": "告警数", "gridcolor": "rgba(148,163,184,0.18)"},
                yaxis2={"title": "平均风险", "overlaying": "y", "side": "right", "range": [0, 1]},
            )
            st.plotly_chart(fig_cluster, use_container_width=True, config={"displayModeBar": False})


def render_high_risk_locator(view_df: pd.DataFrame):
    col_sec = "安全分类"
    col_risk_level = "风险层级"
    col_source = "分类来源"
    col_rag_cat = "RAG辅助分类"
    col_rag_adv = "RAG辅助建议"
    col_rag_title = "RAG案例标题"
    col_rag_score = "RAG相似度"
    col_log = "日志原文"
    col_template = "template"
    col_readable = "模板解读"
    col_advice = "建议处置"
    col_rank = "排名"
    col_preview = "日志预览"
    col_line = "line_num"

    st.markdown("#### 快速定位高危日志")
    st.caption("先筛出最值得优先处理的日志，再按“主判断 / RAG 证据 / 原始证据”查看单条事件的依据。")
    alerts = view_df[view_df["is_alert"]].sort_values("risk_score", ascending=False).copy()
    if alerts.empty:
        st.info("当前阈值下没有告警。")
        return

    with st.container(border=True):
        st.markdown("##### 筛选条件")
        st.caption("建议先收紧风险分和安全类别，再定位单条日志。")
        f1, f2, f3 = st.columns(3)
        min_score = f1.slider("最小风险分", 0.0, 1.0, 0.65, 0.01)
        category_options = sorted(alerts[col_sec].dropna().astype(str).unique().tolist())
        chosen_categories = f2.multiselect("安全分类筛选", options=category_options, default=category_options)
        keyword = f3.text_input("关键词检索", value="", placeholder="输入日志特征...")

    filtered = alerts[alerts["risk_score"] >= float(min_score)].copy()
    if chosen_categories:
        filtered = filtered[filtered[col_sec].isin(chosen_categories)]
    if keyword.strip():
        kw = keyword.strip()
        text_cols = [col_log, col_template, col_readable, col_advice, col_rag_cat, col_rag_adv]
        mask = pd.Series(False, index=filtered.index)
        for col in text_cols:
            if col in filtered.columns:
                mask = mask | filtered[col].astype(str).str.contains(kw, case=False, na=False)
        filtered = filtered[mask]

    with st.container(border=True):
        st.markdown("##### 筛选结果概览")
        summary_cols = st.columns(4)
        summary_cols[0].metric("筛选后告警数", f"{len(filtered):,}")
        summary_cols[1].metric("平均风险分", f"{(filtered['risk_score'].mean() if len(filtered) else 0.0):.3f}")
        summary_cols[2].metric("最高风险分", f"{(filtered['risk_score'].max() if len(filtered) else 0.0):.3f}")
        summary_cols[3].metric("RAG 覆盖率", f"{(filtered[col_rag_cat].astype(str).str.strip().ne('').mean()*100 if len(filtered) else 0.0):.1f}%")

    if filtered.empty:
        st.warning("当前筛选条件下没有匹配日志，请放宽条件后重试。")
        return

    with st.container(border=True):
        st.markdown("##### 分布视图")
        st.caption("左侧看高危日志在序列中的位置，右侧看当前最集中的高危类别。")
        c_left, c_right = st.columns([1.3, 1], gap="large")
        with c_left:
            spot = filtered.head(150).copy()
            fig_spot = px.scatter(
                spot,
                x="seq_index",
                y="risk_score",
                color=col_risk_level,
                symbol=col_source,
                hover_data=[col_line, col_sec],
                title="高危日志定位图（Top 150）",
                color_discrete_map={"严重": "#7f1d1d", "高危": "#ef4444", "中危": "#f59e0b", "低风险": "#10b981"},
            )
            fig_spot.update_layout(height=280, margin={"l": 10, "r": 10, "t": 44, "b": 10}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_spot, use_container_width=True)
        with c_right:
            category_rank = (
                filtered[col_sec]
                .value_counts()
                .head(10)
                .rename_axis(col_sec)
                .reset_index(name="数量")
            )
            fig_rank = px.bar(
                category_rank,
                y=col_sec,
                x="数量",
                orientation="h",
                title="高危类别分布 Top 10",
                color="数量",
                color_continuous_scale="Reds",
            )
            fig_rank.update_layout(height=280, margin={"l": 10, "r": 10, "t": 44, "b": 10}, yaxis={"categoryorder": "total ascending"}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_rank, use_container_width=True)

    selection_source = filtered.copy()
    display_df = filtered.head(300).copy()
    display_df.insert(0, col_rank, np.arange(1, len(display_df) + 1))
    display_df[col_preview] = display_df[col_log].astype(str).map(lambda s: compact_log_preview(s, max_len=120))
    show_cols = [col_rank, col_line, "risk_score", col_risk_level, col_sec, col_rag_cat, col_preview, col_readable, col_advice]
    show_cols = [col for col in show_cols if col in display_df.columns]

    with st.container(border=True):
        st.markdown("##### 高危日志列表")
        st.caption("这里保留最常用字段，方便先浏览，再决定看哪一条证据链。")
        st.dataframe(display_df[show_cols], use_container_width=True, height=340, hide_index=True)
        st.download_button(
            "导出当前筛选结果为 CSV",
            data=display_df[show_cols].to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"high_risk_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_filtered_highrisk",
        )

    max_candidates = max(10, min(int(len(selection_source)), 1000))
    default_candidates = min(200, max_candidates)
    with st.container(border=True):
        st.markdown("##### 单条事件证据链")
        candidate_limit = st.slider("三段式候选日志数", min_value=10, max_value=max_candidates, value=default_candidates, step=10)
        st.caption(f"当前将在风险最高的前 {int(candidate_limit)} 条日志中选择一条查看详细证据。")
        options = selection_source.head(int(candidate_limit)).copy()
        options.insert(0, col_rank, np.arange(1, len(options) + 1))
        select_values = []
        for _, r in options.iterrows():
            select_values.append(
                f"#{int(r[col_rank])} | 行号{int(r[col_line])} | 风险{float(r['risk_score']):.4f} | 主分类{str(r[col_sec])}"
            )
        if not select_values:
            st.info("暂无可查看的日志详情。")
            return
        choice = st.selectbox("选择日志查看三段式证据链", options=select_values)

    if not isinstance(choice, str) or "|" not in choice:
        st.info("请选择一条日志查看三段式证据链。")
        return

    picked_rank = int(choice.split("|")[0].strip().replace("#", ""))
    picked = options[options[col_rank] == picked_rank].head(1)
    if picked.empty:
        return

    row = picked.iloc[0]
    st.markdown("### 这条日志为什么值得先看？")
    st.caption("建议按“主判断 → RAG 证据 → 原始证据”的顺序阅读，这样更容易快速把握风险依据。")

    with st.container(border=True):
        st.markdown("#### 1. 主判断")
        judge_left, judge_right = st.columns([0.95, 1.45], gap="large")
        with judge_left:
            st.markdown(
                f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
  <div class="surface-card">
    <div class="surface-card-title">风险分</div>
    <div class="surface-card-value">{float(row['risk_score']):.4f}</div>
  </div>
  <div class="surface-card">
    <div class="surface-card-title">风险层级</div>
    <div class="surface-card-value" style="font-size:1.45rem;color:var(--danger);">{str(row.get(col_risk_level, '-'))}</div>
  </div>
  <div class="surface-card" style="grid-column:1 / span 2;">
    <div class="surface-card-title">主分类</div>
    <div class="surface-card-value" style="font-size:1.3rem;">{str(row.get(col_sec, '-'))}</div>
    <div class="surface-card-text">分类来源：{str(row.get(col_source, '-'))}</div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )
        with judge_right:
            st.markdown("**模板解读**")
            st.markdown(
                f"""
<div class="surface-card surface-card-accent">
  <div class="surface-card-text">{str(row.get(col_readable, ''))}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown("**建议处置**")
            st.markdown(
                f"""
<div class="surface-card">
  <div class="surface-card-text" style="color:#14532d;">{str(row.get(col_advice, ''))}</div>
</div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("#### 2. RAG 相似案例证据")
    rag_title = str(row.get(col_rag_title, '') or '').strip()
    rag_cat = str(row.get(col_rag_cat, '') or '').strip()
    rag_advice = str(row.get(col_rag_adv, '') or '').strip()
    rag_score = row.get(col_rag_score, None)
    rag_raw_score = row.get('RAG向量相似度', None)
    rag_rank_score = row.get('RAG排序分', rag_score)
    rag_cases = row.get('rag_cases', None)

    current_log_text = str(row.get(col_log, '') or row.get('日志原文', '') or row.get('template', '')).strip()
    if current_log_text:
        try:
            _, _, rag_runtime = load_runtime(config.config)
            try:
                detail_hits = rag_runtime.retrieve(current_log_text, top_k=3, auto_build=False, apply_threshold=False)
            except TypeError:
                detail_hits = rag_runtime.retrieve(current_log_text, top_k=3, auto_build=False)
            if detail_hits:
                rag_cases = [
                    {
                        'title': localize_text(str(item.get('title', ''))),
                        'case_group': localize_case_group(str(item.get('case_group', ''))),
                        'attack_type': localize_text(str(item.get('attack_type', ''))),
                        'advice': localize_advice(str(item.get('advice', ''))),
                        'raw_score': round(float(item.get('raw_score', item.get('score', 0.0))), 4),
                        'score': round(float(item.get('score', 0.0)), 4),
                        'lexical_boost': round(float(item.get('lexical_boost', 0.0)), 4),
                        'evidence_usable': bool(item.get('evidence_usable', False)),
                        'confidence_level': str(item.get('confidence_level', 'candidate')),
                        'case_origin': str(item.get('case_origin', '')),
                        'review_status': str(item.get('review_status', '')),
                        'dataset': str(item.get('dataset', '')),
                        'template_count': int(item.get('template_count', 0) or 0),
                    }
                    for item in detail_hits[:3]
                ]
                top_hit = next((item for item in rag_cases if bool(item.get('evidence_usable', False))), rag_cases[0])
                rag_title = str(top_hit.get('title', '') or rag_title)
                rag_cat = str(top_hit.get('case_group', '') or rag_cat)
                rag_advice = str(top_hit.get('advice', '') or rag_advice)
                rag_score = top_hit.get('score', rag_score)
                rag_raw_score = top_hit.get('raw_score', rag_raw_score)
                rag_rank_score = top_hit.get('score', rag_rank_score)
        except Exception:
            pass

    selected_rag_case = None
    if isinstance(rag_cases, list) and rag_cases:
        selected_rag_case = next((item for item in rag_cases if bool(item.get('evidence_usable', False))), rag_cases[0])
    raw_score_text = '-'
    rank_score_text = '-'
    score_ok = bool(selected_rag_case and selected_rag_case.get('evidence_usable', False))
    try:
        rag_raw_score_float = float(rag_raw_score)
        raw_score_text = f"{rag_raw_score_float:.4f}"
    except Exception:
        pass
    try:
        rag_rank_score_float = float(rag_rank_score)
        rank_score_text = f"{rag_rank_score_float:.4f}"
    except Exception:
        pass

    with st.container(border=True):
        top_left, top_right = st.columns([1.05, 1.25], gap='large')
        with top_left:
            if rag_title or rag_cat or rag_advice:
                confidence_class = 'badge-chip-success' if score_ok else 'badge-chip-warning'
                confidence_text = '高置信案例证据' if score_ok else '候选参考（不进入 AI 主证据）'
                st.markdown(
                    f"""
<div class="surface-card surface-card-accent">
  <div class="surface-card-title">最佳匹配案例</div>
  <div class="surface-card-value" style="font-size:1.25rem;">{rag_title or '暂无'}</div>
  <div style="margin-bottom:12px;">
    <span class="badge-chip badge-chip-accent">{rag_cat or '未分类'}</span>
    <span class="badge-chip {confidence_class}">{confidence_text}</span>
    <span class="badge-chip">向量相似度 {raw_score_text}</span>
    <span class="badge-chip">排序分 {rank_score_text}</span>
  </div>
  <div class="surface-card-text">{rag_advice or '当前没有可直接引用的 RAG 建议。'}</div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("当前日志没有拿到可用的 RAG 辅助结果，请优先参考主判断与原始日志。")

        with top_right:
            candidate_cases = rag_cases[1:3] if isinstance(rag_cases, list) and len(rag_cases) > 1 else []
            if candidate_cases:
                st.markdown("<div class='surface-card-title' style='margin-bottom:10px;'>备选案例（Top-2 / Top-3）</div>", unsafe_allow_html=True)
                cols = st.columns(min(2, len(candidate_cases)), gap='medium')
                for idx_case, case in enumerate(candidate_cases, start=2):
                    case_raw_score = '-'
                    case_rank_score = '-'
                    level = '候选参考'
                    level_class = 'badge-chip-warning'
                    try:
                        case_raw_score_float = float(case.get('raw_score', case.get('score', 0.0)))
                        case_rank_score_float = float(case.get('score', 0.0))
                        case_raw_score = f"{case_raw_score_float:.4f}"
                        case_rank_score = f"{case_rank_score_float:.4f}"
                        if bool(case.get('evidence_usable', False)):
                            level = '高置信案例证据'
                            level_class = 'badge-chip-success'
                    except Exception:
                        pass
                    with cols[idx_case - 2]:
                        st.markdown(
                            f"""
<div class="surface-card" style="height:100%;">
  <div class="surface-card-title">Top-{idx_case}</div>
  <div class="surface-card-value" style="font-size:1.1rem;line-height:1.4;">{str(case.get('title', '') or '未命名案例')}</div>
  <div class="surface-card-text" style="margin-bottom:10px;">{str(case.get('attack_type', '') or '未分类')}</div>
  <div style="margin-bottom:10px;">
    <span class="badge-chip {level_class}">{level}</span>
    <span class="badge-chip">向量相似度 {case_raw_score}</span>
    <span class="badge-chip">排序分 {case_rank_score}</span>
  </div>
  <div class="surface-card-text">{str(case.get('advice', '') or '暂无建议')}</div>
</div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.caption("当前除了最佳匹配外，暂时无额外备选案例。")

    with st.container(border=True):
        st.markdown("#### 3. 原始证据")
        st.markdown("**原始日志**")
        st.code(str(row.get(col_log, ''))[:4000], language='text')
        with st.expander("查看原始模板（技术人员专属）"):
            st.code(str(row.get(col_template, ""))[:2000], language="text")

def render_technical_view(config: Config, view_df: pd.DataFrame, x_seq: np.ndarray, threshold: float, source_name: str = "default"):
    st.markdown("### 多视图模型解释")
    st.caption("从统计、时序、语义三路信号观察风险分布和高危样本抬升，解释融合模型为什么给出当前告警。")

    total_count = int(len(view_df))
    alert_df = view_df[view_df["is_alert"]]
    alert_count = int(len(alert_df))
    alert_ratio = float(alert_count / total_count) if total_count else 0.0
    avg_risk = float(view_df["risk_score"].mean()) if total_count else 0.0

    if alert_count:
        avg_stat_alert = float(alert_df["stat_score"].mean())
        avg_temporal_alert = float(alert_df["temporal_score"].mean())
        avg_semantic_alert = float(alert_df["semantic_score"].mean())
    else:
        avg_stat_alert = avg_temporal_alert = avg_semantic_alert = 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("日志总数", f"{total_count:,}")
    m2.metric("告警数", f"{alert_count:,}")
    m3.metric("告警占比", f"{alert_ratio:.1%}")
    m4.metric("平均风险分", f"{avg_risk:.3f}")
    m5.metric("当前阈值", f"{float(threshold):.3f}")

    with st.container(border=True):
        st.markdown("#### 风险分布与视图贡献")
        st.caption("先看整体分布，再看高危样本相对普通样本主要由哪一路信号拉开。")
        summary_left, summary_right = st.columns([1.15, 1], gap="large")

        with summary_left:
            hist_df = view_df.copy()
            hist_df["风险状态"] = hist_df["is_alert"].map({True: "高于阈值", False: "低于阈值"})
            fig_hist = px.histogram(
                hist_df,
                x="risk_score",
                nbins=36,
                color="风险状态",
                title="风险分分布",
                color_discrete_map={"低于阈值": "#3b82f6", "高于阈值": "#ef4444"},
            )
            fig_hist.add_vline(x=float(threshold), line_dash="dash", line_color="#111827")
            fig_hist.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="",
                xaxis_title="风险分",
                yaxis_title="日志数量",
                margin={"l": 10, "r": 10, "t": 44, "b": 10},
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        with summary_right:
            stat_base = float(view_df["stat_score"].mean()) if total_count else 0.0
            temporal_base = float(view_df["temporal_score"].mean()) if total_count else 0.0
            semantic_base = float(view_df["semantic_score"].mean()) if total_count else 0.0
            stat_gap = avg_stat_alert - stat_base if total_count else 0.0
            temporal_gap = avg_temporal_alert - temporal_base if total_count else 0.0
            semantic_gap = avg_semantic_alert - semantic_base if total_count else 0.0

            view_cards = [
                ("统计视图", stat_base, avg_stat_alert, stat_gap, "补充分布异常背景"),
                ("时序视图", temporal_base, avg_temporal_alert, temporal_gap, "更擅长拉开正常与异常"),
                ("语义视图", semantic_base, avg_semantic_alert, semantic_gap, "提供文本层面的风险提示"),
            ]
            best_gap_name = max(view_cards, key=lambda x: x[3])[0] if view_cards else "暂无"

            st.markdown("##### 三视图贡献对比")
            st.caption("看高危样本相对普通样本的抬升幅度，抬升越大，说明该视图越有区分作用。")
            card_cols = st.columns(3)
            for col, (name, base_v, alert_v, gap_v, role_text) in zip(card_cols, view_cards):
                gap_text = f"{gap_v:+.3f}"
                badge = "当前最明显" if name == best_gap_name else role_text
                chip_class = "badge-chip-accent" if name == best_gap_name else "badge-chip"
                col.markdown(
                    f"""
<div class="surface-card" style="min-height:196px;">
  <div class="surface-card-title">{name}</div>
  <div class="surface-card-text" style="margin-top:10px;">普通样本</div>
  <div class="surface-card-value">{base_v:.3f}</div>
  <div class="surface-card-text" style="margin-top:10px;">高危样本</div>
  <div class="surface-card-value">{alert_v:.3f}</div>
  <div class="surface-card-text" style="margin-top:10px;">抬升幅度</div>
  <div class="surface-card-value" style="font-size:1.5rem;color:{'#dc2626' if gap_v >= 0 else '#2563eb'};">{gap_text}</div>
  <div style="margin-top:12px;"><span class="{chip_class}">{badge}</span></div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

            if best_gap_name == "时序视图":
                summary_text = "当前主要靠时序视图把高危样本拉出来。语义视图提供文本风险提示，统计视图主要补充分布异常背景。"
            elif best_gap_name == "语义视图":
                summary_text = "当前主要靠语义视图提供风险提示。它更像文本层面的风险先验，仍建议结合时序和融合结果一起看。"
            else:
                summary_text = "当前统计视图的抬升更明显，说明分布异常对这一批样本更有帮助；但最终仍建议结合时序和语义一起判断。"
            st.info(summary_text)

    top_cols = ["seq_index", "risk_score", "日志原文", "安全分类", "建议处置"]
    if "风险层级" in view_df.columns:
        top_cols.append("风险层级")
    elif "风险等级" in view_df.columns:
        top_cols.append("风险等级")

    top_df = (
        view_df.sort_values("risk_score", ascending=False)[top_cols]
        .head(10)
        .copy()
    )
    top_df = top_df.rename(
        columns={
            "seq_index": "序号",
            "risk_score": "风险分",
            "日志原文": "代表日志",
            "安全分类": "安全分类",
            "风险层级": "风险等级",
            "风险等级": "风险等级",
            "建议处置": "建议处置",
        }
    )
    top_df["风险分"] = top_df["风险分"].map(lambda x: round(float(x), 4))
    with st.container(border=True):
        st.markdown("#### 最值得先看的高风险样本")
        st.caption("直接列出风险分最高的样本，便于先处理最可能影响答辩演示或实际排查效率的日志。")
        st.dataframe(top_df, use_container_width=True, hide_index=True)

    with st.expander("查看技术图表与模板明细", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            fig_line = px.line(
                view_df.head(min(2000, len(view_df))),
                x="seq_index",
                y="risk_score",
                title="风险趋势（按序列索引展开）",
                color_discrete_sequence=["#3b82f6"],
            )
            fig_line.add_hline(y=float(threshold), line_dash="dash", line_color="#ef4444")
            fig_line.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_line, use_container_width=True)
        with c2:
            fig_scatter = px.scatter(
                view_df.head(min(2000, len(view_df))),
                x="temporal_score",
                y="semantic_score",
                color="risk_score",
                title="时序分 vs 语义分散点图",
                color_continuous_scale="Viridis",
            )
            fig_scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_scatter, use_container_width=True)

        qdf = view_df.copy()
        try:
            qdf["风险分位"] = pd.qcut(qdf["risk_score"], q=10, duplicates="drop").astype(str)
        except Exception:
            qdf["风险分位"] = "单一分位"
        seg = (
            qdf.groupby("风险分位", as_index=False)
            .agg(
                stat_median=("stat_score", "median"),
                stat_p90=("stat_score", lambda s: float(np.quantile(s, 0.90))),
                temporal_median=("temporal_score", "median"),
                temporal_p90=("temporal_score", lambda s: float(np.quantile(s, 0.90))),
                semantic_median=("semantic_score", "median"),
                semantic_p90=("semantic_score", lambda s: float(np.quantile(s, 0.90))),
            )
        )
        seg["风险分位"] = seg["风险分位"].astype(str)
        seg_m = seg.melt(id_vars="风险分位", var_name="指标", value_name="分值")
        metric_name_map = {
            "stat_median": "统计分-中位数",
            "stat_p90": "统计分-P90",
            "temporal_median": "时序分-中位数",
            "temporal_p90": "时序分-P90",
            "semantic_median": "语义分-中位数",
            "semantic_p90": "语义分-P90",
        }
        seg_m["指标"] = seg_m["指标"].map(metric_name_map).fillna(seg_m["指标"])
        fig_seg = px.line(
            seg_m,
            x="风险分位",
            y="分值",
            color="指标",
            markers=True,
            title="多模型分位剖面（中位数 + P90）",
        )
        fig_seg.update_layout(
            height=320,
            margin={"l": 10, "r": 10, "t": 50, "b": 20},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_seg, use_container_width=True)

        st.markdown("#### 模板级聚合明细")
        template_df = (
            view_df.groupby("template_id")
            .agg(
                template_text=("template", "first"),
                template_summary=("模板解读", "first"),
                sample_log=("日志原文", "first"),
                sample_count=("template_id", "count"),
                avg_risk=("risk_score", "mean"),
                alert_count=("is_alert", "sum"),
                rag_fill_count=("RAG辅助分类", lambda s: int(s.fillna("").astype(str).str.strip().ne("").sum())),
            )
            .reset_index()
            .sort_values(["alert_count", "avg_risk"], ascending=[False, False])
        )
        template_view = add_security_columns(template_df).rename(
            columns={
                "template_id": "模板ID",
                "template_text": "原始模板",
                "template_summary": "中文摘要",
                "sample_log": "原始样例日志",
                "sample_count": "样本数",
                "avg_risk": "平均风险",
                "alert_count": "告警数",
                "rag_fill_count": "RAG覆盖数",
                "安全分类": "安全分类",
                "风险等级": "风险等级",
                "建议处置": "处置建议",
                "处置建议": "处置建议",
            }
        )
        show_cols = [
            "模板ID",
            "中文摘要",
            "原始样例日志",
            "样本数",
            "告警数",
            "平均风险",
            "安全分类",
            "风险等级",
            "处置建议",
            "原始模板",
        ]
        show_cols = [col for col in show_cols if col in template_view.columns]
        st.dataframe(template_view[show_cols].head(300), use_container_width=True, hide_index=True)
        render_attention_panel(config, x_seq, view_df)

def render_rag_panel(config: Config, view_df: pd.DataFrame, rag_query_count: int = 5, source_name: str = "default"):
    st.markdown("#### 高危日志相似案例检索")
    alerts = view_df[view_df["is_alert"]].sort_values("risk_score", ascending=False)
    if alerts.empty:
        st.info("当前没有可用于 RAG 检索的高危日志。")
        return

    query_n = max(1, int(rag_query_count))
    top_templates = alerts["template"].astype(str).drop_duplicates().head(query_n).tolist()
    st.info(
        f"这里展示的是 **{len(top_templates)} 个高危查询模板** 的相似案例检索结果。"
        "阅读顺序建议：先看“最佳匹配总览”，再展开单个模板查看 Top-3 候选证据。"
    )

    cache = _get_rag_panel_cache(config)
    cache_key = f"v7_dual_score_cn|{source_name}|{query_n}|{hash(tuple(top_templates))}"
    rag_df = cache.get(cache_key)
    if not isinstance(rag_df, pd.DataFrame) or rag_df.empty:
        _, _, rag = load_runtime(config.config)
        threshold = float(getattr(rag, "similarity_threshold", config.get("rag.retrieval.similarity_threshold", 0.7)))
        rag_rows = []
        for query_template in top_templates:
            try:
                hits = rag.retrieve(query_template, top_k=3, auto_build=False, apply_threshold=False)
            except TypeError:
                hits = rag.retrieve(query_template, top_k=3, auto_build=False)

            if not hits:
                rag_rows.append(
                    {
                        "查询模板": make_template_readable(query_template, max_len=120),
                        "查询模板原文": query_template[:180],
                        "检索位次": "-",
                        "向量相似度": 0.0,
                        "排序分": 0.0,
                        "可信度": "无结果",
                        "案例编号": "-",
                        "案例标题(中文)": "未检索到相似案例",
                        "攻击类型(中文)": "-",
                        "技术编号": "-",
                        "案例分组(中文)": "未分类案例",
                        "处置建议(中文)": "建议先检查案例库与 RAG 索引是否构建正常。",
                        "案例来源": "-",
                        "审核状态": "-",
                        "来源数据集": "-",
                        "模板计数": 0,
                    }
                )
                continue

            for rank, hit in enumerate(hits, start=1):
                final_score = float(hit.get("score", 0.0))
                raw_score = float(hit.get("raw_score", final_score))
                passed = bool(hit.get("evidence_usable", hit.get("threshold_passed", final_score >= threshold)))
                case_origin = str(hit.get("case_origin", "") or "")
                source_label = "自动扩充案例" if case_origin == "auto_labeled_template" or str(hit.get("source", "")) == "auto_from_labeled_data" else "内置案例"
                review_status = str(hit.get("review_status", "") or "")
                review_label = {"pending": "待审核", "approved": "已审核", "rejected": "已拒绝"}.get(review_status, review_status or "-")
                rag_rows.append(
                    {
                        "查询模板": make_template_readable(query_template, max_len=120),
                        "查询模板原文": query_template[:180],
                        "检索位次": f"Top-{rank}",
                        "向量相似度": round(raw_score, 4),
                        "排序分": round(final_score, 4),
                        "可信度": "高置信案例证据" if passed else "候选参考",
                        "案例编号": str(hit.get("case_id", "")),
                        "案例标题(中文)": localize_text(str(hit.get("title", ""))),
                        "攻击类型(中文)": localize_attack_type(str(hit.get("attack_type", ""))),
                        "技术编号": str(hit.get("technique", "")),
                        "案例分组(中文)": localize_case_group(str(hit.get("case_group", ""))),
                        "处置建议(中文)": localize_advice(str(hit.get("advice", ""))),
                        "案例来源": source_label,
                        "审核状态": review_label,
                        "来源数据集": str(hit.get("dataset", "") or "-"),
                        "模板计数": int(hit.get("template_count", 0) or 0),
                    }
                )
        rag_df = pd.DataFrame(rag_rows)
        cache[cache_key] = rag_df.copy()

    if rag_df.empty:
        st.info("暂无可展示的 RAG 检索结果。")
        return

    best_df = rag_df.sort_values(["查询模板", "检索位次"]).drop_duplicates(subset=["查询模板"], keep="first").copy()
    candidate_count = rag_df.groupby("查询模板", dropna=False).size().rename("候选数")
    high_conf_count = rag_df.groupby("查询模板", dropna=False)["可信度"].apply(lambda s: int(s.eq("高置信案例证据").sum())).rename("高置信案例证据数")
    best_df = best_df.merge(candidate_count, on="查询模板", how="left")
    best_df = best_df.merge(high_conf_count, on="查询模板", how="left")
    best_df = best_df[["查询模板", "案例标题(中文)", "攻击类型(中文)", "向量相似度", "排序分", "可信度", "案例来源", "审核状态", "来源数据集", "模板计数", "候选数", "高置信案例证据数", "处置建议(中文)"]].copy()

    metric_cols = st.columns(4)
    metric_cols[0].metric("检索模板数", f"{len(top_templates)}")
    metric_cols[1].metric("返回候选总数", f"{len(rag_df)}")
    metric_cols[2].metric("Top-1 平均向量相似度", f"{best_df['向量相似度'].mean():.4f}")
    metric_cols[3].metric("高置信案例证据占比", f"{(best_df['可信度'].eq('高置信案例证据').mean() * 100):.1f}%")

    st.markdown("**最佳匹配总览**")
    st.caption("向量相似度表示原始向量空间的接近程度；排序分表示加入关键词重排后的最终排序分，因此排序分可能高于 1。")
    st.dataframe(best_df, use_container_width=True, hide_index=True, height=260)

    with st.expander("🔍 按查询模板查看 Top-3 候选证据"):
        total_groups = len(best_df)
        for idx, (query_template, grp) in enumerate(rag_df.groupby("查询模板", dropna=False), start=1):
            high_conf = int(grp["可信度"].eq("高置信案例证据").sum())
            st.markdown(f"### 模板 {idx} / {total_groups}")
            st.markdown(f"**查询模板：{query_template}**")
            st.caption(f"当前返回 {len(grp)} 条候选，其中高置信案例证据 {high_conf} 条。")
            cols = st.columns(min(3, len(grp)), gap="medium")
            for i, (_, case_row) in enumerate(grp.head(3).iterrows()):
                level = str(case_row.get("可信度", "候选参考"))
                level_bg = "#dcfce7" if level == "高置信案例证据" else "#fef3c7"
                level_fg = "#166534" if level == "高置信案例证据" else "#92400e"
                with cols[i]:
                    st.markdown(
                        f"""
<div class="surface-card" style="height:100%;padding:14px 14px 12px 14px;">
  <div class="surface-card-title">{case_row['检索位次']}</div>
  <div style="font-size:16px;font-weight:700;color:#0f172a;line-height:1.4;margin-bottom:8px;">{case_row['案例标题(中文)']}</div>
  <div style="font-size:12px;color:#475569;margin-bottom:10px;">{case_row['攻击类型(中文)']}</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
    <span class="badge-chip" style="background:{level_bg};color:{level_fg};">{level}</span>
    <span class="badge-chip">向量相似度 {float(case_row['向量相似度']):.4f}</span>
    <span class="badge-chip badge-chip-accent">排序分 {float(case_row['排序分']):.4f}</span>
  </div>
  <div class="surface-card-text" style="font-size:12px;">{case_row['处置建议(中文)']}</div>
</div>
                        """,
                        unsafe_allow_html=True,
                    )
            st.markdown("---")

    with st.expander("查看完整 RAG 检索明细（技术人员专属）"):
        st.dataframe(rag_df, use_container_width=True, hide_index=True)

def _severity_rank(level: str) -> int:
    mapping = {"严重": 4, "高危": 3, "中危": 2, "低危": 1}
    return mapping.get(str(level or "").strip(), 2)


def _extract_log_timestamp(log_text: str) -> str:
    text = str(log_text or "").strip()
    patterns = [
        r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",
        r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return "-"


def _extract_log_host(log_text: str) -> str:
    text = str(log_text or "").strip()
    patterns = [
        r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)",
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\s+(\S+)",
        r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}\s+(\S+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "-"


def _extract_event_keywords(texts: List[str], main_class: str = "", attack_family: str = "") -> List[str]:
    joined = " \n ".join([str(x) for x in texts if str(x).strip()]).lower()
    candidates = [
        ("failed password", "failed password"),
        ("accepted password", "accepted password"),
        ("invalid user", "invalid user"),
        ("user unknown", "user unknown"),
        ("session opened", "session opened"),
        ("sudo", "sudo"),
        ("execve", "execve"),
        ("shadow", "/etc/shadow"),
        ("wp-login.php", "wp-login.php"),
        ("wpscan", "WPScan"),
        ("union select", "UNION SELECT"),
        ("../", "路径穿越"),
        ("prompt injection", "prompt injection"),
        ("openvpn", "OpenVPN"),
        ("dns", "DNS"),
        ("refused", "refused"),
        ("ftp", "FTP"),
        ("connection from", "connection from"),
    ]
    tags: List[str] = []
    for needle, label in candidates:
        if needle in joined and label not in tags:
            tags.append(label)
    for extra in [str(main_class or "").strip(), str(attack_family or "").strip()]:
        if extra and extra not in tags:
            tags.append(extra)
    return tags[:8]


def _extract_entities(texts: List[str]) -> List[str]:
    joined = " \n ".join([str(x) for x in texts if str(x).strip()])
    entities: List[str] = []
    seen = set()
    for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", joined):
        if ip not in seen:
            seen.add(ip)
            entities.append(ip)
    user_patterns = [
        r"for\s+([A-Za-z0-9_.-]+)",
        r"user(?:name)?[=:]\s*([A-Za-z0-9_.-]+)",
        r"invalid user\s+([A-Za-z0-9_.-]+)",
        r"ruser=([A-Za-z0-9_.-]+)",
    ]
    for pattern in user_patterns:
        for match in re.findall(pattern, joined, flags=re.I):
            token = str(match or "").strip()
            if token and token.lower() not in {"for", "user", "unknown"} and token not in seen:
                seen.add(token)
                entities.append(token)
    return entities[:8]


def _summarize_anomaly(log_text: str, risk: float, temporal: float, semantic: float, stat: float) -> str:
    text = str(log_text or "").lower()
    if "failed password" in text or "invalid user" in text or "user unknown" in text:
        return "认证失败密集出现，疑似爆破或账号探测。"
    if "accepted password" in text or "accepted publickey" in text:
        return "出现成功登录行为，需要结合来源与账号历史复核。"
    if "session opened" in text:
        return "会话建立成功，需确认是否与前序认证异常相关。"
    if "sudo" in text or "execve" in text or "shadow" in text:
        return "存在高权限命令或敏感文件访问痕迹。"
    if "wp-login" in text or "wpscan" in text or "../" in text or "union select" in text:
        return "存在 Web 探测或利用痕迹，疑似自动化攻击。"
    if "dns" in text and ("refused" in text or "query" in text or "forwarded" in text):
        return "DNS 行为异常，建议核查请求模式与目标。"
    dominant = max(
        [
            ("行为异常", float(temporal or 0.0)),
            ("内容风险", float(semantic or 0.0)),
            ("统计异常", float(stat or 0.0)),
        ],
        key=lambda x: x[1],
    )[0]
    return f"该日志综合风险较高，当前以{dominant}信号最为明显。"


def _build_fusion_reason(incident: Dict[str, Any]) -> str:
    stat_score = float(incident.get("统计分均值", 0.0) or 0.0)
    temporal_score = float(incident.get("时序分均值", 0.0) or 0.0)
    semantic_score = float(incident.get("语义向量分均值", 0.0) or 0.0)
    fusion_score = float(incident.get("最高风险", 0.0) or 0.0)
    parts = [
        ("统计视图", stat_score),
        ("时序视图", temporal_score),
        ("语义视图", semantic_score),
    ]
    lead_name, lead_score = max(parts, key=lambda x: x[1])
    if lead_name == "时序视图":
        reason = "当前主要由行为序列异常拉动，说明同类日志在时间上形成了可疑链路。"
    elif lead_name == "语义视图":
        reason = "当前主要由内容风险拉动，说明日志文本本身与高风险模式更接近。"
    else:
        reason = "当前主要由统计特征拉动，说明该窗口在频率、熵或密度上明显偏离正常分布。"
    return f"{reason} 综合融合总分为 {fusion_score:.3f}，主导视图为{lead_name}（{lead_score:.3f}）。"


def build_incident_candidates(view_df: pd.DataFrame, max_groups: int = 20) -> pd.DataFrame:
    alerts = view_df[view_df["is_alert"]].copy()
    if alerts.empty:
        return pd.DataFrame()

    group_cols = ["安全分类", "template"]
    rows = []
    for _, grp in alerts.groupby(group_cols, dropna=False):
        grp = grp.sort_values(["risk_score", "line_num"], ascending=[False, True]).copy()
        if grp.empty:
            continue

        row0 = grp.iloc[0]
        main_class = str(row0.get("安全分类", "") or "待定事件").strip()
        attack_family = str(row0.get("攻击大类", "") or row0.get("RAG辅助分类", "") or "").strip()
        severity = str(row0.get("风险等级", row0.get("风险层级", "高危")) or "高危").strip()
        raw_logs = grp.get("日志原文", pd.Series(dtype=str)).fillna("").astype(str).tolist()
        template_text = str(row0.get("template", "") or "")
        top_logs = grp["日志原文"].fillna("").astype(str).head(3).tolist() if "日志原文" in grp.columns else []

        entities = _extract_entities(raw_logs)
        source_ips = [entity for entity in entities if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", str(entity))][:5]
        hosts: List[str] = []
        for log in raw_logs:
            host = _extract_log_host(log)
            if host != "-" and host not in hosts:
                hosts.append(host)
        times: List[str] = []
        for log in raw_logs:
            timestamp = _extract_log_timestamp(log)
            if timestamp != "-" and timestamp not in times:
                times.append(timestamp)
        if times:
            time_range = f"{times[0]} - {times[-1]}" if len(times) > 1 else times[0]
        else:
            time_range = f"行号 {int(grp['line_num'].min())} - {int(grp['line_num'].max())}"

        impact_parts: List[str] = []
        if hosts:
            impact_parts.append("主机 " + "、".join(hosts[:3]))
        services: List[str] = []
        joined_logs = " ".join(raw_logs).lower()
        for token, label in [("sshd", "SSH"), ("httpd", "HTTPD"), ("nginx", "Nginx"), ("openvpn", "OpenVPN"), ("kernel", "Kernel"), ("ftpd", "FTP")]:
            if token in joined_logs and label not in services:
                services.append(label)
        if services:
            impact_parts.append("服务 " + "、".join(services[:3]))
        impact_scope = "；".join(impact_parts) if impact_parts else f"行号 {int(grp['line_num'].min())}-{int(grp['line_num'].max())}"

        keywords = _extract_event_keywords(raw_logs[:12], main_class, attack_family)
        summary_source = compact_log_preview(str(row0.get("模板解读", "")).strip(), max_len=80)
        if not summary_source or summary_source == "-":
            summary_source = compact_log_preview(top_logs[0] if top_logs else template_text, max_len=80)

        context_rows = []
        for _, item in grp.sort_values("line_num", ascending=True).head(10).iterrows():
            log_text = str(item.get("日志原文", "") or "")
            context_rows.append(
                {
                    "line_num": int(item.get("line_num", 0) or 0),
                    "时间": _extract_log_timestamp(log_text),
                    "节点": _extract_log_host(log_text),
                    "风险分": float(item.get("risk_score", 0.0) or 0.0),
                    "行为异常置信度": float(item.get("temporal_score", 0.0) or 0.0),
                    "内容威胁置信度": float(item.get("semantic_score", 0.0) or 0.0),
                    "统计异常置信度": float(item.get("stat_score", 0.0) or 0.0),
                    "异常点摘要": _summarize_anomaly(
                        log_text,
                        float(item.get("risk_score", 0.0) or 0.0),
                        float(item.get("temporal_score", 0.0) or 0.0),
                        float(item.get("semantic_score", 0.0) or 0.0),
                        float(item.get("stat_score", 0.0) or 0.0),
                    ),
                    "原始日志": log_text,
                    "原始模板": str(item.get("template", "") or ""),
                }
            )

        focus_rows = []
        for _, item in grp.sort_values("risk_score", ascending=False).head(5).iterrows():
            log_text = str(item.get("日志原文", "") or "")
            focus_rows.append(
                {
                    "line_num": int(item.get("line_num", 0) or 0),
                    "时间": _extract_log_timestamp(log_text),
                    "节点": _extract_log_host(log_text),
                    "风险分": float(item.get("risk_score", 0.0) or 0.0),
                    "行为异常置信度": float(item.get("temporal_score", 0.0) or 0.0),
                    "内容威胁置信度": float(item.get("semantic_score", 0.0) or 0.0),
                    "统计异常置信度": float(item.get("stat_score", 0.0) or 0.0),
                    "异常点摘要": _summarize_anomaly(
                        log_text,
                        float(item.get("risk_score", 0.0) or 0.0),
                        float(item.get("temporal_score", 0.0) or 0.0),
                        float(item.get("semantic_score", 0.0) or 0.0),
                        float(item.get("stat_score", 0.0) or 0.0),
                    ),
                    "原始日志": log_text,
                    "原始模板": str(item.get("template", "") or ""),
                }
            )

        rag_cases = []
        seen_rag_case = set()
        if "rag_cases" in grp.columns:
            for cases in grp["rag_cases"].tolist():
                if not isinstance(cases, list):
                    continue
                for case in cases:
                    if not isinstance(case, dict):
                        continue
                    item = _normalize_rag_case_item(case)
                    key = (str(item.get("title", "")).strip(), str(item.get("attack_type", "")).strip())
                    if not item or key in seen_rag_case:
                        continue
                    seen_rag_case.add(key)
                    rag_cases.append(item)
                    if len(rag_cases) >= 5:
                        break
                if len(rag_cases) >= 5:
                    break

        incident_title = main_class
        if attack_family and attack_family != main_class:
            incident_title = f"{main_class} · {attack_family}"

        rows.append(
            {
                "incident_id": f"{main_class}::{template_text}::{int(grp['line_num'].min())}-{int(grp['line_num'].max())}",
                "事件名称": incident_title,
                "事件标题": incident_title,
                "安全分类": main_class,
                "攻击大类": attack_family,
                "风险等级": severity,
                "模板解读": str(row0.get("模板解读", "") or "").strip(),
                "一句话摘要": summary_source,
                "时间范围": time_range,
                "影响范围": impact_scope,
                "关键实体": "、".join(entities[:5]) if entities else "待进一步解析",
                "攻击源IP": source_ips,
                "命中关键词": keywords,
                "template": template_text,
                "告警数": int(len(grp)),
                "最高风险": float(grp["risk_score"].max()),
                "平均风险": float(grp["risk_score"].mean()),
                "起始行号": int(grp["line_num"].min()),
                "结束行号": int(grp["line_num"].max()),
                "统计分均值": float(grp["stat_score"].mean()),
                "时序分均值": float(grp["temporal_score"].mean()),
                "语义向量分均值": float(grp["semantic_score"].mean()),
                "主建议处置": str(row0.get("建议处置", "") or "").strip(),
                "rag_cases": rag_cases,
                "关键异常日志": top_logs,
                "日志原文": top_logs,
                "上下文日志": context_rows,
                "模型关注热点": focus_rows,
                "时间排序键": str(times[0]) if times else f"{int(grp['line_num'].min()):09d}",
                "风险等级排序": _severity_rank(severity),
            }
        )

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(["风险等级排序", "最高风险", "告警数", "平均风险"], ascending=[False, False, False, False])
        .head(max_groups)
        .reset_index(drop=True)
    )


def _normalize_rag_case_item(case: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(case, dict):
        return {}
    evidence_usable = bool(case.get("evidence_usable", False))
    return {
        "title": localize_text(str(case.get("title", "")).strip()),
        "case_group": localize_case_group(str(case.get("case_group", "")).strip()),
        "attack_type": localize_attack_type(str(case.get("attack_type", "")).strip()),
        "advice": localize_advice(str(case.get("advice", "")).strip()),
        "raw_score": float(case.get("raw_score", case.get("score", 0.0)) or 0.0),
        "score": float(case.get("score", 0.0) or 0.0),
        "lexical_boost": float(case.get("lexical_boost", 0.0) or 0.0),
        "evidence_usable": evidence_usable,
        "confidence_level": str(case.get("confidence_level", "high" if evidence_usable else "candidate")),
        "case_origin": str(case.get("case_origin", "") or ""),
        "source": str(case.get("source", "") or ""),
        "review_status": str(case.get("review_status", "") or ""),
        "dataset": str(case.get("dataset", "") or ""),
        "template_count": int(case.get("template_count", 0) or 0),
    }


def _dedupe_rag_cases(cases: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for case in cases:
        item = _normalize_rag_case_item(case)
        if not item:
            continue
        key = (item["title"], item["attack_type"])
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= top_k:
            break
    return normalized


def _build_incident_rag_query(incident: Dict[str, Any]) -> str:
    title = str(incident.get("事件名称", "")).strip()
    main_class = str(incident.get("安全分类", "")).strip()
    attack_family = str(incident.get("攻击大类", "")).strip()
    top_logs = incident.get("关键异常日志", [])
    if not isinstance(top_logs, list):
        top_logs = []
    key_logs = [str(x).strip() for x in top_logs[:3] if str(x).strip()]
    parts = [
        f"事件标题: {title}" if title else "",
        f"主分类: {main_class}" if main_class else "",
        f"攻击大类: {attack_family}" if attack_family else "",
    ]
    if key_logs:
        parts.append("关键日志: " + " || ".join(key_logs))
    return "\n".join([p for p in parts if p]).strip()


def _retrieve_incident_rag_cases(config: Config, incident: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
    query_text = _build_incident_rag_query(incident)
    fallback_cases = _dedupe_rag_cases(incident.get("rag_cases", []), top_k=top_k)
    if not query_text:
        return fallback_cases

    cache = _get_rag_panel_cache(config)
    cache_key = f"incident::{query_text}"
    cached = cache.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        try:
            return _dedupe_rag_cases(cached.to_dict(orient="records"), top_k=top_k)
        except Exception:
            pass

    _, _, rag = load_runtime(config.config)
    try:
        hits = rag.retrieve(query_text, top_k=top_k, auto_build=False, apply_threshold=False)
    except Exception:
        hits = []

    rows = [_normalize_rag_case_item(item) for item in hits[:top_k] if isinstance(item, dict)]
    rows = [row for row in rows if row]
    if rows:
        cache[cache_key] = pd.DataFrame(rows)
        return _dedupe_rag_cases(rows, top_k=top_k)
    return fallback_cases


def _get_cached_incident_rag_cases(
    config: Config,
    incident: Dict[str, Any],
    source_name: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    incident_id = str(incident.get("incident_id", "") or incident.get("事件名称", "")).strip()
    signature = (
        incident_id,
        round(float(incident.get("最高风险", 0.0) or 0.0), 6),
        int(incident.get("告警数", 0) or 0),
        int(top_k),
    )
    cache_key = f"incident_rag_cache::{_stable_widget_key(source_name, incident_id, top_k)}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and cached.get("signature") == signature and isinstance(cached.get("data"), list):
        return cached["data"]
    rag_cases = _retrieve_incident_rag_cases(config, incident, top_k=top_k)
    st.session_state[cache_key] = {"signature": signature, "data": rag_cases}
    return rag_cases


def _trim_incident_for_llm(incident: Dict[str, Any]) -> Dict[str, Any]:
    candidate_rag_cases = _dedupe_rag_cases(incident.get("rag_cases", []), top_k=5)
    rag_cases = [case for case in candidate_rag_cases if bool(case.get("evidence_usable", False))][:3]
    top_logs = incident.get("关键异常日志", [])
    if not isinstance(top_logs, list):
        top_logs = []
    source_ips = incident.get("攻击源IP", [])
    if not isinstance(source_ips, list):
        source_ips = []
    return {
        "incident_id": str(incident.get("incident_id", incident.get("事件名称", ""))).strip(),
        "title": str(incident.get("事件名称", "")).strip(),
        "severity": str(incident.get("风险等级", "")).strip() or "高危",
        "main_class": str(incident.get("安全分类", "")).strip(),
        "attack_family": str(incident.get("攻击大类", "")).strip(),
        "risk_score": float(incident.get("最高风险", 0.0) or 0.0),
        "risk_mean": float(incident.get("平均风险", 0.0) or 0.0),
        "alert_count": int(incident.get("告警数", 0) or 0),
        "source_ips": source_ips[:5],
        "line_range": {
            "start": int(incident.get("起始行号", 0) or 0),
            "end": int(incident.get("结束行号", 0) or 0),
        },
        "summary": str(incident.get("模板解读", "")).strip(),
        "top_logs": [str(x).strip()[:500] for x in top_logs[:3] if str(x).strip()],
        "rag_cases": rag_cases,
        "rag_evidence_note": "存在候选案例，但未达到证据门槛" if candidate_rag_cases and not rag_cases else "",
        "recommended_action": str(incident.get("主建议处置", "")).strip(),
    }


def _render_incident_rag_cards(rag_cases: List[Dict[str, Any]], section_title: str = "事件级 RAG 检索支撑") -> None:
    if not rag_cases:
        st.info("当前没有命中可用的相似历史案例。")
        return
    st.markdown(f"**{section_title}**")
    for idx, case in enumerate(rag_cases[:5], start=1):
        score = float(case.get("score", 0.0) or 0.0)
        raw_score = float(case.get("raw_score", score) or 0.0)
        title = str(case.get("title", "") or "未命名案例")
        attack_type = str(case.get("attack_type", "") or "未分类")
        advice = str(case.get("advice", "") or "暂无命中依据摘要。")
        evidence_usable = bool(case.get("evidence_usable", False))
        confidence = "高置信案例证据" if evidence_usable else "候选参考"
        case_origin = str(case.get("case_origin", "") or "")
        source_label = "自动扩充案例" if case_origin == "auto_labeled_template" or str(case.get("source", "")) == "auto_from_labeled_data" else "内置案例"
        review_status = str(case.get("review_status", "") or "")
        review_label = {"pending": "待审核", "approved": "已审核", "rejected": "已拒绝"}.get(review_status, review_status or "-")
        dataset = str(case.get("dataset", "") or "-")
        template_count = int(case.get("template_count", 0) or 0)
        st.markdown(
            f"""
<div style="padding:14px 16px;border-radius:16px;border:1px solid rgba(148,163,184,0.22);background:#ffffff;margin-bottom:10px;box-shadow:0 6px 20px rgba(15,23,42,0.04);">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
    <div>
      <div style="font-size:12px;color:#64748b;margin-bottom:6px;">历史案例 {idx}</div>
      <div style="font-size:17px;font-weight:700;color:#0f172a;line-height:1.4;">{title}</div>
      <div style="font-size:12px;color:#475569;margin-top:4px;">{attack_type}</div>
    </div>
    <div style="text-align:right;min-width:132px;">
      <div style="padding:4px 10px;border-radius:999px;background:{'#dcfce7' if evidence_usable else '#fef3c7'};color:{'#166534' if evidence_usable else '#92400e'};font-size:12px;font-weight:700;display:inline-block;">{confidence}</div>
      <div style="font-size:12px;color:#64748b;margin-top:8px;">向量相似度 {raw_score:.4f}</div>
      <div style="font-size:12px;color:#0f766e;margin-top:2px;">排序分 {score:.4f}</div>
    </div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;">
    <span class="badge-chip">{source_label}</span>
    <span class="badge-chip">{review_label}</span>
    <span class="badge-chip">数据集 {dataset}</span>
    <span class="badge-chip">模板数 {template_count}</span>
  </div>
  <div style="font-size:13px;color:#334155;line-height:1.8;margin-top:10px;">{advice}</div>
</div>
            """,
            unsafe_allow_html=True,
        )




def render_triage_center(config: Config, view_df: pd.DataFrame, source_name: str, llm_cfg: Dict[str, str]):
    incidents = _get_cached_incidents(view_df, source_name, max_groups=40)
    st.markdown(
        """
<style>
.triage-left {
  max-height:620px;
  overflow-y:auto;
  padding-right:4px;
}
.triage-left button[kind="secondary"], .triage-left button[kind="primary"] {
  text-align:left !important;
  justify-content:flex-start !important;
  align-items:flex-start !important;
  white-space:pre-wrap !important;
  height:auto !important;
  min-height:76px !important;
  border-radius:14px !important;
  padding:10px 12px !important;
  line-height:1.35 !important;
  font-size:12.5px !important;
  box-shadow:none !important;
}
.triage-left button[kind="secondary"] {
  background:#ffffff !important;
  border:1px solid #dbe3ee !important;
  color:#0f172a !important;
}
.triage-left button[kind="primary"] {
  background:#f8fbff !important;
  border:1px solid #bfdbfe !important;
  color:#0f172a !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    if incidents.empty:
        st.info("当前没有可进入事件分析的高危事件。")
        return

    key_suffix = _stable_widget_key(source_name)
    selection_key = f"triage_pick_{key_suffix}"
    reviewed_key = f"triage_reviewed_{key_suffix}"
    reviewed_state = st.session_state.get(reviewed_key, [])
    if isinstance(reviewed_state, set):
        reviewed_state = sorted(str(item) for item in reviewed_state)
    elif not isinstance(reviewed_state, list):
        reviewed_state = []
    st.session_state[reviewed_key] = [str(item) for item in reviewed_state]

    severity_options = ["全部"] + sorted(
        [str(x) for x in incidents["风险等级"].dropna().astype(str).unique().tolist()],
        key=_severity_rank,
        reverse=True,
    )
    type_options = ["全部"] + sorted([str(x) for x in incidents["安全分类"].dropna().astype(str).unique().tolist()])

    left_col, right_col = st.columns([0.8, 2.0], gap="large")

    with left_col:
        st.markdown("#### 事件队列")
        with st.expander("事件筛选", expanded=False):
            severity_choice = st.selectbox("风险等级", severity_options, key=f"triage_severity_{key_suffix}")
            type_choice = st.selectbox("事件类型", type_options, key=f"triage_type_{key_suffix}")
            keyword = st.text_input("关键词搜索", key=f"triage_keyword_{key_suffix}", placeholder="搜索事件标题、实体、关键词")
            sort_choice = st.selectbox("排序方式", ["按风险", "按时间", "按关联数"], key=f"triage_sort_{key_suffix}")

    filtered = incidents.copy()
    if severity_choice != "全部":
        filtered = filtered[filtered["风险等级"].astype(str) == severity_choice]
    if type_choice != "全部":
        filtered = filtered[filtered["安全分类"].astype(str) == type_choice]

    keyword_norm = str(keyword or "").strip().lower()
    if keyword_norm:
        def _contains(row: pd.Series) -> bool:
            hay = " ".join(
                [
                    str(row.get("事件标题", "") or ""),
                    str(row.get("一句话摘要", "") or ""),
                    str(row.get("影响范围", "") or ""),
                    str(row.get("关键实体", "") or ""),
                    " ".join([str(x) for x in row.get("命中关键词", [])]) if isinstance(row.get("命中关键词", []), list) else "",
                ]
            ).lower()
            return keyword_norm in hay

        filtered = filtered[filtered.apply(_contains, axis=1)]

    if sort_choice == "按时间":
        filtered = filtered.sort_values(["起始行号", "最高风险"], ascending=[False, False])
    elif sort_choice == "按关联数":
        filtered = filtered.sort_values(["告警数", "最高风险"], ascending=[False, False])
    else:
        filtered = filtered.sort_values(["风险等级排序", "最高风险", "平均风险", "告警数"], ascending=[False, False, False, False])

    with left_col:
        st.caption(f"当前命中 {len(filtered)} 条事件")
        st.markdown('<div class="triage-left">', unsafe_allow_html=True)

        if filtered.empty:
            st.info("当前筛选条件下没有待处理事件。")
            st.markdown("</div>", unsafe_allow_html=True)
            with right_col:
                st.info("请调整事件队列上方的筛选条件，或降低告警阈值后重试。")
            return

        available_ids = filtered["incident_id"].astype(str).tolist()
        if selection_key not in st.session_state:
            st.session_state[selection_key] = None
        if st.session_state[selection_key] not in available_ids:
            st.session_state[selection_key] = None

        for row_idx, row in filtered.reset_index(drop=True).iterrows():
            incident_id = str(row.get("incident_id", ""))
            selected = st.session_state.get(selection_key) == incident_id
            card_text = (
                f"[{row.get('风险等级', '高危')}]  {row.get('事件标题', '待定事件')}\n"
                f"{row.get('时间范围', '-')}"
            )
            if st.button(
                card_text,
                key=f"triage_card_{key_suffix}_{row_idx}_{_stable_widget_key(incident_id)}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state[selection_key] = incident_id
        st.markdown("</div>", unsafe_allow_html=True)

    selected_id = st.session_state.get(selection_key)
    if not selected_id:
        with right_col:
            st.info("请先从左侧事件队列中选择一条事件，系统会按“结论 → 支撑 → 证据 → 上下文”的顺序展开详情。")
        return
    chosen_rows = filtered[filtered["incident_id"].astype(str) == str(selected_id)]
    if chosen_rows.empty:
        with right_col:
            st.info("请从左侧事件队列中选择一个事件开始查看。")
        return

    incident = chosen_rows.iloc[0].to_dict()
    incident["rag_cases"] = _get_cached_incident_rag_cases(config, incident, source_name, top_k=5)
    incident_view = _trim_incident_for_llm(incident)
    st.session_state[f"triage_context_{source_name}"] = {**incident_view, "detail_class": str(incident.get("安全分类", ""))}

    source_ips = incident.get("攻击源IP", []) if isinstance(incident.get("攻击源IP", []), list) else []
    source_hint = "、".join(source_ips[:5]) if source_ips else str(incident.get("关键实体", "待进一步解析"))
    main_class = str(incident.get("安全分类", "") or "待定事件")
    attack_family = str(incident.get("攻击大类", "") or "待补充")
    risk_level = str(incident.get("风险等级", "") or "高危")
    time_range = str(incident.get("时间范围", "") or "-")
    impact_scope = str(incident.get("影响范围", "") or "待进一步确认")
    summary = str(incident.get("一句话摘要", "") or str(incident.get("模板解读", "") or "")).strip() or "当前事件已聚合完成，建议结合证据链继续复核。"
    action_text = str(incident.get("主建议处置", "")).strip() or "建议优先核对来源、账号、资产与时间窗口，确认是否需要人工升级处置。"
    fusion_total = float(incident.get("最高风险", 0.0) or 0.0)
    stat_score = float(incident.get("统计分均值", 0.0) or 0.0)
    temporal_score = float(incident.get("时序分均值", 0.0) or 0.0)
    semantic_score = float(incident.get("语义向量分均值", 0.0) or 0.0)
    dominant_name, dominant_score = max(
        [("统计视图", stat_score), ("时序视图", temporal_score), ("语义视图", semantic_score)],
        key=lambda x: x[1],
    )
    rag_cases = incident.get("rag_cases", []) if isinstance(incident.get("rag_cases", []), list) else []
    focus_logs = incident.get("模型关注热点", []) if isinstance(incident.get("模型关注热点", []), list) else []
    context_logs = incident.get("上下文日志", []) if isinstance(incident.get("上下文日志", []), list) else []
    keywords = incident.get("命中关键词", []) if isinstance(incident.get("命中关键词", []), list) else []

    with right_col:
        st.markdown("#### 当前事件详情")
        st.caption("先看结论，再按需查看融合解释、关键证据和相似参考。")

        with st.container(border=True):
            st.markdown(
                f"""
<div class="surface-card surface-card-warning" style="padding:18px 20px;margin-bottom:8px;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:8px;">
    <div>
      <div class="surface-card-title" style="color:#9a3412;margin-bottom:6px;">当前分析结论</div>
      <div class="surface-card-value" style="font-size:1.42rem;line-height:1.28;margin-bottom:0;">{risk_level}：疑似 {main_class}</div>
    </div>
    <div style="text-align:right;min-width:116px;">
      <div class="surface-card-title" style="margin-bottom:4px;">最高风险</div>
      <div class="surface-card-value" style="font-size:1.25rem;line-height:1.2;margin-bottom:0;">{fusion_total:.4f}</div>
    </div>
  </div>
  <div class="surface-card-text" style="margin-top:0;line-height:1.6;">{summary}</div>
  <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">
    <span class="badge-chip badge-chip-warning">分类：{attack_family}</span>
    <span class="badge-chip">关键实体：{source_hint}</span>
    <span class="badge-chip">时间范围：{time_range}</span>
    <span class="badge-chip">影响范围：{impact_scope}</span>
  </div>
</div>
<div class="surface-card surface-card-accent" style="padding:12px 14px;margin-bottom:10px;">
  <div class="surface-card-title" style="margin-bottom:5px;">建议动作</div>
  <div class="surface-card-text" style="color:#0f766e;font-weight:700;line-height:1.5;">{action_text}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:2px;width:100%;box-sizing:border-box;">
  <div class="surface-card" style="padding:10px 14px;min-height:68px;box-sizing:border-box;">
    <div class="surface-card-title" style="margin-bottom:5px;">关联告警数</div>
    <div class="surface-card-value" style="font-size:1.04rem;margin-bottom:0;line-height:1.25;">{int(incident.get('告警数', 0))}</div>
  </div>
  <div class="surface-card" style="padding:10px 14px;min-height:68px;box-sizing:border-box;">
    <div class="surface-card-title" style="margin-bottom:5px;">平均风险分</div>
    <div class="surface-card-value" style="font-size:1.04rem;margin-bottom:0;line-height:1.25;">{float(incident.get('平均风险', 0.0) or 0.0):.4f}</div>
  </div>
  <div class="surface-card" style="padding:10px 14px;min-height:68px;box-sizing:border-box;">
    <div class="surface-card-title" style="margin-bottom:5px;">主导视图</div>
    <div class="surface-card-value" style="font-size:1.04rem;line-height:1.3;margin-bottom:0;word-break:break-word;">{dominant_name}</div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        tab_diag, tab_evidence, tab_ref = st.tabs(["💡 融合诊断", "📂 关键证据", "🔍 相似参考"])

        with tab_diag:
            with st.container(border=True):
                st.markdown("##### 多视图融合解释")
                st.caption(f"主导视图：{dominant_name}（{dominant_score:.3f}）")
            prog_left, prog_right = st.columns([1.1, 0.9], gap="large")
            with prog_left:
                for label, score in [("统计视图", stat_score), ("时序视图", temporal_score), ("语义视图", semantic_score), ("融合总分", fusion_total)]:
                    st.markdown(f"<div style='font-size:13px;color:#6B7280;margin-bottom:4px;'><strong style='color:#374151;'>{label}</strong> {score:.3f}</div>", unsafe_allow_html=True)
                    st.progress(max(0, min(100, int(score * 100))))
            with prog_right:
                st.markdown(
                    f"""
<div class="surface-card">
  <div class="surface-card-title">融合判断摘要</div>
  <div class="surface-card-text">{_build_fusion_reason(incident)}</div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

        with tab_ref:
            with st.container(border=True):
                st.markdown("##### 相似案例支撑")
            if keywords:
                chips = "".join([f"<span class='badge-chip badge-chip-accent'>{kw}</span>" for kw in keywords[:8]])
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.caption("当前事件未提取出稳定关键词，以下案例主要基于事件摘要与关键日志检索。")
            _render_incident_rag_cards(rag_cases, section_title="Top-K 相似历史案例")

        with tab_evidence:
            with st.container(border=True):
                st.markdown("##### 关键证据")
            evidence_rows = focus_logs[:5] if focus_logs else context_logs[:5]
            if evidence_rows:
                for rank, item in enumerate(evidence_rows, start=1):
                    label = f"证据 {rank} · 日志 {int(item.get('line_num', 0) or 0)} · {str(item.get('时间', '-') or '-')} · {str(item.get('节点', '-') or '-')}"
                    with st.expander(label, expanded=False):
                        m1, m2, m3 = st.columns(3, gap="medium")
                        with m1:
                            st.metric("风险评分", f"{float(item.get('风险分', 0.0) or 0.0):.4f}")
                        with m2:
                            st.metric("行为异常度", f"{float(item.get('行为异常置信度', 0.0) or 0.0):.4f}")
                        with m3:
                            st.metric("内容风险度", f"{float(item.get('内容威胁置信度', 0.0) or 0.0):.4f}")
                        summary_text = str(item.get("异常点摘要", "") or "").strip() or "当前证据暂无额外摘要，可直接查看原始日志。"
                        st.markdown(
                            f"""
<div class="surface-card">
  <div class="surface-card-title">异常点摘要</div>
  <div class="surface-card-text">{summary_text}</div>
</div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.markdown("**原始日志**")
                        st.code(str(item.get("原始日志", "") or ""), language="text")
            else:
                st.info("当前事件没有可展示的关键证据。")

            with st.expander("查看原始上下文", expanded=False):
                if context_logs:
                    for item in context_logs:
                        st.markdown(f"**日志 {int(item.get('line_num', 0) or 0)}** · {str(item.get('时间', '-') or '-')} · {str(item.get('节点', '-') or '-')}")
                        st.code(str(item.get("原始日志", "") or ""), language="text")
                        template_text = str(item.get("原始模板", "") or "").strip()
                        if template_text:
                            st.caption("原始模板")
                            st.code(template_text, language="text")
                else:
                    st.info("暂无可展开的原始上下文。")

        with st.expander("导出与复核操作", expanded=False):
            reviewed_bucket = [str(item) for item in st.session_state.get(reviewed_key, [])]
            incident_marker = str(incident.get("incident_id", selected_id))
            incident_marker_key = _stable_widget_key(incident_marker)
            is_reviewed = incident_marker in reviewed_bucket
            action_export_text = (
                f"事件名称：{incident.get('事件标题', main_class)}\n"
                f"主分类：{main_class}\n"
                f"攻击大类：{attack_family}\n"
                f"最高风险分：{fusion_total:.4f}\n"
                f"时间范围：{incident.get('时间范围', '-')}\n"
                f"影响范围：{incident.get('影响范围', '-')}\n"
                f"关键实体：{incident.get('关键实体', '-')}\n"
                f"建议处置：{action_text}\n"
            )
            incident_export_text = action_export_text + "关键日志：\n" + "\n".join([f"- {str(x)}" for x in incident.get("关键异常日志", [])[:3]]) + "\n"
            a1, a2, a3 = st.columns(3)
            with a1:
                if st.button("标记为已复核" if not is_reviewed else "已完成复核", key=f"triage_review_{key_suffix}_{incident_marker_key}", use_container_width=True):
                    if incident_marker not in reviewed_bucket:
                        reviewed_bucket.append(incident_marker)
                    st.session_state[reviewed_key] = reviewed_bucket
            with a2:
                st.download_button(
                    "导出处置建议",
                    data=action_export_text,
                    file_name=f"{source_name}_incident_action.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key=f"triage_action_export_{key_suffix}_{incident_marker_key}",
                )
            with a3:
                st.download_button(
                    "导出事件摘要",
                    data=incident_export_text,
                    file_name=f"{source_name}_incident_summary.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key=f"triage_export_{key_suffix}_{incident_marker_key}",
                )
def render_incident_report_panel(config: Config, view_df: pd.DataFrame, source_name: str, llm_cfg: Dict[str, str]):
    st.markdown("#### 事件分析报告")
    st.caption("系统会先按“主分类 + 模板”聚合事件，再结合相似案例生成可导出的分析报告。" )
    incidents = _get_cached_incidents(view_df, source_name, max_groups=40)
    if incidents.empty:
        st.info("当前没有可生成事件分析报告的高危事件。")
        return

    display_df = incidents[["事件名称", "告警数", "最高风险", "平均风险", "起始行号", "结束行号"]].copy()
    with st.container(border=True):
        st.markdown("##### 事件列表")
        st.dataframe(display_df, use_container_width=True, height=260, hide_index=True)

    event_options = [f"#{i+1} | {name}" for i, name in enumerate(incidents["事件名称"].tolist())]
    chosen = st.selectbox("选择需要生成报告的事件", options=event_options, key=f"incident_pick_{source_name}")
    chosen_idx = int(str(chosen).split("|")[0].replace("#", "").strip()) - 1
    if chosen_idx < 0 or chosen_idx >= len(incidents):
        return

    incident = incidents.iloc[chosen_idx].to_dict()
    incident["rag_cases"] = _get_cached_incident_rag_cases(config, incident, source_name, top_k=3)
    incident_view = _trim_incident_for_llm(incident)
    attack_family = incident_view.get("attack_family", "") or "待补充"

    with st.container(border=True):
        st.markdown("##### 当前事件摘要")
        head_left, head_right = st.columns([1.25, 0.95], gap="large")
        with head_left:
            st.markdown(
                f"""
<div class="surface-card surface-card-warning">
  <div class="surface-card-title">事件名称</div>
  <div class="surface-card-value" style="font-size:1.22rem;line-height:1.45;">{incident['事件名称']}</div>
  <div style="margin-top:10px;">
    <span class="badge-chip badge-chip-warning">主分类 {incident['安全分类']}</span>
    <span class="badge-chip">攻击大类 {attack_family}</span>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )
        with head_right:
            top_metrics = st.columns(2, gap="medium")
            top_metrics[0].markdown(
                f"""
<div class="surface-card" style="padding:14px 16px; min-height:102px; margin-bottom:12px;">
  <div class="surface-card-title" style="margin-bottom:6px;">告警数</div>
  <div class="surface-card-value" style="font-size:1.15rem; margin-bottom:0;">{int(incident['告警数'])}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            top_metrics[1].markdown(
                f"""
<div class="surface-card" style="padding:14px 16px; min-height:102px; margin-bottom:12px;">
  <div class="surface-card-title" style="margin-bottom:6px;">最高风险</div>
  <div class="surface-card-value" style="font-size:1.15rem; margin-bottom:0;">{float(incident['最高风险']):.4f}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            bottom_metrics = st.columns(2, gap="medium")
            bottom_metrics[0].markdown(
                f"""
<div class="surface-card" style="padding:14px 16px; min-height:102px;">
  <div class="surface-card-title" style="margin-bottom:6px;">平均风险</div>
  <div class="surface-card-value" style="font-size:1.15rem; margin-bottom:0;">{float(incident['平均风险']):.4f}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            bottom_metrics[1].markdown(
                f"""
<div class="surface-card" style="padding:14px 16px; min-height:102px;">
  <div class="surface-card-title" style="margin-bottom:6px;">行号范围</div>
  <div class="surface-card-value" style="font-size:1.05rem; line-height:1.35; margin-bottom:0;">{int(incident['起始行号'])}-{int(incident['结束行号'])}</div>
</div>
                """,
                unsafe_allow_html=True,
            )

    rag_cases = incident.get("rag_cases", [])
    with st.container(border=True):
        st.markdown("##### 报告输入依据")
        with st.expander("查看输入上下文", expanded=False):
            st.json(incident_view)
        if isinstance(rag_cases, list) and rag_cases:
            with st.expander("查看相似案例依据（Top-3）", expanded=False):
                st.dataframe(pd.DataFrame(rag_cases), use_container_width=True, hide_index=True)

    judge_runtime = load_ai_judge(config.config, llm_cfg)
    status = judge_runtime.get_runtime_status() if hasattr(judge_runtime, "get_runtime_status") else {}
    with st.container(border=True):
        st.markdown("##### 生成设置")
        st.caption(
            f"引擎状态：{status.get('mode', '未知')} | 模型：{status.get('model', '未配置')} | "
            f"报告上限：{status.get('report_max_tokens', '-')} tokens | 信息：{status.get('reason', 'N/A')}"
        )
        if st.button("生成事件分析报告", key=f"incident_report_btn_{source_name}", type="primary"):
            if status.get("mode") != "llm":
                st.warning(f"LLM 服务不可用：{status.get('reason', '')}")
            else:
                with st.spinner("正在生成事件分析报告..."):
                    report = judge_runtime.generate_incident_report(incident_view)
                st.session_state[f"incident_report_{source_name}"] = report

    report_text = st.session_state.get(f"incident_report_{source_name}")
    if isinstance(report_text, str) and report_text.strip():
        with st.container(border=True):
            st.markdown("##### 报告结果")
            if report_text.startswith("LLM request failed") or report_text.startswith("LLM unavailable") or report_text.startswith("LLM 请求失败") or report_text.startswith("LLM 当前不可用"):
                st.error(report_text)
            else:
                st.write(report_text)
                export_base = f"{source_name}_incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                md_text = (
                    f"# 高危事件分析报告\n\n"
                    f"- 事件名称: {incident['事件名称']}\n"
                    f"- 主分类: {incident['安全分类']}\n"
                    f"- 告警数: {int(incident['告警数'])}\n"
                    f"- 最高风险: {float(incident['最高风险']):.4f}\n"
                    f"- 平均风险: {float(incident['平均风险']):.4f}\n"
                    f"- 行号范围: {int(incident['起始行号'])} - {int(incident['结束行号'])}\n\n"
                    f"## 报告正文\n\n{report_text}\n"
                )
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        "导出为 .txt",
                        data=report_text,
                        file_name=f"{export_base}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"incident_report_txt_{source_name}",
                    )
                with dl2:
                    st.download_button(
                        "导出为 .md",
                        data=md_text,
                        file_name=f"{export_base}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key=f"incident_report_md_{source_name}",
                    )


def render_qa_panel(config: Config, view_df: pd.DataFrame, source_name: str, llm_cfg: Dict[str, str]):
    st.markdown("#### AI 问答")
    st.caption("围绕单条高危日志做解释和处置建议，不改变主检测结果。")
    triage_context = st.session_state.get(f"triage_context_{source_name}", {})
    if isinstance(triage_context, dict) and triage_context.get("title"):
        with st.container(border=True):
            st.markdown("##### 当前事件上下文")
            context_left, context_right = st.columns([1.2, 1.0], gap="large")
            with context_left:
                source_ips = triage_context.get("source_ips", [])
                source_ip_text = "、".join(source_ips[:5]) if isinstance(source_ips, list) and source_ips else "待补充"
                st.markdown(
                    f"""
<div class="surface-card surface-card-accent">
  <div class="surface-card-title">事件名称</div>
  <div class="surface-card-value" style="font-size:1.2rem;line-height:1.45;">{triage_context.get('title', '')}</div>
  <div style="margin-top:10px;">
    <span class="badge-chip badge-chip-accent">主分类 {triage_context.get('main_class', '') or '待补充'}</span>
    <span class="badge-chip">攻击大类 {triage_context.get('attack_family', '') or '待补充'}</span>
  </div>
  <div class="surface-card-text" style="margin-top:12px;">攻击源 IP：{source_ip_text}</div>
</div>
                """,
                    unsafe_allow_html=True,
                )
            with context_right:
                seed_options = [
                    "请总结当前事件最关键的异常迹象，并给出处置优先级。",
                    "请根据当前事件写一段可执行的封禁与核查建议。",
                    "请结合相似案例解释为什么这起事件值得优先处理。",
                ]
                seed_pick = st.selectbox(
                    "推荐提问",
                    options=["自定义问题"] + seed_options,
                    index=0,
                    key=f"qa_seed_pick_{source_name}",
                )
                if seed_pick != "自定义问题":
                    st.session_state[f"qa_prompt_{source_name}"] = seed_pick

    alerts = view_df[view_df["is_alert"]].sort_values("risk_score", ascending=False)
    if alerts.empty:
        st.info("当前没有可疑日志可提问。")
        return

    options = alerts.head(100)
    seq_values = options["seq_index"].astype(int).tolist()
    chosen_seq = st.selectbox("选择高危序列", options=seq_values, key=f"qa_seq_{source_name}")
    chosen = options[options["seq_index"] == int(chosen_seq)].head(1)
    if chosen.empty:
        return
    row = chosen.iloc[0]

    with st.container(border=True):
        st.markdown("##### 当前日志摘要")
        info_left, info_right = st.columns([1.05, 1.15], gap="large")
        with info_left:
            st.markdown(
                f"""
<div class="surface-card">
  <div class="surface-card-title">日志定位</div>
  <div class="surface-card-value" style="font-size:1.2rem;">行号 {int(row['line_num'])}</div>
  <div style="margin-top:10px;">
    <span class="badge-chip">综合风险 {float(row['risk_score']):.4f}</span>
    <span class="badge-chip">统计 {float(row['stat_score']):.3f}</span>
    <span class="badge-chip">时序 {float(row['temporal_score']):.3f}</span>
    <span class="badge-chip">语义 {float(row['semantic_score']):.3f}</span>
  </div>
  <div class="surface-card-text" style="margin-top:12px;">{compact_log_preview(str(row.get('log_text', '')))}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
        with info_right:
            readable = make_template_readable(str(row.get("template", "")), max_len=260)
            st.markdown(
                f"""
<div class="surface-card surface-card-accent">
  <div class="surface-card-title">模板解读</div>
  <div class="surface-card-text">{readable}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("AI 仅对已筛出的高危日志做补充说明，不参与主检测阶段的风险打分。")

    with st.container(border=True):
        st.markdown("##### 原始证据")
        st.markdown("**原始日志**")
        st.code(str(row.get("log_text", ""))[:4000], language="text")
        with st.expander("查看原始模板", expanded=False):
            st.code(str(row.get("template", ""))[:2000], language="text")

    question = st.text_area(
        "提出具体诊断问题",
        value="请分析这条日志的异常点，并按优先级列出处理建议。",
        key=f"qa_prompt_{source_name}",
        height=100,
    )
    judge_runtime = load_ai_judge(config.config, llm_cfg)
    status = judge_runtime.get_runtime_status() if hasattr(judge_runtime, "get_runtime_status") else {}
    with st.container(border=True):
        st.markdown("##### 问答设置")
        st.caption(
            f"引擎状态：{status.get('mode', '未知')} | 模型：{status.get('model', '未配置')} | 信息：{status.get('reason', 'N/A')}"
        )
        if st.button("提交 AI 分析", key=f"qa_ask_{source_name}", type="primary"):
            if not str(question).strip():
                st.warning("请输入问题后再提交。")
            else:
                load_ai_judge.clear()
                judge_runtime = load_ai_judge(config.config, llm_cfg)
                status = judge_runtime.get_runtime_status() if hasattr(judge_runtime, "get_runtime_status") else {}
                if status.get("mode") != "llm":
                    st.warning(f"LLM 服务不可达：{status.get('reason', '')}")
                else:
                    with st.spinner("正在生成 AI 分析结果..."):
                        answer = judge_runtime.ask_about_log(
                            log_text=str(row.get("log_text", "")) or str(row.get("template", "")),
                            question=str(question).strip(),
                            context={
                                "risk_score": float(row.get("risk_score", 0.0)),
                                "stat_score": float(row.get("stat_score", 0.0)),
                                "temporal_score": float(row.get("temporal_score", 0.0)),
                                "semantic_score": float(row.get("semantic_score", 0.0)),
                                "incident_context": _trim_incident_for_llm(triage_context) if isinstance(triage_context, dict) else {},
                            },
                        )
                    if not str(answer or "").strip():
                        answer = "服务返回空响应，建议检查 Token 额度或网络策略配置。"
                    st.session_state[f"qa_answer_{source_name}"] = answer

    qa_text = st.session_state.get(f"qa_answer_{source_name}")
    if isinstance(qa_text, str) and qa_text.strip():
        with st.container(border=True):
            st.markdown("##### AI 分析结果")
            if qa_text.startswith("LLM request failed") or qa_text.startswith("LLM unavailable") or qa_text.startswith("LLM 请求失败") or qa_text.startswith("LLM 当前不可用"):
                st.error(qa_text)
            else:
                st.write(qa_text)


def _persist_ai_judge_config(config: Config, ai_cfg: Dict[str, Any]):
    config_path = Path(getattr(config, 'config_path', 'configs/config.yaml'))
    with open(config_path, 'r', encoding='utf-8') as f:
        payload = yaml.safe_load(f) or {}
    payload['ai_judge'] = ai_cfg
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
    refreshed = Config(str(config_path))
    config.config = refreshed.config


def _test_ai_judge_connection(judge: Any) -> Dict[str, str]:
    if hasattr(judge, 'test_connection'):
        return judge.test_connection()
    status = judge.get_runtime_status() if hasattr(judge, 'get_runtime_status') else {}
    client = getattr(judge, 'client', None)
    model = str(getattr(judge, 'model', '') or status.get('model', ''))
    provider = str(getattr(judge, 'provider', '') or status.get('provider', ''))
    profile = str(getattr(judge, 'profile_name', '') or status.get('profile', ''))
    base_url = str(status.get('base_url', '') or status.get('base_url_display', '') or '')
    if client is None:
        return {
            'success': 'false',
            'message': str(status.get('reason', 'LLM 当前不可用')),
            'provider': provider,
            'profile': profile,
            'model': model,
            'base_url': base_url,
        }
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=8,
            timeout=min(float(getattr(judge, 'request_timeout', 15) or 15), 15),
            messages=[
                {'role': 'system', 'content': 'Reply with OK only.'},
                {'role': 'user', 'content': 'OK'},
            ],
        )
        text = (resp.choices[0].message.content or '').strip()
        return {
            'success': 'true',
            'message': text or '连接成功',
            'provider': provider,
            'profile': profile,
            'model': model,
            'base_url': base_url,
        }
    except Exception as exc:
        return {
            'success': 'false',
            'message': str(exc),
            'provider': provider,
            'profile': profile,
            'model': model,
            'base_url': base_url,
        }


def _normalize_ai_judge_admin_config(ai_cfg: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(ai_cfg or {})
    default_profile = str(current.get('default_profile', '') or '').strip() or 'default'
    fallback_provider = str(current.get('provider', 'deepseek') or 'deepseek').strip() or 'deepseek'
    fallback_base_url = str(current.get('base_url', '') or '').strip()
    if not fallback_base_url and fallback_provider == 'deepseek':
        fallback_base_url = 'https://api.deepseek.com'
    fallback_profile = {
        'provider': fallback_provider,
        'model': str(current.get('model', 'deepseek-chat') or 'deepseek-chat').strip() or 'deepseek-chat',
        'base_url': fallback_base_url,
        'api_key': str(current.get('api_key', '') or '').strip(),
        'temperature': float(current.get('temperature', 0.2) or 0.2),
        'max_tokens': int(current.get('max_tokens', 300) or 300),
        'qa_max_tokens': int(current.get('qa_max_tokens', 3000) or 3000),
        'report_max_tokens': int(current.get('report_max_tokens', 8000) or 8000),
        'request_timeout': float(current.get('request_timeout', 45) or 45),
    }
    raw_profiles = dict(current.get('profiles', {}) or {})
    profiles = {}
    for name, payload in raw_profiles.items():
        profile_name = str(name or '').strip()
        if not profile_name:
            continue
        data = dict(payload or {})
        provider = str(data.get('provider', fallback_profile['provider']) or fallback_profile['provider']).strip() or fallback_profile['provider']
        base_url = str(data.get('base_url', fallback_profile['base_url']) or '').strip()
        if not base_url and provider == 'deepseek':
            base_url = 'https://api.deepseek.com'
        profiles[profile_name] = {
            'provider': provider,
            'model': str(data.get('model', fallback_profile['model']) or fallback_profile['model']).strip() or fallback_profile['model'],
            'base_url': base_url,
            'api_key': str(data.get('api_key', fallback_profile['api_key']) or '').strip(),
            'temperature': float(data.get('temperature', fallback_profile['temperature']) or fallback_profile['temperature']),
            'max_tokens': int(data.get('max_tokens', fallback_profile['max_tokens']) or fallback_profile['max_tokens']),
            'qa_max_tokens': int(data.get('qa_max_tokens', fallback_profile['qa_max_tokens']) or fallback_profile['qa_max_tokens']),
            'report_max_tokens': int(data.get('report_max_tokens', fallback_profile['report_max_tokens']) or fallback_profile['report_max_tokens']),
            'request_timeout': float(data.get('request_timeout', fallback_profile['request_timeout']) or fallback_profile['request_timeout']),
        }
    if default_profile not in profiles:
        profiles[default_profile] = dict(fallback_profile)
    default_payload = dict(profiles.get(default_profile, fallback_profile) or fallback_profile)
    return {
        'use_llm': bool(current.get('use_llm', False)),
        'default_profile': default_profile,
        'profiles': profiles,
        'provider': str(default_payload.get('provider', fallback_profile['provider']) or fallback_profile['provider']),
        'model': str(default_payload.get('model', fallback_profile['model']) or fallback_profile['model']),
        'base_url': str(default_payload.get('base_url', fallback_profile['base_url']) or ''),
        'api_key': str(default_payload.get('api_key', fallback_profile['api_key']) or ''),
        'temperature': float(default_payload.get('temperature', fallback_profile['temperature']) or fallback_profile['temperature']),
        'max_tokens': int(default_payload.get('max_tokens', fallback_profile['max_tokens']) or fallback_profile['max_tokens']),
        'qa_max_tokens': int(default_payload.get('qa_max_tokens', fallback_profile['qa_max_tokens']) or fallback_profile['qa_max_tokens']),
        'report_max_tokens': int(default_payload.get('report_max_tokens', fallback_profile['report_max_tokens']) or fallback_profile['report_max_tokens']),
        'request_timeout': float(default_payload.get('request_timeout', fallback_profile['request_timeout']) or fallback_profile['request_timeout']),
    }


def _profile_widget_key(profile_name: str, field_name: str) -> str:
    return f"api_admin_field__{profile_name}__{field_name}"


def _clear_api_admin_form_state():
    for key in list(st.session_state.keys()):
        if key.startswith('api_admin_field__') or key in {'api_admin_use_llm', 'api_admin_test_result'}:
            del st.session_state[key]


def _queue_api_admin_profile_pick(profile_name: str):
    st.session_state['api_admin_pending_profile_pick'] = str(profile_name or '').strip()


def _queue_api_admin_widget_value(key: str, value: Any):
    pending = dict(st.session_state.get('api_admin_pending_widget_values', {}) or {})
    pending[str(key)] = value
    st.session_state['api_admin_pending_widget_values'] = pending


def _get_profile_form_payload(profile_name: str, profile_cfg: Dict[str, Any], fallback_cfg: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(
        st.session_state.get(
            _profile_widget_key(profile_name, 'provider'),
            profile_cfg.get('provider', fallback_cfg.get('provider', 'deepseek')),
        )
        or 'deepseek'
    ).strip() or 'deepseek'
    model = str(
        st.session_state.get(
            _profile_widget_key(profile_name, 'model'),
            profile_cfg.get('model', fallback_cfg.get('model', 'deepseek-chat')),
        )
        or 'deepseek-chat'
    ).strip() or 'deepseek-chat'
    base_url = str(
        st.session_state.get(
            _profile_widget_key(profile_name, 'base_url'),
            profile_cfg.get('base_url', fallback_cfg.get('base_url', '')),
        )
        or ''
    ).strip()
    if not base_url and provider == 'deepseek':
        base_url = 'https://api.deepseek.com'
    return {
        'provider': provider,
        'model': model,
        'base_url': base_url,
        'api_key': str(
            st.session_state.get(
                _profile_widget_key(profile_name, 'api_key'),
                profile_cfg.get('api_key', fallback_cfg.get('api_key', '')),
            )
            or ''
        ).strip(),
        'temperature': float(
            st.session_state.get(
                _profile_widget_key(profile_name, 'temperature'),
                profile_cfg.get('temperature', fallback_cfg.get('temperature', 0.2)),
            )
            or 0.2
        ),
        'max_tokens': int(
            st.session_state.get(
                _profile_widget_key(profile_name, 'max_tokens'),
                profile_cfg.get('max_tokens', fallback_cfg.get('max_tokens', 300)),
            )
            or 300
        ),
        'qa_max_tokens': int(
            st.session_state.get(
                _profile_widget_key(profile_name, 'qa_max_tokens'),
                profile_cfg.get('qa_max_tokens', fallback_cfg.get('qa_max_tokens', 3000)),
            )
            or 3000
        ),
        'report_max_tokens': int(
            st.session_state.get(
                _profile_widget_key(profile_name, 'report_max_tokens'),
                profile_cfg.get('report_max_tokens', fallback_cfg.get('report_max_tokens', 8000)),
            )
            or 8000
        ),
        'request_timeout': float(
            st.session_state.get(
                _profile_widget_key(profile_name, 'request_timeout'),
                profile_cfg.get('request_timeout', fallback_cfg.get('request_timeout', 45)),
            )
            or 45
        ),
    }


def _sync_api_admin_draft_state(draft_ai_cfg: Dict[str, Any], selected_profile: str) -> Dict[str, Any]:
    normalized = _normalize_ai_judge_admin_config(draft_ai_cfg)
    profiles = {name: dict(payload or {}) for name, payload in dict(normalized.get('profiles', {}) or {}).items()}
    fallback_cfg = dict(profiles.get(normalized.get('default_profile', 'default'), {}) or normalized)
    current_profile_cfg = dict(profiles.get(selected_profile, fallback_cfg) or fallback_cfg)
    profiles[selected_profile] = _get_profile_form_payload(selected_profile, current_profile_cfg, fallback_cfg)
    normalized['profiles'] = profiles
    normalized['use_llm'] = bool(st.session_state.get('api_admin_use_llm', normalized.get('use_llm', False)))
    default_profile = str(normalized.get('default_profile', '') or 'default').strip() or 'default'
    default_cfg = dict(profiles.get(default_profile, profiles.get(selected_profile, fallback_cfg)) or fallback_cfg)
    normalized['provider'] = str(default_cfg.get('provider', normalized.get('provider', 'deepseek')) or 'deepseek')
    normalized['model'] = str(default_cfg.get('model', normalized.get('model', 'deepseek-chat')) or 'deepseek-chat')
    normalized['base_url'] = str(default_cfg.get('base_url', normalized.get('base_url', '')) or '')
    normalized['api_key'] = str(default_cfg.get('api_key', normalized.get('api_key', '')) or '')
    normalized['temperature'] = float(default_cfg.get('temperature', normalized.get('temperature', 0.2)) or 0.2)
    normalized['max_tokens'] = int(default_cfg.get('max_tokens', normalized.get('max_tokens', 300)) or 300)
    normalized['qa_max_tokens'] = int(default_cfg.get('qa_max_tokens', normalized.get('qa_max_tokens', 3000)) or 3000)
    normalized['report_max_tokens'] = int(default_cfg.get('report_max_tokens', normalized.get('report_max_tokens', 8000)) or 8000)
    normalized['request_timeout'] = float(default_cfg.get('request_timeout', normalized.get('request_timeout', 45)) or 45)
    return normalized


def render_api_admin_panel(config: Config, llm_cfg: Dict[str, str], threshold: float, seq_len: int, rag_query_count: int):
    snapshot = build_ai_judge_admin_snapshot(config.config, llm_cfg)
    pending_widget_values = dict(st.session_state.pop('api_admin_pending_widget_values', {}) or {})
    for widget_key, widget_value in pending_widget_values.items():
        st.session_state[str(widget_key)] = widget_value
    persisted_ai_cfg = _normalize_ai_judge_admin_config(config.get('ai_judge', {}) or {})
    if not isinstance(st.session_state.get('api_admin_draft_ai_cfg'), dict):
        st.session_state['api_admin_draft_ai_cfg'] = persisted_ai_cfg
        st.session_state['api_admin_use_llm'] = bool(persisted_ai_cfg.get('use_llm', False))
    draft_ai_cfg = _normalize_ai_judge_admin_config(st.session_state.get('api_admin_draft_ai_cfg', persisted_ai_cfg))
    st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg

    st.markdown('### 配置管理')
    st.caption('管理 AI 研判服务、Profile、连接测试和 YAML 持久化配置。侧边栏只用于本次会话快速覆盖。')

    notice = st.session_state.pop('api_admin_notice', None)
    if isinstance(notice, dict) and str(notice.get('message', '')).strip():
        level = str(notice.get('level', 'info') or 'info').lower()
        if level == 'success':
            st.success(str(notice.get('message', '')))
        elif level == 'warning':
            st.warning(str(notice.get('message', '')))
        elif level == 'error':
            st.error(str(notice.get('message', '')))
        else:
            st.info(str(notice.get('message', '')))

    metric_cols = st.columns(4)
    metric_cols[0].metric('AI 状态', '启用' if bool(snapshot.get('use_llm', False)) else '关闭')
    metric_cols[1].metric('默认 Profile', snapshot.get('default_profile', '-'))
    metric_cols[2].metric('当前模型', snapshot.get('model', '-'))
    metric_cols[3].metric('报告输出上限', f"{int(snapshot.get('report_max_tokens', 8000) or 8000):,}")

    with st.expander('当前生效配置', expanded=False):
        st.json(
            {
                'active_profile': snapshot.get('active_profile', ''),
                'default_profile': snapshot.get('default_profile', ''),
                'provider': snapshot.get('provider', ''),
                'use_llm': bool(snapshot.get('use_llm', False)),
                'model': snapshot.get('model', ''),
                'base_url': snapshot.get('base_url', ''),
                'api_key_masked': snapshot.get('api_key_masked', ''),
                'temperature': snapshot.get('temperature', 0.2),
                'max_tokens': snapshot.get('max_tokens', 300),
                'qa_max_tokens': snapshot.get('qa_max_tokens', 3000),
                'report_max_tokens': snapshot.get('report_max_tokens', 8000),
                'request_timeout': snapshot.get('request_timeout', 45),
            },
            expanded=False,
        )

    draft_profiles = {name: dict(payload or {}) for name, payload in dict(draft_ai_cfg.get('profiles', {}) or {}).items()}
    profile_names = list(draft_profiles.keys()) or ['default']
    pending_profile_pick = str(st.session_state.pop('api_admin_pending_profile_pick', '') or '').strip()
    selected_profile_state = pending_profile_pick or str(st.session_state.get('api_admin_profile_pick', '') or '').strip()
    if selected_profile_state not in profile_names:
        selected_profile_state = str(draft_ai_cfg.get('default_profile', profile_names[0]) or profile_names[0])
    st.session_state['api_admin_profile_pick'] = selected_profile_state
    if 'api_admin_use_llm' not in st.session_state:
        st.session_state['api_admin_use_llm'] = bool(draft_ai_cfg.get('use_llm', False))

    with st.container(border=True):
        st.markdown('##### Profile 管理')
        pick_col, summary_col = st.columns([1.2, 0.8], gap='large')
        with pick_col:
            selected_profile = st.selectbox('当前编辑 Profile', options=profile_names, index=profile_names.index(selected_profile_state))
            st.session_state['api_admin_profile_pick'] = selected_profile
        with summary_col:
            st.caption(f"默认 Profile：{draft_ai_cfg.get('default_profile', '-')}")
            st.caption(f"已配置数量：{len(profile_names)}")
            st.caption(f"当前 Provider：{draft_profiles.get(selected_profile, {}).get('provider', '-')}")

        with st.expander('新增 Profile', expanded=False):
            st.text_input('新增 Profile 名称', key='api_admin_new_profile_name', placeholder='如 openai_gpt4o')
            add_profile_clicked = st.button('从当前 Profile 复制新增', key='api_admin_add_profile_btn', use_container_width=True)
        if add_profile_clicked:
            selected_profile = str(st.session_state.get('api_admin_profile_pick', profile_names[0]) or profile_names[0])
            draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
            draft_profiles = {name: dict(payload or {}) for name, payload in dict(draft_ai_cfg.get('profiles', {}) or {}).items()}
            new_profile_name = str(st.session_state.get('api_admin_new_profile_name', '') or '').strip()
            if not new_profile_name:
                st.session_state['api_admin_notice'] = {'level': 'warning', 'message': '请先输入新的 Profile 名称。'}
            elif new_profile_name in draft_profiles:
                st.session_state['api_admin_notice'] = {'level': 'warning', 'message': f'Profile “{new_profile_name}” 已存在。'}
            else:
                draft_profiles[new_profile_name] = dict(draft_profiles.get(selected_profile, {}))
                draft_ai_cfg['profiles'] = draft_profiles
                draft_ai_cfg = _normalize_ai_judge_admin_config(draft_ai_cfg)
                st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg
                _clear_api_admin_form_state()
                _queue_api_admin_widget_value('api_admin_use_llm', bool(draft_ai_cfg.get('use_llm', False)))
                _queue_api_admin_profile_pick(new_profile_name)
                _queue_api_admin_widget_value('api_admin_new_profile_name', '')
                st.session_state['api_admin_notice'] = {'level': 'success', 'message': f'已新增 Profile：{new_profile_name}。'}
                st.rerun()
        op_col1, op_col2, op_col3 = st.columns(3, gap='small')
        if op_col1.button('设为默认 Profile', key='api_admin_default_profile_btn', use_container_width=True):
            selected_profile = str(st.session_state.get('api_admin_profile_pick', profile_names[0]) or profile_names[0])
            draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
            draft_ai_cfg['default_profile'] = selected_profile
            draft_ai_cfg = _normalize_ai_judge_admin_config(draft_ai_cfg)
            st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg
            _queue_api_admin_widget_value('api_admin_use_llm', bool(draft_ai_cfg.get('use_llm', False)))
            st.session_state['api_admin_notice'] = {'level': 'success', 'message': f'默认 Profile 已切换为 {selected_profile}。'}
            st.rerun()
        if op_col2.button('删除当前 Profile', key='api_admin_delete_profile_btn', use_container_width=True):
            selected_profile = str(st.session_state.get('api_admin_profile_pick', profile_names[0]) or profile_names[0])
            draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
            draft_profiles = {name: dict(payload or {}) for name, payload in dict(draft_ai_cfg.get('profiles', {}) or {}).items()}
            if len(draft_profiles) <= 1:
                st.session_state['api_admin_notice'] = {'level': 'warning', 'message': '至少保留一个 Profile，当前项不能删除。'}
            else:
                draft_profiles.pop(selected_profile, None)
                remaining_profiles = list(draft_profiles.keys())
                if str(draft_ai_cfg.get('default_profile', '') or '') == selected_profile:
                    draft_ai_cfg['default_profile'] = remaining_profiles[0]
                draft_ai_cfg['profiles'] = draft_profiles
                draft_ai_cfg = _normalize_ai_judge_admin_config(draft_ai_cfg)
                st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg
                _clear_api_admin_form_state()
                _queue_api_admin_widget_value('api_admin_use_llm', bool(draft_ai_cfg.get('use_llm', False)))
                _queue_api_admin_profile_pick(str(draft_ai_cfg.get('default_profile', remaining_profiles[0]) or remaining_profiles[0]))
                st.session_state['api_admin_notice'] = {'level': 'success', 'message': f'已删除 Profile：{selected_profile}。'}
                st.rerun()
        if op_col3.button('放弃草稿并重载 YAML', key='api_admin_reload_yaml_btn', use_container_width=True):
            st.session_state['api_admin_draft_ai_cfg'] = persisted_ai_cfg
            _clear_api_admin_form_state()
            _queue_api_admin_widget_value('api_admin_use_llm', bool(persisted_ai_cfg.get('use_llm', False)))
            _queue_api_admin_profile_pick(str(persisted_ai_cfg.get('default_profile', 'default') or 'default'))
            _queue_api_admin_widget_value('api_admin_new_profile_name', '')
            st.session_state['api_admin_notice'] = {'level': 'success', 'message': '已从 YAML 重新加载草稿配置。'}
            st.rerun()

        summary_rows = []
        for profile_name, payload in draft_profiles.items():
            profile_payload = dict(payload or {})
            summary_rows.append(
                {
                    'Profile': profile_name,
                    '默认': '是' if profile_name == str(draft_ai_cfg.get('default_profile', '') or '') else '',
                    'Provider': str(profile_payload.get('provider', '-')),
                    'Model': str(profile_payload.get('model', '-')),
                    'Base URL': str(profile_payload.get('base_url', '-')),
                    'API Key': '已配置' if str(profile_payload.get('api_key', '') or '').strip() else '未配置',
                    'QA 上限': int(profile_payload.get('qa_max_tokens', 3000) or 3000),
                    '报告上限': int(profile_payload.get('report_max_tokens', 8000) or 8000),
                    'Timeout': float(profile_payload.get('request_timeout', 45) or 45),
                }
            )
        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

    selected_profile = str(st.session_state.get('api_admin_profile_pick', profile_names[0]) or profile_names[0])
    selected_profile_cfg = dict(draft_profiles.get(selected_profile, draft_ai_cfg) or draft_ai_cfg)
    provider_options = ['deepseek', 'openai', 'custom']
    provider_value = str(selected_profile_cfg.get('provider', 'deepseek') or 'deepseek')
    provider_index = provider_options.index(provider_value) if provider_value in provider_options else provider_options.index('custom')

    with st.container(border=True):
        st.markdown('##### 编辑当前 Profile')
        st.caption('这里编辑的是草稿配置；只有点击“保存到 YAML 并应用”后，才会持久化并刷新前端实际运行配置。')
        st.markdown('###### 连接信息')
        c1, c2 = st.columns(2)
        c1.selectbox('服务类型', provider_options, index=provider_index, key=_profile_widget_key(selected_profile, 'provider'))
        c2.toggle('默认启用 LLM', key='api_admin_use_llm')
        st.text_input('模型名称', value=str(selected_profile_cfg.get('model', draft_ai_cfg.get('model', 'deepseek-chat')) or ''), key=_profile_widget_key(selected_profile, 'model'))
        base_url_default = str(selected_profile_cfg.get('base_url', draft_ai_cfg.get('base_url', '')) or '')
        if not base_url_default and provider_value == 'deepseek':
            base_url_default = 'https://api.deepseek.com'
        st.text_input('Base URL', value=base_url_default, key=_profile_widget_key(selected_profile, 'base_url'))
        st.text_input('API Key', value=str(selected_profile_cfg.get('api_key', draft_ai_cfg.get('api_key', '')) or ''), type='password', key=_profile_widget_key(selected_profile, 'api_key'))

        st.markdown('###### 生成参数')
        p1, p2, p3 = st.columns(3)
        p1.number_input('Temperature', min_value=0.0, max_value=2.0, value=float(selected_profile_cfg.get('temperature', draft_ai_cfg.get('temperature', 0.2)) or 0.2), step=0.1, key=_profile_widget_key(selected_profile, 'temperature'))
        p2.number_input('批量判断上限', min_value=100, max_value=8000, value=int(selected_profile_cfg.get('max_tokens', draft_ai_cfg.get('max_tokens', 300)) or 300), step=100, key=_profile_widget_key(selected_profile, 'max_tokens'))
        p3.number_input('请求超时秒数', min_value=10.0, max_value=300.0, value=float(selected_profile_cfg.get('request_timeout', draft_ai_cfg.get('request_timeout', 90)) or 90), step=5.0, key=_profile_widget_key(selected_profile, 'request_timeout'))
        q1, q2 = st.columns(2)
        q1.number_input('AI 问答输出上限', min_value=300, max_value=12000, value=int(selected_profile_cfg.get('qa_max_tokens', draft_ai_cfg.get('qa_max_tokens', 3000)) or 3000), step=100, key=_profile_widget_key(selected_profile, 'qa_max_tokens'))
        q2.number_input('事件报告输出上限', min_value=800, max_value=20000, value=int(selected_profile_cfg.get('report_max_tokens', draft_ai_cfg.get('report_max_tokens', 8000)) or 8000), step=200, key=_profile_widget_key(selected_profile, 'report_max_tokens'))
        st.caption('批量判断上限用于 JSON 分类；AI 问答和事件报告上限决定页面中文分析最多可输出多少 token。')

    draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
    st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg
    draft_profiles = {name: dict(payload or {}) for name, payload in dict(draft_ai_cfg.get('profiles', {}) or {}).items()}
    current_profile_cfg = dict(draft_profiles.get(selected_profile, {}) or {})

    with st.container(border=True):
        st.markdown('##### 测试与保存')
        st.info('保存会写入 configs/config.yaml，并在当前前端中立即应用；API Key 会以明文保存在 YAML 中，提交仓库前请检查。')
        test_col, save_col = st.columns(2)
        with test_col:
            if st.button('测试当前 Profile 连接', key='api_admin_test_btn', type='secondary', use_container_width=True):
                draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
                st.session_state['api_admin_draft_ai_cfg'] = draft_ai_cfg
                current_profile_cfg = dict(draft_ai_cfg.get('profiles', {}).get(selected_profile, {}) or {})
                test_cfg = dict(config.config)
                test_cfg['ai_judge'] = _normalize_ai_judge_admin_config(draft_ai_cfg)
                test_judge = load_ai_judge.__wrapped__(
                    test_cfg,
                    {
                        'use_llm': bool(draft_ai_cfg.get('use_llm', False)),
                        'provider': str(current_profile_cfg.get('provider', 'deepseek') or 'deepseek'),
                        'profile': selected_profile,
                        'model': str(current_profile_cfg.get('model', '') or ''),
                        'base_url': str(current_profile_cfg.get('base_url', '') or ''),
                        'api_key': str(current_profile_cfg.get('api_key', '') or ''),
                        'qa_max_tokens': int(current_profile_cfg.get('qa_max_tokens', 3000) or 3000),
                        'report_max_tokens': int(current_profile_cfg.get('report_max_tokens', 8000) or 8000),
                    },
                )
                st.session_state['api_admin_test_result'] = _test_ai_judge_connection(test_judge)
        with save_col:
            if st.button('保存到 YAML 并应用', key='api_admin_save_btn', type='primary', use_container_width=True):
                draft_ai_cfg = _sync_api_admin_draft_state(draft_ai_cfg, selected_profile)
                persisted_payload = _normalize_ai_judge_admin_config(draft_ai_cfg)
                _persist_ai_judge_config(config, persisted_payload)
                st.session_state['api_admin_draft_ai_cfg'] = persisted_payload
                _clear_api_admin_form_state()
                _queue_api_admin_widget_value('api_admin_use_llm', bool(persisted_payload.get('use_llm', False)))
                _queue_api_admin_profile_pick(selected_profile)
                load_ai_judge.clear()
                st.session_state['api_admin_saved'] = True
                st.rerun()

        result = st.session_state.get('api_admin_test_result')
        if isinstance(result, dict) and result:
            if str(result.get('success', 'false')).lower() == 'true':
                st.success(f"连接成功：{result.get('profile', selected_profile)} / {result.get('model', '-')}")
            else:
                st.error(f"连接失败：{result.get('message', '未知错误')}")

        if st.session_state.get('api_admin_saved'):
            st.success('API 多 Profile 配置已写入 YAML，并已在当前前端会话中刷新。')
            st.session_state['api_admin_saved'] = False


def render_detection_view(
    config: Config,
    result_df: pd.DataFrame,
    threshold: float,
    x_seq: np.ndarray,
    source_name: str,
    llm_cfg: Dict[str, str],
    rag_query_count: int,
    workbench_mode: str,
    seq_len: int,
):
    view_df = _get_cached_view_df(config, result_df, threshold, source_name)
    render_hero_and_kpis(view_df, threshold)

    mode_name = str(workbench_mode or '')
    is_overview_mode = mode_name.endswith('安全态势大盘')
    is_event_mode = mode_name.endswith('事件分析')
    is_explain_mode = mode_name.endswith('模型解释') or mode_name.endswith('技术分析')

    if is_overview_mode:
        mode_desc = '查看整体风险水平、告警趋势和分类分布。'
    elif is_event_mode:
        mode_desc = '查看高风险事件列表，逐条确认并完成分析处置。'
    elif is_explain_mode:
        mode_desc = '查看多视图模型解释、相似案例检索和 AI 问答。'
    else:
        mode_desc = '查看当前检测参数、模型配置和 RAG 状态。'

    hint = '当前模块：<strong>{}</strong>。{}'.format(mode_name, mode_desc)
    st.markdown(f'<div class="section-hint">{hint}</div>', unsafe_allow_html=True)

    if is_overview_mode:
        render_overview(view_df, threshold)

    elif is_event_mode:
        st.markdown('### 事件分析中心')
        st.caption('查看高风险事件的详细信息、证据核查和处理建议。')
        render_triage_center(config, view_df, source_name, llm_cfg)

    elif is_explain_mode:
        hunt_tab_tech, hunt_tab_rag, hunt_tab_qa = st.tabs(
            ['模型解释', '相似案例检索', 'AI 安全助手']
        )
        with hunt_tab_tech:
            render_technical_view(config, view_df, x_seq, threshold)
        with hunt_tab_rag:
            render_rag_panel(config, view_df, rag_query_count=rag_query_count, source_name=source_name)
        with hunt_tab_qa:
            render_incident_report_panel(config, view_df, source_name, llm_cfg)
            st.markdown('---')
            render_qa_panel(config, view_df, source_name, llm_cfg)

    else:
        render_api_admin_panel(config, llm_cfg, threshold, seq_len, rag_query_count)

    st.markdown('---')
    save_key = f"save_{_stable_widget_key(source_name)}"
    if st.button(f'💾 导出检测结果与批次报告（{source_name}）', key=save_key, type='primary'):
        csv_path, json_path, md_path, html_path = write_report(config, source_name, view_df)
        st.success(f'已导出 4 份文件：{csv_path}、{json_path}、{md_path}、{html_path}')
