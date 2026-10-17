"""Functional code-review contracts (producer: code-review / Sai)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from shared.assessment import AgentRunStatus
from shared.base import Confidence, LongText, RepoRelPath, ShortText, StrictModel
from shared.evidence import EvidenceRef
from shared.findings import Finding, PatchCandidate
from shared.ids import AgentRunId, ArtifactId, AssessmentId, ExpectationId, TestRunId
from shared.intelligence import SnapshotRef
from shared.tenancy import Budget


class ChangeIntentSource(StrEnum):
    pull_request = "pull_request"
    push = "push"
    manual = "manual"


class ChangeIntent(StrictModel):
    """Declared intent of a change. ALWAYS untrusted data, never instructions."""

    source: ChangeIntentSource
    title: ShortText = ""
    body: LongText = ""
    base_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    changed_paths: list[RepoRelPath] = Field(default_factory=list)


class IntentClaimStatus(StrEnum):
    confirmed = "confirmed"
    inferred = "inferred"
    ambiguous = "ambiguous"
    conflicting = "conflicting"


class IntentClaim(StrictModel):
    statement: ShortText
    status: IntentClaimStatus
    citations: list[EvidenceRef] = Field(min_length=1)
    expectation_id: ExpectationId | None = None
    confidence: Confidence


class IntentEvidence(StrictModel):
    claims: list[IntentClaim] = Field(default_factory=list)
    open_questions: list[ShortText] = Field(default_factory=list)


class ReviewRequest(StrictModel):
    assessment_id: AssessmentId
    snapshot_ref: SnapshotRef
    change_intent: ChangeIntent
    focus_paths: list[RepoRelPath] = Field(default_factory=list)
    budget: Budget


class GeneratedTest(StrictModel):
    id: TestRunId
    path: RepoRelPath
    expectation_ids: list[ExpectationId] = Field(default_factory=list)
    artifact_id: ArtifactId
    outcome_on_head: ShortText = Field(description="passed | failed | error, as executed")


class ReviewStatus(StrEnum):
    completed = "completed"
    needs_clarification = "needs_clarification"
    failed = "failed"


class ReviewResult(StrictModel):
    assessment_id: AssessmentId
    agent_run_id: AgentRunId
    run_status: AgentRunStatus
    status: ReviewStatus
    intent_evidence: IntentEvidence
    findings: list[Finding] = Field(default_factory=list)
    patch_candidates: list[PatchCandidate] = Field(default_factory=list)
    generated_tests: list[GeneratedTest] = Field(default_factory=list)
