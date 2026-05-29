from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import numpy as np

from src.feature_extraction.semantic_features import SemanticFeatureExtractor
from src.rag.vector_store import SimpleVectorStore
from src.utils import Config, Logger


DEFAULT_CASES = [
    {
        "case_id": "CASE-SEC-001",
        "case_group": "security_attack",
        "title": "SSH brute force",
        "attack_type": "Credential Access",
        "technique": "T1110",
        "content": "Many failed password or invalid user events in a short time window.",
        "advice": "Limit source IP, enable MFA, and audit weak credentials.",
        "advice_cn": "\u9650\u5236\u9ad8\u98ce\u9669\u6765\u6e90 IP\uff0c\u542f\u7528 MFA\uff0c\u5e76\u5ba1\u8ba1\u5f31\u53e3\u4ee4\u8d26\u53f7\u4e0e\u66b4\u529b\u7834\u89e3\u6765\u6e90\u3002"
    },
    {
        "case_id": "CASE-SEC-002",
        "case_group": "security_attack",
        "title": "Unauthorized access attempt",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "Frequent permission denied, unauthorized, or forbidden events across protected resources.",
        "advice": "Review access policy boundaries and account permissions.",
        "advice_cn": "\u6838\u67e5\u8bbf\u95ee\u8fb9\u754c\u3001\u9632\u62a4\u89c4\u5219\u4e0e\u8d26\u53f7\u6743\u9650\u914d\u7f6e\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8d8a\u6743\u8bbf\u95ee\u3002"
    },
    {
        "case_id": "CASE-SEC-003",
        "case_group": "security_attack",
        "title": "SQL injection pattern",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "Request parameters include union select, or 1=1, sleep and similar SQL injection payloads.",
        "advice": "Enable WAF and parameterized queries, audit DB error logs.",
        "advice_cn": "\u542f\u7528 WAF \u4e0e\u53c2\u6570\u5316\u67e5\u8be2\uff0c\u5e76\u7ed3\u5408\u6570\u636e\u5e93\u9519\u8bef\u65e5\u5fd7\u6838\u67e5\u662f\u5426\u5b58\u5728\u6ce8\u5165\u63a2\u6d4b\u6216\u5229\u7528\u3002"
    },
    {
        "case_id": "CASE-SEC-004",
        "case_group": "security_attack",
        "title": "XSS injection pattern",
        "attack_type": "Execution",
        "technique": "T1059.007",
        "content": "Request contains script tag or onerror/onload style script injection patterns.",
        "advice": "Apply output encoding and CSP, strengthen input validation.",
        "advice_cn": "\u5b9e\u65bd\u8f93\u51fa\u7f16\u7801\u4e0e CSP \u7b56\u7565\uff0c\u5e76\u52a0\u5f3a\u8f93\u5165\u6821\u9a8c\uff0c\u6392\u67e5\u53d7\u5f71\u54cd\u9875\u9762\u6a21\u677f\u3002"
    },
    {
        "case_id": "CASE-SEC-005",
        "case_group": "security_attack",
        "title": "Privilege escalation activity",
        "attack_type": "Privilege Escalation",
        "technique": "T1068",
        "content": "Frequent sudo, su, or root transitions with sensitive command execution.",
        "advice": "Apply least privilege and audit sudoers and command chains.",
        "advice_cn": "\u843d\u5b9e\u6700\u5c0f\u6743\u9650\u539f\u5219\uff0c\u5ba1\u8ba1 sudoers\u3001\u7279\u6743\u7ec4\u6210\u5458\u4e0e\u9ad8\u5371\u547d\u4ee4\u94fe\u3002"
    },
    {
        "case_id": "CASE-SYS-001",
        "case_group": "system_anomaly",
        "title": "HDFS block transfer interruption",
        "attack_type": "System Reliability",
        "technique": "SYS-NET",
        "content": "Connection reset by peer or broken pipe during block transfer.",
        "advice": "Check network stability and DataNode link health.",
        "advice_cn": "\u68c0\u67e5\u7f51\u7edc\u7a33\u5b9a\u6027\u4e0e DataNode \u94fe\u8def\u5065\u5eb7\u72b6\u6001\u3002"
    },
    {
        "case_id": "CASE-SYS-002",
        "case_group": "system_anomaly",
        "title": "HDFS replication timeout",
        "attack_type": "System Reliability",
        "technique": "SYS-REPL",
        "content": "PendingReplicationMonitor timed out blocks and replication lag increased.",
        "advice": "Inspect replication queue and cluster load balance.",
        "advice_cn": "\u68c0\u67e5\u526f\u672c\u961f\u5217\u3001\u590d\u5236\u538b\u529b\u4e0e\u96c6\u7fa4\u8d1f\u8f7d\u5747\u8861\u60c5\u51b5\u3002"
    },
    {
        "case_id": "CASE-SYS-003",
        "case_group": "system_anomaly",
        "title": "DataNode IO stream exception",
        "attack_type": "System Reliability",
        "technique": "SYS-IO",
        "content": "IOException while receiving or writing HDFS blocks.",
        "advice": "Audit disk IO pressure and verify storage hardware state.",
        "advice_cn": "\u5ba1\u8ba1\u78c1\u76d8 IO \u538b\u529b\u4e0e\u6587\u4ef6\u7cfb\u7edf\u72b6\u6001\uff0c\u68c0\u67e5\u5b58\u50a8\u786c\u4ef6\u5065\u5eb7\u3002"
    },
    {
        "case_id": "CASE-SYS-004",
        "case_group": "system_anomaly",
        "title": "NameNode metadata inconsistency",
        "attack_type": "System Reliability",
        "technique": "SYS-META",
        "content": "Block map update anomalies or redundant addStoredBlock requests.",
        "advice": "Verify NameNode metadata consistency and replay state.",
        "advice_cn": "\u6838\u67e5 NameNode \u5143\u6570\u636e\u4e00\u81f4\u6027\u4e0e\u6062\u590d\u72b6\u6001\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u5757\u72b6\u6001\u6f02\u79fb\u3002"
    },
    {
        "case_id": "CASE-SEC-006",
        "case_group": "security_attack",
        "title": "Suspicious SSH successful login",
        "attack_type": "Credential Access",
        "technique": "T1078",
        "content": "Accepted password or publickey login from a new host, unusual source IP, or suspicious account context.",
        "advice": "Verify login user, source IP, login time, and post-login command activity; disable or lock the account if unauthorized.",
        "advice_cn": "\u6838\u5bf9\u767b\u5f55\u7528\u6237\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u6bb5\u4e0e\u540e\u7eed\u547d\u4ee4\u6d3b\u52a8\uff0c\u5982\u975e\u6388\u6743\u5e94\u7acb\u5373\u9501\u5b9a\u8d26\u53f7\u5e76\u963b\u65ad\u6765\u6e90\u3002"
    },
    {
        "case_id": "CASE-SEC-007",
        "case_group": "security_attack",
        "title": "Suspicious SSH session establishment",
        "attack_type": "Credential Access",
        "technique": "T1078",
        "content": "pam_unix(sshd:session) session opened events after risky authentication activity.",
        "advice": "Correlate with preceding authentication logs and audit commands executed in the session; review lateral movement traces.",
        "advice_cn": "\u7ed3\u5408\u524d\u5e8f\u8ba4\u8bc1\u65e5\u5fd7\u4e0e\u4f1a\u8bdd\u5185\u547d\u4ee4\u8fdb\u884c\u5173\u8054\u5206\u6790\uff0c\u91cd\u70b9\u6838\u67e5\u662f\u5426\u5b58\u5728\u6a2a\u5411\u79fb\u52a8\u75d5\u8ff9\u3002"
    },
    {
        "case_id": "CASE-SEC-008",
        "case_group": "security_attack",
        "title": "Privileged audit command execution",
        "attack_type": "Privilege Escalation",
        "technique": "T1068",
        "content": "Linux audit EXECVE or related privileged events involving sudo, uid=0, or sensitive command chains.",
        "advice": "Review audit trail, sudo chain, privileged binaries, and sensitive file changes; tighten sudoers and privileged group membership.",
        "advice_cn": "\u91cd\u70b9\u5ba1\u67e5 audit \u8f68\u8ff9\u3001sudo \u94fe\u8def\u3001\u7279\u6743\u4e8c\u8fdb\u5236\u4e0e\u654f\u611f\u6587\u4ef6\u53d8\u66f4\uff0c\u5e76\u6536\u7d27 sudoers \u4e0e\u7279\u6743\u7ec4\u6743\u9650\u3002"
    },
    {
        "case_id": "CASE-SEC-009",
        "case_group": "security_attack",
        "title": "Restricted web resource probing",
        "attack_type": "Discovery",
        "technique": "T1595",
        "content": "Apache errors such as AH01630 or denied-by-configuration indicating probing of restricted paths.",
        "advice": "Inspect requested paths, tighten Apache or WAF rules, and rate-limit or block probing clients.",
        "advice_cn": "\u68c0\u67e5\u88ab\u8bf7\u6c42\u8d44\u6e90\u8def\u5f84\uff0c\u6536\u7d27 Apache/WAF \u89c4\u5219\uff0c\u5e76\u5bf9\u63a2\u6d4b\u5ba2\u6237\u7aef\u5b9e\u65bd\u9650\u901f\u6216\u5c01\u7981\u3002"
    },
    {
        "case_id": "CASE-SEC-010",
        "case_group": "security_attack",
        "title": "Web scanner fingerprint activity",
        "attack_type": "Discovery",
        "technique": "T1046",
        "content": "WPScan, Nmap NSE, or similar scanner fingerprints in access logs targeting admin paths or plugins.",
        "advice": "Block or rate-limit scanner IPs, review exposed admin paths and plugins, and correlate with WAF or reverse proxy logs.",
        "advice_cn": "\u5c01\u7981\u6216\u9650\u901f\u626b\u63cf\u6e90 IP\uff0c\u68c0\u67e5\u66b4\u9732\u7684\u7ba1\u7406\u8def\u5f84\u4e0e\u63d2\u4ef6\uff0c\u5e76\u7ed3\u5408 WAF \u6216\u53cd\u5411\u4ee3\u7406\u65e5\u5fd7\u6838\u5bf9\u5f71\u54cd\u8303\u56f4\u3002"
    },
    {
        "case_id": "CASE-SEC-011",
        "case_group": "security_attack",
        "title": "Content negotiation probing",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "Apache negotiation errors such as AH00687 that may indicate path discovery or malformed request probing.",
        "advice": "Review suspicious request paths and file extensions, verify Apache content negotiation settings, and investigate repeated probing from the same client.",
        "advice_cn": "\u6838\u67e5\u53ef\u7591\u8bf7\u6c42\u8def\u5f84\u4e0e\u6269\u5c55\u540d\uff0c\u68c0\u67e5 Apache \u534f\u5546\u914d\u7f6e\uff0c\u5e76\u8ffd\u8e2a\u540c\u4e00\u5ba2\u6237\u7aef\u7684\u91cd\u590d\u63a2\u6d4b\u884c\u4e3a\u3002"
    },
    {
        "case_id": "CASE-SEC-012",
        "case_group": "security_attack",
        "title": "SSH excessive login attempts",
        "attack_type": "Credential Access",
        "technique": "T1110",
        "content": "Maximum login attempts exceeded or repeated authentication failures for privileged accounts.",
        "advice": "Block the offending source, inspect targeted accounts, and enable account lockout or MFA for exposed identities.",
        "advice_cn": "\u5c01\u7981\u5f02\u5e38\u6765\u6e90\uff0c\u68c0\u67e5\u88ab\u9488\u5bf9\u8d26\u53f7\uff0c\u5e76\u4e3a\u66b4\u9732\u8eab\u4efd\u542f\u7528\u767b\u5f55\u5931\u8d25\u9501\u5b9a\u6216 MFA\u3002"
    },
    {
        "case_id": "CASE-SEC-013",
        "case_group": "security_attack",
        "title": "SSH root login success",
        "attack_type": "Credential Access",
        "technique": "T1078",
        "content": "Accepted password or publickey login for root or another privileged account from an unusual source.",
        "advice": "Immediately verify the legitimacy of the privileged login, rotate exposed credentials, and review commands executed after login.",
        "advice_cn": "\u7acb\u5373\u6838\u67e5\u7279\u6743\u8d26\u53f7\u767b\u5f55\u5408\u6cd5\u6027\uff0c\u8f6e\u6362\u53ef\u7591\u51ed\u636e\uff0c\u5e76\u5ba1\u8ba1\u767b\u5f55\u540e\u7684\u547d\u4ee4\u6267\u884c\u4e0e\u4f1a\u8bdd\u884c\u4e3a\u3002"
    },
    {
        "case_id": "CASE-SEC-013A",
        "case_group": "security_attack",
        "title": "SSH service account successful login",
        "attack_type": "Credential Access",
        "technique": "T1078",
        "content": "Accepted password login for deploy, backup, db_admin, admin, or other service-like accounts from unusual sources or time windows.",
        "advice": "Verify the service account owner, source IP, login time window, and follow-up commands; suspend the account if the login is not expected.",
        "advice_cn": "\u6838\u5bf9\u670d\u52a1\u8d26\u53f7\u5f52\u5c5e\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u6bb5\u4e0e\u540e\u7eed\u547d\u4ee4\uff0c\u5982\u4e0d\u7b26\u5408\u9884\u671f\u5e94\u6682\u505c\u8be5\u8d26\u53f7\u5e76\u8fdb\u4e00\u6b65\u6838\u67e5\u3002"
    },
    {
        "case_id": "CASE-SEC-014",
        "case_group": "security_attack",
        "title": "SSH publickey login from unusual source",
        "attack_type": "Credential Access",
        "technique": "T1078",
        "content": "Accepted publickey authentication from a new host, unusual subnet, or unexpected service account context.",
        "advice": "Check authorized_keys, source subnet, and account history; revoke suspicious keys and review lateral movement traces.",
        "advice_cn": "\u68c0\u67e5 authorized_keys\u3001\u6765\u6e90\u7f51\u6bb5\u4e0e\u8d26\u53f7\u5386\u53f2\u884c\u4e3a\uff0c\u540a\u9500\u53ef\u7591\u5bc6\u94a5\u5e76\u6838\u67e5\u6a2a\u5411\u79fb\u52a8\u75d5\u8ff9\u3002"
    },
    {
        "case_id": "CASE-SEC-015",
        "case_group": "security_attack",
        "title": "SSH disconnect churn after authentication",
        "attack_type": "Credential Access",
        "technique": "T1110",
        "content": "Frequent disconnect, reset, or short-lived SSH sessions after authentication attempts, suggesting enumeration or unstable brute force tooling.",
        "advice": "Correlate disconnects with nearby failed and successful logins, inspect tooling fingerprints, and throttle the source host.",
        "advice_cn": "\u5c06\u5f02\u5e38\u65ad\u8fde\u4e0e\u76f8\u90bb\u8ba4\u8bc1\u5931\u8d25\u3001\u6210\u529f\u767b\u5f55\u4e8b\u4ef6\u5173\u8054\u5206\u6790\uff0c\u8bc6\u522b\u5de5\u5177\u6307\u7eb9\uff0c\u5e76\u5bf9\u6765\u6e90\u4e3b\u673a\u5b9e\u65bd\u9650\u901f\u3002"
    },
    {
        "case_id": "CASE-SEC-015A",
        "case_group": "security_attack",
        "title": "SSH account probing and user enumeration",
        "attack_type": "Credential Access",
        "technique": "T1110",
        "content": "user unknown, invalid user, check pass, or similar SSH traces indicating username enumeration or early-stage credential probing.",
        "advice": "Review unknown usernames and source IP cadence, identify enumeration sources, and block or rate-limit probing hosts before brute-force escalation.",
        "advice_cn": "核查未知用户名、来源 IP 与探测频率，识别账号枚举来源，并在暴力破解升级前对探测主机实施限速或封禁。"
    },
    {
        "case_id": "CASE-SEC-016",
        "case_group": "security_attack",
        "title": "Web admin path enumeration",
        "attack_type": "Discovery",
        "technique": "T1595",
        "content": "Repeated access to /admin, /login, /wp-login.php, or management endpoints with probing behavior.",
        "advice": "Review exposed admin endpoints, tighten authentication and access controls, and block aggressive probing clients.",
        "advice_cn": "\u68c0\u67e5\u66b4\u9732\u7684\u7ba1\u7406\u5165\u53e3\uff0c\u5f3a\u5316\u8ba4\u8bc1\u4e0e\u8bbf\u95ee\u63a7\u5236\uff0c\u5e76\u5c01\u7981\u9ad8\u9891\u63a2\u6d4b\u5ba2\u6237\u7aef\u3002"
    },
    {
        "case_id": "CASE-SEC-017",
        "case_group": "security_attack",
        "title": "Web login brute-force pattern",
        "attack_type": "Credential Access",
        "technique": "T1110",
        "content": "Repeated login attempts against application login endpoints with changing usernames, parameters, or source cadence.",
        "advice": "Enable login throttling, MFA, and account lockout; review targeted users and originating IP reputation.",
        "advice_cn": "\u542f\u7528\u767b\u5f55\u9650\u901f\u3001MFA \u4e0e\u8d26\u53f7\u9501\u5b9a\u7b56\u7565\uff0c\u5e76\u68c0\u67e5\u88ab\u9488\u5bf9\u7528\u6237\u4e0e\u6765\u6e90 IP \u4fe1\u8a89\u3002"
    },
    {
        "case_id": "CASE-SEC-018",
        "case_group": "security_attack",
        "title": "PHP script probing",
        "attack_type": "Discovery",
        "technique": "T1595",
        "content": "script not found or unable to stat errors indicating direct probing of PHP scripts or upload paths.",
        "advice": "Inspect probed script paths, review Referer and user agent, and block repeated script enumeration attempts.",
        "advice_cn": "\u6838\u67e5\u88ab\u63a2\u6d4b\u811a\u672c\u8def\u5f84\u3001Referer \u4e0e User-Agent\uff0c\u5e76\u5c01\u7981\u91cd\u590d\u811a\u672c\u679a\u4e3e\u6765\u6e90\u3002"
    },
    {
        "case_id": "CASE-SEC-019",
        "case_group": "security_attack",
        "title": "Sensitive resource denial probing",
        "attack_type": "Discovery",
        "technique": "T1595",
        "content": "403, denied-by-configuration, or similar responses while probing restricted directories or files.",
        "advice": "Confirm whether the requested resource should ever be reachable, tighten virtual host rules, and preserve source evidence.",
        "advice_cn": "\u786e\u8ba4\u88ab\u63a2\u6d4b\u8d44\u6e90\u662f\u5426\u672c\u5e94\u5f00\u653e\uff0c\u6536\u7d27\u865a\u62df\u4e3b\u673a\u89c4\u5219\uff0c\u5e76\u4fdd\u7559\u6765\u6e90\u8bc1\u636e\u7528\u4e8e\u8ffd\u8e2a\u3002"
    },
    {
        "case_id": "CASE-SEC-020",
        "case_group": "security_attack",
        "title": "Audit command execution chain",
        "attack_type": "Privilege Escalation",
        "technique": "T1059",
        "content": "Audit records show chained command execution, shell spawning, or sensitive binary invocation from a privileged context.",
        "advice": "Reconstruct parent-child process chains, identify initial trigger commands, and inspect file or account changes made by the chain.",
        "advice_cn": "\u8fd8\u539f\u7236\u5b50\u8fdb\u7a0b\u94fe\u8def\uff0c\u5b9a\u4f4d\u6700\u521d\u89e6\u53d1\u547d\u4ee4\uff0c\u5e76\u68c0\u67e5\u8be5\u94fe\u8def\u5f15\u53d1\u7684\u6587\u4ef6\u6216\u8d26\u53f7\u53d8\u66f4\u3002"
    },
    {
        "case_id": "CASE-SEC-021",
        "case_group": "security_attack",
        "title": "Sensitive account file access in audit logs",
        "attack_type": "Credential Access",
        "technique": "T1003",
        "content": "Audit logs indicate access to passwd, shadow, sudoers, SSH keys, or related identity artifacts.",
        "advice": "Validate whether the access was expected, review the accessing process and user, and rotate exposed credentials or keys if needed.",
        "advice_cn": "\u786e\u8ba4\u5bf9 passwd\u3001shadow\u3001sudoers \u6216\u5bc6\u94a5\u6587\u4ef6\u7684\u8bbf\u95ee\u662f\u5426\u7b26\u5408\u9884\u671f\uff0c\u5e76\u89c6\u60c5\u51b5\u8f6e\u6362\u66b4\u9732\u51ed\u636e\u6216\u5bc6\u94a5\u3002"
    },
    {
        "case_id": "CASE-SEC-022",
        "case_group": "security_attack",
        "title": "Sudo chain anomaly",
        "attack_type": "Privilege Escalation",
        "technique": "T1548",
        "content": "Sudo-related logs indicate unusual privilege escalation cadence, sensitive commands, or unexpected accounts using sudo.",
        "advice": "Audit sudoers entries, confirm command legitimacy, and review whether the account should hold elevated privileges at that time.",
        "advice_cn": "\u5ba1\u8ba1 sudoers \u914d\u7f6e\u3001\u786e\u8ba4\u547d\u4ee4\u5408\u6cd5\u6027\uff0c\u5e76\u6838\u67e5\u8be5\u8d26\u53f7\u5728\u5f53\u524d\u65f6\u6bb5\u662f\u5426\u5e94\u5177\u5907\u63d0\u6743\u6743\u9650\u3002"
    },
    {
        "case_id": "CASE-SEC-023",
        "case_group": "security_attack",
        "title": "OpenVPN remote access establishment",
        "attack_type": "Initial Access",
        "technique": "T1133",
        "content": "OpenVPN peer connection initiated events from unusual peers, networks, or service accounts.",
        "advice": "Verify peer identity, certificate usage, connection time window, and subsequent host activity; revoke suspicious certificates if needed.",
        "advice_cn": "\u6838\u67e5\u5bf9\u7aef\u8eab\u4efd\u3001\u8bc1\u4e66\u4f7f\u7528\u60c5\u51b5\u3001\u8fde\u63a5\u65f6\u6bb5\u4e0e\u540e\u7eed\u4e3b\u673a\u884c\u4e3a\uff0c\u5fc5\u8981\u65f6\u540a\u9500\u53ef\u7591\u8bc1\u4e66\u3002"
    },
    {
        "case_id": "CASE-SEC-024",
        "case_group": "security_attack",
        "title": "OpenVPN reconnect churn",
        "attack_type": "Initial Access",
        "technique": "T1133",
        "content": "Repeated OpenVPN connect-disconnect cycles that may indicate credential abuse, unstable tunneling tools, or probing.",
        "advice": "Correlate reconnect cycles with authentication results, peer IP changes, and tunnel activity; consider temporary source blocking.",
        "advice_cn": "\u5c06\u91cd\u590d\u91cd\u8fde\u4e0e\u8ba4\u8bc1\u7ed3\u679c\u3001\u5bf9\u7aef IP \u53d8\u5316\u548c\u96a7\u9053\u6d3b\u52a8\u5173\u8054\u5206\u6790\uff0c\u5fc5\u8981\u65f6\u4e34\u65f6\u5c01\u7981\u6765\u6e90\u3002"
    },
    {
        "case_id": "CASE-SEC-025",
        "case_group": "security_attack",
        "title": "Apache malformed request spray",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "A burst of malformed HTTP requests, uncommon verbs, or invalid protocol combinations targeting the same host.",
        "advice": "Inspect request variants, confirm whether they target a known parser weakness, and tune reverse proxy or WAF signatures.",
        "advice_cn": "\u68c0\u67e5\u5f02\u5e38\u8bf7\u6c42\u53d8\u4f53\uff0c\u786e\u8ba4\u662f\u5426\u9488\u5bf9\u5df2\u77e5\u89e3\u6790\u5f31\u70b9\uff0c\u5e76\u4f18\u5316\u53cd\u5411\u4ee3\u7406\u6216 WAF \u89c4\u5219\u3002"
    },
    {
        "case_id": "CASE-SEC-026",
        "case_group": "security_attack",
        "title": "Web error trigger after scanner probe",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "Web error logs spike shortly after scanning or probing traffic, suggesting the scanner is now hitting executable paths or weak handlers.",
        "advice": "Correlate access and error logs by client and timestamp, identify the first failing endpoint, and validate whether a vulnerable handler exists.",
        "advice_cn": "\u6309\u5ba2\u6237\u7aef\u4e0e\u65f6\u95f4\u5173\u8054\u8bbf\u95ee\u65e5\u5fd7\u548c\u9519\u8bef\u65e5\u5fd7\uff0c\u5b9a\u4f4d\u6700\u65e9\u89e6\u53d1\u5f02\u5e38\u7684\u7aef\u70b9\uff0c\u5e76\u9a8c\u8bc1\u662f\u5426\u5b58\u5728\u8106\u5f31\u5904\u7406\u5668\u3002"
    },
    {
        "case_id": "CASE-SEC-027",
        "case_group": "security_attack",
        "title": "Prompt injection attempt against AI agent",
        "attack_type": "Defense Evasion",
        "technique": "LLM-PI",
        "content": "Prompt injection, instruction override, jailbreak, or secret extraction attempts targeting an AI agent or LLM workflow.",
        "advice": "Preserve the original prompt content, isolate the affected agent session, review prompt templates and tool permissions, and add deny rules for instruction override or secret exfiltration patterns.",
        "advice_cn": "保留原始 prompt 与上下文，隔离受影响的 AI agent 会话，检查提示词模板与工具权限，并为指令覆写、秘密提取等模式增加阻断规则。"
    },
    {
        "case_id": "CASE-SEC-028",
        "case_group": "security_attack",
        "title": "WebShell upload or execution signal",
        "attack_type": "Persistence",
        "technique": "T1505.003",
        "content": "Web access or error logs show suspicious upload paths, webshell-like filenames, command parameters, or server-side script execution from writable directories.",
        "advice": "Quarantine the suspected file, preserve access and error logs, verify upload handlers and file permissions, and hunt for follow-up command execution from the web server account.",
        "advice_cn": "隔离可疑文件并保留访问/错误日志，核查上传接口、目录权限与 Web 服务账号后续命令执行痕迹。"
    },
    {
        "case_id": "CASE-SEC-029",
        "case_group": "security_attack",
        "title": "Command injection through web request",
        "attack_type": "Execution",
        "technique": "T1059",
        "content": "HTTP parameters contain command separators, shell metacharacters, curl, wget, bash, sh, nc, or encoded command payloads consistent with command injection attempts.",
        "advice": "Identify the vulnerable endpoint, correlate access logs with process execution and outbound traffic, block the source, and validate input handling on the affected route.",
        "advice_cn": "定位可疑接口，将访问日志与进程执行、出站连接关联分析，阻断来源并复核受影响路由的输入处理逻辑。"
    },
    {
        "case_id": "CASE-SEC-030",
        "case_group": "security_attack",
        "title": "Suspicious file download by server process",
        "attack_type": "Command and Control",
        "technique": "T1105",
        "content": "Audit or process logs show wget, curl, python, perl, or shell tools downloading scripts, binaries, or payloads into temporary or web-writable directories.",
        "advice": "Preserve the downloaded artifact hash, block the destination domain or IP, inspect the launching process tree, and search for execution or persistence after download.",
        "advice_cn": "保留下载文件哈希，阻断目标域名或 IP，审查发起进程树，并排查下载后的执行与持久化行为。"
    },
    {
        "case_id": "CASE-SEC-031",
        "case_group": "security_attack",
        "title": "Outbound C2 beaconing pattern",
        "attack_type": "Command and Control",
        "technique": "T1071",
        "content": "Repeated outbound connections, DNS queries, or HTTP requests with regular cadence, unusual user agents, rare domains, or small periodic payloads.",
        "advice": "Correlate destination reputation, connection periodicity, process owner, and DNS history; isolate the host if the beacon is unauthorized.",
        "advice_cn": "结合目标信誉、连接周期、进程归属和 DNS 历史进行研判；如确认为异常信标，应隔离主机并保留流量证据。"
    },
    {
        "case_id": "CASE-SEC-032",
        "case_group": "security_attack",
        "title": "Data exfiltration over web or DNS",
        "attack_type": "Exfiltration",
        "technique": "T1041",
        "content": "Logs show abnormal outbound transfer volume, long encoded query strings, repeated POST uploads, archive downloads, or unusual DNS query length from a sensitive host.",
        "advice": "Identify transferred objects and destination, preserve proxy or DNS logs, disable the involved account or process, and verify whether sensitive files were accessed before transfer.",
        "advice_cn": "定位传输对象与目标地址，保留代理/DNS 日志，停用相关账号或进程，并核查传输前是否访问敏感文件。"
    },
    {
        "case_id": "CASE-SEC-033",
        "case_group": "security_attack",
        "title": "Lateral movement through SSH or remote service",
        "attack_type": "Lateral Movement",
        "technique": "T1021",
        "content": "A host initiates SSH, VPN, SMB, RDP, or service-login activity to multiple internal systems shortly after suspicious authentication or privilege activity.",
        "advice": "Map the source account and target hosts, inspect authentication chains, revoke exposed credentials, and hunt for copied keys or remote command execution.",
        "advice_cn": "梳理源账号与目标主机，关联认证链路，吊销可疑凭据，并排查密钥复制或远程命令执行痕迹。"
    },
    {
        "case_id": "CASE-SEC-034",
        "case_group": "security_attack",
        "title": "SSH key tampering or unauthorized key addition",
        "attack_type": "Persistence",
        "technique": "T1098.004",
        "content": "Audit logs indicate writes to authorized_keys, sshd_config, known_hosts, or SSH key files by an unexpected process or account.",
        "advice": "Review file diff and ownership, remove unauthorized keys, rotate affected credentials, and check whether the change followed a suspicious login.",
        "advice_cn": "检查 SSH 配置和密钥文件变更、属主与差异，移除未授权密钥，轮换受影响凭据，并关联前序可疑登录。"
    },
    {
        "case_id": "CASE-SEC-035",
        "case_group": "security_attack",
        "title": "Cron or systemd persistence change",
        "attack_type": "Persistence",
        "technique": "T1053",
        "content": "Audit or system logs show unexpected creation or modification of crontab, systemd service, rc.local, init script, or timer units.",
        "advice": "Disable suspicious scheduled tasks or services, preserve unit files and command targets, and trace the user or process that created the persistence entry.",
        "advice_cn": "停用可疑计划任务或服务，保留 unit/脚本内容与命令目标，并追踪创建该持久化项的用户或进程。"
    },
    {
        "case_id": "CASE-SEC-036",
        "case_group": "security_attack",
        "title": "Credential dumping or secret discovery",
        "attack_type": "Credential Access",
        "technique": "T1552",
        "content": "Audit or shell activity references shadow, passwd, id_rsa, credential files, token files, browser secrets, environment dumps, or config files containing keys.",
        "advice": "Preserve process and file access evidence, rotate exposed secrets, search for archive or exfiltration activity, and validate least-privilege controls.",
        "advice_cn": "保留进程与文件访问证据，轮换暴露密钥或凭据，搜索压缩打包与外传行为，并复核最小权限控制。"
    },
    {
        "case_id": "CASE-SEC-037",
        "case_group": "security_attack",
        "title": "Log tampering or audit trail deletion",
        "attack_type": "Defense Evasion",
        "technique": "T1070",
        "content": "Audit or shell logs show deletion, truncation, permission changes, or service stops affecting auth.log, audit.log, web logs, bash history, or security telemetry.",
        "advice": "Preserve remaining logs, compare with remote collectors, identify the account and process performing tampering, and rebuild the timeline from independent telemetry.",
        "advice_cn": "保留残余日志并与远程采集端比对，定位篡改账号和进程，使用独立遥测重建事件时间线。"
    },
    {
        "case_id": "CASE-SEC-038",
        "case_group": "security_attack",
        "title": "Suspicious archive staging before transfer",
        "attack_type": "Collection",
        "technique": "T1560",
        "content": "Commands or audit events show tar, zip, gzip, 7z, or archive creation over web roots, home directories, configuration folders, or sensitive data paths.",
        "advice": "Inspect archive contents, correlate with later network transfer, preserve file metadata, and determine whether sensitive data was staged for exfiltration.",
        "advice_cn": "检查压缩包内容，关联后续网络传输，保留文件元数据，并判断是否为敏感数据外传前的暂存。"
    },
    {
        "case_id": "CASE-SEC-039",
        "case_group": "security_attack",
        "title": "Apache path traversal or file disclosure probe",
        "attack_type": "Initial Access",
        "technique": "T1190",
        "content": "Web requests include ../ traversal, encoded traversal, passwd, shadow, proc, env, backup files, or configuration file disclosure probes.",
        "advice": "Review requested paths and response codes, verify canonicalization and static file handling, block the source, and check whether sensitive files were returned.",
        "advice_cn": "复核请求路径与响应码，验证路径规范化和静态文件处理，阻断来源，并确认是否返回了敏感文件。"
    },
    {
        "case_id": "CASE-SEC-040",
        "case_group": "security_attack",
        "title": "VPN credential abuse or impossible travel",
        "attack_type": "Initial Access",
        "technique": "T1133",
        "content": "OpenVPN or remote access logs show the same identity connecting from unusual countries, new ASN ranges, overlapping sessions, or rapid reconnects after failures.",
        "advice": "Verify user legitimacy, compare geo and ASN history, revoke or rotate the certificate or password, and inspect internal activity after VPN establishment.",
        "advice_cn": "核实用户合法性，对比地理位置和 ASN 历史，吊销或轮换证书/密码，并审查 VPN 建立后的内网活动。"
    },
    {
        "case_id": "CASE-SEC-041",
        "case_group": "security_attack",
        "title": "DNS tunneling or encoded domain pattern",
        "attack_type": "Command and Control",
        "technique": "T1071.004",
        "content": "DNS logs contain unusually long labels, high-entropy subdomains, repeated NXDOMAIN responses, rare domains, or query bursts from a single host.",
        "advice": "Analyze query entropy and destination reputation, isolate the source if tunneling is suspected, and correlate with process and proxy telemetry.",
        "advice_cn": "分析查询熵值与目标信誉，疑似隧道时隔离源主机，并关联进程、代理和网络遥测。"
    },
    {
        "case_id": "CASE-SEC-042",
        "case_group": "security_attack",
        "title": "Container or service account abuse",
        "attack_type": "Privilege Escalation",
        "technique": "T1611",
        "content": "Audit logs show service accounts, container runtimes, or web server users invoking privileged binaries, mounting paths, changing capabilities, or accessing host secrets.",
        "advice": "Review runtime permissions, mounted paths, service account scope, and host file access; isolate the workload if privilege boundaries were crossed.",
        "advice_cn": "核查运行时权限、挂载路径、服务账号范围与主机文件访问；如存在越界提权，应隔离相关工作负载。"
    }
]


