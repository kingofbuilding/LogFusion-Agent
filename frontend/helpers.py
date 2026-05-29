from __future__ import annotations

import gzip
import json
import re
import zipfile
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.data_processing.drain_parser import DrainParser
from src.utils import Config

ATTACK_TYPE_CN = {
    "Credential Access": "凭证访问",
    "Initial Access": "初始入侵",
    "Execution": "恶意执行",
    "Privilege Escalation": "权限提升",
    "Lateral Movement": "横向移动",
    "Discovery": "侦察探测",
    "Defense Evasion": "防御绕过",
    "Persistence": "持久化",
    "Exfiltration": "数据外传",
    "Command and Control": "命令与控制",
    "System Reliability": "系统稳定性异常",
    "Unknown": "未知类型",
}

CASE_GROUP_CN = {
    "security_attack": "安全攻击案例",
    "system_anomaly": "系统异常案例",
    "unknown": "未分类案例",
}

TITLE_CN = {
    "SSH brute force": "SSH 暴力破解",
    "Unauthorized access attempt": "未授权访问尝试",
    "SQL injection pattern": "SQL 注入特征",
    "XSS injection pattern": "XSS 注入特征",
    "Privilege escalation activity": "权限提升行为",
    "Lateral movement sign": "横向移动迹象",
    "Suspicious PowerShell execution": "可疑 PowerShell 执行",
    "Port scan behavior": "端口扫描行为",
    "Credential brute-force sign": "凭证暴力尝试",
    "Unauthorized access sign": "未授权访问迹象",
    "Privilege escalation sign": "权限提升迹象",
    "SQL injection sign": "SQL 注入迹象",
    "XSS injection sign": "XSS 注入迹象",
    "Suspicious script execution": "可疑脚本执行",
    "Port scan sign": "端口扫描迹象",
    "Generic suspicious pattern": "通用可疑行为",
    "Network interruption during log pipeline": "日志链路网络中断",
    "HDFS replication timeout": "HDFS 副本超时",
    "IO stream exception": "IO 流异常",
    "HDFS metadata inconsistency sign": "HDFS 元数据不一致迹象",
    "DataNode block pipeline anomaly": "DataNode 块处理链路异常",
    "HDFS block transfer interruption": "HDFS 块传输中断",
    "DataNode IO stream exception": "DataNode IO 流异常",
    "NameNode metadata inconsistency": "NameNode 元数据不一致",
}

ADVICE_CN = {
    "Block source IPs and enable MFA.": "\u5c01\u7981\u9ad8\u98ce\u9669\u6765\u6e90 IP\uff0c\u5e76\u542f\u7528\u591a\u56e0\u7d20\u8ba4\u8bc1\u3002",
    "Limit source IP, enable MFA, and audit weak credentials.": "\u9650\u5236\u9ad8\u98ce\u9669\u6765\u6e90 IP\uff0c\u542f\u7528 MFA\uff0c\u5e76\u5ba1\u8ba1\u5f31\u53e3\u4ee4\u4e0e\u9ad8\u98ce\u9669\u8d26\u53f7\u3002",
    "Review authorization boundary and account policy.": "\u6838\u67e5\u6388\u6743\u8fb9\u754c\u3001\u8bbf\u95ee\u63a7\u5236\u7b56\u7565\u4e0e\u8d26\u53f7\u5b89\u5168\u7b56\u7565\u3002",
    "Review access policy boundaries and account permissions.": "\u6838\u67e5\u8bbf\u95ee\u7b56\u7565\u8fb9\u754c\u4e0e\u8d26\u53f7\u6743\u9650\u914d\u7f6e\u3002",
    "Audit sudoers and privileged operations.": "\u5ba1\u8ba1 sudoers \u914d\u7f6e\u3001\u7279\u6743\u64cd\u4f5c\u94fe\u8def\u4e0e\u9ad8\u5371\u547d\u4ee4\u6267\u884c\u3002",
    "Harden WAF and DB query parameterization.": "\u52a0\u56fa WAF \u89c4\u5219\uff0c\u5e76\u68c0\u67e5\u6570\u636e\u5e93\u53c2\u6570\u5316\u67e5\u8be2\u4e0e\u8f93\u5165\u6821\u9a8c\u3002",
    "Enable WAF and parameterized queries, audit DB error logs.": "\u542f\u7528 WAF \u4e0e\u53c2\u6570\u5316\u67e5\u8be2\uff0c\u5e76\u5ba1\u8ba1\u6570\u636e\u5e93\u9519\u8bef\u65e5\u5fd7\u3002",
    "Enable CSP and output encoding.": "\u542f\u7528 CSP\uff0c\u5e76\u7edf\u4e00\u8f93\u51fa\u7f16\u7801\u4e0e\u8f93\u5165\u8fc7\u6ee4\u7b56\u7565\u3002",
    "Apply output encoding and CSP, strengthen input validation.": "\u5b9e\u65bd\u8f93\u51fa\u7f16\u7801\u4e0e CSP \u7b56\u7565\uff0c\u5e76\u52a0\u5f3a\u8f93\u5165\u6821\u9a8c\u3002",
    "Apply least privilege and audit sudoers and command chains.": "\u843d\u5b9e\u6700\u5c0f\u6743\u9650\u539f\u5219\uff0c\u5e76\u5ba1\u8ba1 sudoers \u4e0e\u7279\u6743\u547d\u4ee4\u94fe\u3002",
    "Restrict script execution and monitor command lines.": "\u9650\u5236\u811a\u672c\u6267\u884c\u6743\u9650\uff0c\u5e76\u91cd\u70b9\u76d1\u63a7\u547d\u4ee4\u884c\u4e0e\u5b50\u8fdb\u7a0b\u94fe\u8def\u3002",
    "Rate-limit or block scanner sources.": "\u5bf9\u626b\u63cf\u6e90\u5b9e\u65bd\u9650\u901f\u3001\u5c01\u7981\uff0c\u5e76\u7ee7\u7eed\u8ddf\u8e2a\u5176\u540e\u7eed\u63a2\u6d4b\u884c\u4e3a\u3002",
    "Manual review with context is required.": "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002",
    "Check node network path and connection retry policy.": "\u68c0\u67e5\u8282\u70b9\u7f51\u7edc\u94fe\u8def\u72b6\u6001\u4e0e\u91cd\u8bd5\u7b56\u7565\u914d\u7f6e\u3002",
    "Check replication queue pressure and DataNode availability.": "\u68c0\u67e5\u526f\u672c\u961f\u5217\u538b\u529b\u3001DataNode \u53ef\u7528\u6027\u4e0e\u96c6\u7fa4\u8d1f\u8f7d\u3002",
    "Check disk/IO health and JVM network IO behavior.": "\u68c0\u67e5\u78c1\u76d8 IO \u5065\u5eb7\u72b6\u6001\u4e0e JVM \u7f51\u7edc IO \u884c\u4e3a\u3002",
    "Inspect NameNode metadata state and block reports.": "\u6838\u67e5 NameNode \u5143\u6570\u636e\u72b6\u6001\u4e0e\u5757\u4e0a\u62a5\u60c5\u51b5\u3002",
    "Inspect DataNode pipeline and storage node pressure.": "\u68c0\u67e5 DataNode \u5904\u7406\u94fe\u8def\u4e0e\u5b58\u50a8\u8282\u70b9\u538b\u529b\u3002",
    "Check network stability and DataNode link health.": "\u68c0\u67e5\u7f51\u7edc\u7a33\u5b9a\u6027\u4e0e DataNode \u94fe\u8def\u5065\u5eb7\u72b6\u6001\u3002",
    "Inspect replication queue and cluster load balance.": "\u68c0\u67e5\u526f\u672c\u961f\u5217\u79ef\u538b\u60c5\u51b5\u4e0e\u96c6\u7fa4\u8d1f\u8f7d\u5747\u8861\u72b6\u6001\u3002",
    "Audit disk IO pressure and verify storage hardware state.": "\u5ba1\u8ba1\u78c1\u76d8 IO \u538b\u529b\u5e76\u6838\u67e5\u5b58\u50a8\u786c\u4ef6\u72b6\u6001\u3002",
    "Verify NameNode metadata consistency and replay state.": "\u6838\u67e5 NameNode \u5143\u6570\u636e\u4e00\u81f4\u6027\u4e0e\u6062\u590d\u56de\u653e\u72b6\u6001\u3002",
}

