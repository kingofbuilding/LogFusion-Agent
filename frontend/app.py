from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.helpers import prepare_input_df
from frontend.panels import render_detection_view
from frontend.runtime import build_ai_judge_admin_snapshot, run_pipeline
from frontend.theme import inject_ui_theme
from src.utils import Config, Logger


def build_llm_sidebar(config: Config) -> dict:
    base_snapshot = build_ai_judge_admin_snapshot(config.config)
    profile_options = list(base_snapshot.get("profile_names", []) or [])
    default_profile = str(base_snapshot.get("default_profile", "default") or "default")
    if default_profile not in profile_options:
        profile_options.insert(0, default_profile)

    if "llm_selected_profile" not in st.session_state:
        st.session_state["llm_selected_profile"] = default_profile
    if st.session_state["llm_selected_profile"] not in profile_options:
        st.session_state["llm_selected_profile"] = default_profile

    st.sidebar.markdown("### AI 研判")
    selected_profile = st.sidebar.selectbox(
        "当前 AI Profile",
        profile_options,
        index=profile_options.index(st.session_state["llm_selected_profile"]),
        key="llm_selected_profile",
    )
    snapshot = build_ai_judge_admin_snapshot(config.config, {"profile": selected_profile})
    st.sidebar.caption(f"当前模型：{snapshot.get('model', '-')}")

    provider_options = ["deepseek", "openai", "custom"]
    default_provider = str(snapshot.get("provider", "deepseek") or "deepseek")
    if default_provider not in provider_options:
        default_provider = "custom"

    default_base_url = str(snapshot.get("base_url", "") or "").strip()
    if not default_base_url and default_provider == "deepseek":
        default_base_url = "https://api.deepseek.com"
    default_api_key = (
        str(config.get("ai_judge.profiles", {}).get(selected_profile, {}).get("api_key", "")).strip()
        or str(config.get("ai_judge.api_key", "")).strip()
        or os.getenv("AI_JUDGE_API_KEY", "").strip()
        or os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )

    if st.session_state.get("llm_override_profile") != selected_profile:
        st.session_state["llm_base_url_input"] = default_base_url
        st.session_state["llm_api_key_input"] = default_api_key
        st.session_state["llm_override_profile"] = selected_profile
    else:
        if "llm_base_url_input" not in st.session_state:
            st.session_state["llm_base_url_input"] = default_base_url
        if "llm_api_key_input" not in st.session_state:
            st.session_state["llm_api_key_input"] = default_api_key

    use_llm = st.sidebar.toggle("启用 AI 分析", value=bool(snapshot.get("use_llm", False)))
    with st.sidebar.expander("AI 服务高级配置", expanded=False):
        use_override = st.toggle("临时覆盖当前 Profile", value=False)
        if use_override:
            provider = st.selectbox("服务类型", provider_options, index=provider_options.index(default_provider))
            llm_model = st.text_input("模型名称", value=str(snapshot.get("model", "deepseek-chat") or "deepseek-chat"))
            llm_base_url = st.text_input("Base URL", key="llm_base_url_input")
            llm_api_key = st.text_input("API Key", type="password", key="llm_api_key_input")
        else:
            provider = str(snapshot.get("provider", default_provider) or default_provider)
            llm_model = str(snapshot.get("model", "") or "")
            llm_base_url = str(snapshot.get("base_url", "") or "")
            llm_api_key = default_api_key
            st.caption("当前使用侧边栏选择的已保存 Profile。需要临时调试时再开启覆盖。")
        st.caption("Profile 选择只影响当前会话；如需修改或保存默认配置，请前往“配置管理”。")

    return {
        "use_llm": bool(use_llm),
        "provider": provider,
        "profile": str(selected_profile or default_profile),
        "model": llm_model,
        "base_url": llm_base_url,
        "api_key": llm_api_key,
        "override": bool(use_override),
    }


