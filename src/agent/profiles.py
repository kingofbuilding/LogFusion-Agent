"""Log-domain profiles: the vocabulary layer between raw text and the investigation loop.

The harness (loop, budgets, gate, context layer, tool contract) does not care which log family it
is reading. What *is* domain-specific is small and predictable:

* how a raw line is classified into event types,
* which event type counts as "failure" and which as "success",
* the query used by the completion stage to look for follow-up evidence,
* the wording of findings and limitations.

Those live here, in one object, so adding a log dialect means writing a profile rather than editing
the engine. ``SSH_AUTH`` reproduces the original behaviour byte for byte and stays the default.

Scope, stated plainly: a profile swaps **vocabulary**, not **security semantics**. The conclusion
rules in ``engine.grounded_findings`` (5-in-5minutes clusters, spray, stuffing, low-and-slow) assume
an authentication story — a failure burst followed by a success for the same (source, account, host).
Reading web access logs or process telemetry needs new conclusion rules, not just a new profile.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

Predicate = Callable[[str], bool]


def _test(text: str, needle) -> bool:
    """A needle is either a literal substring or a nested predicate."""
    return needle(text) if callable(needle) else needle in text


def all_of(*needles) -> Predicate:
    return lambda text: all(_test(text, n) for n in needles)


def any_of(*needles) -> Predicate:
    return lambda text: any(_test(text, n) for n in needles)


def regex(pattern: str) -> Predicate:
    compiled = re.compile(pattern)
    return lambda text: compiled.search(text) is not None


@dataclass(frozen=True)
class LogProfile:
    """Everything the pipeline needs to know about one log dialect."""

    name: str
    label: str                                   # used in findings and limitations, e.g. "SSH 认证日志"
    failure_type: str = "auth_failure"
    success_type: str = "auth_success"
    escalation_types: tuple[str, ...] = ("privileged_command", "account_change")
    completion_query: str = ""
    # Ordered: the first rule whose predicate matches decides the event type.
    rules: tuple[tuple[str, Predicate], ...] = field(default_factory=tuple)
    # Patterns used to recover an account name from the raw line.
    user_patterns: tuple[str, ...] = field(default_factory=tuple)

    def classify(self, raw_lower: str) -> str:
        for event_type, predicate in self.rules:
            if predicate(raw_lower):
                return event_type
        return "other"

    def extract_user(self, raw: str) -> str:
        for pattern in self.user_patterns:
            match = re.search(pattern, raw, re.I)
            if match:
                return match.group(1)
        return ""


SSH_AUTH = LogProfile(
    name="ssh_auth",
    label="SSH 认证日志",
    completion_query="SSH brute force failed password accepted sudo",
    rules=(
        ("auth_failure", all_of("sshd", any_of("failed password", "invalid user", "authentication failure"))),
        ("auth_success", all_of("sshd", regex(r"accepted (password|publickey) for"))),
        ("privileged_command", regex(r"sudo(?:\[\d+\])?:.*command=")),
        ("account_change", any_of("useradd[", "usermod[", "new user:", "adduser:")),
    ),
    user_patterns=(r"(?:Failed password|Accepted (?:password|publickey)) for (?:invalid user )?(\S+)",
                   r"Invalid user (\S+)",
                   r"sudo(?:\[\d+\])?:\s*(\S+)\s*:",
                   r"(?:user|acct|ruser)=\"?([\w.@-]+)"),
)

# Same authentication story, different dialect: RADIUS / PAM / appliance-style lines that do not
# say "sshd". Used by the tests to prove the vocabulary layer is swappable without touching the loop.
AUTH_GENERIC = LogProfile(
    name="auth_generic",
    label="通用认证日志",
    completion_query="authentication failure burst followed by success",
    rules=(
        ("auth_failure", any_of("authentication failed", "login failed", "access denied",
                                "invalid credentials", "auth failure", "rejected")),
        ("auth_success", any_of("authentication succeeded", "login successful", "access granted",
                                "session opened for user")),
        ("privileged_command", any_of("elevated privileges", "runas=", "admin session")),
        ("account_change", any_of("account created", "account modified", "password changed")),
    ),
    user_patterns=(r"(?:user|username|account|acct)[=:\s]+([\w.@-]+)",
                   r"(?:for|by)\s+([\w.@-]+)"),
)

PROFILES = {profile.name: profile for profile in (SSH_AUTH, AUTH_GENERIC)}
DEFAULT_PROFILE = SSH_AUTH


def get_profile(name: str | None) -> LogProfile:
    """Look up a profile by name, falling back to the default instead of failing a run."""
    return PROFILES.get((name or "").strip().lower(), DEFAULT_PROFILE)
