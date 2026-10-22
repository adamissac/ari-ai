"""Live Defense shadow-pilot contracts (Phase 2).

These types describe recorded evidence for a customer shadow deployment:
connected staging applications, ingest-token metadata, timestamps from the
job worker and runtime ingest, a topology derived from those records, and
analyst reviews of stored recommendations.

They do **not** describe autonomous enforcement. ``AnalystReview.executes`` is
always false. ``DefenseHealth.status`` is always ``unknown``: HTTP 200 from
this API is not a healthy verdict, and there is no live health-check producer.
There is no live policy-decision producer on the control plane; stored
``DefenseRecommendation`` rows remain simulation-derived.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from shared.base import ShortText, StrictModel, UtcDatetime
from shared.ids import (
    AnalystReviewId,
    ConnectedApplicationId,
    IngestTokenId,
    ProjectId,
    RecommendationId,
    UserId,
)


class StagingEnvironment(StrEnum):
    """Environments a shadow-pilot app may declare. Production is not allowed."""

    sandbox = "sandbox"
    owned_test = "owned_test"


class ApplicationVerification(StrEnum):
    unverified = "unverified"
    ingest_seen = "ingest_seen"
    token_revoked = "token_revoked"


class ConnectedApplication(StrictModel):
    """Owner-registered staging app under watch. Never includes secrets."""

    id: ConnectedApplicationId
    project_id: ProjectId
    name: ShortText
    environment: StagingEnvironment
    ingest_configured: bool = Field(
        description="True when a non-revoked ingest token exists; the token itself is never returned"
    )
    last_ingest_at: UtcDatetime | None = None
    verification: ApplicationVerification
    shadow_mode: Literal[True] = True
    created_by: UserId
    created_at: UtcDatetime


class ConnectedApplicationCreate(StrictModel):
    name: ShortText
    environment: StagingEnvironment = StagingEnvironment.sandbox


class IngestTokenView(StrictModel):
    """Metadata for an ingest token. The secret is never included after issuance."""

    id: IngestTokenId
    project_id: ProjectId
    application_id: ConnectedApplicationId | None = None
    created_at: UtcDatetime
    revoked_at: UtcDatetime | None = None
    last_used_at: UtcDatetime | None = None


class DefenseHealth(StrictModel):
    """Recorded timestamps for ingest and the job worker. Not a liveness verdict."""

    project_id: ProjectId
    worker_seen_at: UtcDatetime | None = Field(
        default=None, description="Latest jobs.heartbeat_at; null if no worker has heartbeated"
    )
    queue_depth: int | None = Field(
        default=None, ge=0, description="Queued jobs; null if the queue was not readable"
    )
    last_ingest_at: UtcDatetime | None = Field(
        default=None, description="Latest runtime_windows.window_end for this project"
    )
    last_runtime_event_at: UtcDatetime | None = Field(
        default=None, description="Latest monitoring event with source=runtime"
    )
    status: Literal["unknown"] = "unknown"
    status_reason: ShortText = (
        "No recorded health-check producer. Timestamps are evidence only; "
        "HTTP 200 is not a healthy verdict."
    )


class ComponentNodeKind(StrEnum):
    application = "application"
    route = "route"


class ComponentHealthState(StrEnum):
    unknown = "unknown"
    checking = "checking"
    healthy = "healthy"
    attention = "attention"


class ComponentObservationSource(StrEnum):
    ingest = "ingest"
    github = "github"
    none = "none"


class ComponentNode(StrictModel):
    id: ShortText
    label: ShortText
    kind: ComponentNodeKind
    critical: bool = False


class ComponentLink(StrictModel):
    source_id: ShortText
    target_id: ShortText


class ComponentObservation(StrictModel):
    node_id: ShortText
    state: ComponentHealthState
    last_checked_at: UtcDatetime | None = None
    source: ComponentObservationSource
    simulated: bool
    note: ShortText | None = None


class ComponentGraph(StrictModel):
    """Topology from registered apps and observed ingest routes. Missing checks stay unknown."""

    project_id: ProjectId
    nodes: list[ComponentNode] = Field(default_factory=list)
    links: list[ComponentLink] = Field(default_factory=list)
    observations: list[ComponentObservation] = Field(default_factory=list)
    generated_at: UtcDatetime
    note: ShortText = (
        "healthy is never inferred from HTTP 200. attention is only set when the "
        "latest recorded runtime score was anomalous; every other node is unknown."
    )


class AnalystReviewDecision(StrEnum):
    accept = "accept"
    reject = "reject"
    needs_investigation = "needs_investigation"


class AnalystReview(StrictModel):
    """Human review of a stored recommendation. Accept does not execute anything."""

    id: AnalystReviewId
    project_id: ProjectId
    recommendation_id: RecommendationId
    decision: AnalystReviewDecision
    reason: ShortText | None = None
    reviewed_by: UserId
    reviewed_at: UtcDatetime
    executes: Literal[False] = False
    enforcement: Literal["none"] = "none"


class AnalystReviewCreate(StrictModel):
    decision: AnalystReviewDecision
    reason: ShortText | None = None
