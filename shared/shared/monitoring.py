"""Monitoring events and reassessment requests (docs/10)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shared.base import CommitSha, ShortText, StrictModel, UtcDatetime
from shared.ids import (
    ArtifactId,
    AssessmentId,
    IngestTokenId,
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


# --------------------------------------------------------------- runtime signals (docs/10 "S")

RuntimeSource = Literal["runtime_demo", "replay", "simulated"]
"""Provenance label. There is NO production telemetry source in MVP: ``runtime_demo`` is
the sandboxed demo target, ``replay``/``simulated`` are recorded or synthetic windows."""


class RouteWindow(StrictModel):
    """Aggregated counters for one route over one window (no raw logs, no payloads)."""

    route: str = Field(pattern=r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /[^\s]{0,300}$")
    requests: int = Field(ge=0, le=10_000_000)
    status_4xx: int = Field(default=0, ge=0)
    status_5xx: int = Field(default=0, ge=0)
    auth_failures: int = Field(default=0, ge=0, description="401/403 responses")

    @model_validator(mode="after")
    def _bounded(self) -> RouteWindow:
        if (
            self.status_4xx + self.status_5xx > self.requests
            or self.auth_failures > self.status_4xx
        ):
            raise ValueError("error counts exceed request counts")
        return self


class RuntimeSignalBatch(StrictModel):
    source: RuntimeSource
    repo_id: RepositoryId | None = None
    window_start: UtcDatetime
    window_end: UtcDatetime
    routes: list[RouteWindow] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _window(self) -> RuntimeSignalBatch:
        seconds = (self.window_end - self.window_start).total_seconds()
        if not 1 <= seconds <= 3600:
            raise ValueError("window must be between 1 second and 1 hour")
        if len({r.route for r in self.routes}) != len(self.routes):
            raise ValueError("duplicate route in batch")
        return self


class RouteScore(StrictModel):
    """Explainable per-route score against that route's own recent history."""

    route: str
    source: RuntimeSource
    window_end: UtcDatetime
    request_rate_z: float
    error_ratio: float = Field(ge=0, le=1)
    error_ratio_delta: float
    auth_failure_ratio: float = Field(ge=0, le=1)
    auth_failure_ratio_delta: float
    history_windows: int = Field(ge=0)
    alert_rate: float = Field(ge=0, description="Number of triggered rules in this window")
    anomaly_score: float = Field(ge=0, le=1)
    reasons: list[ShortText] = Field(default_factory=list)


class RuntimeIngestAck(StrictModel):
    accepted_routes: int
    anomalies: int
    monitoring_event_ids: list[MonitoringEventId] = Field(default_factory=list)
    scores: list[RouteScore]


class IngestTokenCreated(StrictModel):
    id: IngestTokenId
    project_id: ProjectId
    token: str = Field(description="Shown once; only its SHA-256 is stored")
    created_at: UtcDatetime
