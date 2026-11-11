"""Pull request review text: a summary body and inline comments.

Everything here is rendered from persisted findings and their records (hypothesis,
validation result, root cause, remediation plan). No model is called, so a review can
only say what an agent run already recorded, and its status words are the finding's own.
"""

from __future__ import annotations

import re
from typing import Any

from backend.redaction import redact_text
from shared.findings import SeverityLevel

MAX_DETAILED = 10  # findings explained in full; the rest stay in the table
MAX_INLINE = 10
_TEXT_LIMIT = 1200
_INLINE_TEXT_LIMIT = 600

_THRESHOLDS = {
    1: {level.value for level in SeverityLevel},
    2: {"medium", "high", "critical"},
    3: {"high", "critical"},
}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
# What each recorded status lets the review claim. Anything else is shown as recorded.
_STATUS_LABEL = {
    "validated": "Confirmed by an executed check",
    "diagnosed": "Confirmed by an executed check",
    "patch_proposed": "Confirmed by an executed check",
    "verified": "Confirmed, and a fix passed independent re-testing",
    "hardened": "Confirmed, and a fix passed independent re-testing",
    "patch_rejected": "Confirmed; the candidate fix was rejected",
    "refuted": "Ruled out by an executed check",
    "inconclusive": "Not confirmed: no executed check covered it",
    "hypothesis": "Suspicion, not tested",
}
_CONFIRMED = {"validated", "diagnosed", "patch_proposed", "verified", "hardened", "patch_rejected"}
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def included(finding_docs: list[dict[str, Any]], strictness: int) -> list[dict[str, Any]]:
    """Findings at or above the project's strictness, confirmed first, then by severity."""
    kept = [
        f
        for f in finding_docs
        if f.get("status") != "closed"  # resolved, or a duplicate of a listed finding
        and (strictness == 1 or _level(f) in _THRESHOLDS[strictness])
    ]
    return sorted(
        kept,
        key=lambda f: (f.get("status") not in _CONFIRMED, _SEVERITY_RANK.get(_level(f) or "", 5)),
    )


def _level(finding: dict[str, Any]) -> str | None:
    return (finding.get("severity") or {}).get("level")


