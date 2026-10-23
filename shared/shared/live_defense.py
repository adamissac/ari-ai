"""Live Defense contracts (Phase 2–4).

Phase 2/3 types describe recorded evidence for a customer shadow deployment:
connected staging applications, ingest-token metadata, timestamps from the
job worker and runtime ingest, a topology derived from those records,
analyst reviews, and genuine ``LivePolicyDecision`` rows produced only when
deterministic rules or validated frozen-v6 inference actually ran.

``AnalystReview.executes`` is always false. ``LivePolicyDecision.enforcement``
is always ``NOT_EXECUTED``. Those rows never become a live control.

Phase 4 adds a **separate** control lifecycle (``LiveControl``) and a
deterministic authorization DTO. Executable actions exist only after
``authorize.check``, only against a registered owned-test/sandbox app, and
only for the four allowlisted kinds. Production is still not a
``StagingEnvironment`` value. ``DefenseHealth.status`` is always ``unknown``:
HTTP 200 from this API is not a healthy verdict.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shared.base import Sha256Hex, ShortText, StrictModel, UtcDatetime
from shared.ids import (
    AnalystReviewId,
    ConnectedApplicationId,
    ControlChannelId,
    ControlGrantId,
    EmergencyStopId,
    IngestTokenId,
    LiveControlId,
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
    control_channel_configured: bool = Field(
        default=False,
        description="True when a control channel exists; the HMAC secret is never returned",
    )
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


# ---------------------------------------------------------------------------
# Phase 4 — controlled enforcement (owned test only)
# ---------------------------------------------------------------------------

ISOLATED_FIXTURE_SOURCE = "198.51.100.66"
"""The only address the gate and adapter accept as a ``block_source`` target.

