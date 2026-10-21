from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent import EventStore, InvestigationAgent
from src.agent.adapters import upstream_detector, upstream_retriever
from src.agent.planner import LLMPlanner
from src.agent.tools import InvestigationTools


def render_agent_workbench():
    st.title("LogFusion-Agent")
    st.subheader("证据驱动的安全日志调查智能体")
    st.caption("第一版聚焦 SSH 集中失败 → 后续成功登录 → 账户活动核查。支持合成演示和自有日志。")
    source = st.radio("日志来源", ["合成 SSH 演示", "上传日志"], horizontal=True, key="agent_source")
    if source == "合成 SSH 演示":
        path = ROOT / "data/demo/ssh_investigation.jsonl"
        data, name = path.read_bytes(), path.name
        st.info("演示日志全部为合成数据，IP 使用文档保留地址，包含同 IP 不同账号/主机的干扰事件。")
    else:
        upload = st.file_uploader("上传 UTF-8 日志（最多 20 MiB / 100000 条）", type=["log", "txt", "jsonl", "json", "csv"], key="agent_upload")
        if upload is None:
            return
        data, name = upload.getvalue(), upload.name
    try:
        store = EventStore.from_bytes(data, name)
    except (ValueError, UnicodeError, KeyError) as exc:
        st.error(f"无法读取日志：{type(exc).__name__}。请检查格式、大小以及 message 字段。")
        return
    fingerprint = hashlib.sha256(data + name.encode()).hexdigest()
    if st.session_state.get("agent_input_hash") != fingerprint:
        st.session_state.pop("agent_result", None)
        st.session_state["agent_input_hash"] = fingerprint
    coverage = store.coverage()
    left, middle, right = st.columns(3)
    left.metric("输入日志", coverage["events"])
    middle.metric("带完整时间", coverage["timestamped_events"])
    right.metric("时间未知", coverage["missing_timestamps"])
    with st.expander("查看原始日志"):
        st.dataframe([e.to_dict() for e in store.events[:100]], use_container_width=True)
        st.caption("预览最多 100 条；调查工具查询完整输入。")
    with st.form("agent_investigation_form"):
        goal = st.text_area("调查目标", "检查是否存在 SSH 暴力破解，以及是否出现后续成功登录和账户活动。", max_chars=2000)
        mode = st.selectbox("运行方式", ["规则调查演示（无需密钥）", "LLM Agent（自主选择工具）"])
        st.caption("LLM 模式会将调查目标及工具返回的部分日志发送到配置的模型服务；密钥只从本地环境读取。")
        col1, col2 = st.columns(2)
        with col1:
            detector = st.checkbox("接入原项目已训练检测模型", value=False)
        with col2:
            vector_rag = st.checkbox("使用原项目向量 RAG 索引", value=False)
        with st.expander("调查预算"):
            max_steps = st.slider("最大工具决策轮数", 4, 40, 16)
            max_seconds = st.slider("时间预算（秒）", 20, 300, 90)
            max_tokens = st.slider("Token 停止阈值", 2000, 60000, 24000, step=2000)
        submitted = st.form_submit_button("开始调查", type="primary")
    if submitted:
        st.session_state.pop("agent_result", None)
        try:
            planner = LLMPlanner.from_env(timeout=min(20, max_seconds)) if mode.startswith("LLM") else None
            tools = InvestigationTools(store, detector=upstream_detector() if detector else None,
                                       retriever=upstream_retriever() if vector_rag else None)
            with st.status("正在调查日志…", expanded=True) as status:
                result = InvestigationAgent(store, planner=planner, tools=tools, max_steps=max_steps,
                                            max_seconds=max_seconds, max_tokens=max_tokens).run(
                    goal, on_step=lambda step: st.write(f"步骤 {step['step']} · {step['tool']} · {'失败' if step.get('error') else '完成'}"))
                status.update(label=f"调查状态：{result.status} · {result.stop_reason}",
                              state="complete" if result.status == "completed" else "error", expanded=False)
            st.session_state["agent_result"] = result
        except Exception as exc:
            st.error(f"调查未能启动：{type(exc).__name__}。请检查密钥、可选依赖及模型/索引是否已准备。")
    result = st.session_state.get("agent_result")
    if result is None:
        return
    st.divider()
    st.write(f"调查编号：{result.run_id} · 模式：{result.mode} · 耗时：{result.elapsed_seconds}s · Tokens：{result.tokens_used}")
    st.write("调查目标：", result.goal)
    if result.status != "completed":
        st.warning(f"调查未正常完成，以下为部分结果。停止原因：{result.stop_reason}")
    findings_tab, timeline_tab, trace_tab = st.tabs(["调查发现", "证据时间线", "工具轨迹"])
    with findings_tab:
        for finding in result.findings:
            st.write(finding.statement)
            st.caption(finding.interpretation)
            st.code(", ".join(finding.evidence_ids) or "暂无足够证据")
        with st.expander("参考案例：仅作解释，不代表本次事件事实"):
            for case in result.case_references:
                st.write(case["case_id"], case["title"])
        with st.expander("不确定性与边界", expanded=True):
            for limitation in result.limitations:
                st.write("• " + limitation)
    with timeline_tab:
        for e in sorted(result.evidence, key=lambda e: (not bool(e["timestamp"]), e["timestamp"], e["line"])):
            with st.expander(f"{e['timestamp'] or '时间未知'} | {e['event_type']} | {e['event_id']}"):
                st.write("来源：", e["source"], "行/记录：", e["line"])
                st.code(e["raw"], language="text")
    with trace_tab:
        for t in result.trace:
            with st.expander(f"{t['step']}. {t['tool']}"):
                st.json(t)
    col1, col2 = st.columns(2)
    col1.download_button("下载调查报告 Markdown", result.to_markdown(), f"{result.run_id}.md", mime="text/markdown")
    col2.download_button("下载完整证据与轨迹 JSON", json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                         f"{result.run_id}.json", mime="application/json")


def main():
    st.set_page_config(page_title="LogFusion-Agent", page_icon="🛡️", layout="wide")
    render_agent_workbench()


if __name__ == "__main__":
    main()