TITLE_CN.update({
    "Suspicious SSH successful login": "可疑 SSH 成功登录",
    "Suspicious SSH session establishment": "可疑 SSH 会话建立",
    "Privileged audit command execution": "特权审计命令执行",
    "Restricted web resource probing": "受限 Web 资源探测",
    "Web scanner fingerprint activity": "Web 扫描器指纹活动",
    "Content negotiation probing": "内容协商探测",
    "SSH excessive login attempts": "SSH 超限登录尝试",
    "SSH root login success": "SSH root 账户成功登录",
    "SSH service account successful login": "SSH 服务账号成功登录",
    "SSH publickey login from unusual source": "异常来源 SSH 公钥登录",
    "SSH disconnect churn after authentication": "认证后 SSH 异常断连",
    "SSH account probing and user enumeration": "SSH 账号探测与用户枚举",
    "Web admin path enumeration": "Web 管理路径探测",
    "Web login brute-force pattern": "Web 登录暴力尝试",
    "PHP script probing": "PHP 脚本探测",
    "Sensitive resource denial probing": "敏感资源拒绝访问探测",
    "Audit command execution chain": "审计命令执行链异常",
    "Sensitive account file access in audit logs": "审计日志中的敏感账户文件访问",
    "Sudo chain anomaly": "sudo 链异常",
    "OpenVPN remote access establishment": "OpenVPN 远程接入建立",
    "OpenVPN reconnect churn": "OpenVPN 反复重连异常",
    "Apache malformed request spray": "Apache 畸形请求喷洒",
    "Web error trigger after scanner probe": "扫描后触发的 Web 错误",
    "Prompt injection attempt against AI agent": "针对 AI 代理的提示词注入尝试",
    "Abnormal web access": "异常 Web 访问",
    "WPScan web scan": "WPScan Web 扫描",
    "Linux privilege escalation audit": "Linux 提权审计痕迹",
    "Web path and script probing": "Web 路径与脚本探测",
    "Restricted resource probing": "受限资源探测",
    "Nmap scripted probe": "Nmap 脚本化探测",
    "Suspicious successful login session": "可疑成功登录会话",
    "Authentication chain anomaly": "认证链异常",
})
ADVICE_CN.update({
    "Verify login user, source IP, login time, and post-login command activity; disable or lock the account if unauthorized.": "\u6838\u5bf9\u767b\u5f55\u7528\u6237\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u95f4\u4e0e\u540e\u7eed\u4f1a\u8bdd\u547d\u4ee4\uff0c\u5982\u975e\u6388\u6743\u767b\u5f55\u5e94\u7acb\u5373\u9501\u5b9a\u6216\u7981\u7528\u8d26\u53f7\u3002",
    "Correlate with preceding authentication logs and audit commands executed in the session; review lateral movement traces.": "\u7ed3\u5408\u524d\u5e8f\u8ba4\u8bc1\u65e5\u5fd7\u4e0e\u4f1a\u8bdd\u5185\u6267\u884c\u547d\u4ee4\u8fdb\u884c\u5173\u8054\u5206\u6790\uff0c\u91cd\u70b9\u68c0\u67e5\u662f\u5426\u5b58\u5728\u6a2a\u5411\u79fb\u52a8\u75d5\u8ff9\u3002",
    "Review audit trail, sudo chain, privileged binaries, and sensitive file changes; tighten sudoers and privileged group membership.": "\u91cd\u70b9\u5ba1\u67e5 audit \u8f68\u8ff9\u3001sudo \u94fe\u8def\u3001\u7279\u6743\u4e8c\u8fdb\u5236\u4e0e\u654f\u611f\u6587\u4ef6\u53d8\u66f4\uff0c\u5e76\u6536\u7d27 sudoers \u4e0e\u7279\u6743\u7ec4\u6743\u9650\u3002",
    "Inspect requested paths, tighten Apache or WAF rules, and rate-limit or block probing clients.": "\u68c0\u67e5\u88ab\u8bf7\u6c42\u8d44\u6e90\u8def\u5f84\uff0c\u6536\u7d27 Apache/WAF \u89c4\u5219\uff0c\u5e76\u5bf9\u63a2\u6d4b\u5ba2\u6237\u7aef\u5b9e\u65bd\u9650\u901f\u6216\u5c01\u7981\u3002",
    "Block or rate-limit scanner IPs, review exposed admin paths and plugins, and correlate with WAF or reverse proxy logs.": "\u5c01\u7981\u6216\u9650\u901f\u626b\u63cf\u6e90 IP\uff0c\u68c0\u67e5\u66b4\u9732\u7684\u7ba1\u7406\u8def\u5f84\u4e0e\u63d2\u4ef6\uff0c\u5e76\u7ed3\u5408 WAF \u6216\u53cd\u5411\u4ee3\u7406\u65e5\u5fd7\u8fdb\u884c\u6838\u5bf9\u3002",
    "Review suspicious request paths and file extensions, verify Apache content negotiation settings, and investigate repeated probing from the same client.": "\u68c0\u67e5\u53ef\u7591\u8bf7\u6c42\u8def\u5f84\u4e0e\u6269\u5c55\u540d\uff0c\u6838\u67e5 Apache content negotiation \u914d\u7f6e\uff0c\u5e76\u8ffd\u8e2a\u540c\u4e00\u5ba2\u6237\u7aef\u7684\u91cd\u590d\u63a2\u6d4b\u884c\u4e3a\u3002",
})

def _consistency_votes_by_quantile(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=int)

    work = df.copy()
    thresholds = {}
    for col in ["stat_score", "temporal_score", "semantic_score"]:
        series = pd.to_numeric(work.get(col), errors="coerce")
        if series.notna().any():
            q = float(series.quantile(0.90))
            thresholds[col] = max(q, float(series.median()))
        else:
            thresholds[col] = 1.0

    votes = pd.Series(0, index=work.index, dtype=int)
    for col, thr in thresholds.items():
        series = pd.to_numeric(work.get(col), errors="coerce").fillna(0.0)
        votes = votes + (series >= thr).astype(int)
    return votes


