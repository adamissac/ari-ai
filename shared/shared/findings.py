"""Findings and the security/repair evidence chain (docs/12 "Findings and evidence")."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from shared.base import Confidence, RepoRelPath, Sha256Hex, ShortText, StrictModel, UtcDatetime
from shared.evidence import EvidenceRef
from shared.ids import (
    AgentRunId,
    ArtifactId,
    AssessmentId,
    AttackPathId,
    ExpectationId,
    FindingId,
    HardeningId,
    HypothesisId,
    PatchId,
    RemediationPlanId,
    RootCauseId,
    SnapshotId,
    TestRunId,
    ValidationId,
    VerificationId,
)
from shared.standards import CVSSAssessment, DefensiveMapping, FindingStandards, StandardMapping


class FindingKind(StrEnum):
    functional = "functional"
    security = "security"


class FindingStatus(StrEnum):
    hypothesis = "hypothesis"
    validated = "validated"
    refuted = "refuted"
    inconclusive = "inconclusive"
    diagnosed = "diagnosed"
    patch_proposed = "patch_proposed"
    verified = "verified"
    patch_rejected = "patch_rejected"
    unresolved = "unresolved"
    hardened = "hardened"
    accepted_risk = "accepted_risk"
    closed = "closed"
    needs_recheck = "needs_recheck"


class SeverityLevel(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SeverityFactors(StrictModel):
    reachability: ShortText
    privileges_required: ShortText
    data_sensitivity: ShortText
    verified_path: bool


class SeverityAssessment(StrictModel):
    cvss: CVSSAssessment | None = None
    level: SeverityLevel
    factors: SeverityFactors
    rationale: ShortText


class StatusChange(StrictModel):
    from_status: FindingStatus | None
    to_status: FindingStatus
    at: UtcDatetime
    actor: ShortText = Field(description="'agent:<name>', 'user:<usr_id>' or 'system'")
    reason: ShortText | None = None


class Finding(StrictModel):
    id: FindingId
    assessment_id: AssessmentId
    snapshot_id: SnapshotId | None = None
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    kind: FindingKind
    title: ShortText
    status: FindingStatus
    severity: SeverityAssessment | None = None
    subject_refs: list[ShortText] = Field(default_factory=list)
    expectation_ids: list[ExpectationId] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: Confidence
    produced_by_run_id: AgentRunId | None = None
    history: list[StatusChange] = Field(default_factory=list)
    standards: FindingStandards | None = Field(
        default=None, description="0.7.0: CWE/ATT&CK/D3FEND/CVSS classification with evidence"
    )
    created_at: UtcDatetime
    updated_at: UtcDatetime


class Hypothesis(StrictModel):
    id: HypothesisId
    finding_id: FindingId
    weakness_class: str = Field(pattern=r"^CWE-\d{1,5}$")
    rationale: ShortText
    cited_spans: list[EvidenceRef] = Field(min_length=1)
    expectation_ids: list[ExpectationId] = Field(default_factory=list)
    confidence: Confidence
    suggested_check_category: ShortText

    @field_validator("weakness_class")
    @classmethod
    def _known_cwe(cls, value: str) -> str:
        from standards.catalog import cwe

        try:
            entry = cwe(value)
        except KeyError as exc:
            raise ValueError("unknown CWE identifier") from exc
        if entry.status != "active":
            raise ValueError("CWE identifier is not active")
        return value


class ValidationOutcome(StrEnum):
    confirmed = "confirmed"
    refuted = "refuted"
    inconclusive = "inconclusive"


class ValidationResult(StrictModel):
    id: ValidationId
    hypothesis_id: HypothesisId
    outcome: ValidationOutcome
    check_template_id: ShortText
    check_template_version: ShortText
    sandbox_run_id: ShortText
    evidence: list[EvidenceRef] = Field(min_length=1)


class PathStep(StrictModel):
    attack: list[StandardMapping] = Field(default_factory=list)
    order: int = Field(ge=1)
    description: ShortText
    symbol_ref: ShortText | None = None
    verified: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)


class AttackPath(StrictModel):
    id: AttackPathId
    finding_id: FindingId
    steps: list[PathStep] = Field(min_length=1)
    preconditions: list[ShortText] = Field(default_factory=list)
    impact_summary: ShortText


class RootCause(StrictModel):
    id: RootCauseId
    finding_id: FindingId
    summary: ShortText
    violated_expectation_ids: list[ExpectationId] = Field(default_factory=list)
    cause_spans: list[EvidenceRef] = Field(min_length=1)
    cause_class: ShortText


class RemediationPlan(StrictModel):
    id: RemediationPlanId
    finding_id: FindingId
    strategy: ShortText
    constraints: list[ShortText] = Field(default_factory=list)
    files_expected: list[RepoRelPath] = Field(default_factory=list)
    test_plan: ShortText


class PatchCandidate(StrictModel):
    id: PatchId
    finding_id: FindingId
    attempt: int = Field(ge=1, le=5)
    diff_artifact_id: ArtifactId
    diff_sha256: Sha256Hex
    base_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    worktree_ref: ShortText
    files_changed: list[RepoRelPath] = Field(min_length=1)
    tests_added: list[ShortText] = Field(default_factory=list)
    local_test_run_id: TestRunId | None = None
    produced_by_run_id: AgentRunId
    rationale: ShortText
    created_at: UtcDatetime


class VerificationCheckName(StrEnum):
    original_check_now_fails_to_reproduce = "original_check_now_fails_to_reproduce"
    functional_suite_passes = "functional_suite_passes"
    generated_tests_pass = "generated_tests_pass"
    no_test_tampering = "no_test_tampering"
    diff_scope_ok = "diff_scope_ok"


class VerificationCheck(StrictModel):
    name: VerificationCheckName
    passed: bool
    evidence: list[EvidenceRef] = Field(min_length=1)


class VerificationVerdict(StrEnum):
    accepted = "accepted"
    rejected = "rejected"


class VerificationResult(StrictModel):
    """Independent Verify verdict. ``accepted`` requires every check to pass."""

    id: VerificationId
    patch_id: PatchId
    verdict: VerificationVerdict
    checks: list[VerificationCheck] = Field(min_length=1)
    sandbox_run_ids: list[ShortText] = Field(min_length=1)
    reasons: list[ShortText] = Field(default_factory=list)
    produced_by_run_id: AgentRunId
    created_at: UtcDatetime

    @model_validator(mode="after")
    def _accepted_requires_all_checks(self) -> VerificationResult:
        if self.verdict is VerificationVerdict.accepted and not all(c.passed for c in self.checks):
            raise ValueError("accepted verdict requires every verification check to pass")
        return self


class HardeningRecommendation(StrictModel):
    d3fend: list[DefensiveMapping] = Field(default_factory=list)
    id: HardeningId
    finding_id: FindingId
    category: ShortText
    recommendation: ShortText
    proposed_test_artifact_id: ArtifactId | None = None
    effort: ShortText
