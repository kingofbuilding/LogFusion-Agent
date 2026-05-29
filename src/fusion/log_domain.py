from __future__ import annotations

from typing import Iterable, List


DOMAIN_KEYWORDS = {
    "hdfs": [
        "hdfs",
        "namenode",
        "datanode",
        "packetresponder",
        "packet responder",
        "dataxceiver",
        "dfsclient",
        "block report",
        "receiving block",
        "served block",
        "addstoredblock",
        "allocateblock",
        "lease recovery",
        "replication",
        "blk_",
    ],
    "bgl": [
        "ras kernel",
        "ras app",
        "generating core",
        "app fatal",
        "kernel fatal",
        "kernel info",
        "cache parity",
        "alignment exception",
        "double hummer",
        "ce sym",
        "node card",
    ],
    "security": [
        "failed password",
        "authentication failure",
        "invalid user",
        "accepted password",
        "sudo",
        "unauthorized",
        "access denied",
        "permission denied",
        "sql injection",
        "xss",
        "webshell",
        "brute force",
        "credential stuffing",
        "port scan",
        "reverse shell",
        "malware",
        "command and control",
        "exfiltration",
        "ssh",
        "login",
        "session opened",
    ],
    "system": [
        "kernel panic",
        "segmentation fault",
        "out of memory",
        "oom",
        "disk failure",
        "i/o error",
        "io error",
        "service unavailable",
        "connection reset",
        "connection refused",
        "broken pipe",
        "network unreachable",
        "timeout",
        "traceback",
        "exception",
        "fatal",
        "error",
        "openstack",
        "nova",
        "neutron",
        "cinder",
        "keystone",
        "glance",
    ],
}


def detect_log_domain(text: str) -> str:
    value = str(text or "").lower()
    if not value.strip():
        return "generic"

    domain_scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        domain_scores[domain] = sum(1 for keyword in keywords if keyword in value)

    ranked = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
    best_domain, best_score = ranked[0]
    if best_score <= 0:
        return "generic"

    if best_domain == "system" and domain_scores.get("security", 0) >= best_score:
        return "security"
    return best_domain


def detect_log_domains(texts: Iterable[str]) -> List[str]:
    return [detect_log_domain(text) for text in texts]
