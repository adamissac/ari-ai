"""Conservative line-preserving redaction before storing or returning source context."""

import re

from shared.evidence import EvidenceRef

_PEM = re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----[\s\S]*?-----END [^-\n]*PRIVATE KEY-----")
_KNOWN = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}"
)
# Replace only the assigned value: a string literal's contents, or a bare token that
# ends at a line/clause boundary — EOL/comment (any token), or a mid-line `,`/`;`/
# closing bracket (token must contain a digit, so identifiers like `secret: bytes,`
# or `api_key=key` keep their references). Never the rest of the line and never a
# token followed by `(` or an operator, so `secret_configured=bool(` stays parseable.
_ASSIGN = re.compile(
    r"(?im)([\w.-]*(?:secret|password|passwd|api_key|access_token|private_key|auth_token)"
    r"[\w.-]*[\"']?[ \t]*[:=][ \t]*)"
    r"(?:([rbuf]{0,2})(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''"
    r"|\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')(?![\w\"'])"
    r"|[^\s\"'#,;()\[\]{}=](?:[^\n\"'#,;()\[\]{}=]*[^\s\"'#,;()\[\]{}=])?"
    r"(?=[ \t]*[,;]?[ \t]*(?:#[^\n]*)?$)"
    r"|[^\s\"'#,;()\[\]{}=0-9]*[0-9][^\n\"'#,;()\[\]{}=]*(?=[ \t]*[,;)\]}]))"
)


def _assigned(match: re.Match[str]) -> str:
    literal = match[3]
    if literal is None:
        return match[1] + "[REDACTED]"
    quote = literal[:3] if literal[:3] in ('"""', "'''") else literal[0]
    return match[1] + match[2] + quote + "[REDACTED]" + "\n" * literal.count("\n") + quote


_BEARER = re.compile(r"(?i)\bBearer[ \t]+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIAL = re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@")


def redact(text: str) -> str:
    text = _PEM.sub(lambda m: "[REDACTED]" + "\n" * m[0].count("\n"), text)
    text = _KNOWN.sub("[REDACTED]", text)
    text = _ASSIGN.sub(_assigned, text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    return _URL_CREDENTIAL.sub(r"\1[REDACTED]@", text)


def redact_evidence(evidence: EvidenceRef) -> EvidenceRef:
    """Copy free-form citation metadata for context output, preserving stored evidence.

    Identity fields (SHA, artifact, path, span and symbol) remain exact. Redaction can
    expand a short token, so bound the display metadata to canonical ShortText's
    500-character limit before validating the new reference.
    """
    return EvidenceRef.model_validate(
        {
            **evidence.model_dump(),
            "provenance": redact(evidence.provenance)[:500],
            "note": redact(evidence.note)[:500] if evidence.note is not None else None,
        }
    )