SECURITY_HINT_KEYWORDS = [
    "failed password",
    "invalid user",
    "authentication failure",
    "maximum login attempts exceeded",
    "accepted password",
    "accepted publickey",
    "accepted keyboard-interactive",
    "permission denied",
    "unauthorized",
    "forbidden",
    "sudo",
    "privilege",
    "escalat",
    "audit(",
    "execve",
    "uid=0",
    "sql",
    "union",
    "or 1=1",
    "sleep(",
    "xss",
    "script",
    "script not found",
    "client denied",
    "negotiation:error",
    "ah01630",
    "ah00687",
    "onerror",
    "onload",
    "powershell",
    "iex",
    "base64",
    "scan",
    "nmap",
    "wpscan",
    "malware",
    "c2",
    "exploit",
    "openvpn",
    "peer connection initiated",
    "tls error",
    "certificate",
    "session opened for user"
]



SYSTEM_HINT_KEYWORDS = [
    "datanode",
    "namenode",
    "block",
    "packetresponder",
    "pendingreplication",
    "replication",
    "connection reset by peer",
    "broken pipe",
    "sockettimeoutexception",
    "ioexception",
    "interruptedioexception",
    "could not read from stream",
    "blockreceiver",
    "addstoredblock",
    "volumemap",
]


ADVICE_CN_MAP = {
    "Limit source IP, enable MFA, and audit weak credentials.": "\u9650\u5236\u9ad8\u98ce\u9669\u6765\u6e90 IP\uff0c\u542f\u7528 MFA\uff0c\u5e76\u5ba1\u8ba1\u5f31\u53e3\u4ee4\u8d26\u53f7\u4e0e\u66b4\u529b\u7834\u89e3\u6765\u6e90\u3002",
    "Review access policy boundaries and account permissions.": "\u6838\u67e5\u8bbf\u95ee\u8fb9\u754c\u3001\u9632\u62a4\u89c4\u5219\u4e0e\u8d26\u53f7\u6743\u9650\u914d\u7f6e\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u8d8a\u6743\u8bbf\u95ee\u3002",
    "Enable WAF and parameterized queries, audit DB error logs.": "\u542f\u7528 WAF \u4e0e\u53c2\u6570\u5316\u67e5\u8be2\uff0c\u5e76\u7ed3\u5408\u6570\u636e\u5e93\u9519\u8bef\u65e5\u5fd7\u6838\u67e5\u662f\u5426\u5b58\u5728\u6ce8\u5165\u63a2\u6d4b\u6216\u5229\u7528\u3002",
    "Apply output encoding and CSP, strengthen input validation.": "\u5b9e\u65bd\u8f93\u51fa\u7f16\u7801\u4e0e CSP \u7b56\u7565\uff0c\u5e76\u52a0\u5f3a\u8f93\u5165\u6821\u9a8c\uff0c\u6392\u67e5\u53d7\u5f71\u54cd\u9875\u9762\u6a21\u677f\u3002",
    "Apply least privilege and audit sudoers and command chains.": "\u843d\u5b9e\u6700\u5c0f\u6743\u9650\u539f\u5219\uff0c\u5ba1\u8ba1 sudoers\u3001\u7279\u6743\u7ec4\u6210\u5458\u4e0e\u9ad8\u5371\u547d\u4ee4\u94fe\u3002",
    "Check network stability and DataNode link health.": "\u68c0\u67e5\u7f51\u7edc\u7a33\u5b9a\u6027\u4e0e DataNode \u94fe\u8def\u5065\u5eb7\u72b6\u6001\u3002",
    "Inspect replication queue and cluster load balance.": "\u68c0\u67e5\u526f\u672c\u961f\u5217\u3001\u590d\u5236\u538b\u529b\u4e0e\u96c6\u7fa4\u8d1f\u8f7d\u5747\u8861\u60c5\u51b5\u3002",
    "Audit disk IO pressure and verify storage hardware state.": "\u5ba1\u8ba1\u78c1\u76d8 IO \u538b\u529b\u4e0e\u6587\u4ef6\u7cfb\u7edf\u72b6\u6001\uff0c\u68c0\u67e5\u5b58\u50a8\u786c\u4ef6\u5065\u5eb7\u3002",
    "Verify NameNode metadata consistency and replay state.": "\u6838\u67e5 NameNode \u5143\u6570\u636e\u4e00\u81f4\u6027\u4e0e\u6062\u590d\u72b6\u6001\uff0c\u786e\u8ba4\u662f\u5426\u5b58\u5728\u5757\u72b6\u6001\u6f02\u79fb\u3002",
    "Verify login user, source IP, login time, and post-login command activity; disable or lock the account if unauthorized.": "\u6838\u5bf9\u767b\u5f55\u7528\u6237\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u6bb5\u4e0e\u540e\u7eed\u547d\u4ee4\u6d3b\u52a8\uff0c\u5982\u975e\u6388\u6743\u5e94\u7acb\u5373\u9501\u5b9a\u8d26\u53f7\u5e76\u963b\u65ad\u6765\u6e90\u3002",
    "Correlate with preceding authentication logs and audit commands executed in the session; review lateral movement traces.": "\u7ed3\u5408\u524d\u5e8f\u8ba4\u8bc1\u65e5\u5fd7\u4e0e\u4f1a\u8bdd\u5185\u547d\u4ee4\u8fdb\u884c\u5173\u8054\u5206\u6790\uff0c\u91cd\u70b9\u6838\u67e5\u662f\u5426\u5b58\u5728\u6a2a\u5411\u79fb\u52a8\u75d5\u8ff9\u3002",
    "Review audit trail, sudo chain, privileged binaries, and sensitive file changes; tighten sudoers and privileged group membership.": "\u91cd\u70b9\u5ba1\u67e5 audit \u8f68\u8ff9\u3001sudo \u94fe\u8def\u3001\u7279\u6743\u4e8c\u8fdb\u5236\u4e0e\u654f\u611f\u6587\u4ef6\u53d8\u66f4\uff0c\u5e76\u6536\u7d27 sudoers \u4e0e\u7279\u6743\u7ec4\u6743\u9650\u3002",
    "Inspect requested paths, tighten Apache or WAF rules, and rate-limit or block probing clients.": "\u68c0\u67e5\u88ab\u8bf7\u6c42\u8d44\u6e90\u8def\u5f84\uff0c\u6536\u7d27 Apache/WAF \u89c4\u5219\uff0c\u5e76\u5bf9\u63a2\u6d4b\u5ba2\u6237\u7aef\u5b9e\u65bd\u9650\u901f\u6216\u5c01\u7981\u3002",
    "Block or rate-limit scanner IPs, review exposed admin paths and plugins, and correlate with WAF or reverse proxy logs.": "\u5c01\u7981\u6216\u9650\u901f\u626b\u63cf\u6e90 IP\uff0c\u68c0\u67e5\u66b4\u9732\u7684\u7ba1\u7406\u8def\u5f84\u4e0e\u63d2\u4ef6\uff0c\u5e76\u7ed3\u5408 WAF \u6216\u53cd\u5411\u4ee3\u7406\u65e5\u5fd7\u6838\u5bf9\u5f71\u54cd\u8303\u56f4\u3002",
    "Review suspicious request paths and file extensions, verify Apache content negotiation settings, and investigate repeated probing from the same client.": "\u6838\u67e5\u53ef\u7591\u8bf7\u6c42\u8def\u5f84\u4e0e\u6269\u5c55\u540d\uff0c\u68c0\u67e5 Apache \u534f\u5546\u914d\u7f6e\uff0c\u5e76\u8ffd\u8e2a\u540c\u4e00\u5ba2\u6237\u7aef\u7684\u91cd\u590d\u63a2\u6d4b\u884c\u4e3a\u3002",
    "Block the offending source, inspect targeted accounts, and enable account lockout or MFA for exposed identities.": "\u5c01\u7981\u5f02\u5e38\u6765\u6e90\uff0c\u68c0\u67e5\u88ab\u9488\u5bf9\u8d26\u53f7\uff0c\u5e76\u4e3a\u66b4\u9732\u8eab\u4efd\u542f\u7528\u767b\u5f55\u5931\u8d25\u9501\u5b9a\u6216 MFA\u3002",
    "Immediately verify the legitimacy of the privileged login, rotate exposed credentials, and review commands executed after login.": "\u7acb\u5373\u6838\u67e5\u7279\u6743\u8d26\u53f7\u767b\u5f55\u5408\u6cd5\u6027\uff0c\u8f6e\u6362\u53ef\u7591\u51ed\u636e\uff0c\u5e76\u5ba1\u8ba1\u767b\u5f55\u540e\u7684\u547d\u4ee4\u6267\u884c\u4e0e\u4f1a\u8bdd\u884c\u4e3a\u3002",
    "Verify the service account owner, source IP, login time window, and follow-up commands; suspend the account if the login is not expected.": "\u6838\u5bf9\u670d\u52a1\u8d26\u53f7\u5f52\u5c5e\u3001\u6765\u6e90 IP\u3001\u767b\u5f55\u65f6\u6bb5\u4e0e\u540e\u7eed\u547d\u4ee4\uff0c\u5982\u4e0d\u7b26\u5408\u9884\u671f\u5e94\u6682\u505c\u8be5\u8d26\u53f7\u5e76\u8fdb\u4e00\u6b65\u6838\u67e5\u3002",
    "Check authorized_keys, source subnet, and account history; revoke suspicious keys and review lateral movement traces.": "\u68c0\u67e5 authorized_keys\u3001\u6765\u6e90\u7f51\u6bb5\u4e0e\u8d26\u53f7\u5386\u53f2\u884c\u4e3a\uff0c\u540a\u9500\u53ef\u7591\u5bc6\u94a5\u5e76\u6838\u67e5\u6a2a\u5411\u79fb\u52a8\u75d5\u8ff9\u3002",
    "Correlate disconnects with nearby failed and successful logins, inspect tooling fingerprints, and throttle the source host.": "\u5c06\u5f02\u5e38\u65ad\u8fde\u4e0e\u76f8\u90bb\u8ba4\u8bc1\u5931\u8d25\u3001\u6210\u529f\u767b\u5f55\u4e8b\u4ef6\u5173\u8054\u5206\u6790\uff0c\u8bc6\u522b\u5de5\u5177\u6307\u7eb9\uff0c\u5e76\u5bf9\u6765\u6e90\u4e3b\u673a\u5b9e\u65bd\u9650\u901f\u3002",
    "Review exposed admin endpoints, tighten authentication and access controls, and block aggressive probing clients.": "\u68c0\u67e5\u66b4\u9732\u7684\u7ba1\u7406\u5165\u53e3\uff0c\u5f3a\u5316\u8ba4\u8bc1\u4e0e\u8bbf\u95ee\u63a7\u5236\uff0c\u5e76\u5c01\u7981\u9ad8\u9891\u63a2\u6d4b\u5ba2\u6237\u7aef\u3002",
    "Enable login throttling, MFA, and account lockout; review targeted users and originating IP reputation.": "\u542f\u7528\u767b\u5f55\u9650\u901f\u3001MFA \u4e0e\u8d26\u53f7\u9501\u5b9a\u7b56\u7565\uff0c\u5e76\u68c0\u67e5\u88ab\u9488\u5bf9\u7528\u6237\u4e0e\u6765\u6e90 IP \u4fe1\u8a89\u3002",
    "Inspect probed script paths, review Referer and user agent, and block repeated script enumeration attempts.": "\u6838\u67e5\u88ab\u63a2\u6d4b\u811a\u672c\u8def\u5f84\u3001Referer \u4e0e User-Agent\uff0c\u5e76\u5c01\u7981\u91cd\u590d\u811a\u672c\u679a\u4e3e\u6765\u6e90\u3002",
    "Confirm whether the requested resource should ever be reachable, tighten virtual host rules, and preserve source evidence.": "\u786e\u8ba4\u88ab\u63a2\u6d4b\u8d44\u6e90\u662f\u5426\u672c\u5e94\u5f00\u653e\uff0c\u6536\u7d27\u865a\u62df\u4e3b\u673a\u89c4\u5219\uff0c\u5e76\u4fdd\u7559\u6765\u6e90\u8bc1\u636e\u7528\u4e8e\u8ffd\u8e2a\u3002",
    "Reconstruct parent-child process chains, identify initial trigger commands, and inspect file or account changes made by the chain.": "\u8fd8\u539f\u7236\u5b50\u8fdb\u7a0b\u94fe\u8def\uff0c\u5b9a\u4f4d\u6700\u521d\u89e6\u53d1\u547d\u4ee4\uff0c\u5e76\u68c0\u67e5\u8be5\u94fe\u8def\u5f15\u53d1\u7684\u6587\u4ef6\u6216\u8d26\u53f7\u53d8\u66f4\u3002",
    "Validate whether the access was expected, review the accessing process and user, and rotate exposed credentials or keys if needed.": "\u786e\u8ba4\u5bf9 passwd\u3001shadow\u3001sudoers \u6216\u5bc6\u94a5\u6587\u4ef6\u7684\u8bbf\u95ee\u662f\u5426\u7b26\u5408\u9884\u671f\uff0c\u5e76\u89c6\u60c5\u51b5\u8f6e\u6362\u66b4\u9732\u51ed\u636e\u6216\u5bc6\u94a5\u3002",
    "Audit sudoers entries, confirm command legitimacy, and review whether the account should hold elevated privileges at that time.": "\u5ba1\u8ba1 sudoers \u914d\u7f6e\u3001\u786e\u8ba4\u547d\u4ee4\u5408\u6cd5\u6027\uff0c\u5e76\u6838\u67e5\u8be5\u8d26\u53f7\u5728\u5f53\u524d\u65f6\u6bb5\u662f\u5426\u5e94\u5177\u5907\u63d0\u6743\u6743\u9650\u3002",
    "Verify peer identity, certificate usage, connection time window, and subsequent host activity; revoke suspicious certificates if needed.": "\u6838\u67e5\u5bf9\u7aef\u8eab\u4efd\u3001\u8bc1\u4e66\u4f7f\u7528\u60c5\u51b5\u3001\u8fde\u63a5\u65f6\u6bb5\u4e0e\u540e\u7eed\u4e3b\u673a\u884c\u4e3a\uff0c\u5fc5\u8981\u65f6\u540a\u9500\u53ef\u7591\u8bc1\u4e66\u3002",
    "Correlate reconnect cycles with authentication results, peer IP changes, and tunnel activity; consider temporary source blocking.": "\u5c06\u91cd\u590d\u91cd\u8fde\u4e0e\u8ba4\u8bc1\u7ed3\u679c\u3001\u5bf9\u7aef IP \u53d8\u5316\u548c\u96a7\u9053\u6d3b\u52a8\u5173\u8054\u5206\u6790\uff0c\u5fc5\u8981\u65f6\u4e34\u65f6\u5c01\u7981\u6765\u6e90\u3002",
    "Inspect request variants, confirm whether they target a known parser weakness, and tune reverse proxy or WAF signatures.": "\u68c0\u67e5\u5f02\u5e38\u8bf7\u6c42\u53d8\u4f53\uff0c\u786e\u8ba4\u662f\u5426\u9488\u5bf9\u5df2\u77e5\u89e3\u6790\u5f31\u70b9\uff0c\u5e76\u4f18\u5316\u53cd\u5411\u4ee3\u7406\u6216 WAF \u89c4\u5219\u3002",
    "Correlate access and error logs by client and timestamp, identify the first failing endpoint, and validate whether a vulnerable handler exists.": "\u6309\u5ba2\u6237\u7aef\u4e0e\u65f6\u95f4\u5173\u8054\u8bbf\u95ee\u65e5\u5fd7\u548c\u9519\u8bef\u65e5\u5fd7\uff0c\u5b9a\u4f4d\u6700\u65e9\u89e6\u53d1\u5f02\u5e38\u7684\u7aef\u70b9\uff0c\u5e76\u9a8c\u8bc1\u662f\u5426\u5b58\u5728\u8106\u5f31\u5904\u7406\u5668\u3002",
    "Manual review with context is required.": "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002",
    "Rate-limit or block scanner sources.": "\u5bf9\u626b\u63cf\u6e90\u9650\u6d41\u6216\u5c01\u7981\u3002",
    "Enable CSP and output encoding.": "\u542f\u7528 CSP\uff0c\u5e76\u7edf\u4e00\u8f93\u51fa\u7f16\u7801\u7b56\u7565\u3002",
    "Block source IPs and enable MFA.": "\u5c01\u7981\u5f02\u5e38\u6765\u6e90 IP\uff0c\u5e76\u542f\u7528 MFA\u3002",
    "Review authorization boundary and account policy.": "\u6838\u67e5\u8bbf\u95ee\u63a7\u5236\u8fb9\u754c\u548c\u8d26\u53f7\u7b56\u7565\u3002",
    "Audit sudoers and privileged operations.": "\u5ba1\u8ba1 sudoers \u4e0e\u9ad8\u5371\u63d0\u6743\u64cd\u4f5c\u3002",
    "Harden WAF and DB query parameterization.": "\u5f3a\u5316 WAF\uff0c\u5e76\u4f7f\u7528\u6570\u636e\u5e93\u53c2\u6570\u5316\u67e5\u8be2\u3002",
    "Restrict script execution and monitor command lines.": "\u9650\u5236\u811a\u672c\u6267\u884c\u5e76\u76d1\u63a7\u547d\u4ee4\u884c\u884c\u4e3a\u3002"
}