RFC 5737 TEST-NET-2. Exact string match only — no CIDR, ranges, parsing, or
public/private/loopback/link-local unicast. Authz and the HMAC adapter share
:func:`is_owned_test_block_source`. This is the isolated owned-test fixture,
not a production attribution identity.
"""

OWNED_TEST_OTHER_PROBE_SOURCE = "203.0.113.50"
"""RFC 5737 TEST-NET-3. Fixture-only *other-source* probe, never a block target."""

OWNED_TEST_BLOCK_SOURCES = frozenset({ISOLATED_FIXTURE_SOURCE})
OWNED_TEST_PROBE_SOURCES = frozenset({ISOLATED_FIXTURE_SOURCE, OWNED_TEST_OTHER_PROBE_SOURCE})
FIXTURE_SOURCE_HEADER = "x-ari-source"
"""Owned-test probe header. Spoofable; never production identity or auth."""


def is_owned_test_block_source(value: str) -> bool:
    """Exact allowlist membership. Authz, adapter, and fixture must all use this."""
    return value in OWNED_TEST_BLOCK_SOURCES


def is_owned_test_probe_source(value: str) -> bool:
    """Whether ``x-ari-source`` may be honored on the owned-test fixture."""
    return value in OWNED_TEST_PROBE_SOURCES


CONTROL_PATH: Literal["/live-defense/control"] = "/live-defense/control"
MIN_CONTROL_DURATION_S = 5
MAX_CONTROL_DURATION_S = 3600
RATE_LIMIT_MIN_REQUESTS = 1
AUTHORIZATION_CHECKS: tuple[str, ...] = (
    "authenticated_session",
    "action_allowlist",
    "application_registered",
    "environment_owned_test",
    "owner_grant_exact_kind",
    "owner_grant_exact_app",
    "grant_active",
    "duration_within_grant",
    "hourly_budget",
    "approval_binding",
    "blast_radius",
    "address_policy",
    "control_channel_allowlist",
    "kill_switch_clear",
    "no_unresolved_control",
)

CONTROL_LIFECYCLE_CAVEAT = (
    "Owned-test control. Not customer production. Adapter HTTP 200 is not "
    "effectiveness. Shadow recommendations stay NOT_EXECUTED."
)


class LiveControlKind(StrEnum):
    """The only actions that have an adapter or a recorded human escalation."""

    rate_limit = "rate_limit"
    block_source = "block_source"
    increase_logging = "increase_logging"
    escalate = "escalate"


class LiveControlTargetType(StrEnum):
    route = "route"
    source_ip = "source_ip"
    application = "application"
    none = "none"


class LiveControlStatus(StrEnum):
    """Control lifecycle. Distinct from NIST SP 800-61r3 incident phases."""

    pending_authorization = "pending_authorization"
    authorized = "authorized"
    executing = "executing"
    verifying = "verifying"
    verified = "verified"
    failed = "failed"
    expired = "expired"
    rolled_back = "rolled_back"
    escalated = "escalated"
    rejected = "rejected"
    emergency_stopped = "emergency_stopped"


class LiveControlOrigin(StrEnum):
    """Who proposed the action. Origin never bypasses the gate."""

    analyst = "analyst"
    rules = "rules"
    v6_shadow = "v6_shadow"


class AuthorizationCheckResult(StrictModel):
    name: ShortText
    passed: bool
    reason: ShortText


class ControlTarget(StrictModel):
    type: LiveControlTargetType
    value: ShortText = ""


class ControlGrant(StrictModel):
    """Owner grant for exact kinds on one owned-test/sandbox application."""

    id: ControlGrantId
    project_id: ProjectId
    application_id: ConnectedApplicationId
    allowed_kinds: list[LiveControlKind] = Field(min_length=1)
    max_duration_s: int = Field(ge=MIN_CONTROL_DURATION_S, le=MAX_CONTROL_DURATION_S)
    hourly_budget: int = Field(ge=1, le=20)
    created_by: UserId
    created_at: UtcDatetime
    expires_at: UtcDatetime | None = None
    revoked_at: UtcDatetime | None = None


class ControlGrantCreate(StrictModel):
    application_id: ConnectedApplicationId
    allowed_kinds: list[LiveControlKind] = Field(min_length=1)
    max_duration_s: int = Field(default=300, ge=MIN_CONTROL_DURATION_S, le=MAX_CONTROL_DURATION_S)
    hourly_budget: int = Field(default=5, ge=1, le=20)
    expires_at: UtcDatetime | None = None


class ControlChannelView(StrictModel):
    """Registered adapter destination. Secret is never included after issuance."""

    id: ControlChannelId
    project_id: ProjectId
    application_id: ConnectedApplicationId
    host: Literal["127.0.0.1"]
    port: int = Field(ge=1024, le=65535)
    path: Literal["/live-defense/control"] = CONTROL_PATH
    created_at: UtcDatetime
    revoked_at: UtcDatetime | None = None


class ControlChannelCreate(StrictModel):
    """Owner registers a loopback port. Arbitrary URLs are rejected by construction."""

    port: int = Field(ge=1024, le=65535)


class ControlChannelCreated(ControlChannelView):
    hmac_secret: ShortText = Field(description="Shown once; never re-returned")


class ControlAuthorizationCreate(StrictModel):
    """Analyst authorization request. Actor identity is the session, not this body."""

    kind: LiveControlKind
    target: ControlTarget
    duration_s: int = Field(ge=MIN_CONTROL_DURATION_S, le=MAX_CONTROL_DURATION_S)
    rationale: ShortText | None = None
    live_policy_decision_id: LivePolicyDecisionId | None = None
    max_requests: int | None = Field(
        default=None,
        ge=RATE_LIMIT_MIN_REQUESTS,
        le=10_000,
        description="Required for rate_limit; ignored otherwise",
    )


class LiveControlVerification(StrictModel):
    observed_effect: bool
    adapter_http_status: int | None = None
    probe_http_statuses: list[int] = Field(default_factory=list)
    method: ShortText
    detail: ShortText
    verified_at: UtcDatetime
    adapter_http_200_is_not_effectiveness: Literal[True] = True


class LiveControl(StrictModel):
    """One authorized (or denied) owned-test control. Not a NIST incident."""

    id: LiveControlId
    project_id: ProjectId
    application_id: ConnectedApplicationId
    live_policy_decision_id: LivePolicyDecisionId | None = None
    grant_id: ControlGrantId | None = None
    kind: LiveControlKind
    target: ControlTarget
    duration_s: int = Field(ge=MIN_CONTROL_DURATION_S, le=MAX_CONTROL_DURATION_S)
    status: LiveControlStatus
    origin: LiveControlOrigin
    binding_sha256: Sha256Hex
    requested_by: UserId
    requested_at: UtcDatetime
    authorized_at: UtcDatetime | None = None
    executing_at: UtcDatetime | None = None
    verified_at: UtcDatetime | None = None
    expires_at: UtcDatetime | None = None
    ended_at: UtcDatetime | None = None
    checks: list[AuthorizationCheckResult] = Field(default_factory=list)
    verification: LiveControlVerification | None = None
    unresolved: bool = False
    simulated: Literal[False] = False
    environment_label: Literal["OWNED TEST ENVIRONMENT"] = "OWNED TEST ENVIRONMENT"
    caveat: ShortText = CONTROL_LIFECYCLE_CAVEAT
    max_requests: int | None = None
    rationale: ShortText | None = None
    denial_reason: ShortText | None = None


class EmergencyStop(StrictModel):
    id: EmergencyStopId
    project_id: ProjectId
    application_id: ConnectedApplicationId | None = None
    active: bool
    requested_by: UserId
    requested_at: UtcDatetime
    cleared_at: UtcDatetime | None = None
    verified_cleared: bool = False
    note: ShortText | None = None


class EmergencyStopCreate(StrictModel):
    application_id: ConnectedApplicationId | None = None
    note: ShortText | None = None


class LiveControlRollbackCreate(StrictModel):
    reason: ShortText | None = None
