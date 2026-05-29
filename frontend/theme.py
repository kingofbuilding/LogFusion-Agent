from __future__ import annotations

import streamlit as st

def inject_ui_theme():
    st.markdown(
        """
<style>
:root {
  --bg-app: #f6f8fb;
  --bg-sidebar: #fbfcfe;
  --bg-elevated: #ffffff;
  --card-bg: #ffffff;
  --card-muted: #f8fafc;
  --ink: #0f172a;
  --muted: #64748b;
  --accent: #1d4ed8;
  --accent-soft: #eff6ff;
  --danger: #dc2626;
  --warn: #d97706;
  --ok: #059669;
  --border-color: #e2e8f0;
  --border-strong: #cbd5e1;
  --shadow-sm: 0 6px 18px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 10px 24px rgba(15, 23, 42, 0.06);
  --radius-sm: 12px;
  --radius-md: 16px;
  --radius-lg: 20px;
}

html, body, [class*="css"] {
  font-family: "Inter", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--ink);
}

[data-testid="stAppViewContainer"] {
  background: var(--bg-app);
}

[data-testid="stSidebar"] {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
  margin-top: 0.35rem;
  margin-bottom: 0.55rem;
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.01em;
}

[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h3 {
  text-align: left;
  margin-left: 10px;
}

[data-testid="stHeader"] {
  background: transparent;
}

.block-container {
  padding-top: 2rem;
  padding-bottom: 3rem;
}

.hero-wrap {
  background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.98) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--ink);
  padding: 24px 28px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin-bottom: 14px;
}

.hero-title {
  font-size: 1.72rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 10px;
  line-height: 1.2;
}

.hero-sub {
  color: #334155;
  font-size: 0.98rem;
  line-height: 1.7;
}

.hero-meta {
  margin-top: 14px;
  color: var(--muted);
  font-size: 0.9rem;
}

.hero-meta strong {
  color: var(--ink);
  font-weight: 700;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin: 0 0 24px 0;
}

.kpi-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px;
  box-shadow: var(--shadow-sm);
}

.kpi-label {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.kpi-value {
  color: var(--ink);
  font-size: 1.72rem;
  font-weight: 700;
  line-height: 1.1;
}

.kpi-value-accent {
  color: var(--accent);
}

.kpi-hint {
  color: var(--muted);
  font-size: 0.84rem;
  margin-top: 10px;
  line-height: 1.6;
}

.surface-card {
  padding: 18px 20px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
}

.surface-card-accent {
  background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(239,246,255,0.72) 100%);
  border: 1px solid rgba(191, 219, 254, 0.95);
}

.surface-card-warning {
  background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(255,247,237,0.86) 100%);
  border: 1px solid rgba(253, 186, 116, 0.48);
}

.surface-card-title {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.surface-card-value {
  font-size: 1.55rem;
  line-height: 1.15;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 10px;
}

.surface-card-text {
  font-size: 0.94rem;
  line-height: 1.75;
  color: #334155;
}

.badge-chip {
  display: inline-block;
  margin: 0 8px 8px 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.badge-chip-accent {
  background: var(--accent-soft);
  color: var(--accent);
}

.badge-chip-success {
  background: #ecfdf5;
  color: #166534;
}

.badge-chip-warning {
  background: #fff7ed;
  color: #9a3412;
}

.badge-chip-danger {
  background: #fee2e2;
  color: #b91c1c;
}

.stTabs [data-baseweb="tab-list"] {
  gap: 6px;
  background: #f8fafc;
  padding: 5px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
}

.stTabs [data-baseweb="tab"] {
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-weight: 600;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
  background: var(--bg-elevated);
  color: var(--ink);
  box-shadow: none;
}

[data-testid="stMetric"] {
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 10px 12px;
  min-height: 92px;
}

[data-testid="stMetricLabel"] {
  color: var(--muted);
  font-size: 0.85rem;
}

[data-testid="stMetricValue"] {
  color: var(--ink);
  font-size: 1.4rem !important;
  font-weight: 700 !important;
}

.stProgress > div > div > div > div {
  height: 8px;
}

[data-testid="stCaptionContainer"] {
  color: #6B7280;
}

[data-testid="stExpander"] {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-elevated);
  box-shadow: none;
}

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 1px 8px rgba(15, 23, 42, 0.04);
}

[data-testid="stVerticalBlock"] [data-testid="stMarkdownContainer"] code {
  background: #eff6ff;
  color: var(--accent);
}

button[kind="primary"] {
  background: #0f172a !important;
  border: 1px solid #0f172a !important;
}

button[kind="secondary"] {
  border-color: var(--border-strong) !important;
}

.section-hint {
  background: rgba(255,255,255,0.92);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 12px 16px;
  color: #334155;
  font-size: 0.94rem;
  line-height: 1.65;
  margin-bottom: 1rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )
