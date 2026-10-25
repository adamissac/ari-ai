"""Secret redaction applied before anything is persisted, logged or sent to a model."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "[REDACTED:anthropic_key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED:github_token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED:github_token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws_key]"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"), "[REDACTED:slack_token]"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        "[REDACTED:private_key]",
    ),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{8,}"), r"\1 [REDACTED:bearer]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{2,}"), "[REDACTED:jwt]"),
    # credentials inside connection strings: scheme://user:pass@host -> scheme://[REDACTED]@host
    (re.compile(r"\bsk_live_[A-Za-z0-9]{8,}\b"), "[REDACTED:stripe_key]"),
    (
        re.compile(
            r"(?i)\b(postgres(?:ql)?(?:\+\w+)?|mysql(?:\+\w+)?|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@]+:[^\s@]+@"
        ),
        r"\1://[REDACTED:dsn_credentials]@",
    ),
    # generic secret key=value / key: value pairs (password=hunter2, token: xyz,
    # password='quoted Pw1', refresh_token: "r3fr3sh", ...)
    (
        re.compile(
            r"(?i)\b\w*(?:password|passwd|pwd|api_key|apikey|secret|token)\w*"
            r"\s*[=:]\s*(?:'[^'\n]*'|\"[^\"\n]*\"|[^\s'\"]+)"
        ),
        "[REDACTED:kv]",
    ),
]

# Deliberately NOT scrubbed: absolute paths and internal hostnames. They aid
# debugging and are bounded to project members; revisit if members must be
# isolated from infra internals (see docs/release/RELEASE_GATE_2026-10-24.md).

_SENSITIVE_KEYS = re.compile(
    r"(?i)^(password|passwd|secret|client_secret|token|access_token|refresh_token|api_key|"
    r"private_key|authorization|cookie|set-cookie|x-hub-signature(-256)?)$"
)


def redact_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value: Any) -> Any:
    """Recursively redact strings and values under credential-like keys."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]" if isinstance(k, str) and _SENSITIVE_KEYS.match(k) and v else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value
