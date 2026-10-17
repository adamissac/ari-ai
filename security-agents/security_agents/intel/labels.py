"""Load behavioural expectations for a target that has no derived index yet.

STATUS: INTERIM. Expectations are supposed to be *derived* from the target by
`code_intelligence` (Sarosh, INTEL-007): from docstrings, tests, conventions and
specs. Until that lands, the security pillar needs some statement of intended
behaviour to reason against, so this module reads the expectation records a
human wrote in a labels file and marks every one `origin="fixture"`.

Only the `expectations` section is read. The answer-key sections
(`planted_findings`, `negatives`) are deliberately **not** loaded: an agent that
could read them would not be finding anything. `load_expectations` raises if a
caller points it at a file and asks for those keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import BehavioralExpectation, Confidence, EvidenceRef, SourceSpan

ANSWER_KEY_SECTIONS = ("planted_findings", "negatives")

_SENSITIVITY = {"none", "internal", "personal", "financial"}

# Expectation kinds seen in labels files, mapped onto the contract's vocabulary.
_KIND_ALIASES = {
    "authorization": "access_control",
    "invariant": "business_rule",
    "authentication": "authentication",
    "access_control": "access_control",
    "business_rule": "business_rule",
    "functional": "functional",
}


def _criticality(sensitivity: str | None) -> str:
    if sensitivity in ("financial", "personal"):
        return "high"
    if sensitivity == "internal":
        return "medium"
    return "low"


def load_expectations(
    labels_path: Path,
    *,
    snapshot_id: str,
    commit_sha: str,
    strip_prefix: str | None = None,
) -> list[BehavioralExpectation]:
    """Read `expectations:` from a YAML labels file.

    `strip_prefix` removes the labels file's path prefix (e.g. `target/`) so the
    cited paths are relative to the indexed snapshot root.
    """
    import yaml

    raw = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{labels_path} does not contain a mapping")
    out: list[BehavioralExpectation] = []
    for item in raw.get("expectations", []) or []:
        sources: list[EvidenceRef] = []
        for source in item.get("sources", []) or []:
            path = str(source.get("path", ""))
            if strip_prefix and path.startswith(strip_prefix):
                path = path[len(strip_prefix) :]
            if not path:
                continue
            line = source.get("start_line")
            span = (
                SourceSpan(start_line=int(line), end_line=int(source.get("end_line", line))) if line else None
            )
            sources.append(
                EvidenceRef(
                    path=path,
                    sha=commit_sha,
                    span=span,
                    symbol=source.get("symbol"),
                    provenance="expectation",
                )
            )
        sensitivity = item.get("data_sensitivity")
        if sensitivity not in _SENSITIVITY:
            sensitivity = None
        kind = _KIND_ALIASES.get(str(item.get("kind", "functional")), "functional")
        out.append(
            BehavioralExpectation(
                id=str(item["id"]),
                snapshot_id=snapshot_id,
                subject_ref=str(item.get("subject") or item.get("subject_ref") or ""),
                statement=str(item["statement"]),
                kind=kind,
                sources=sources,
                confidence=Confidence(str(item.get("confidence", "high"))),
                origin="fixture",
                status=str(item.get("status", "confirmed")),
                data_sensitivity=sensitivity,
                criticality=str(item.get("criticality") or _criticality(sensitivity)),
            )
        )
    return out


def answer_key(labels_path: Path) -> dict[str, Any]:
    """Load the answer-key sections. For EVALUATION ONLY — never for an agent."""
    import yaml

    raw = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
    return {section: raw.get(section) for section in ANSWER_KEY_SECTIONS}
