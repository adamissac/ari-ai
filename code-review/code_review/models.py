"""Typed payloads the reviewer agent submits through the gateway's ``submit_result`` tool.

These are the *model-facing* schemas. They are validated strictly (unknown fields are
rejected) and then adjudicated deterministically against executed evidence before any
shared ``Finding`` / ``IntentClaim`` is produced. A model can propose; only code and
executed tests decide statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import Field, field_validator
from standards.mapping import check_cwe

from shared.base import ShortText, StrictModel
from shared.findings import Finding, PatchCandidate
from shared.review import GeneratedTest, ReviewResult


class SourceKind(StrEnum):
    code = "code"
    docstring = "docstring"
    doc = "doc"
    test = "test"
    change_intent = "change_intent"
    expectation = "expectation"


class CitationIn(StrictModel):
    source_kind: SourceKind
    path: str | None = Field(
        default=None, description="Repository-relative path. Omit only for change_intent."
    )
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    expectation_id: str | None = Field(default=None, pattern=r"^exp_[0-9A-Za-z]{8,64}$")
    quote: ShortText = Field(default="", description="Short excerpt of the cited text")


class ClaimStatusIn(StrEnum):
    confirmed = "confirmed"
    inferred = "inferred"
    ambiguous = "ambiguous"
    conflicting = "conflicting"


class ClaimIn(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$", description="Local id, e.g. 'c1'")
    statement: ShortText
    proposed_status: ClaimStatusIn
    citations: list[CitationIn] = Field(min_length=1)
    rationale: ShortText = ""


class SeverityIn(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingIn(StrictModel):
    weakness_class: str | None = Field(default=None, pattern=r"^CWE-\d{1,5}$")

    @field_validator("weakness_class")
    @classmethod
    def _catalog_cwe(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                entry = check_cwe(value)
                if entry.status != "active" or entry.detail.get("kind", "").lower() != "weakness":
                    raise ValueError("SCHEMA_INVALID: CWE must be an active weakness")
            except (KeyError, ValueError) as exc:
                raise ValueError(f"SCHEMA_INVALID: rejected CWE identifier {value}: {exc}") from exc
        return value

    title: ShortText
    claim_key: str = Field(description="The intent claim this finding says is violated")
    test_id: str | None = Field(
        default=None,
        pattern=r"^tst_[0-9A-Za-z]{8,64}$",
        description="id returned by write_test for the test that demonstrates the bug",
    )
    suspected_spans: list[CitationIn] = Field(min_length=1)
    severity: SeverityIn
    rationale: ShortText


class SecurityConcernIn(StrictModel):
    title: ShortText
    weakness_class: str = Field(pattern=r"^CWE-\d{1,5}$")

    @field_validator("weakness_class")
    @classmethod
    def _catalog_cwe(cls, value: str) -> str:
        try:
            entry = check_cwe(value)
            if entry.status != "active" or entry.detail.get("kind", "").lower() != "weakness":
                raise ValueError("SCHEMA_INVALID: CWE must be an active weakness")
        except (KeyError, ValueError) as exc:
            raise ValueError(f"SCHEMA_INVALID: rejected CWE identifier {value}: {exc}") from exc
        return value

    spans: list[CitationIn] = Field(min_length=1)
    rationale: ShortText
    claim_key: str | None = None


class ReviewerReport(StrictModel):
    summary: ShortText
    claims: list[ClaimIn] = Field(default_factory=list, max_length=20)
    findings: list[FindingIn] = Field(default_factory=list, max_length=10)
    security_concerns: list[SecurityConcernIn] = Field(default_factory=list, max_length=10)
    open_questions: list[ShortText] = Field(default_factory=list, max_length=10)


class RepairReport(StrictModel):
    summary: ShortText
    rationale: ShortText
    root_cause: ShortText


# ----------------------------------------------------------------- outcomes


@dataclass
class GeneratedTestSource:
    test_id: str
    path: str  # repository-relative
    content: str
    claim_key: str
    sha256: str
    artifact_id: str


@dataclass
class ReviewOutcome:
    """Everything a review produced. ``result`` is the shared contract payload."""

    result: ReviewResult
    test_sources: dict[str, GeneratedTestSource] = field(default_factory=dict)
    security_handoffs: list[Finding] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # model proposals rejected by adjudication
    turns: int = 0
    provider_mode: str = ""
    model: str = ""

    @property
    def generated_tests(self) -> list[GeneratedTest]:
        return self.result.generated_tests


@dataclass
class RepairOutcome:
    patch: PatchCandidate | None
    finding: Finding
    accepted_locally: bool
    reasons: list[str]
    diff_text: str = ""
    agent_run_id: str = ""
    test_report_artifact_id: str | None = None
    turns: int = 0