def render_hero_and_kpis(view_df: pd.DataFrame, threshold: float):
    if view_df is None or view_df.empty:
        return
    alerts = int(view_df["is_alert"].sum())
    total = int(len(view_df))
    ratio = (alerts / max(1, total)) * 100.0
    severe = int((view_df["风险层级"] == "严重").sum())
    high = int((view_df["风险层级"] == "高危").sum())
    mean_risk = float(view_df["risk_score"].mean())
    max_risk = float(view_df["risk_score"].max())

    alert_view = view_df[view_df["is_alert"]].copy()
    if alert_view.empty:
        incident_count = 0
        incident_hint = "当前没有达到阈值的高危事件"
    else:
        group_cols = [c for c in ["安全分类", "template"] if c in alert_view.columns]
        if group_cols:
            incident_count = int(alert_view.groupby(group_cols, dropna=False).ngroups)
        else:
            incident_count = int(len(alert_view))
        incident_hint = "按分类与模板聚合的待处理事件"

    st.markdown(
        f"""
<div class="hero-wrap">
  <div class="hero-eyebrow">多源日志智能分析平台</div>
  <div class="hero-title">日志异常检测结果总览</div>
  <div class="hero-sub">统计视图、时序视图、语义视图共同形成风险分数，适配安全、系统与服务日志的异常发现和事件研判。</div>
  <div class="hero-meta"><strong>多视图融合</strong> · <strong>相似案例辅助</strong> · 当前判定阈值 <strong>{threshold:.2f}</strong></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">告警总量</div>
    <div class="kpi-value">{alerts:,}</div>
    <div class="kpi-hint">总序列 {total:,} · 占比 {ratio:.2f}%</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">严重 / 高危</div>
    <div class="kpi-value"><span style="color:#FF4B4B">{severe}</span> / <span style="color:#FF4B4B">{high}</span></div>
    <div class="kpi-hint">严重与高危样本需优先排查</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">平均风险</div>
    <div class="kpi-value" style="color:#FFA500">{mean_risk:.3f}</div>
    <div class="kpi-hint">峰值风险 {max_risk:.3f}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">待处理事件</div>
    <div class="kpi-value kpi-value-accent">{incident_count:,}</div>
    <div class="kpi-hint">{incident_hint}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

def build_sequences(template_ids: np.ndarray, seq_len: int) -> Tuple[np.ndarray, np.ndarray]:
    if len(template_ids) < seq_len:
        return np.empty((0, seq_len), dtype=np.int64), np.empty((0,), dtype=np.int64)
    sequences = []
    ends = []
    for i in range(0, len(template_ids) - seq_len + 1):
        sequences.append(template_ids[i : i + seq_len])
        ends.append(i + seq_len - 1)
    return np.array(sequences, dtype=np.int64), np.array(ends, dtype=np.int64)


def build_sequence_timestamps(df: pd.DataFrame, seq_len: int) -> Optional[np.ndarray]:
    if df is None or df.empty or seq_len <= 1:
        return None
    candidates = ["timestamp", "time", "datetime", "event_time", "event_ts", "ts"]
    cols = {str(c).lower(): str(c) for c in df.columns}
    col = None
    for key in candidates:
        if key in cols:
            col = cols[key]
            break
    if col is None:
        return None

    s = df[col]
    num = pd.to_numeric(s, errors="coerce")
    if float(num.notna().mean()) >= 0.8:
        vals = num.astype(float).values
        med = np.nanmedian(vals)
        if np.isfinite(med) and med > 1e12:
            vals = vals / 1000.0
    else:
        dt = pd.to_datetime(s, errors="coerce", utc=True)
        if float(dt.notna().mean()) < 0.5:
            return None
        vals = (dt.astype("int64") / 1e9).astype(float).values

    n = len(vals) - seq_len + 1
    if n <= 0:
        return None
    mat = np.zeros((n, seq_len), dtype=float)
    for i in range(n):
        mat[i] = vals[i : i + seq_len]
    return mat





def risk_level(score: float) -> str:
    s = float(score)
    if s >= 0.85:
        return "\u4e25\u91cd"
    if s >= 0.65:
        return "\u9ad8\u5371"
    if s >= 0.45:
        return "\u4e2d\u5371"
    return "\u4f4e\u98ce\u9669"


def interpret_template_security(template_text: str) -> Tuple[str, str, str]:
    t = str(template_text or "").lower()

    def has_any(keywords: List[str]) -> bool:
        return any(k in t for k in keywords)

    ssh_limit = ["maximum login attempts exceeded", "too many authentication failures"]
    ssh_failed = ["failed password", "authentication failure", "invalid user", "user not known"]
    ssh_enum = ["user unknown", "unknown user", "check pass", "illegal user", "invalid user"]
    ssh_root_login = ["accepted password for root", "accepted publickey for root", "session opened for user root"]
    ssh_publickey = ["accepted publickey", "publickey for"]
    ssh_accept = ["accepted password", "accepted keyboard-interactive"]
    ssh_session = ["pam_unix(sshd:session)", "session opened for user"]

    sudo_exec = ["sudo:", " command=", " tty=", " pwd=", "sudoers"]
    audit_priv = ["type=execve", "type=cmd", "audit(", "uid=0", "euid=0", " execve", "res=success"]
    account_change = ["useradd", "adduser", "new user", "usermod", "password changed", "chpasswd", "groupadd", "chage"]
    cron_persist = ["crontab", "/etc/cron", "anacron", "systemd timer", "cron["]
    reverse_shell = ["/dev/tcp/", "nc -e", "bash -i", "sh -i", "reverse shell", "meterpreter", "socat tcp", "python -c", "perl -e"]
    download_exec = ["wget http", "curl http", "chmod +x", "base64 -d", "nohup ", "mktemp", "python3 -c", "busybox wget"]
    file_tamper = ["authorized_keys", "/etc/passwd", "/etc/shadow", "sshd_config", "chattr", "setfacl", "chmod 777", "chown root"]

    ftp_probe = ["ftpd", "ftp", "connection from", "ftpd["]
    openvpn_access = ["peer connection initiated", "initial packet from", "openvpn", "client connected"]
    openvpn_tls = ["tls error", "tls-auth", "certificate verify failed", "auth failed", "verify error"]

    web_scan = ["wpscan", "nmap scripting engine", "nmap", "nikto", "dirbuster", "gobuster", "masscan", "sqlmap"]
    admin_probe = ["wp-login", "xmlrpc.php", "/wp-admin", "/phpmyadmin", "/manager/html", "/boaform", "/cgi-bin", "/actuator", "/admin"]
    web_probe = ["script not found", "client denied by server configuration", "negotiation:error", "ah01630", "ah00687", "404 not found", "403 forbidden"]
    path_traversal = ["../", "..%2f", "..\\", "/etc/passwd", "/proc/self", "win.ini"]
    sql_injection = ["union select", "or 1=1", "sleep(", "benchmark(", "information_schema", "sql syntax", "mysql_fetch", "sqlmap"]
    xss_injection = ["<script", "onerror", "onload", "javascript:", "alert(", "document.cookie"]
    cmd_injection = ["cmd=", ";cat ", ";id", "&& whoami", "|bash", "/bin/sh -c", "powershell -enc", "bash -c", "uname -a"]
    upload_webshell = ["multipart/form-data", "move_uploaded_file", "shell.php", "cmd.php", "webshell", "phpinfo.php", "file upload"]
    db_auth = ["access denied for user", "password authentication failed", "too many connections", "postgres", "mysql", "mariadb"]

    oom_keywords = ["out of memory", "oom", "killed process"]
    kernel_crash = ["kernel panic", "call trace", "soft lockup", "segfault", "segmentation fault", "fatal exception", "panic"]
    permission_denied = ["permission denied", "unauthorized", "access denied", "forbidden"]
    honeypot_hit = ["combo ", "cowrie", "dionaea", "honeypot"]

    hdfs_network = ["connection reset by peer", "broken pipe", "sockettimeoutexception", "connection timed out", "network unreachable"]
    hdfs_replication = ["pendingreplication", "replication monitor", "timed out block", "under replicated", "replica"]
    hdfs_block = ["packetresponder", "packet responder", "blockreceiver", "dataxceiver", "receiving block", "served block", "block transfer"]
    hdfs_io = ["ioexception", "interruptedioexception", "could not read from stream", "input/output error", "i/o error"]
    hdfs_meta = ["addstoredblock", "blockmap updated", "volumemap", "block report", "lease recovery", "namenode"]

    rules = [
        (ssh_root_login, ("\u0052\u006f\u006f\u0074\u8d26\u6237\u6210\u529f\u767b\u5f55", "\u4e25\u91cd", "\u7acb\u5373\u6838\u67e5 root \u767b\u5f55\u6765\u6e90\u3001\u767b\u5f55\u65f6\u95f4\u4e0e\u540e\u7eed\u547d\u4ee4\uff0c\u786e\u8ba4\u662f\u5426\u4e3a\u6388\u6743\u8fd0\u7ef4\u884c\u4e3a\u3002")),
        (ssh_limit, ("\u8ba4\u8bc1\u5931\u8d25/\u66b4\u529b\u7834\u89e3", "\u9ad8\u5371", "\u5efa\u8bae\u6838\u67e5\u6765\u6e90 IP\u3001\u5931\u8d25\u7528\u6237\u540d\u4e0e\u65f6\u95f4\u7a97\u53e3\uff0c\u6392\u67e5\u66b4\u529b\u7834\u89e3\u6216\u51ed\u8bc1\u649e\u5e93\uff0c\u5e76\u68c0\u67e5\u5f31\u53e3\u4ee4\u8d26\u53f7\u3002")),
        (ssh_failed, ("\u8ba4\u8bc1\u5931\u8d25/\u66b4\u529b\u7834\u89e3", "\u9ad8\u5371", "\u5efa\u8bae\u6838\u67e5\u6765\u6e90 IP\u3001\u5931\u8d25\u7528\u6237\u540d\u4e0e\u65f6\u95f4\u7a97\u53e3\uff0c\u6392\u67e5\u66b4\u529b\u7834\u89e3\u6216\u51ed\u8bc1\u649e\u5e93\uff0c\u5e76\u68c0\u67e5\u5f31\u53e3\u4ee4\u8d26\u53f7\u3002")),
        (ssh_enum, ("\u8d26\u53f7\u63a2\u6d4b/\u7528\u6237\u679a\u4e3e", "\u4e2d\u5371", "\u5efa\u8bae\u7edf\u8ba1\u672a\u77e5\u7528\u6237\u4e0e\u5f02\u5e38\u7528\u6237\u540d\u6a21\u5f0f\uff0c\u8bc6\u522b\u8d26\u53f7\u679a\u4e3e\u6765\u6e90\uff0c\u5e76\u8bc4\u4f30\u662f\u5426\u9700\u8981\u5c01\u7981\u3002")),
        (ssh_publickey, ("\u0053\u0053\u0048\u516c\u94a5\u767b\u5f55\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u6838\u5bf9\u516c\u94a5\u6765\u6e90\u3001\u767b\u5f55\u4e3b\u673a\u548c\u5386\u53f2\u57fa\u7ebf\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u5f02\u5e38\u5bc6\u94a5\u6295\u9012\u6216\u6ee5\u7528\u3002")),
        (ssh_accept, ("\u53ef\u7591\u6210\u529f\u767b\u5f55", "\u9ad8\u5371", "\u5efa\u8bae\u7acb\u5373\u6838\u5bf9\u767b\u5f55\u7528\u6237\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u95f4\u53ca\u540e\u7eed\u547d\u4ee4\u6267\u884c\u60c5\u51b5\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u51ed\u8bc1\u88ab\u76d7\u7528\u3002")),
        (ssh_session, ("\u53ef\u7591\u4f1a\u8bdd\u5efa\u7acb", "\u4e2d\u5371", "\u5efa\u8bae\u7ed3\u5408\u524d\u5e8f\u8ba4\u8bc1\u65e5\u5fd7\u4e0e\u4f1a\u8bdd\u5185\u547d\u4ee4\u6267\u884c\u60c5\u51b5\u8fdb\u884c\u5173\u8054\u5206\u6790\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u6a2a\u5411\u79fb\u52a8\u6216\u5f02\u5e38\u8fd0\u7ef4\u64cd\u4f5c\u3002")),
        (sudo_exec, ("\u0073\u0075\u0064\u006f\u7279\u6743\u6267\u884c", "\u9ad8\u5371", "\u5efa\u8bae\u5ba1\u8ba1 sudoers\u3001TTY/PWD \u4e0e\u6267\u884c\u547d\u4ee4\u94fe\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8d8a\u6743\u63d0\u6743\u6216\u654f\u611f\u547d\u4ee4\u6ee5\u7528\u3002")),
        (audit_priv, ("\u5ba1\u8ba1\u63d0\u6743\u75d5\u8ff9", "\u9ad8\u5371", "\u5efa\u8bae\u7ed3\u5408 audit \u65e5\u5fd7\u4e2d\u7684 EXECVE/CMD \u8bb0\u5f55\u590d\u539f\u63d0\u6743\u94fe\u8def\uff0c\u91cd\u70b9\u68c0\u67e5 sudoers\u3001\u8d26\u6237\u6743\u9650\u4e0e\u654f\u611f\u6587\u4ef6\u4fee\u6539\u3002")),
        (account_change, ("\u8d26\u6237\u53d8\u66f4/\u6743\u9650\u53d8\u66f4", "\u9ad8\u5371", "\u5efa\u8bae\u6838\u67e5\u8d26\u6237\u65b0\u589e\u3001\u5bc6\u7801\u4fee\u6539\u548c\u7ec4\u6743\u9650\u53d8\u5316\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u6301\u4e45\u5316\u8d26\u6237\u690d\u5165\u6216\u6743\u9650\u6269\u5f20\u3002")),
        (cron_persist, ("\u6301\u4e45\u5316\u4efb\u52a1\u53d8\u66f4", "\u9ad8\u5371", "\u5efa\u8bae\u68c0\u67e5 crontab\u3001systemd timer \u4e0e\u8ba1\u5212\u4efb\u52a1\u6765\u6e90\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u5b9a\u65f6\u6301\u4e45\u5316\u884c\u4e3a\u3002")),
        (reverse_shell, ("\u53cd\u5f39\u0053\u0068\u0065\u006c\u006c/\u8fdc\u7a0b\u63a7\u5236", "\u4e25\u91cd", "\u5efa\u8bae\u7acb\u5373\u9694\u79bb\u4e3b\u673a\u3001\u5c01\u7981\u5bf9\u5916\u8fde\u63a5\u76ee\u6807\u5e76\u4fdd\u7559\u53d6\u8bc1\uff0c\u91cd\u70b9\u6838\u67e5\u662f\u5426\u5df2\u5efa\u7acb\u8fdc\u7a0b\u63a7\u5236\u94fe\u8def\u3002")),
        (download_exec, ("\u53ef\u7591\u4e0b\u8f7d\u6267\u884c", "\u9ad8\u5371", "\u5efa\u8bae\u6838\u67e5\u4e0b\u8f7d\u6e90\u3001\u843d\u5730\u6587\u4ef6\u548c\u540e\u7eed\u6267\u884c\u884c\u4e3a\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u6076\u610f\u8f7d\u8377\u6295\u9012\u3002")),
        (path_traversal, ("\u8def\u5f84\u904d\u5386/\u654f\u611f\u6587\u4ef6\u63a2\u6d4b", "\u9ad8\u5371", "\u5efa\u8bae\u68c0\u67e5\u662f\u5426\u5b58\u5728\u76ee\u5f55\u904d\u5386\u4e0e\u654f\u611f\u6587\u4ef6\u8bfb\u53d6\u5c1d\u8bd5\uff0c\u5e76\u5c3d\u5feb\u4fee\u8865\u8bbf\u95ee\u63a7\u5236\u4e0e\u8def\u5f84\u6821\u9a8c\u3002")),
        (file_tamper, ("\u654f\u611f\u6587\u4ef6\u7be1\u6539", "\u9ad8\u5371", "\u5efa\u8bae\u68c0\u67e5\u654f\u611f\u6587\u4ef6\u53d8\u66f4\u6765\u6e90\uff0c\u91cd\u70b9\u6838\u67e5 SSH \u914d\u7f6e\u3001\u8d26\u6237\u6587\u4ef6\u4e0e\u6743\u9650\u4fee\u6539\u3002")),
        (ftp_probe, ("\u0046\u0054\u0050\u53ef\u7591\u8bbf\u95ee", "\u4e2d\u5371", "\u5efa\u8bae\u6838\u67e5 FTP/FTPD \u6765\u6e90\u5730\u5740\u3001\u8bbf\u95ee\u9891\u7387\u4e0e\u8d26\u53f7\u72b6\u6001\uff0c\u786e\u8ba4\u662f\u5426\u4e3a\u63a2\u6d4b\u6216\u5f02\u5e38\u5916\u8fde\u3002")),
        (openvpn_tls, ("\u004f\u0070\u0065\u006e\u0056\u0050\u004e\u63a5\u5165\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5 VPN \u8bc1\u4e66\u3001TLS \u63e1\u624b\u548c\u8ba4\u8bc1\u5931\u8d25\u539f\u56e0\uff0c\u8bc6\u522b\u5f02\u5e38\u63a5\u5165\u6e90\u4e0e\u914d\u7f6e\u95ee\u9898\u3002")),
        (openvpn_access, ("\u004f\u0070\u0065\u006e\u0056\u0050\u004e\u8fdc\u7a0b\u63a5\u5165", "\u4e2d\u5371", "\u5efa\u8bae\u6838\u67e5 VPN \u63a5\u5165\u7528\u6237\u3001\u6765\u6e90\u5730\u5740\u548c\u63a5\u5165\u65f6\u6bb5\uff0c\u786e\u8ba4\u662f\u5426\u7b26\u5408\u6388\u6743\u57fa\u7ebf\u3002")),
        (web_scan, ("\u7f51\u7ad9\u626b\u63cf/\u63a2\u6d4b", "\u9ad8\u5371", "\u5efa\u8bae\u8bc6\u522b\u626b\u63cf\u5668\u6765\u6e90\u3001\u63a2\u6d4b\u8def\u5f84\u4e0e\u9891\u7387\uff0c\u5fc5\u8981\u65f6\u5c01\u7981\u6765\u6e90\u5e76\u52a0\u5f3a WAF/\u8bbf\u95ee\u63a7\u5236\u3002")),
        (admin_probe, ("\u540e\u53f0\u5165\u53e3\u63a2\u6d4b", "\u9ad8\u5371", "\u5efa\u8bae\u91cd\u70b9\u6838\u67e5\u540e\u53f0\u3001\u7ba1\u7406\u63a5\u53e3\u548c\u767b\u5f55\u9875\u8bbf\u95ee\u8f68\u8ff9\uff0c\u5e76\u5bf9\u53ef\u7591\u6765\u6e90\u5b9e\u65bd\u9650\u6d41\u6216\u5c01\u7981\u3002")),
        (sql_injection, ("\u0053\u0051\u004c\u6ce8\u5165", "\u9ad8\u5371", "\u5efa\u8bae\u7acb\u5373\u542f\u7528 WAF \u89c4\u5219\u3001\u5ba1\u8ba1\u6570\u636e\u5e93\u5f02\u5e38\u65e5\u5fd7\uff0c\u5e76\u68c0\u67e5\u5e94\u7528\u5c42\u8f93\u5165\u6821\u9a8c\u4e0e\u53c2\u6570\u5316\u67e5\u8be2\u3002")),
        (xss_injection, ("\u0058\u0053\u0053\u6ce8\u5165", "\u4e2d\u5371", "\u5efa\u8bae\u542f\u7528 CSP\u3001\u7edf\u4e00\u8f93\u51fa\u7f16\u7801\u5e76\u68c0\u67e5\u8f93\u5165\u8fc7\u6ee4\u903b\u8f91\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u53cd\u5c04\u6216\u5b58\u50a8\u578b XSS\u3002")),
        (cmd_injection, ("\u547d\u4ee4\u6ce8\u5165/\u8fdc\u7a0b\u6267\u884c", "\u4e25\u91cd", "\u5efa\u8bae\u7acb\u5373\u9694\u79bb\u670d\u52a1\u3001\u5ba1\u8ba1 Web \u53c2\u6570\u4e0e\u547d\u4ee4\u6267\u884c\u94fe\u8def\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8fdc\u7a0b\u4ee3\u7801\u6267\u884c\u3002")),
        (upload_webshell, ("\u53ef\u7591\u6587\u4ef6\u4e0a\u4f20/\u0057\u0065\u0062\u0053\u0068\u0065\u006c\u006c", "\u4e25\u91cd", "\u5efa\u8bae\u68c0\u67e5\u4e0a\u4f20\u76ee\u5f55\u3001\u53ef\u6267\u884c\u811a\u672c\u4e0e\u8bbf\u95ee\u65e5\u5fd7\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728 WebShell \u843d\u5730\u4e0e\u6267\u884c\u3002")),
        (web_probe, ("\u0057\u0065\u0062\u8d44\u6e90\u63a2\u6d4b", "\u4e2d\u5371", "\u5efa\u8bae\u7ed3\u5408 Apache/WAF \u65e5\u5fd7\u6838\u67e5\u654f\u611f\u8def\u5f84\u63a2\u6d4b\u4e0e\u5f02\u5e38\u8bbf\u95ee\u6a21\u5f0f\u3002")),
        (db_auth, ("\u6570\u636e\u5e93\u8ba4\u8bc1\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5\u6570\u636e\u5e93\u8ba4\u8bc1\u5931\u8d25\u539f\u56e0\u3001\u8fde\u63a5\u6e90\u4e0e\u8d26\u53f7\u66b4\u9732\u60c5\u51b5\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u649e\u5e93\u6216\u914d\u7f6e\u9519\u8bef\u3002")),
        (oom_keywords, ("\u7cfb\u7edf\u8d44\u6e90\u8017\u5c3d/\u004f\u004f\u004d", "\u4e2d\u9ad8", "\u5efa\u8bae\u68c0\u67e5\u5f53\u524d\u4e3b\u673a\u5185\u5b58\u3001\u8fdb\u7a0b\u8d44\u6e90\u5360\u7528\u548c\u670d\u52a1\u538b\u529b\uff0c\u786e\u8ba4\u662f\u5426\u4e3a\u8d44\u6e90\u8017\u5c3d\u3001\u5f02\u5e38\u6d41\u91cf\u6216 DoS \u524d\u5146\u3002")),
        (kernel_crash, ("\u5185\u6838/\u670d\u52a1\u5d29\u6e83", "\u4e25\u91cd", "\u5efa\u8bae\u7acb\u5373\u68c0\u67e5\u5185\u6838\u9519\u8bef\u3001\u8c03\u7528\u6808\u548c\u670d\u52a1\u5065\u5eb7\u72b6\u6001\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u7cfb\u7edf\u5d29\u6e83\u6216\u5e95\u5c42\u6545\u969c\u3002")),
        (hdfs_network, ("\u0048\u0044\u0046\u0053/\u7f51\u7edc\u94fe\u8def\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5 DataNode \u4e0e\u7f51\u7edc\u94fe\u8def\u7a33\u5b9a\u6027\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8fde\u63a5\u4e2d\u65ad\u6216\u8d85\u65f6\u3002")),
        (hdfs_replication, ("\u0048\u0044\u0046\u0053\u526f\u672c\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5\u526f\u672c\u961f\u5217\u3001DataNode \u72b6\u6001\u4e0e\u96c6\u7fa4\u8d1f\u8f7d\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u526f\u672c\u6ede\u540e\u3002")),
        (hdfs_block, ("\u0048\u0044\u0046\u0053\u6570\u636e\u5757\u4f20\u8f93\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5 DataNode \u95f4\u5757\u4f20\u8f93\u4e0e\u63a5\u6536\u65e5\u5fd7\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u6570\u636e\u5757\u53d1\u9001\u5931\u8d25\u3002")),
        (hdfs_io, ("\u0048\u0044\u0046\u0053/\u0049\u004f\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u68c0\u67e5\u78c1\u76d8 IO\u3001\u5b58\u50a8\u4ecb\u8d28\u72b6\u6001\u548c\u8282\u70b9\u8d1f\u8f7d\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728 IO \u74f6\u9888\u3002")),
        (hdfs_meta, ("\u004e\u0061\u006d\u0065\u004e\u006f\u0064\u0065\u5143\u6570\u636e\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u6838\u67e5 NameNode \u5143\u6570\u636e\u4e00\u81f4\u6027\u4e0e\u6062\u590d\u72b6\u6001\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u5757\u6620\u5c04\u5f02\u5e38\u3002")),
        (honeypot_hit, ("\u871c\u7f50\u547d\u4e2d/\u5916\u90e8\u63a2\u6d4b", "\u4e2d\u5371", "\u5efa\u8bae\u8bb0\u5f55\u6765\u6e90 IP\u3001\u534f\u8bae\u7279\u5f81\u4e0e\u547d\u4e2d\u884c\u4e3a\uff0c\u7eb3\u5165\u5c01\u7981\u4e0e\u5173\u8054\u5206\u6790\u3002")),
        (permission_denied, ("\u672a\u6388\u6743\u8bbf\u95ee", "\u4e2d\u5371", "\u5efa\u8bae\u6838\u67e5\u8bbf\u95ee\u4e3b\u4f53\u3001\u76ee\u6807\u8d44\u6e90\u4e0e\u8bbf\u95ee\u63a7\u5236\u914d\u7f6e\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8d8a\u6743\u8bbf\u95ee\u5c1d\u8bd5\u3002")),
        (["timeout", "connection reset", "connection closed"], ("\u8fde\u63a5\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u7ed3\u5408\u7f51\u7edc\u94fe\u8def\u4e0e\u670d\u52a1\u7aef\u65e5\u5fd7\u68c0\u67e5\u8fde\u63a5\u4e2d\u65ad\u539f\u56e0\u3002")),
        (["error", "exception", "fatal"], ("\u7cfb\u7edf\u5f02\u5e38", "\u4e2d\u5371", "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u65e5\u5fd7\u5b9a\u4f4d\u5f02\u5e38\u6765\u6e90\uff0c\u5224\u65ad\u662f\u5426\u4e3a\u670d\u52a1\u6545\u969c\u6216\u653b\u51fb\u526f\u4f5c\u7528\u3002")),
    ]

    for keys, value in rules:
        if has_any(keys):
            return value
    return ("\u5176\u4ed6\u53ef\u7591\u884c\u4e3a", "\u4e2d\u5371", "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002")


TEMPLATE_TOKEN_CN = {
    "<NUM>": "\u6570\u5b57",
    "<IP>": "IP\u5730\u5740",
    "<HEXID>": "\u5341\u516d\u8fdb\u5236ID",
    "<*>": "\u53c2\u6570",
}


def make_template_readable(template_text: str, max_len: int = 220) -> str:
    """Render a stable Chinese summary for a parsed template."""
    text = str(template_text or "").strip()
    if not text:
        return "-"

    t = text.lower()
    if any(k in t for k in ["kernel panic", "call trace", "soft lockup", "segfault", "segmentation fault", "fatal exception", "panic"]):
        return "\u7cfb\u7edf\u7a33\u5b9a\u6027\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u5185\u6838\u9519\u8bef\u3001\u5d29\u6e83\u6216\u4e25\u91cd\u5f02\u5e38\uff0c\u5efa\u8bae\u7acb\u5373\u68c0\u67e5\u7cfb\u7edf\u5065\u5eb7\u72b6\u6001\u4e0e\u8c03\u7528\u6808\u3002"[:max_len]
    if any(k in t for k in ["out of memory", "oom", "killed process"]):
        return "\u7cfb\u7edf\u8d44\u6e90\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u5185\u5b58\u8017\u5c3d\u6216 OOM \u6740\u8fdb\u7a0b\u884c\u4e3a\uff0c\u53ef\u80fd\u4e0e\u8d44\u6e90\u8017\u5c3d\u3001\u5f02\u5e38\u8d1f\u8f7d\u6216\u62d2\u7edd\u670d\u52a1\u524d\u5146\u6709\u5173\u3002"[:max_len]
    if any(k in t for k in ["maximum login attempts exceeded", "too many authentication failures"]):
        return "\u8d26\u53f7\u5b89\u5168\u544a\u8b66\uff1a\u51fa\u73b0\u8d85\u9650\u767b\u5f55\u5c1d\u8bd5\u6216\u8fc7\u591a\u8ba4\u8bc1\u5931\u8d25\uff0c\u7591\u4f3c\u66b4\u529b\u7834\u89e3\u6216\u51ed\u8bc1\u649e\u5e93\u3002"[:max_len]
    if any(k in t for k in ["failed password", "authentication failure", "invalid user"]):
        return "\u8d26\u53f7\u5b89\u5168\u544a\u8b66\uff1a\u51fa\u73b0\u8ba4\u8bc1\u5931\u8d25\u3001\u65e0\u6548\u7528\u6237\u6216\u5bc6\u7801\u9519\u8bef\uff0c\u7591\u4f3c\u66b4\u529b\u7834\u89e3\u6216\u51ed\u8bc1\u649e\u5e93\u3002"[:max_len]
    if any(k in t for k in ["user unknown", "unknown user", "check pass", "illegal user"]):
        return "\u8d26\u53f7\u63a2\u6d4b\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u672a\u77e5\u7528\u6237\u3001\u975e\u6cd5\u7528\u6237\u6216\u5f02\u5e38\u8ba4\u8bc1\u63a2\u6d4b\u7ebf\u7d22\uff0c\u7591\u4f3c\u7528\u6237\u679a\u4e3e\u884c\u4e3a\u3002"[:max_len]
    if any(k in t for k in ["accepted password for root", "accepted publickey for root", "session opened for user root"]):
        return "\u0052\u006f\u006f\u0074 \u767b\u5f55\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 root \u8d26\u6237\u6210\u529f\u767b\u5f55\u6216\u4f1a\u8bdd\u5efa\u7acb\uff0c\u9700\u8981\u91cd\u70b9\u6838\u67e5\u6765\u6e90\u4e0e\u540e\u7eed\u64cd\u4f5c\u3002"[:max_len]
    if any(k in t for k in ["accepted publickey", "publickey for"]):
        return "\u0053\u0053\u0048 \u516c\u94a5\u767b\u5f55\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u57fa\u4e8e\u516c\u94a5\u7684 SSH \u767b\u5f55\uff0c\u5e94\u6838\u5bf9\u5bc6\u94a5\u6765\u6e90\u548c\u767b\u5f55\u57fa\u7ebf\u3002"[:max_len]
    if any(k in t for k in ["accepted password", "accepted keyboard-interactive"]):
        return "\u767b\u5f55\u6210\u529f\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 SSH \u6210\u529f\u767b\u5f55\uff0c\u5e94\u91cd\u70b9\u6838\u67e5\u767b\u5f55\u7528\u6237\u3001\u6765\u6e90\u5730\u5740\u548c\u540e\u7eed\u884c\u4e3a\u3002"[:max_len]
    if any(k in t for k in ["pam_unix(sshd:session)", "session opened for user"]):
        return "\u4f1a\u8bdd\u5efa\u7acb\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 SSH \u4f1a\u8bdd\u5df2\u6210\u529f\u6253\u5f00\uff0c\u5efa\u8bae\u7ed3\u5408\u524d\u5e8f\u8ba4\u8bc1\u65e5\u5fd7\u4e0e\u4f1a\u8bdd\u5185\u547d\u4ee4\u6267\u884c\u60c5\u51b5\u5206\u6790\u3002"[:max_len]
    if any(k in t for k in ["sudo:", " command=", " tty=", " pwd=", "sudoers"]):
        return "\u7279\u6743\u6267\u884c\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 sudo \u547d\u4ee4\u6267\u884c\u6216\u6743\u9650\u63d0\u5347\u75d5\u8ff9\uff0c\u5efa\u8bae\u5ba1\u8ba1 sudoers \u914d\u7f6e\u4e0e\u9ad8\u5371\u547d\u4ee4\u94fe\u3002"[:max_len]
    if any(k in t for k in ["type=execve", "type=cmd", "audit(", "uid=0", "euid=0", " execve", "res=success"]):
        return "\u004c\u0069\u006e\u0075\u0078 \u5ba1\u8ba1\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 audit \u63d0\u6743\u6216\u9ad8\u5371\u547d\u4ee4\u6267\u884c\u75d5\u8ff9\uff0c\u5efa\u8bae\u590d\u539f\u547d\u4ee4\u94fe\u5e76\u6838\u67e5\u6743\u9650\u53d8\u5316\u3002"[:max_len]
    if any(k in t for k in ["useradd", "adduser", "new user", "usermod", "password changed", "chpasswd", "groupadd", "chage"]):
        return "\u8d26\u6237\u53d8\u66f4\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8d26\u6237\u65b0\u589e\u3001\u5bc6\u7801\u4fee\u6539\u6216\u6743\u9650\u7ec4\u53d8\u66f4\uff0c\u9700\u6838\u67e5\u662f\u5426\u4e3a\u6388\u6743\u8fd0\u7ef4\u884c\u4e3a\u3002"[:max_len]
    if any(k in t for k in ["crontab", "/etc/cron", "anacron", "systemd timer", "cron["]):
        return "\u6301\u4e45\u5316\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8ba1\u5212\u4efb\u52a1\u6216\u5b9a\u65f6\u5668\u76f8\u5173\u53d8\u66f4\uff0c\u9700\u68c0\u67e5\u662f\u5426\u5b58\u5728\u6076\u610f\u6301\u4e45\u5316\u3002"[:max_len]
    if any(k in t for k in ["/dev/tcp/", "nc -e", "bash -i", "sh -i", "reverse shell", "meterpreter", "socat tcp", "python -c", "perl -e"]):
        return "\u8fdc\u7a0b\u63a7\u5236\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u53cd\u5f39 Shell \u6216\u8fdc\u7a0b\u63a7\u5236\u94fe\u8def\u7279\u5f81\uff0c\u5efa\u8bae\u7acb\u5373\u9694\u79bb\u4e3b\u673a\u5e76\u4fdd\u7559\u53d6\u8bc1\u3002"[:max_len]
    if any(k in t for k in ["wget http", "curl http", "chmod +x", "base64 -d", "nohup ", "mktemp", "python3 -c", "busybox wget"]):
        return "\u6076\u610f\u8f7d\u8377\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u53ef\u7591\u4e0b\u8f7d\u4e0e\u6267\u884c\u94fe\u8def\uff0c\u9700\u6838\u67e5\u4e0b\u8f7d\u6e90\u3001\u843d\u5730\u6587\u4ef6\u53ca\u540e\u7eed\u8fdb\u7a0b\u884c\u4e3a\u3002"[:max_len]
    if any(k in t for k in ["../", "..%2f", "..\\", "/etc/passwd", "/proc/self", "win.ini"]):
        return "\u8def\u5f84\u904d\u5386\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u76ee\u5f55\u904d\u5386\u6216\u654f\u611f\u6587\u4ef6\u63a2\u6d4b\u7279\u5f81\uff0c\u5e94\u68c0\u67e5\u8def\u5f84\u6821\u9a8c\u4e0e\u8bbf\u95ee\u63a7\u5236\u3002"[:max_len]
    if any(k in t for k in ["authorized_keys", "/etc/passwd", "/etc/shadow", "sshd_config", "chattr", "setfacl", "chmod 777", "chown root"]):
        return "\u654f\u611f\u6587\u4ef6\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8d26\u6237\u3001\u6743\u9650\u6216 SSH \u5173\u952e\u914d\u7f6e\u6587\u4ef6\u53d8\u66f4\uff0c\u5e94\u7acb\u5373\u6838\u67e5\u53d8\u66f4\u6765\u6e90\u3002"[:max_len]
    if any(k in t for k in ["ftpd", "ftp", "connection from"]) and "sshd" not in t:
        return "\u0046\u0054\u0050 \u8bbf\u95ee\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 FTP/FTPD \u8fde\u63a5\u6216\u8bbf\u95ee\u6765\u6e90\uff0c\u5efa\u8bae\u6838\u67e5\u6765\u6e90\u5730\u5740\u3001\u9891\u7387\u548c\u8d26\u53f7\u72b6\u6001\u3002"[:max_len]
    if any(k in t for k in ["tls error", "certificate verify failed", "verify error", "auth failed"]):
        return "\u0056\u0050\u004e \u63a5\u5165\u5f02\u5e38\uff1a\u68c0\u6d4b\u5230 TLS \u63e1\u624b\u6216\u8bc1\u4e66\u6821\u9a8c\u5931\u8d25\uff0c\u5efa\u8bae\u6392\u67e5 OpenVPN \u8ba4\u8bc1\u4e0e\u914d\u7f6e\u5f02\u5e38\u3002"[:max_len]
    if any(k in t for k in ["peer connection initiated", "initial packet from", "openvpn", "client connected"]):
        return "\u004f\u0070\u0065\u006e\u0056\u0050\u004e \u63a5\u5165\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 VPN \u4f1a\u8bdd\u5efa\u7acb\u6216\u5ba2\u6237\u7aef\u63a5\u5165\uff0c\u5e94\u6838\u67e5\u6765\u6e90\u5730\u5740\u4e0e\u63a5\u5165\u65f6\u6bb5\u3002"[:max_len]
    if any(k in t for k in ["wpscan", "nmap scripting engine", "nmap", "nikto", "gobuster", "dirbuster", "masscan", "sqlmap"]):
        return "\u0057\u0065\u0062 \u626b\u63cf\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u626b\u63cf\u5668\u6307\u7eb9\u6216\u63a2\u6d4b\u884c\u4e3a\uff0c\u5efa\u8bae\u8bc6\u522b\u6765\u6e90\u5e76\u52a0\u5f3a\u7ad9\u70b9\u8bbf\u95ee\u63a7\u5236\u3002"[:max_len]
    if any(k in t for k in ["wp-login", "xmlrpc.php", "/wp-admin", "/phpmyadmin", "/manager/html", "/boaform", "/cgi-bin", "/actuator", "/admin"]):
        return "\u540e\u53f0\u63a2\u6d4b\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u7ba1\u7406\u5165\u53e3\u6216\u540e\u53f0\u9875\u9762\u8bbf\u95ee\u5c1d\u8bd5\uff0c\u9700\u6838\u67e5\u6765\u6e90 IP \u4e0e\u8bbf\u95ee\u9891\u7387\u3002"[:max_len]
    if any(k in t for k in ["../", "..%2f", "..\\", "/etc/passwd", "/proc/self", "win.ini"]):
        return "\u8def\u5f84\u904d\u5386\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u76ee\u5f55\u904d\u5386\u6216\u654f\u611f\u6587\u4ef6\u63a2\u6d4b\u7279\u5f81\uff0c\u5e94\u68c0\u67e5\u8def\u5f84\u6821\u9a8c\u4e0e\u8bbf\u95ee\u63a7\u5236\u3002"[:max_len]
    if any(k in t for k in ["union select", "or 1=1", "sleep(", "benchmark(", "information_schema", "sql syntax", "mysql_fetch", "sqlmap"]):
        return "\u0057\u0065\u0062 \u653b\u51fb\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 SQL \u6ce8\u5165\u8f7d\u8377\u6216\u6570\u636e\u5e93\u62a5\u9519\u7ebf\u7d22\uff0c\u5efa\u8bae\u7acb\u5373\u68c0\u67e5 WAF \u4e0e\u53c2\u6570\u5316\u67e5\u8be2\u3002"[:max_len]
    if any(k in t for k in ["<script", "onerror", "onload", "javascript:", "alert(", "document.cookie"]):
        return "\u0057\u0065\u0062 \u653b\u51fb\u544a\u8b66\uff1a\u68c0\u6d4b\u5230 XSS \u6ce8\u5165\u7279\u5f81\uff0c\u5efa\u8bae\u542f\u7528 CSP \u5e76\u5f3a\u5316\u8f93\u51fa\u7f16\u7801\u3002"[:max_len]
    if any(k in t for k in ["cmd=", ";cat ", ";id", "&& whoami", "|bash", "/bin/sh -c", "powershell -enc", "bash -c", "uname -a"]):
        return "\u547d\u4ee4\u6267\u884c\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u547d\u4ee4\u6ce8\u5165\u6216\u8fdc\u7a0b\u6267\u884c\u7ebf\u7d22\uff0c\u5e94\u7acb\u5373\u6838\u67e5\u53c2\u6570\u6765\u6e90\u4e0e\u6267\u884c\u94fe\u8def\u3002"[:max_len]
    if any(k in t for k in ["multipart/form-data", "move_uploaded_file", "shell.php", "cmd.php", "webshell", "phpinfo.php", "file upload"]):
        return "\u6587\u4ef6\u4e0a\u4f20\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u53ef\u7591\u4e0a\u4f20\u6216 WebShell \u843d\u5730\u7ebf\u7d22\uff0c\u5e94\u68c0\u67e5\u4e0a\u4f20\u76ee\u5f55\u4e0e\u6267\u884c\u75d5\u8ff9\u3002"[:max_len]
    if any(k in t for k in ["script not found", "negotiation:error", "ah01630", "ah00687", "client denied by server configuration", "404 not found", "403 forbidden"]):
        return "\u0057\u0065\u0062 \u8d44\u6e90\u63a2\u6d4b\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u654f\u611f\u8def\u5f84\u3001\u53d7\u9650\u8d44\u6e90\u6216\u5f02\u5e38\u534f\u5546\u9519\u8bef\uff0c\u5efa\u8bae\u7ed3\u5408 Apache/WAF \u65e5\u5fd7\u5206\u6790\u3002"[:max_len]
    if any(k in t for k in ["access denied for user", "password authentication failed", "too many connections", "postgres", "mysql", "mariadb"]):
        return "\u6570\u636e\u5e93\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u6570\u636e\u5e93\u8ba4\u8bc1\u5931\u8d25\u6216\u8fde\u63a5\u5f02\u5e38\uff0c\u5efa\u8bae\u6838\u67e5\u8fde\u63a5\u6e90\u4e0e\u6570\u636e\u5e93\u5b89\u5168\u7b56\u7565\u3002"[:max_len]
    if any(k in t for k in ["permission denied", "unauthorized", "access denied", "forbidden"]):
        return "\u672a\u6388\u6743\u8bbf\u95ee\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u6743\u9650\u62d2\u7edd\u6216\u8d8a\u6743\u8bbf\u95ee\u7ebf\u7d22\uff0c\u5efa\u8bae\u6838\u67e5\u8bbf\u95ee\u4e3b\u4f53\u4e0e\u8d44\u6e90\u6743\u9650\u3002"[:max_len]
    if any(k in t for k in ["connection reset by peer", "broken pipe", "sockettimeoutexception", "connection timed out", "network unreachable"]):
        return "\u7f51\u7edc\u94fe\u8def\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8fde\u63a5\u4e2d\u65ad\u3001\u91cd\u7f6e\u6216\u8d85\u65f6\uff0c\u5efa\u8bae\u68c0\u67e5\u7f51\u7edc\u94fe\u8def\u4e0e\u670d\u52a1\u7aef\u72b6\u6001\u3002"[:max_len]
    if any(k in t for k in ["pendingreplication", "replication monitor", "timed out block", "under replicated", "replica"]):
        return "\u0048\u0044\u0046\u0053 \u526f\u672c\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u526f\u672c\u8d85\u65f6\u3001\u6ede\u540e\u6216\u526f\u672c\u6570\u5f02\u5e38\uff0c\u5efa\u8bae\u68c0\u67e5\u96c6\u7fa4\u526f\u672c\u72b6\u6001\u3002"[:max_len]
    if any(k in t for k in ["packetresponder", "packet responder", "blockreceiver", "dataxceiver", "receiving block", "served block", "block transfer"]):
        return "\u0048\u0044\u0046\u0053 \u6570\u636e\u5757\u4f20\u8f93\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u5757\u4f20\u8f93\u3001\u63a5\u6536\u6216\u53d1\u9001\u5f02\u5e38\uff0c\u5efa\u8bae\u68c0\u67e5 DataNode \u95f4\u94fe\u8def\u3002"[:max_len]
    if any(k in t for k in ["ioexception", "interruptedioexception", "could not read from stream", "input/output error", "i/o error"]):
        return "\u0049\u004f \u5f02\u5e38\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8f93\u5165\u8f93\u51fa\u9519\u8bef\u6216\u6d41\u8bfb\u53d6\u5931\u8d25\uff0c\u5efa\u8bae\u68c0\u67e5\u78c1\u76d8\u548c\u8282\u70b9 IO \u72b6\u6001\u3002"[:max_len]
    if any(k in t for k in ["addstoredblock", "blockmap updated", "volumemap", "block report", "lease recovery", "namenode"]):
        return "\u004e\u0061\u006d\u0065\u004e\u006f\u0064\u0065 \u5143\u6570\u636e\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u5757\u6620\u5c04\u3001\u79df\u7ea6\u6062\u590d\u6216\u5143\u6570\u636e\u5f02\u5e38\uff0c\u5efa\u8bae\u6838\u67e5 NameNode \u72b6\u6001\u3002"[:max_len]
    if any(k in t for k in ["combo ", "cowrie", "dionaea", "honeypot"]):
        return "\u871c\u7f50\u547d\u4e2d\u544a\u8b66\uff1a\u68c0\u6d4b\u5230\u8bf1\u6355\u6216\u81ea\u52a8\u5316\u63a2\u6d4b\u7ebf\u7d22\uff0c\u5efa\u8bae\u8bb0\u5f55\u6765\u6e90\u6307\u7eb9\u5e76\u7eb3\u5165\u5173\u8054\u5206\u6790\u3002"[:max_len]

    cleaned = text
    for token in TEMPLATE_TOKEN_CN:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"\d+", " ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z\u4e00-\u9fa5 ]", " ", cleaned)
    words = [w.lower() for w in cleaned.split() if len(w) >= 3]
    stop = {"info", "warn", "error", "debug", "trace", "dfs", "hdfs", "namenode", "datanode", "kernel", "the", "for", "and", "with", "during", "calls"}
    keywords: List[str] = []
    for w in words:
        if w in stop:
            continue
        if w not in keywords:
            keywords.append(w)
        if len(keywords) >= 6:
            break

    if keywords:
        return f"\u53ef\u7591\u65e5\u5fd7\u6458\u8981\uff1a\u5173\u952e\u8bcd {', '.join(keywords)}\uff08\u5efa\u8bae\u67e5\u770b\u539f\u59cb\u6a21\u677f\u786e\u8ba4\u4e0a\u4e0b\u6587\uff09\u3002"[:max_len]
    return "\u53ef\u7591\u65e5\u5fd7\u6458\u8981\uff1a\u5f53\u524d\u6a21\u677f\u547d\u4e2d\u7279\u5f81\u8f83\u5c11\uff0c\u5efa\u8bae\u7ed3\u5408\u539f\u59cb\u65e5\u5fd7\u8fdb\u4e00\u6b65\u5206\u6790\u3002"

def compact_log_preview(log_text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(log_text or "")).strip()
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _decode_escaped_unicode(text: str) -> str:
    value = str(text or "")
    if "\\u" not in value and "\\x" not in value:
        return value
    try:
        return value.encode("utf-8").decode("unicode_escape")
    except Exception:
        return value


def localize_text(text: str) -> str:
    value = str(text or "")
    if any("\u4e00" <= ch <= "\u9fff" for ch in value):
        return value
    mapped = TITLE_CN.get(value, value)
    mapped = ADVICE_CN.get(mapped, mapped)
    mapped = _decode_escaped_unicode(mapped)
    return mapped


def localize_advice(text: str) -> str:
    value = localize_text(text)
    if any("\u4e00" <= ch <= "\u9fff" for ch in value):
        return value
    raw = str(text or "").strip()
    if not raw:
        return "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002"
    return (
        f"\u5efa\u8bae\u4eba\u5de5\u590d\u6838\u5e76\u6267\u884c\u6700\u5c0f\u6743\u9650\u3001"
        f"\u6765\u6e90\u5c01\u7981\u3001\u914d\u7f6e\u52a0\u56fa\u7b49\u5904\u7f6e\u63aa\u65bd\u3002"
        f"\uff08\u539f\u6587: {raw[:120]}\uff09"
    )


def localize_attack_type(text: str) -> str:
    v = str(text or "")
    if any("\u4e00" <= ch <= "\u9fff" for ch in v):
        return v
    return ATTACK_TYPE_CN.get(v, v)


def localize_case_group(group: str) -> str:
    return CASE_GROUP_CN.get(str(group or "").strip().lower(), "\u672a\u5206\u7c7b\u6848\u4f8b")


def rag_hit_to_security_category(hit: Dict) -> str:
    group = str(hit.get("case_group", "")).strip().lower()
    attack_cn = localize_attack_type(str(hit.get("attack_type", ""))).strip()
    title_cn = localize_text(str(hit.get("title", ""))).strip()
    if group == "system_anomaly":
        return f"\u7cfb\u7edf\u5f02\u5e38/{title_cn or attack_cn or '\u672a\u77e5'}"
    if group == "security_attack":
        return f"\u5b89\u5168\u653b\u51fb/{attack_cn or title_cn or '\u672a\u77e5'}"
    return title_cn or attack_cn or "\u5176\u4ed6\u53ef\u7591\u884c\u4e3a"


def add_security_columns(df: pd.DataFrame, template_col: str = "template_text") -> pd.DataFrame:
    if df is None or df.empty or template_col not in df.columns:
        return df
    out = df.copy()
    mapped = out[template_col].apply(interpret_template_security)
    out["\u5b89\u5168\u5206\u7c7b"] = mapped.apply(lambda x: x[0])
    out["\u98ce\u9669\u7b49\u7ea7"] = mapped.apply(lambda x: x[1])
    out["\u5efa\u8bae\u5904\u7f6e"] = mapped.apply(lambda x: x[2])
    return out


def _decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _extract_log_text_from_df(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty:
        return []
    for col in ["log", "message", "content", "raw", "text", "line"]:
        if col in df.columns:
            return [str(x).strip() for x in df[col].tolist() if str(x).strip()]
    first_col = str(df.columns[0])
    return [str(x).strip() for x in df[first_col].tolist() if str(x).strip()]


def pick_log_text_from_df(df: pd.DataFrame) -> List[str]:
    return _extract_log_text_from_df(df)


def load_structured_upload_bytes(name: str, data: bytes) -> pd.DataFrame:
    name = str(name or "").lower()

    if name.endswith(".csv"):
        return pd.read_csv(BytesIO(data))
    if name.endswith(".tsv"):
        return pd.read_csv(BytesIO(data), sep="	")
    if name.endswith(".jsonl"):
        return pd.read_json(BytesIO(data), lines=True)
    if name.endswith(".json"):
        try:
            return pd.read_json(BytesIO(data))
        except Exception:
            return pd.read_json(BytesIO(data), lines=True)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(BytesIO(data))
    if name.endswith(".parquet"):
        return pd.read_parquet(BytesIO(data))
    if name.endswith(".gz"):
        inner = gzip.decompress(data)
        return load_structured_upload_bytes(name[:-3], inner)
    if name.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(data), "r") as zf:
            members = [m for m in zf.namelist() if not m.endswith("/")]
            if not members:
                raise ValueError("\u538b\u7f29\u5305\u4e2d\u6ca1\u6709\u53ef\u8bfb\u53d6\u6587\u4ef6")
            inner_name = members[0]
            inner = zf.read(inner_name)
            return load_structured_upload_bytes(inner_name, inner)
    raise ValueError(f"\u4e0d\u652f\u6301\u7684\u7ed3\u6784\u5316\u4e0a\u4f20\u6587\u4ef6\u7c7b\u578b: {name}")


def load_structured_upload(uploaded_file) -> pd.DataFrame:
    name = str(getattr(uploaded_file, "name", "")).lower()
    data = uploaded_file.getvalue()
    return load_structured_upload_bytes(name, data)


def load_raw_lines_bytes(name: str, data: bytes) -> List[str]:
    name = str(name or "").lower()

    if name.endswith((".log", ".txt", ".text", ".jsonl")):
        text = _decode_bytes(data)
        return [x.strip() for x in text.splitlines() if x.strip()]
    if name.endswith(".json"):
        text = _decode_bytes(data).strip()
        if not text:
            return []
        try:
            obj = json.loads(text)
        except Exception:
            return [x.strip() for x in text.splitlines() if x.strip()]
        if isinstance(obj, list):
            result = []
            for item in obj:
                if isinstance(item, dict):
                    for key in ["log", "message", "content", "raw", "text", "line"]:
                        if key in item and str(item[key]).strip():
                            result.append(str(item[key]).strip())
                            break
                else:
                    result.append(str(item).strip())
            return [x for x in result if x]
        if isinstance(obj, dict):
            for key in ["log", "message", "content", "raw", "text", "line"]:
                if key in obj and str(obj[key]).strip():
                    return [str(obj[key]).strip()]
            return [json.dumps(obj, ensure_ascii=False)]
        return [str(obj).strip()]
    if name.endswith(".csv"):
        return _extract_log_text_from_df(pd.read_csv(BytesIO(data)))
    if name.endswith(".tsv"):
        return _extract_log_text_from_df(pd.read_csv(BytesIO(data), sep="	"))
    if name.endswith((".xlsx", ".xls")):
        return _extract_log_text_from_df(pd.read_excel(BytesIO(data)))
    if name.endswith(".gz"):
        inner = gzip.decompress(data)
        return load_raw_lines_bytes(name[:-3], inner)
    if name.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(data), "r") as zf:
            members = [m for m in zf.namelist() if not m.endswith("/")]
            if not members:
                return []
            inner_name = members[0]
            inner = zf.read(inner_name)
            return load_raw_lines_bytes(inner_name, inner)
    raise ValueError(f"\u4e0d\u652f\u6301\u7684\u539f\u59cb\u65e5\u5fd7\u6587\u4ef6\u7c7b\u578b: {name}")



def load_raw_lines(uploaded_file) -> List[str]:
    name = str(getattr(uploaded_file, "name", "")).lower()
    data = uploaded_file.getvalue()
    return load_raw_lines_bytes(name, data)


@st.cache_data(show_spinner=False)
def _cached_parse_upload(
    name: str,
    data: bytes,
    drain_depth: int,
    drain_sim_th: float,
    drain_max_children: int,
) -> pd.DataFrame:
    cfg = Config()
    cfg.config.setdefault("drain", {})
    cfg.config["drain"]["depth"] = int(drain_depth)
    cfg.config["drain"]["sim_th"] = float(drain_sim_th)
    cfg.config["drain"]["max_children"] = int(drain_max_children)
    lines = load_raw_lines_bytes(name, data)
    if not lines:
        raise ValueError("\u4e0a\u4f20\u5185\u5bb9\u4e2d\u6ca1\u6709\u53ef\u89e3\u6790\u7684\u65e5\u5fd7\u884c")
    df = parse_lines_to_template_df(cfg, lines)
    if df.empty:
        raise ValueError("\u4f7f\u7528 Drain \u89e3\u6790\u540e\u672a\u751f\u6210\u6709\u6548\u6a21\u677f")
    return df


@st.cache_data(show_spinner=False)
def _cached_parse_upload(
    name: str,
    data: bytes,
    drain_depth: int,
    drain_sim_th: float,
    drain_max_children: int,
) -> pd.DataFrame:
    cfg = Config()
    cfg.config.setdefault("drain", {})
    cfg.config["drain"]["depth"] = int(drain_depth)
    cfg.config["drain"]["sim_th"] = float(drain_sim_th)
    cfg.config["drain"]["max_children"] = int(drain_max_children)
    lines = load_raw_lines_bytes(name, data)
    if not lines:
        raise ValueError("ä¸ä¼ æä»¶ä¸­æªè§£æåºæææ¥å¿")
    df = parse_lines_to_template_df(cfg, lines)
    if df.empty:
        raise ValueError("Drain è§£æåæªçææææ¨¡æ¿æ°æ®")
    return df



def parse_lines_to_template_df(config: Config, lines: List[str]) -> pd.DataFrame:
    parser = DrainParser(config)
    rows = []
    for i, line in enumerate(lines, 1):
        try:
            row = parser.parse_log_line(line)
            row["line_num"] = i
            rows.append(row)
        except Exception:
            continue
    return pd.DataFrame(rows)


def prepare_input_df(config: Config, uploaded_file) -> pd.DataFrame:
    name = str(getattr(uploaded_file, "name", "")).lower()
    data = uploaded_file.getvalue()
    required = {"template_id", "template"}

    structured_first = (".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet", ".gz", ".zip")
    if name.endswith(structured_first):
        try:
            df = load_structured_upload_bytes(name, data)
            if required.issubset(set(df.columns)):
                if "line_num" not in df.columns:
                    df["line_num"] = np.arange(1, len(df) + 1)
                return df
        except Exception:
            pass

    return _cached_parse_upload(
        name=name,
        data=data,
        drain_depth=int(config.get("drain.depth", 4)),
        drain_sim_th=float(config.get("drain.sim_th", 0.4)),
        drain_max_children=int(config.get("drain.max_children", 100)),
    )
