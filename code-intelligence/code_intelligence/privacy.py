"""Conservative line-preserving redaction before storing or returning source context."""

import re

_PEM = re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----[\s\S]*?-----END [^-\n]*PRIVATE KEY-----")
_KNOWN = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}"
)
_ASSIGN = re.compile(
    r"(?im)([\w.-]*(?:secret|password|passwd|api_key|access_token|private_key|auth_token)"
    r"[\w.-]*[\"']?\s*[:=]\s*)([^\n]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIAL = re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@")


def redact(text: str) -> str:
    text = _PEM.sub(lambda m: "[REDACTED]" + "\n" * m[0].count("\n"), text)
    text = _KNOWN.sub("[REDACTED]", text)
    text = _ASSIGN.sub(r"\1[REDACTED]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    return _URL_CREDENTIAL.sub(r"\1[REDACTED]@", text)
