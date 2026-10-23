"""Live Defense shadow-pilot contracts (Phase 2 + Phase 3 shadow runtime).

These types describe recorded evidence for a customer shadow deployment:
connected staging applications, ingest-token metadata, timestamps from the
job worker and runtime ingest, a topology derived from those records,
analyst reviews, and genuine ``LivePolicyDecision`` rows produced only when
deterministic rules or validated frozen-v6 inference actually ran.

They do **not** describe autonomous enforcement. ``AnalystReview.executes`` is
always false. ``LivePolicyDecision.enforcement`` is always ``NOT_EXECUTED``.
``DefenseHealth.status`` is always ``unknown``: HTTP 200 from this API is not
a healthy verdict, and there is no live health-check producer. Stored
``DefenseRecommendation`` rows remain simulation-derived.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shared.base import Sha256Hex, ShortText, StrictModel, UtcDatetime
from shared.ids import (
    AnalystReviewId,
    ConnectedApplicationId,
    IngestTokenId,
    LivePolicyDecisionId,
    MonitoringEventId,
    ProjectId,
    RecommendationId,
    UserId,
)
from shared.monitoring import PrincipalRef, RuntimeSource
from shared.rl import ActionScore, DefenseActionName, NodeName


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
    """Human review of a stored recommendation or live shadow decision.

    Accept does not execute anything and is never converted into an RL label.
    """

    id: AnalystReviewId
    project_id: ProjectId
    recommendation_id: RecommendationId | None = None
    live_policy_decision_id: LivePolicyDecisionId | None = None
    decision: AnalystReviewDecision
    reason: ShortText | None = None
    reviewed_by: UserId
    reviewed_at: UtcDatetime
    executes: Literal[False] = False
    enforcement: Literal["none"] = "none"

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> AnalystReview:
        rec = self.recommendation_id is not None
        live = self.live_policy_decision_id is not None
        if rec == live:
            raise ValueError(
                "exactly one of recommendation_id or live_policy_decision_id is required"
            )
        return self


class AnalystReviewCreate(StrictModel):
    decision: AnalystReviewDecision
    reason: ShortText | None = None


class ShadowProducer(StrEnum):
    """What actually produced the persisted shadow decision."""

    rules = "rules"
    v6_shadow = "v6_shadow"
    abstention = "abstention"


class AuthorizationContext(StrEnum):
    """Whether the reporter supplied ownership classification with the window."""

    verified = "verified"
    unverified = "unverified"
    missing = "missing"


class InferenceStatus(StrEnum):
    """Whether frozen v6 inference ran. Q-values exist only when ``ran``."""

    ran = "ran"
    skipped_quiet_window = "skipped_quiet_window"
    skipped_incomplete = "skipped_incomplete"
    skipped_stale = "skipped_stale"
    skipped_source = "skipped_source"
    skipped_unavailable = "skipped_unavailable"
    skipped_schema = "skipped_schema"
    skipped_mask = "skipped_mask"
    skipped_authorization = "skipped_authorization"
    skipped_target = "skipped_target"


SHADOW_DECISION_CAVEAT = (
    "Shadow recommendation from authenticated staging telemetry. Not executed. "
    "Q-values appear only when frozen v6 inference actually ran."
)


class LivePolicyDecision(StrictModel):
    """One shadow decision for one ingest window. Never an executed control."""

    id: LivePolicyDecisionId
    project_id: ProjectId
    application_id: ConnectedApplicationId | None = None
    created_at: UtcDatetime
    window_end: UtcDatetime
    telemetry_source: RuntimeSource
    simulated: bool
    producer: ShadowProducer
    rules_ran: bool
    inference_ran: bool
    inference_status: InferenceStatus
    action: DefenseActionName | None = None
    node: NodeName | None = None
    top_actions: list[ActionScore] | None = Field(
        default=None,
        description="Q ranking from frozen v6; null when inference did not run",
    )
    q_margin: float | None = Field(
        default=None, description="Null when inference did not run; never synthesized"
    )
    observation: list[float] | None = Field(
        default=None, description="Null when inference did not run; never synthesized"
    )
    policy_version: ShortText | None = None
    checkpoint_sha256: Sha256Hex | None = None
    abstention_reason: ShortText | None = None
    observation_complete: bool
    feature_schema_ok: bool
    action_mask_valid: bool
    freshness_ok: bool
    authorization_context: AuthorizationContext
    enforcement: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"
    executed: Literal[False] = False
    evidence_event_ids: list[MonitoringEventId] = Field(default_factory=list)
    rule_hits: list[ShortText] = Field(default_factory=list)
    principal_targets: list[PrincipalRef] = Field(default_factory=list)
    feature_mapping_note: ShortText | None = None
    caveat: ShortText = SHADOW_DECISION_CAVEAT
