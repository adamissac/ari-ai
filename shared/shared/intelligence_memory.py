"""Authenticated intent and independently verified candidate memory.

These append to an exact immutable index; they never modify repository facts or
claim a candidate patch was applied to another commit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from shared.base import RepoRelPath, ShortText, StrictModel, UtcDatetime, looks_like_secret
from shared.evidence import EvidenceKind, EvidenceRef
from shared.ids import ExpectationId, FindingId, PatchId, UserId, VerificationId
from shared.intelligence import SnapshotRef

DecisionStatus = Literal["confirmed", "conflicting", "rejected"]


class ExpectationDecisionRequest(StrictModel):
    status: DecisionStatus
    reason: ShortText = Field(min_length=3)
    expected_revision: int = Field(ge=0)

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str) -> str:
        if len(value.strip()) < 3 or looks_like_secret(value):
            raise ValueError("reason must be meaningful and contain no credentials")
        return value


class ExpectationDecision(ExpectationDecisionRequest):
    snapshot_ref: SnapshotRef
    expectation_id: ExpectationId
    revision: int = Field(ge=1)
    decided_by: UserId
    decided_at: UtcDatetime

    @model_validator(mode="after")
    def next_revision(self) -> ExpectationDecision:
        if self.revision != self.expected_revision + 1:
            raise ValueError("revision must follow expected_revision")
        return self


class VerifiedRegression(StrictModel):
    snapshot_ref: SnapshotRef
    finding_id: FindingId
    patch_id: PatchId
    verification_id: VerificationId
    affected_paths: list[RepoRelPath] = Field(min_length=1, max_length=200)
    test_paths: list[RepoRelPath] = Field(min_length=1, max_length=100)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=100)
    created_at: UtcDatetime

    @field_validator("test_paths")
    @classmethod
    def unique_paths(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate regression paths")
        return value

    @field_validator("evidence")
    @classmethod
    def executed_evidence(cls, value: list[EvidenceRef]) -> list[EvidenceRef]:
        if not any(e.kind in {EvidenceKind.test_run, EvidenceKind.sandbox_run} for e in value):
            raise ValueError("regression requires executed test/sandbox evidence")
        return value
