"""Deterministic scan for credentials committed in a change.

A committed secret is observable directly in the diff; finding it must not depend on a
model noticing it (the source a model reads is redacted first, so it often cannot).
Only added lines are scanned and only high-confidence shapes are matched; the matched
value is never returned, only its location and kind."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "aws_secret_access_key",
        re.compile(
            r"(?i)aws_?secret_?(?:access_?)?key\w*['\"]?\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]"
        ),
    ),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    ),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("stripe_live_key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
]
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class SecretHit:
    path: str
    line: int
    kind: str


def scan_added_secrets(diff: str) -> list[SecretHit]:
    """Credential-shaped values on lines a unified diff adds, one hit per (path, line)."""
    hits: list[SecretHit] = []
    path: str | None = None
    line = 0
    for raw in (diff or "").splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            path = None if target == "/dev/null" else target.removeprefix("b/")
            continue
        if (m := _HUNK.match(raw)) is not None:
            line = int(m.group(1))
            continue
        if path is None or raw.startswith(("---", "diff ", "index ")):
            continue
        if raw.startswith("+"):
            for kind, pattern in _PATTERNS:
                if pattern.search(raw[1:]):
                    hits.append(SecretHit(path, line, kind))
                    break
            line += 1
        elif not raw.startswith("-"):
            line += 1
    return hits