def _clip(text: Any, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _cell(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _span(finding: dict[str, Any]) -> tuple[str, int, int] | None:
    """(path, start_line, end_line) of the finding's first source location."""
    for evidence in finding.get("evidence") or []:
        path, span = evidence.get("path"), evidence.get("span") or {}
        if path and span.get("start_line"):
            start = int(span["start_line"])
            return str(path), start, int(span.get("end_line") or start)
    return None


def _location(finding: dict[str, Any]) -> str:
    span = _span(finding)
    return f"{span[0]}:{span[1]}" if span else "—"


def _status(finding: dict[str, Any]) -> str:
    status = str(finding.get("status", "unknown"))
    return _STATUS_LABEL.get(status, status)


def _cwe(finding: dict[str, Any]) -> str | None:
    cwe = (finding.get("standards") or {}).get("cwe") or {}
    return str(cwe["id"]) if cwe.get("id") else None


def _check_ref(records: dict[str, Any]) -> str | None:
    """The reviewed check template a validation result executed, when one ran."""
    for evidence in (records.get("validation_result") or {}).get("evidence") or []:
        if evidence.get("kind") == "sandbox_run" and evidence.get("symbol"):
            return str(evidence["symbol"])
    return None


def _why(records: dict[str, Any]) -> str:
    return (records.get("root_cause") or {}).get("summary") or (
        records.get("hypothesis") or {}
    ).get("rationale", "")


def _fix(records: dict[str, Any]) -> str:
    return (records.get("remediation_plan") or {}).get("strategy", "")


def _facts(finding: dict[str, Any], records: dict[str, Any]) -> str:
    parts = [f"**{(_level(finding) or 'unrated').capitalize()}**"]
    if cwe := _cwe(finding):
        parts.append(cwe)
    status = _status(finding)
    if (ref := _check_ref(records)) and finding.get("status") in _CONFIRMED:
        status += f" (`{ref}`)"
    parts.append(status)
    return " · ".join(parts)


def _details(summary: str, text: str, limit: int) -> list[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", _clip(text, limit), "", "</details>"]


def render_body(
    assessment_id: str,
    project_id: str,
    finding_docs: list[dict[str, Any]],
    strictness: int,
    origin: str,
    records: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, int]:
    """The review's top-level comment and how many findings it reports."""
    records = records or {}
    kept = included(finding_docs, strictness)
    confirmed = sum(1 for f in kept if f.get("status") in _CONFIRMED)
    lines = [
        "## Ari security review",
        "",
        f"{len(kept)} findings meet strictness level {strictness}.",
        "",
    ]
    if not kept:
        lines.append("No findings at this strictness.")
    else:
        lines.append(
            f"{confirmed} confirmed by an executed check, {len(kept) - confirmed} not confirmed."
        )
        for finding in kept[:MAX_DETAILED]:
            mine = records.get(str(finding.get("id")), {})
            lines += [
                "",
                f"### {_cell(finding.get('title', 'Untitled finding'))}",
                "",
                f"{_facts(finding, mine)} · `{_location(finding)}`",
            ]
            if why := _why(mine):
                lines += ["", *_details("Why this matters", why, _TEXT_LIMIT)]
            if fix := _fix(mine):
                lines += ["", *_details("Suggested fix", fix, _TEXT_LIMIT)]
        lines += [
            "",
            "| Title | Severity | Status | Evidence location |",
            "| --- | --- | --- | --- |",
        ]
        for finding in kept:
            cells = (
                finding.get("title", "Untitled finding"),
                _level(finding) or "unrated",
                finding.get("status", "unknown"),
                _location(finding),
            )
            lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    lines += [
        "",
        f"[View assessment]({origin}/projects/{project_id}/assessments/{assessment_id})"
        " · Ari comments only; it never merges or deploys.",
    ]
    return redact_text("\n".join(lines)), len(kept)


def commentable_ranges(patch: str | None) -> list[tuple[int, int]]:
    """Head-side line ranges a review comment may anchor to, one per hunk of a file patch."""
    ranges: list[tuple[int, int]] = []
    line = start = 0
    for row in (patch or "").splitlines():
        if match := _HUNK.match(row):
            if line > start:
                ranges.append((start, line - 1))
            line = start = int(match.group(1))
        elif start and not row.startswith(("-", "\\")):
            line += 1
    if line > start:
        ranges.append((start, line - 1))
    return ranges


def inline_comments(
    finding_docs: list[dict[str, Any]],
    strictness: int,
    files: list[dict[str, Any]],
    records: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """One comment per changed location a finding points at. A finding whose evidence is
    outside the pull request's diff gets none; the summary still lists it."""
    records = records or {}
    ranges = {str(f.get("filename")): commentable_ranges(f.get("patch")) for f in files}
    comments: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for finding in included(finding_docs, strictness):
        span = _span(finding)
        if span is None:
            continue
        path, start, end = span
        overlap = next(
            (
                (max(lo, start), min(hi, end))
                for lo, hi in ranges.get(path, [])
                if lo <= end and start <= hi
            ),
            None,
        )
        if overlap is None or (path, overlap[1]) in seen:
            continue
        seen.add((path, overlap[1]))
        mine = records.get(str(finding.get("id")), {})
        body = [_facts(finding, mine), "", str(finding.get("title", "Untitled finding"))]
        if why := _why(mine):
            body += ["", _clip(why, _INLINE_TEXT_LIMIT)]
        if fix := _fix(mine):
            body += ["", *_details("Suggested fix", fix, _INLINE_TEXT_LIMIT)]
        comment: dict[str, Any] = {
            "path": path,
            "line": overlap[1],
            "side": "RIGHT",
            "body": redact_text("\n".join(body)),
        }
        if overlap[0] < overlap[1]:
            comment |= {"start_line": overlap[0], "start_side": "RIGHT"}
        comments.append(comment)
        if len(comments) == MAX_INLINE:
            break
    return comments


def finding_brief(finding: dict[str, Any], records: dict[str, Any]) -> dict[str, Any]:
    """What a reply may say about one finding: its recorded facts, nothing inferred."""
    return {
        "title": finding.get("title", "Untitled finding"),
        "severity": _level(finding) or "unrated",
        "status": finding.get("status", "unknown"),
        "status_meaning": _status(finding),
        "executed_check": _check_ref(records),
        "cwe": _cwe(finding),
        "location": _location(finding),
        "why": _clip(_why(records), _TEXT_LIMIT),
        "suggested_fix": _clip(_fix(records), _TEXT_LIMIT),
    }
