"""Monitoring events and reassessment requests (docs/10)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from shared.base import CommitSha, ShortText, StrictModel, UtcDatetime
from shared.ids import (
    ArtifactId,
    AssessmentId,
    MonitoringEventId,
    ProjectId,
    ReassessmentRequestId,
    RepositoryId,
)
from shared.intelligence import ImpactSet


class EventSource(StrEnum):
    github = "github"
    runtime = "runtime"
    internal = "internal"
    advisory = "advisory"


class EventType(StrEnum):
    push = "push"
    pull_request = "pull_request"
    log_anomaly = "log_anomaly"
    assessment_completed = "assessment_completed"
    advisory = "advisory"


class EventStatus(StrEnum):
    received = "received"
    processing = "processing"
    processed = "processed"
    ignored = "ignored"
    failed = "failed"


class CommitRange(StrictModel):
    base_sha: CommitSha | None = None
    head_sha: CommitSha


class MonitoringEvent(StrictModel):
    id: MonitoringEventId
    project_id: ProjectId
    repo_id: RepositoryId | None = None
    source: EventSource
    type: EventType
    occurred_at: UtcDatetime
    received_at: UtcDatetime
    dedupe_key: ShortText
    payload_artifact_id: ArtifactId | None = None
    commit_range: CommitRange | None = None
    ref: ShortText | None = Field(default=None, description="git ref, e.g. refs/heads/main")
    pr_number: int | None = Field(default=None, ge=1)
    simulated: bool = Field(
        default=False, description="True for replayed/fixture events; UI must label them"
    )
    status: EventStatus
    status_reason: ShortText | None = None
    impact: ImpactSet | None = None


class ReassessmentScope(StrEnum):
    full = "full"
    targeted = "targeted"
    regression_only = "regression_only"


class ReassessmentStatus(StrEnum):
    queued = "queued"
    coalesced = "coalesced"
    started = "started"
    blocked_no_scope = "blocked_no_scope"
    skipped = "skipped"


class ReassessmentRequest(StrictModel):
    id: ReassessmentRequestId
    project_id: ProjectId
    repo_id: RepositoryId
    event_ids: list[MonitoringEventId] = Field(min_length=1)
    scope: ReassessmentScope
    head_sha: CommitSha
    targets: list[ShortText] = Field(default_factory=list)
    status: ReassessmentStatus
    reason: ShortText
    assessment_id: AssessmentId | None = None
    created_at: UtcDatetime