class AttackCaseRAG:
    """RAG case base build and retrieval service."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.semantic = SemanticFeatureExtractor(config)
        self.store = SimpleVectorStore()

        self.case_file = Path(config.get("rag.case_base.file", "data/rag/attack_cases.jsonl"))
        self.index_file = Path(config.get("rag.case_base.index_file", "data/vectors/rag_attack_cases.npz"))
        self.top_k = int(config.get("rag.retrieval.top_k", 3))
        self.similarity_threshold = float(config.get("rag.retrieval.similarity_threshold", 0.3))
        self.raw_score_threshold = float(config.get("rag.retrieval.raw_score_threshold", 0.65))
        self.ui_candidate_min_raw_score = float(config.get("rag.retrieval.ui_candidate_min_raw_score", 0.40))
        self.allow_top1_fallback = bool(config.get("rag.retrieval.allow_top1_fallback", False))

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        s = str(text or "")
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)

    @staticmethod
    def _looks_like_mojibake(text: str) -> bool:
        s = str(text or "")
        if not s:
            return False
        markers = "???????????????"
        return sum(ch in markers for ch in s) >= 3

    @staticmethod
    def _decode_escaped_unicode(text: str) -> str:
        raw = str(text or "")
        if "\\u" not in raw and "\\x" not in raw:
            return raw
        try:
            return raw.encode("utf-8").decode("unicode_escape")
        except Exception:
            return raw

    @staticmethod
    def _advice_to_cn(advice: str) -> str:
        raw = str(advice or "").strip()
        if not raw:
            return "\u5efa\u8bae\u7ed3\u5408\u4e0a\u4e0b\u6587\u8fdb\u884c\u4eba\u5de5\u590d\u6838\u3002"
        raw = AttackCaseRAG._decode_escaped_unicode(raw)
        if AttackCaseRAG._contains_chinese(raw):
            return raw

        direct = ADVICE_CN_MAP.get(raw)
        if direct:
            return AttackCaseRAG._decode_escaped_unicode(direct)

        compact = re.sub(r"\s+", " ", raw).strip()
        mapped = ADVICE_CN_MAP.get(compact)
        if mapped:
            return AttackCaseRAG._decode_escaped_unicode(mapped)
        return (
            f"\u5efa\u8bae\u4eba\u5de5\u590d\u6838\u5e76\u6267\u884c\u6765\u6e90\u5c01\u7981\u3001"
            f"\u6743\u9650\u6536\u655b\u4e0e\u914d\u7f6e\u52a0\u56fa\u3002"
            f"\uff08\u539f\u6587: {raw[:120]}\uff09"
        )

    @staticmethod
    def _extract_query_signals(text: str) -> set[str]:
        q = str(text or "").lower()
        signals: set[str] = set()

        if any(k in q for k in ["failed password", "authentication failure", "maximum login attempts exceeded"]):
            signals.add("ssh_auth_fail")
        if any(k in q for k in ["invalid user", "user unknown", "check pass"]):
            signals.add("ssh_account_probe")
        if any(k in q for k in ["accepted password", "accepted keyboard-interactive"]):
            signals.add("ssh_password_success")
        if "accepted publickey" in q:
            signals.add("ssh_publickey_success")
        if any(k in q for k in ["session opened for user", "pam_unix(sshd:session)"]):
            signals.add("ssh_session")
        if any(k in q for k in [" for deploy ", " for backup ", " for db_admin ", " for admin ", " for svc_", " for service"]):
            signals.add("service_account")
        if any(k in q for k in [" for root ", " root from ", " root port "]):
            signals.add("root_account")
        if any(k in q for k in ["wpscan", "nmap scripting engine", "nikto", "gobuster", "dirbuster"]):
            signals.add("web_scan")
        if any(k in q for k in ["/wp-login.php", "/admin", "/login", "management endpoints"]):
            signals.add("web_admin_probe")
        if any(k in q for k in ["ah01630", "client denied by server configuration"]):
            signals.add("web_restricted")
        if any(k in q for k in ["negotiation:error", "ah00687"]):
            signals.add("web_negotiation")
        if "script not found" in q:
            signals.add("web_script_probe")
        if any(k in q for k in ["audit(", "type=execve", "uid=0", "euid=0", "sudo"]):
            signals.add("audit_privilege")
        if any(k in q for k in ["peer connection initiated", "tls error", "openvpn", "certificate"]):
            signals.add("openvpn")
        if any(k in q for k in ["prompt injection", "security_alert", "ai-agent", "ignore previous", "jailbreak", "system prompt", "reveal secrets"]):
            signals.add("prompt_injection")
        if any(k in q for k in ["dnsmasq", "query[a]", "forwarded", "refused"]):
            signals.add("dns")
        return signals

    @staticmethod
    def _extract_case_signals(case: Dict) -> set[str]:
        hay = " ".join([
            str(case.get("title", "") or "").lower(),
            str(case.get("content", "") or "").lower(),
            str(case.get("template", "") or "").lower(),
            str(case.get("attack_type", "") or "").lower(),
            str(case.get("technique", "") or "").lower(),
        ])
        signals: set[str] = set()
        if any(k in hay for k in ["ssh brute", "excessive login attempts", "t1110"]):
            signals.add("ssh_auth_fail")
        if any(k in hay for k in ["account probing", "user enumeration", "unknown usernames", "credential probing"]):
            signals.add("ssh_account_probe")
        if any(k in hay for k in ["successful login", "root login success", "t1078"]):
            signals.add("ssh_password_success")
        if "publickey login" in hay:
            signals.add("ssh_publickey_success")
        if "session establishment" in hay or "successful login session" in hay:
            signals.add("ssh_session")
        if "service account successful login" in hay:
            signals.add("service_account")
        if "root login success" in hay:
            signals.add("root_account")
        if any(k in hay for k in ["scanner fingerprint", "web scan", "t1046"]):
            signals.add("web_scan")
        if any(k in hay for k in ["web admin path enumeration", "wp-login", "/admin"]):
            signals.add("web_admin_probe")
        if any(k in hay for k in ["restricted resource", "resource probing", "ah01630", "t1595"]):
            signals.add("web_restricted")
        if any(k in hay for k in ["content negotiation", "ah00687"]):
            signals.add("web_negotiation")
        if "script probing" in hay:
            signals.add("web_script_probe")
        if any(k in hay for k in ["privileged audit", "privilege escalation", "audit trail anomaly", "t1068"]):
            signals.add("audit_privilege")
        if any(k in hay for k in ["remote access establishment", "peer connection", "t1133", "openvpn"]):
            signals.add("openvpn")
        if any(k in hay for k in ["prompt injection", "instruction override", "jailbreak", "llm-pi", "secret extraction"]):
            signals.add("prompt_injection")
        if "dns" in hay:
            signals.add("dns")
        return signals

    @staticmethod
    def _lexical_case_boost(query_text: str, case: Dict) -> float:
        q = str(query_text or "").lower()
        title = str(case.get("title", "") or "").lower()
        content = str(case.get("content", "") or "").lower()
        template = str(case.get("template", "") or "").lower()
        attack_type = str(case.get("attack_type", "") or "").lower()
        hay = " ".join([title, content, template, attack_type])

        boost = 0.0

        def has_any(words):
            return any(w in q for w in words)

        def case_has_any(words):
            return any(w in hay for w in words)

        query_signals = AttackCaseRAG._extract_query_signals(query_text)
        case_signals = AttackCaseRAG._extract_case_signals(case)
        signal_overlap = len(query_signals & case_signals)
        signal_miss = len(query_signals - case_signals)
        if signal_overlap:
            boost += 0.14 * signal_overlap
        if signal_miss and signal_overlap == 0:
            boost -= min(0.28, 0.05 * signal_miss)

        is_ssh_query = has_any(["sshd", "failed password", "accepted password", "accepted publickey", "pam_unix(sshd:session)", "session opened for user"])
        is_web_query = has_any(["http/", "wpscan", "nmap scripting engine", "ah01630", "ah00687", "script not found", "/wp-login.php", "/admin", "/login", "apache"])
        is_audit_query = has_any(["audit(", "type=execve", "uid=0", "euid=0", "sudo"])
        is_prompt_query = has_any(["prompt injection", "security_alert", "ai-agent", "ignore previous", "ignore all previous", "reveal secrets", "system prompt", "jailbreak", "instruction override", "secret extraction"])

        if is_ssh_query and not case_has_any(["ssh", "login", "session", "credential", "t1078", "t1110"]):
            boost -= 0.18
        if is_web_query and not case_has_any(["web", "apache", "probe", "scan", "t1595", "t1046", "t1190"]):
            boost -= 0.18
        if is_audit_query and not case_has_any(["audit", "privilege", "sudo", "t1068"]):
            boost -= 0.18
        if is_prompt_query and not case_has_any(["prompt injection", "instruction override", "jailbreak", "ai agent", "llm-pi", "secret extraction"]):
            boost -= 0.28

        if "ssh_account_probe" in query_signals:
            if "ssh_account_probe" in case_signals:
                boost += 1.00
            if case_has_any(["session establishment", "successful login", "root login success", "publickey login", "t1078"]):
                boost -= 0.60

        if "ssh_auth_fail" in query_signals:
            if case_has_any(["ssh brute", "credential", "t1110", "brute-force", "authentication chain", "excessive login attempts"]):
                boost += 0.48
            if case_has_any(["successful login", "root login success", "publickey login", "session establishment", "t1078"]):
                boost -= 0.28

        if "ssh_password_success" in query_signals or "ssh_publickey_success" in query_signals:
            is_service_account_login = "service_account" in query_signals
            if "ssh_password_success" in query_signals and case_has_any(["successful login", "root login success", "t1078"]):
                boost += 0.74
            if is_service_account_login and "service_account" in case_signals:
                boost += 1.18
            if is_service_account_login and "root_account" in case_signals:
                boost -= 0.58
            if is_service_account_login and "service_account" not in case_signals and "ssh_session" in case_signals:
                boost -= 0.36
            if is_service_account_login and "service_account" not in case_signals and case_has_any(["successful login", "root login success"]) and not case_has_any(["service account successful login"]):
                boost -= 0.22
            if "ssh_password_success" in query_signals and "root_account" in case_signals and "root_account" not in query_signals:
                boost -= 0.24
            if "ssh_password_success" in query_signals and "ssh_session" in case_signals and "ssh_session" not in query_signals:
                boost -= 0.20
            if "ssh_publickey_success" in query_signals and case_has_any(["publickey login", "successful login", "t1078"]):
                boost += 0.68
            if "ssh_password_success" in query_signals and case_has_any(["publickey login"]):
                boost -= 0.12
            if case_has_any(["ssh brute", "excessive login attempts", "t1110", "brute-force"]):
                boost -= 0.18
            if case_has_any(["web admin path enumeration", "/admin", "/wp-login.php", "management endpoints"]):
                boost -= 0.32

        if "ssh_session" in query_signals:
            if "ssh_session" in case_signals:
                boost += 0.60
            elif case_has_any(["successful login", "t1078"]):
                boost += 0.34
            if case_has_any(["ssh brute", "excessive login attempts", "t1110", "brute-force"]):
                boost -= 0.20

        if "audit_privilege" in query_signals:
            if "audit_privilege" in case_signals or case_has_any(["privileged audit", "privilege escalation", "audit trail anomaly", "t1068"]):
                boost += 0.42
            if case_has_any(["sql", "xss", "web", "scanner"]):
                boost -= 0.10

        if "web_scan" in query_signals:
            if case_has_any(["scanner fingerprint", "fingerprint", "web scan", "t1046"]):
                boost += 0.62
            elif case_has_any(["restricted resource", "probe", "t1595", "discovery"]):
                boost += 0.28

        if "openvpn" in query_signals:
            if case_has_any(["remote access establishment", "peer connection", "t1133"]):
                boost += 0.42
            if case_has_any(["reconnect churn", "reconnect", "disconnect"]):
                boost += 0.12

        if "web_restricted" in query_signals and case_has_any(["restricted resource", "resource probing", "t1595", "discovery"]):
            boost += 0.55
        if "web_negotiation" in query_signals and case_has_any(["content negotiation", "t1190", "initial access"]):
            boost += 0.40
        if "web_script_probe" in query_signals and case_has_any(["script probing", "resource probing", "web", "t1595"]):
            boost += 0.35

        if "web_admin_probe" in query_signals:
            if case_has_any(["scanner fingerprint", "web scan", "t1046"]):
                boost += 0.35
            elif case_has_any(["web", "scan", "probe", "initial access", "discovery"]):
                boost += 0.18

        if "prompt_injection" in query_signals:
            if "prompt_injection" in case_signals or case_has_any(["prompt injection", "instruction override", "jailbreak", "ai agent", "llm-pi", "secret extraction"]):
                boost += 1.20
            if case_has_any(["web admin path enumeration", "restricted web resource", "scanner fingerprint", "apache", "wp-login.php", "/admin"]):
                boost -= 0.45

        return boost
    def _normalize_case_record(self, case: Dict) -> Dict:
        if not isinstance(case, dict):
            return case
        out = dict(case)
        advice = str(out.get("advice", "")).strip()
        advice_cn = str(out.get("advice_cn", "")).strip()

        if advice_cn and not self._looks_like_mojibake(advice_cn):
            cn_text = self._advice_to_cn(advice_cn)
        else:
            cn_text = self._advice_to_cn(advice)

        if advice and not self._contains_chinese(advice):
            out.setdefault("advice_en", advice)
        case_id = str(out.get("case_id", "") or "")
        is_auto = case_id.startswith("AUTO-") or str(out.get("source", "")) == "auto_from_labeled_data"
        if case_id.startswith("CASE-"):
            out.setdefault("case_origin", "default_builtin")
        elif is_auto:
            out.setdefault("case_origin", "auto_labeled_template")
            out.setdefault("review_status", str(self.config.get("rag.case_base.auto_case_review_status_default", "pending") or "pending"))
            out.setdefault("label_source", str(self.config.get("rag.case_base.auto_case_label_source", "labeled_data") or "labeled_data"))
            out.setdefault("dataset", "")
            out.setdefault("template_id", "")
            out.setdefault("quality_gate", ["legacy_auto_case", "deduplicated"])
            if "template_count" not in out:
                count = self._extract_count_from_case(out)
                if count:
                    out["template_count"] = count
        out["advice_cn"] = cn_text
        out["advice"] = cn_text
        return out

    def _format_case_text(self, case: Dict) -> str:
        advice_cn = case.get("advice_cn", case.get("advice", ""))
        advice_en = case.get("advice_en", "")
        return (
            f"title: {case.get('title', '')}\n"
            f"group: {case.get('case_group', '')}\n"
            f"type: {case.get('attack_type', '')}\n"
            f"technique: {case.get('technique', '')}\n"
            f"origin: {case.get('case_origin', '')}\n"
            f"dataset: {case.get('dataset', '')}\n"
            f"review_status: {case.get('review_status', '')}\n"
            f"template_count: {case.get('template_count', '')}\n"
            f"content: {case.get('content', '')}\n"
            f"advice_cn: {advice_cn}\n"
            f"advice_en: {advice_en}"
        )

    @staticmethod
    def _contains_security_hint(template_text: str) -> bool:
        t = str(template_text).lower()
        return any(k in t for k in SECURITY_HINT_KEYWORDS)

    @staticmethod
    def _contains_system_hint(template_text: str) -> bool:
        t = str(template_text).lower()
        return any(k in t for k in SYSTEM_HINT_KEYWORDS)

    @staticmethod
    def _contains_source_security_hint(source_file: str) -> bool:
        s = str(source_file or '').lower()
        return any(k in s for k in ['/apache2/', '/auth.log', '/audit/audit.log', '/openvpn.log'])

    @staticmethod
    def _auto_case_relaxed_source_ok(source_file: str) -> bool:
        s = str(source_file or '').lower()
        return any(k in s for k in ['/apache2/', '/auth.log', '/audit/audit.log', '/openvpn.log', 'dnsmasq.log'])

    @staticmethod
    def _source_kind(source_file: str) -> str:
        s = str(source_file or '').lower()
        if '/apache2/' in s and 'access' in s:
            return 'web_access'
        if '/apache2/' in s and 'error' in s:
            return 'web_error'
        if '/auth.log' in s:
            return 'auth'
        if '/audit/audit.log' in s:
            return 'audit'
        if '/openvpn.log' in s:
            return 'openvpn'
        if 'dnsmasq' in s:
            return 'dns'
        return 'other'

    @staticmethod
    def _extract_source_file_from_case(case: Dict) -> str:
        source_file = str(case.get('source_file', '') or '').strip()
        if source_file:
            return source_file
        content = str(case.get('content', '') or '')
        m = re.search(r'source=([^;]+)', content)
        return m.group(1).strip() if m else ''

    @staticmethod
    def _extract_count_from_case(case: Dict) -> int:
        for key in ('template_count', 'count'):
            if key in case:
                try:
                    return int(case.get(key, 0) or 0)
                except Exception:
                    return 0
        content = str(case.get('content', '') or '')
        m = re.search(r'count=(\d+)', content)
        return int(m.group(1)) if m else 0

    @staticmethod
    def _case_signature(case: Dict) -> str:
        source_file = AttackCaseRAG._extract_source_file_from_case(case)
        source_kind = AttackCaseRAG._source_kind(source_file)
        attack_type = str(case.get('attack_type', '') or '').strip().lower()
        template = str(case.get('template', '') or case.get('content', '') or '')
        template_sig = AttackCaseRAG._template_signature(template)
        return f'{source_kind}|{attack_type}|{template_sig}'

    @staticmethod
    def _infer_case_meta(template_text: str, source_file: str = ''):
        t = str(template_text or '').lower()
        source_kind = AttackCaseRAG._source_kind(source_file)

        if 'wpscan' in t:
            return ('security_attack', 'WPScan web scan', 'Discovery', 'T1046', '封禁或限速扫描源 IP，核查暴露目录、插件与弱口令入口，并结合 WAF 日志确认扫描范围。')
        if 'nmap scripting engine' in t or 'nmap' in t:
            return ('security_attack', 'Nmap scripted probe', 'Discovery', 'T1046', '限制扫描源访问速率，检查被探测端口与目录暴露情况，并保留扫描时段流量证据。')
        if 'prompt injection' in t or 'security_alert' in t or 'ignore previous' in t or 'jailbreak' in t or 'reveal secrets' in t:
            return ('security_attack', 'Prompt injection attempt', 'Defense Evasion', 'LLM-PI', '保留原始提示词与上下文，隔离受影响的 AI 会话，核查工具权限与提示词模板，并补充拦截规则。')
        if 'user unknown' in t or 'check pass' in t:
            return ('security_attack', 'SSH account probing sign', 'Credential Access', 'T1110', '核查未知用户名、来源 IP 与探测频率，识别账号枚举来源，并在暴力破解升级前对探测主机实施限速或封禁。')
        if 'failed password' in t or 'invalid user' in t or 'authentication failure' in t:
            return ('security_attack', 'SSH brute-force sign', 'Credential Access', 'T1110', '封禁高频失败来源 IP，核查受影响账号，启用 MFA 或登录失败锁定策略，并审计弱口令账户。')
        if 'session opened for user' in t and source_kind == 'auth':
            return ('security_attack', 'Suspicious successful login session', 'Credential Access', 'T1078', '复核登录来源 IP、登录时段与账号历史行为，检查是否伴随 sudo/su 操作，并核查会话是否为授权登录。')
        if 'sudo' in t or ' root ' in t or 'escalat' in t or ('type=' in t and 'audit(' in t and source_kind == 'audit'):
            return ('security_attack', 'Linux privilege escalation audit', 'Privilege Escalation', 'T1068', '重点审查 audit 记录对应的命令链、父子进程与提权二进制，核查 sudoers、特权组成员和近期敏感文件变更。')
        if 'union' in t or 'or 1=1' in t or 'sleep(' in t or 'sql' in t:
            return ('security_attack', 'SQL injection access pattern', 'Initial Access', 'T1190', '检查对应 URL 与参数，确认是否命中注入探测或利用，启用 WAF/参数化查询，并审计数据库异常日志。')
        if 'script ' in t and 'not found' in t:
            return ('security_attack', 'Web path and script probing', 'Discovery', 'T1595', '核查被探测脚本路径与 Referer，确认是否为目录枚举或敏感路径探测，并对来源 IP 启用封禁或频率限制。')
        if 'ah01630' in t or 'client denied by server configuration' in t:
            return ('security_attack', 'Restricted resource probing', 'Discovery', 'T1595', '检查被拒绝资源路径与虚拟主机配置，确认是否存在越权探测，并对来源地址实施限速或封禁。')
        if 'negotiation:error' in t or 'ah00687' in t:
            return ('security_attack', 'Content negotiation probing', 'Initial Access', 'T1190', '核查异常请求路径、扩展名与 Apache 协商配置，确认是否存在恶意探测或错误利用尝试。')
        if 'xss' in t or 'onerror' in t or 'onload' in t or ('script' in t and source_kind == 'web_access'):
            return ('security_attack', 'Cross-site scripting sign', 'Execution', 'T1059.007', '检查请求参数与响应页面是否包含脚本注入点，启用输出编码与 CSP，并排查受影响页面模板。')
        if source_kind == 'web_access':
            return ('security_attack', 'Abnormal web access', 'Initial Access', 'T1190', '结合访问路径、User-Agent 与状态码分析可疑请求，检查是否存在扫描、爆破或应用层攻击入口。')
        if source_kind == 'web_error':
            return ('security_attack', 'Abnormal web error trigger', 'Initial Access', 'T1190', '结合错误日志与访问日志定位触发请求，核查异常脚本、受限目录与服务配置，判断是否存在攻击前探测。')
        if source_kind == 'auth':
            return ('security_attack', 'Authentication chain anomaly', 'Credential Access', 'T1110', '检查登录账号、来源地址、登录频率与认证结果，必要时锁定账号并核查凭据泄露风险。')
        if source_kind == 'audit':
            return ('security_attack', 'Audit trail anomaly', 'Privilege Escalation', 'T1068', '基于 audit 事件还原执行命令与提权链路，核查敏感文件访问、特权命令执行与身份切换行为。')
        if source_kind == 'openvpn':
            return ('security_attack', 'Remote access anomaly', 'Initial Access', 'T1133', '核查 VPN 对端 IP、证书使用情况、会话建立时段与并发连接数，必要时吊销异常证书并阻断来源。')
        if 'connection reset by peer' in t or 'broken pipe' in t or 'sockettimeoutexception' in t:
            return ('system_anomaly', 'Network interruption anomaly', 'System Reliability', 'SYS-NET', '检查节点网络链路、连接重试策略与上游服务可用性，确认是否存在链路抖动或服务端主动断连。')
        if 'pendingreplication' in t or 'replication' in t or 'timed out block' in t:
            return ('system_anomaly', 'Replication timeout anomaly', 'System Reliability', 'SYS-REPL', '检查副本队列压力、节点可用性与网络拥塞情况，确认是否需要扩容或调整复制策略。')
        if 'ioexception' in t or 'could not read from stream' in t or 'interruptedioexception' in t:
            return ('system_anomaly', 'IO stream anomaly', 'System Reliability', 'SYS-IO', '排查磁盘 IO、文件系统错误与 JVM 网络 IO 状态，确认是否存在硬件故障或资源耗尽。')
        if 'namenode' in t or 'addstoredblock' in t or 'volumemap' in t or 'blockmap updated' in t:
            return ('system_anomaly', 'Metadata consistency anomaly', 'System Reliability', 'SYS-META', '核查 NameNode 元数据状态、块上报与恢复流程，确认是否存在元数据漂移或块状态不同步。')
        if 'datanode' in t or 'packetresponder' in t or 'blockreceiver' in t:
            return ('system_anomaly', 'DataNode pipeline anomaly', 'System Reliability', 'SYS-DN', '检查 DataNode 写入管线、存储节点压力与块接收链路，确认是否存在节点退化或链路故障。')
        return ('unknown', 'Generic suspicious pattern', 'Unknown', 'N/A', '建议结合原始日志、上下文会话与相关主机状态进行人工复核。')

    @staticmethod
    def _is_text_corrupted(text: str) -> bool:
        s = str(text or "")
        return bool(s) and ("????" in s or s.count("?") >= 4)

    @staticmethod
    def _template_quality_ok(template_text: str) -> bool:
        t = str(template_text or "").strip()
        if not t:
            return False
        if len(t) < 24:
            return False
        placeholder_count = len(re.findall(r"<[^>]+>", t))
        words = re.findall(r"[a-zA-Z_]+", t.lower())
        if len(words) < 4:
            return False
        if placeholder_count > max(3, len(words) + 4):
            return False
        return True

    @staticmethod
    def _template_signature(template_text: str) -> str:
        t = str(template_text or "").lower()
        t = re.sub(r"<[^>]+>", " ", t)
        t = re.sub(r"blk_-?\d+", " ", t)
        t = re.sub(r"\b\d+\b", " ", t)
        t = re.sub(r"[^a-z\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def _case_priority(case: Dict) -> tuple:
        is_default = 0 if str(case.get('case_id', '')).startswith('CASE-') else 1
        count = AttackCaseRAG._extract_count_from_case(case)
        template_len = len(str(case.get('template', '') or ''))
        return (is_default, -count, -template_len)

    def _consolidate_cases(self, cases: List[Dict]) -> List[Dict]:
        if not cases:
            return []

        normalized_cases: List[Dict] = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            case = self._normalize_case_record(case)
            source_file = self._extract_source_file_from_case(case)
            template = str(case.get('template', '') or '')
            if template:
                case_group, title, attack_type, technique, advice_cn = self._infer_case_meta(template, source_file=source_file)
                case['case_group'] = case_group
                case['title'] = title
                case['attack_type'] = attack_type
                case['technique'] = technique
                case['advice'] = advice_cn
                case['advice_cn'] = advice_cn
                if source_file:
                    case['source_file'] = source_file
            normalized_cases.append(case)

        defaults = [c for c in normalized_cases if str(c.get('case_id', '')).startswith('CASE-')]
        autos = [c for c in normalized_cases if not str(c.get('case_id', '')).startswith('CASE-')]

        merged_defaults: List[Dict] = []
        seen_default_ids = set()
        for case in defaults:
            cid = str(case.get('case_id', '')).strip()
            if cid and cid not in seen_default_ids:
                seen_default_ids.add(cid)
                merged_defaults.append(case)

        grouped: Dict[str, Dict] = {}
        for case in autos:
            sig = self._case_signature(case)
            if not sig or sig.endswith('|'):
                continue
            existing = grouped.get(sig)
            if existing is None or self._case_priority(case) < self._case_priority(existing):
                grouped[sig] = case

        merged_autos: List[Dict] = []
        for idx, case in enumerate(sorted(grouped.values(), key=lambda x: self._case_priority(x)), start=1):
            case = dict(case)
            case['case_id'] = f'AUTO-{idx:04d}'
            merged_autos.append(case)

        return merged_defaults + merged_autos

    def _is_case_base_corrupted(self, cases: List[Dict]) -> bool:
        if not cases:
            return False
        bad = 0
        for case in cases:
            if not isinstance(case, dict):
                continue
            text = " ".join([str(case.get("title", "")), str(case.get("content", "")), str(case.get("advice", ""))])
            if self._is_text_corrupted(text):
                bad += 1
        return bad / max(1, len(cases)) >= 0.3

    def _write_cases(self, cases: List[Dict]) -> None:
        self.case_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.case_file, "w", encoding="utf-8") as f:
            for case in cases:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")

    def ensure_case_file(self):
        if not self.case_file.exists():
            self._write_cases(self._consolidate_cases([self._normalize_case_record(c) for c in DEFAULT_CASES]))
            self.logger.info(f"Initialized case base: {self.case_file}")
            return

        cases = self.load_cases(normalize=False)
        if self._is_case_base_corrupted(cases):
            backup = self.case_file.with_suffix(self.case_file.suffix + ".corrupted.bak")
            try:
                self.case_file.replace(backup)
                self.logger.warning(f"Corrupted case base detected, backup: {backup}")
            except Exception:
                self.logger.warning("Corrupted case base detected, backup failed, overwrite directly.")
            self._write_cases(self._consolidate_cases([self._normalize_case_record(c) for c in DEFAULT_CASES]))
            self.logger.info(f"Rebuilt case base: {self.case_file}")
            return

        normalized = [self._normalize_case_record(c) for c in cases]
        consolidated = self._consolidate_cases(normalized)
        if consolidated != cases:
            self._write_cases(consolidated)
            self.logger.info("Normalized and consolidated RAG case base.")

    def load_cases(self, normalize: bool = True) -> List[Dict]:
        if not self.case_file.exists():
            return []
        rows: List[Dict] = []
        with open(self.case_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except Exception:
                    continue
        if not normalize:
            return rows
        return self._consolidate_cases([self._normalize_case_record(c) for c in rows])

    def augment_case_base_from_labeled_data(self, max_new_cases: int | None = None, min_template_count: int | None = None) -> int:
        try:
            from src.data_processing.data_loader import DataLoader
        except Exception as e:
            self.logger.warning(f"DataLoader unavailable, skip augment: {e}")
            return 0

        if max_new_cases is None:
            max_new_cases = int(self.config.get("rag.case_base.max_new_cases", 80))
        if min_template_count is None:
            min_template_count = int(self.config.get("rag.case_base.min_template_count", 5))
        dataset_name = str(self.config.get("data.dataset", "") or "").strip()
        review_status = str(self.config.get("rag.case_base.auto_case_review_status_default", "pending") or "pending")
        label_source = str(self.config.get("rag.case_base.auto_case_label_source", "labeled_data") or "labeled_data")
        require_template_quality = bool(self.config.get("rag.case_base.auto_case_require_template_quality", True))
        require_domain_hint = bool(self.config.get("rag.case_base.auto_case_require_security_or_system_hint", True))
        incremental_append = bool(self.config.get("rag.case_base.incremental_append", True))

        loader = DataLoader(self.config)
        try:
            parsed_df = loader.load_parsed_data()
            labels_df = loader.load_labels()
        except Exception as e:
            self.logger.warning(f"Load labeled data failed, skip augment: {e}")
            return 0

        if labels_df is None:
            self.logger.warning("No labels found, skip auto-augment.")
            return 0

        work = parsed_df.copy()
        if {"line_num", "label"}.issubset(labels_df.columns):
            work = work.merge(labels_df[["line_num", "label"]], on="line_num", how="left")
            work["label"] = work["label"].fillna(0).astype(int)
        elif {"source_file", "source_line_num", "label"}.issubset(labels_df.columns):
            if "source_line_num" not in work.columns:
                work["source_line_num"] = work["line_num"]
            work = work.merge(
                labels_df[["source_file", "source_line_num", "label"]],
                on=["source_file", "source_line_num"],
                how="left",
            )
            work["label"] = work["label"].fillna(0).astype(int)
        elif {"BlockId", "label"}.issubset(labels_df.columns) and "raw_log" in work.columns:
            work["BlockId"] = work["raw_log"].astype(str).apply(
                lambda s: (re.search(r"(blk_-?\d+)", s).group(1) if re.search(r"(blk_-?\d+)", s) else None)
            )
            work = work.merge(labels_df[["BlockId", "label"]], on="BlockId", how="left")
            work["label"] = work["label"].fillna(0).astype(int)
        else:
            self.logger.warning("Unsupported label schema, skip auto-augment.")
            return 0

        anomaly_df = work[work["label"] == 1]
        if anomaly_df.empty:
            self.logger.warning("No anomaly samples found for auto-augment.")
            return 0

        grouped = (
            anomaly_df.groupby(["source_file", "template_id", "template"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        grouped = grouped[grouped["count"] >= int(min_template_count)]
        if grouped.empty:
            self.logger.warning("No templates pass count threshold for auto-augment.")
            return 0

        self.ensure_case_file()
        if incremental_append:
            current_cases = self.load_cases()
        else:
            current_cases = []
        current_cases = current_cases + [self._normalize_case_record(c) for c in DEFAULT_CASES]
        base_cases = self._consolidate_cases(current_cases)

        used_signatures = set()
        for case in base_cases:
            sig = self._case_signature(case)
            if sig:
                used_signatures.add(sig)

        added_cases: List[Dict] = []
        existing_auto_idx = []
        for case in base_cases:
            case_id = str(case.get("case_id", ""))
            if case_id.startswith("AUTO-"):
                try:
                    existing_auto_idx.append(int(case_id.split("-")[-1]))
                except Exception:
                    pass
        next_idx = (max(existing_auto_idx) + 1) if existing_auto_idx else 1
        for _, row in grouped.iterrows():
            if len(added_cases) >= int(max_new_cases):
                break
            template_text = str(row.get("template", "")).strip()
            source_file = str(row.get("source_file", "")).strip()
            count = int(row.get("count", 0))
            if require_template_quality and not self._template_quality_ok(template_text):
                continue

            has_security = self._contains_security_hint(template_text)
            has_system = self._contains_system_hint(template_text)
            has_source_security = self._contains_source_security_hint(source_file)
            domain_hint_ok = bool(has_security or has_system or has_source_security)
            if require_domain_hint and not domain_hint_ok:
                continue
            if not domain_hint_ok and not self._auto_case_relaxed_source_ok(source_file):
                continue

            case_group, title, attack_type, technique, advice = self._infer_case_meta(template_text, source_file=source_file)
            sig = self._case_signature(
                {
                    "template": template_text,
                    "source_file": source_file,
                    "attack_type": attack_type,
                }
            )
            if not sig or sig in used_signatures:
                continue
            used_signatures.add(sig)

            advice_cn = self._advice_to_cn(advice)
            added_cases.append(
                {
                    "case_id": f"AUTO-{next_idx:04d}",
                    "case_group": case_group,
                    "title": title,
                    "attack_type": attack_type,
                    "technique": technique,
                    "content": f"Auto-generated from labeled anomaly template; source={source_file}; count={count}; template={template_text[:320]}",
                    "advice": advice_cn,
                    "advice_cn": advice_cn,
                    "advice_en": advice if not self._contains_chinese(advice) else "",
                    "template": template_text,
                    "template_id": str(row.get("template_id", "") or ""),
                    "template_count": count,
                    "source_file": source_file,
                    "source": "auto_from_labeled_data",
                    "dataset": dataset_name,
                    "label_source": label_source,
                    "review_status": review_status,
                    "case_origin": "auto_labeled_template",
                    "quality_gate": [
                        "label==1",
                        "min_template_count",
                        "template_quality_ok",
                        "domain_hint_ok" if domain_hint_ok else "domain_hint_relaxed",
                        "deduplicated",
                    ],
                }
            )
            next_idx += 1

        merged_cases = self._consolidate_cases([self._normalize_case_record(c) for c in (base_cases + added_cases)])
        self._write_cases(merged_cases)
        self.logger.info(f"Auto-augment added {len(added_cases)} cases into {self.case_file}")
        return len(added_cases)

    def build_index(self, force_rebuild: bool = False) -> int:
        if self.index_file.exists() and not force_rebuild:
            self.store.load(self.index_file)
            self.logger.info(f"Loaded case index: {self.index_file}")
            return len(self.store.payloads)

        self.ensure_case_file()
        cases = self.load_cases()
        if not cases:
            self.logger.warning("Case base is empty, skip index build.")
            return 0

        texts = [self._format_case_text(c) for c in cases]
        embeddings = self.semantic.extract_embeddings(texts, show_progress=False)
        self.store = SimpleVectorStore()
        self.store.add(np.asarray(embeddings, dtype=np.float32), cases)
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.store.save(self.index_file)
        self.logger.info(f"Attack case index built: {self.index_file}, count={len(cases)}")
        return len(cases)

    def load_index_if_exists(self) -> bool:
        if not self.index_file.exists():
            self.logger.warning(f"RAG index not found, build it offline first: {self.index_file}")
            return False
        try:
            self.store.load(self.index_file)
            self.logger.info(f"Loaded RAG index: {self.index_file}")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to load RAG index: {e}")
            return False

    def retrieve(
        self,
        query_text: str,
        top_k: int | None = None,
        auto_build: bool = True,
        apply_threshold: bool = True,
    ) -> List[Dict]:
        if top_k is None:
            top_k = self.top_k
        if self.store.vectors is None:
            if auto_build:
                self.build_index(force_rebuild=False)
            else:
                if not self.load_index_if_exists():
                    return []

        query_vector = self.semantic.extract_embeddings([str(query_text)], show_progress=False)[0]
        payload_count = len(self.store.payloads) if getattr(self.store, "payloads", None) is not None else 0
        if payload_count:
            fetch_ceiling = payload_count
        else:
            fetch_ceiling = 24
        fetch_k = max(int(top_k), min(max(int(top_k) * 12, 48), fetch_ceiling))
        try:
            hits = self.store.search(query_vector, top_k=fetch_k)
        except ValueError as e:
            # Frontend sessions may load an index built with an older embedding mode.
            # Rebuild eagerly so the UI always gets a usable Top-K result set.
            self.logger.warning(f"RAG index/query dimension mismatch, rebuilding index: {e}")
            self.build_index(force_rebuild=True)
            hits = self.store.search(query_vector, top_k=fetch_k)

        ranked: List[Dict] = []
        for hit in hits:
            score = float(hit["score"])
            payload = hit["payload"] if isinstance(hit["payload"], dict) else {"content": str(hit["payload"])}
            payload = self._normalize_case_record(payload)
            boost = self._lexical_case_boost(query_text, payload)
            final_score = score + boost
            raw_threshold_passed = score >= self.raw_score_threshold
            final_threshold_passed = final_score >= self.similarity_threshold
            evidence_usable = raw_threshold_passed and final_threshold_passed
            ranked.append({
                **payload,
                "raw_score": score,
                "score": final_score,
                "lexical_boost": boost,
                "raw_threshold_passed": raw_threshold_passed,
                "final_threshold_passed": final_threshold_passed,
                "threshold_passed": evidence_usable,
                "evidence_usable": evidence_usable,
                "confidence_level": "high" if evidence_usable else "candidate",
            })

        ranked.sort(key=lambda x: (float(x.get("score", 0.0)), float(x.get("raw_score", 0.0))), reverse=True)

        results: List[Dict] = []
        for item in ranked:
            if apply_threshold and not item["evidence_usable"]:
                continue
            results.append(item)
            if len(results) >= int(top_k):
                break

        if apply_threshold and not results and ranked and self.allow_top1_fallback:
            results.append(ranked[0])
        if not apply_threshold:
            candidates = [item for item in ranked if float(item.get("raw_score", 0.0)) >= self.ui_candidate_min_raw_score]
            results = candidates[: int(top_k)]
        return results


def main():
    config = Config()
    rag = AttackCaseRAG(config)
    count = rag.build_index(force_rebuild=True)
    print(f"Case index built: {count}")
    print(rag.retrieve("failed password invalid user", top_k=3))


if __name__ == "__main__":
    main()