def render_demo_landing():
    st.markdown(
        """
<div class="hero-wrap">
  <div class="hero-eyebrow">多源日志智能分析平台</div>
  <div class="hero-title">日志异常检测与事件研判系统</div>
  <div class="hero-sub">面向通用系统、安全与服务日志的多视图异常检测平台，结合统计、时序、语义信号完成风险融合，并通过相似案例与 AI 报告辅助研判。</div>
  <div class="hero-meta"><strong>分析流程</strong>：上传日志 → 开始检测 → 查看态势 → 分析事件 → 导出报告</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">多视图检测</div>
    <div class="kpi-value kpi-value-accent">3 Views</div>
    <div class="kpi-hint">统计视图、时序视图、语义视图共同描述日志风险。</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">融合判别</div>
    <div class="kpi-value">XGBoost</div>
    <div class="kpi-hint">融合多路风险分数，输出最终告警排序。</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">事件分析</div>
    <div class="kpi-value">Evidence</div>
    <div class="kpi-hint">聚合高危日志，展示主判断、相似案例和原始证据。</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">辅助研判</div>
    <div class="kpi-value">RAG + AI</div>
    <div class="kpi-hint">检索相似安全案例，并生成可导出的分析报告。</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def main():
    config = Config()
    logger = Logger.get_logger("frontend", config)

    st.set_page_config(page_title="IntelliLog 日志检测平台", page_icon="🛡️", layout="wide")
    inject_ui_theme()

    st.sidebar.caption("IntelliLog")
    st.sidebar.markdown("### 工作台")
    default_threshold = float(config.get("frontend.controls.default_threshold", 0.68))
    default_seq_len = int(config.get("data.temporal_sequence_length", config.get("data.sequence_length", 50)))
    default_rag_query_count = int(config.get("frontend.controls.default_rag_query_count", 12))
    threshold = float(default_threshold)
    seq_len = int(default_seq_len)
    rag_query_count = int(default_rag_query_count)
    workbench_mode = st.sidebar.radio(
        "工作台模式",
        [
            "安全态势大盘",
            "事件分析",
            "模型解释",
            "配置管理",
        ],
        index=0,
    )
    with st.sidebar.expander("高级参数", expanded=False):
        st.caption("默认情况下建议直接使用系统推荐配置。只有在调试、论文复现或对比实验时，才建议手动调整。")
        threshold = st.slider("风险告警阈值", 0.0, 1.0, float(default_threshold), 0.01)
        seq_len = st.number_input("时序窗口长度", 10, 200, int(default_seq_len), 1)
        rag_query_count = st.slider("RAG 检索模板数", 3, 30, int(default_rag_query_count), 1)

    st.sidebar.markdown("---")
    llm_cfg = build_llm_sidebar(config)

    logger.info(
        f"frontend params threshold={threshold}, seq_len={seq_len}, use_llm={llm_cfg['use_llm']}, workbench_mode={workbench_mode}"
    )

    st.markdown("### 上传日志")
    st.caption("支持 `.log`、`.txt`、`.jsonl`、`.json`、`.csv`、`.tsv`、`.xlsx`、`.parquet`、`.gz`、`.zip`。")
    uploaded = st.file_uploader(
        "选择待检测的日志文件",
        type=["log", "txt", "text", "jsonl", "json", "csv", "tsv", "xlsx", "xls", "parquet", "gz", "zip"],
        key="upload_any",
    )

    if uploaded is not None and st.button("开始检测", key="run_detect_any", type="primary"):
        try:
            input_df = prepare_input_df(config, uploaded)
            result_df, x_seq = run_pipeline(config, input_df, int(seq_len), float(threshold))
            st.session_state["result_any"] = result_df
            st.session_state["xseq_any"] = x_seq
            st.session_state["source_any"] = f"upload_{datetime.now().strftime('%H%M%S')}"
        except Exception as exc:
            st.error(f"处理失败: {exc}")

    result_df = st.session_state.get("result_any")
    x_seq = st.session_state.get("xseq_any")
    source_name = st.session_state.get("source_any", "upload")

    if isinstance(result_df, pd.DataFrame) and isinstance(x_seq, np.ndarray):
        if result_df.empty:
            st.warning("样本不足，无法构建有效序列。建议扩大日志窗口或降低序列长度。")
        else:
            render_detection_view(
                config=config,
                result_df=result_df,
                threshold=float(threshold),
                x_seq=x_seq,
                source_name=source_name,
                llm_cfg=llm_cfg,
                rag_query_count=int(rag_query_count),
                workbench_mode=workbench_mode,
                seq_len=int(seq_len),
            )
    else:
        render_demo_landing()


if __name__ == "__main__":
    main()
