"""Local V0 mirrors of the docs/12 entities used by the seven-agent pillar.

See `base.py` for the adapter status note. Field names follow docs/12 exactly;
additions needed by the security pillar are marked `# PROPOSED` and are listed
in the coordination message to Srihith.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator
from shared.standards import CVSSAssessment, DefensiveMapping, StandardMapping
from standards.mapping import check_cwe

from .base import (
    AgentName,
    Confidence,
    ErrorCode,
    LongText,
    RelPath,
    ShortText,
    StrictModel,
    new_id,
    utcnow,
)

# --------------------------------------------------------------------------- evidence


class SourceSpan(StrictModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @field_validator("end_line")
    @classmethod
    def _ordered(cls, v: int, info):  # type: ignore[no-untyped-def]
        start = info.data.get("start_line")
        if start is not None and v < start:
            raise ValueError("end_line must be >= start_line")
        return v


class EvidenceRef(StrictModel):
    """Citation to code, a tool run, or an artifact (CONTRACTS.md V0)."""

    path: RelPath | None = None
    sha: str | None = None  # commit SHA of the snapshot the span belongs to
    span: SourceSpan | None = None
    symbol: str | None = None
    artifact_id: str | None = None  # e.g. sandbox run id, test run id
    provenance: Literal[
        "code", "static_analysis", "check_run", "test_run", "expectation", "diff", "agent_output"
    ] = "code"


# --------------------------------------------------------------------------- scope


class ScopeStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ScopeTarget(StrictModel):
    target_id: str  # PROPOSED: docs/12 tool args reference targets by id; ScopeTarget had none
    kind: Literal["sandbox_build"] = "sandbox_build"
    repo_id: str
    build_recipe_ref: RelPath
    exposed_ports: list[int] = Field(default_factory=list)


class AuthorizedScope(StrictModel):
    id: str
    project_id: str
    name: str
    targets: list[ScopeTarget]
    allowed_check_categories: list[str]
    status: ScopeStatus
    requested_by: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    expires_at: datetime
    notes: str = ""


class Approval(StrictModel):
    id: str = Field(default_factory=lambda: new_id("apv"))
    project_id: str
    subject_type: Literal["scope", "remediation", "pr"]
    subject_id: str
    decision: Literal["approved", "declined"]
    decided_by: str  # must be a human user id (usr_*), never an agent
    decided_at: datetime = Field(default_factory=utcnow)
    reason: str | None = None


# --------------------------------------------------------------------------- intelligence


class BehavioralExpectation(StrictModel):
    id: str
    snapshot_id: str
    subject_ref: str
    statement: ShortText
    kind: str
    sources: list[EvidenceRef] = Field(default_factory=list)
    confidence: Confidence
    origin: Literal["test", "doc", "spec", "inferred", "fixture"]
    status: Literal["confirmed", "inferred", "ambiguous", "conflicting"]
    data_sensitivity: Literal["none", "internal", "personal", "financial"] | None = None
    criticality: Literal["low", "medium", "high"] = "medium"  # PROPOSED for Scout ranking


class EntryPoint(StrictModel):
    id: str
    snapshot_id: str
    kind: Literal["http_route", "cli", "job"]
    handler_symbol: str
    path: RelPath
    span: SourceSpan
    method: str | None = None
    path_template: str | None = None
    auth_dependencies: list[str] = Field(default_factory=list)


class SnapshotRef(StrictModel):
    project_id: str
    repo_id: str
    commit_sha: str
    snapshot_id: str
    index_version: str


# --------------------------------------------------------------------------- findings


class Hypothesis(StrictModel):
    id: str = Field(default_factory=lambda: new_id("hyp"))
    finding_id: str = Field(default_factory=lambda: new_id("fnd"))
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

    title: ShortText
    rationale: LongText
    cited_spans: list[EvidenceRef] = Field(min_length=1)
    expectation_ids: list[str] = Field(default_factory=list)
    entry_point_id: str | None = None  # PROPOSED: which entry point the hypothesis concerns
    confidence: Confidence
    suggested_check_category: str
    status_label: Literal["hypothesis"] = "hypothesis"
    cwe_name: str = ""
    cwe_mapping_usage: str = ""
    cwe_catalog_version: str = ""
    owasp_api_category: str | None = None
    owasp_api_title: str | None = None
    owasp_api_edition: str = ""
    owasp_mapping_kind: str = ""


class ValidationOutcome(StrEnum):
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"


class ValidationResult(StrictModel):
    id: str = Field(default_factory=lambda: new_id("val"))
    hypothesis_id: str
    outcome: ValidationOutcome
    check_template_id: str | None
    check_template_version: str | None
    parameters: dict[str, object] = Field(default_factory=dict)
    sandbox_run_id: str | None
    observations: dict[str, object] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    interpretation: str = Field(default="", max_length=500)  # non-authoritative LLM text


class PathStep(StrictModel):
    attack: list[StandardMapping] = Field(default_factory=list)
    order: int = Field(ge=1)
    description: ShortText
    symbol_ref: str | None = None
    verified: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)
    attack_technique: str | None = None
    attack_technique_name: str = ""
    attack_version: str = ""
    attack_label: str = "no applicable technique"


class SeverityFactors(StrictModel):
    reachability: Literal["unauthenticated", "authenticated", "internal"]
    privileges_required: Literal["none", "low", "high"]
    data_sensitivity: Literal["none", "internal", "personal", "financial"]
    verified_path: bool


class SeverityLevel(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CvssMetricEvidence(StrictModel):
    metric: str
    value: str
    status: Literal["cited", "unverified"]
    evidence: list[EvidenceRef] = Field(default_factory=list)
    rationale: str = ""


class SeverityAssessment(StrictModel):
    cvss: CVSSAssessment | None = None
    level: SeverityLevel
    factors: SeverityFactors
    rationale: ShortText
    cvss_version: str = ""
    cvss_vector: str = ""
    cvss_base_score: float | None = None
    cvss_rating: str = ""
    score_kind: str = ""
    level_source: str = ""
    metric_evidence: list[CvssMetricEvidence] = Field(default_factory=list)


class AttackPath(StrictModel):
    id: str = Field(default_factory=lambda: new_id("atp"))
    finding_id: str
    steps: list[PathStep] = Field(min_length=1)
    preconditions: list[ShortText] = Field(default_factory=list)
    impact_summary: ShortText


class CauseClass(StrEnum):
    MISSING_CHECK = "missing_check"
    WRONG_CHECK = "wrong_check"
    UNSAFE_DEFAULT = "unsafe_default"
    LOGIC_ERROR = "logic_error"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"


class RootCause(StrictModel):
    id: str = Field(default_factory=lambda: new_id("rc"))
    finding_id: str
    summary: ShortText
    violated_expectation_ids: list[str]
    cause_spans: list[EvidenceRef] = Field(min_length=1)
    cause_class: CauseClass


class RemediationTestPlan(StrictModel):
    must_fail_before: list[ShortText] = Field(default_factory=list)
    must_pass_after: list[ShortText] = Field(default_factory=list)


class RemediationPlan(StrictModel):
    id: str = Field(default_factory=lambda: new_id("rmp"))
    finding_id: str
    strategy: LongText
    constraints: list[ShortText] = Field(default_factory=list)
    files_expected: list[RelPath] = Field(min_length=1)
    test_plan: RemediationTestPlan
    d3fend_technique: str | None = None
    d3fend_label: str = ""
    d3fend_version: str = ""


class PatchCandidate(StrictModel):
    id: str = Field(default_factory=lambda: new_id("pat"))
    finding_id: str
    attempt: int = Field(ge=1, le=2)
    diff_uri: str
    diff_sha256: str
    worktree_ref: str
    files_changed: list[RelPath]
    tests_added: list[RelPath] = Field(default_factory=list)
    local_test_run_id: str | None
    local_tests_passed: bool | None = None  # PROPOSED: outcome of Patch's own run (informational)


class VerificationCheckName(StrEnum):
    ORIGINAL_CHECK_NOW_FAILS = "original_check_now_fails_to_reproduce"
    FUNCTIONAL_SUITE_PASSES = "functional_suite_passes"
    GENERATED_TESTS_PASS = "generated_tests_pass"
    NO_TEST_TAMPERING = "no_test_tampering"
    DIFF_SCOPE_OK = "diff_scope_ok"


class VerificationCheck(StrictModel):
    name: VerificationCheckName
    passed: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)
    detail: ShortText = ""


class VerificationResult(StrictModel):
    id: str = Field(default_factory=lambda: new_id("ver"))
    patch_id: str
    verdict: Literal["accepted", "rejected"]
    checks: list[VerificationCheck]
    sandbox_run_ids: list[str]
    reasons: list[str] = Field(default_factory=list)
    summary: str = ""  # LLM, non-authoritative
    verify_run_id: str | None = None  # AgentRun id of the independent Verify run


class RegressionTest(StrictModel):
    id: str = Field(default_factory=lambda: new_id("tst"))
    finding_id: str
    test_path: RelPath
    test_name: str
    affected_symbols: list[str] = Field(default_factory=list)
    origin: Literal["patch", "probe", "fortify"]


class HardeningRecommendation(StrictModel):
    d3fend: list[DefensiveMapping] = Field(default_factory=list)
    id: str = Field(default_factory=lambda: new_id("hdn"))
    finding_id: str
    category: Literal["centralize_check", "lint_rule", "policy_test", "config", "monitoring", "other"]
    recommendation: LongText
    references: list[EvidenceRef] = Field(default_factory=list)
    proposed_test_uri: str | None = None
    effort: Literal["small", "medium", "large"]
    owner_review_note: ShortText = ""
    d3fend_technique: str | None = None
    d3fend_label: str = ""
    d3fend_version: str = ""


class HypothesisDraft(StrictModel):
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

    title: ShortText
    rationale: ShortText
    cited_spans: list[EvidenceRef] = Field(min_length=1)


# --------------------------------------------------------------------------- runs / audit


class Usage(StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    sandbox_seconds: float = 0.0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.usd += other.usd
        self.sandbox_seconds += other.sandbox_seconds

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Budget(StrictModel):
    max_tokens: int = Field(gt=0)
    max_usd: float = Field(gt=0)
    max_wall_clock_s: float = Field(gt=0)


class AgentRun(StrictModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    assessment_id: str
    agent: AgentName
    step_key: str
    attempt: int = 1
    status: Literal["running", "succeeded", "failed"]
    input_ref: str
    output_ref: str | None = None
    model_id: str
    provider_mode: Literal["live", "fake", "replay", "none"]
    usage: Usage = Field(default_factory=Usage)
    llm_turns: int = 0
    tool_calls: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None
    error_code: ErrorCode | None = None
    error_detail: str | None = None
    transcript_ref: str | None = None


class AuditEvent(StrictModel):
    id: str = Field(default_factory=lambda: new_id("aud"))
    org_id: str
    project_id: str | None = None
    actor: Literal["user", "system", "agent"]
    actor_id: str
    action: str
    subject_type: str
    subject_id: str
    at: datetime = Field(default_factory=utcnow)
    details: dict[str, object] = Field(default_factory=dict)
    prev_hash: str
    hash: str
