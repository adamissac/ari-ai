"""Secret redaction for transcripts, tool output and logs (docs/15 §6, SB-11)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Token shapes are matched WITHOUT a leading word boundary: a secret glued to
# other characters (e.g. inside a longer string or a URL) must still be removed.
# Over-redaction is the safe direction here.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._\-~+/]{8,}=*"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/]{16,}=*"),
    # KEY=value / "key": "value" for names ending in SECRET/KEY/TOKEN/PASSWORD
    re.compile(
        r"(?i)([A-Z0-9_]*(?:SECRET|API_KEY|_KEY|TOKEN|PASSWORD)[\"']?\s*[:=]\s*[\"']?)"
        r"([^\s\"',}]{6,})"
    ),
]


def redact_text(text: str) -> str:
    out = text
    for pat in _PATTERNS:
        if pat.groups >= 2 or pat.groups == 1:
            out = pat.sub(lambda m: m.group(1) + REDACTED, out)
        else:
            out = pat.sub(REDACTED, out)
    return out


def redact(obj: Any) -> Any:
    """Recursively redact strings inside JSON-like structures."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact(v) for v in obj)
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj
