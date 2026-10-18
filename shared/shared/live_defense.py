"""Live autonomous defense contracts (docs/LIVE_AUTONOMOUS_DEFENSE_PLAN.md).

An owner connects one of their applications. The application sends authenticated
security telemetry; deterministic rules open incidents; a policy (the hash-pinned RL
checkpoint when available, otherwise deterministic rules) proposes a response; an
independent authorization gate decides; only allowlisted, reversible, expiring controls
are executed against the owner's registered control endpoint; new telemetry verifies
them. Every decision keeps the RL recommendation, the rule evaluation, the final
authorized response, the executed action and the verification result separate, so no
reader can mistake a rule-selected block for an RL decision.

Signing secrets never appear in any model here except ``ConnectedAppCreated`` (shown once).
"""

from __future__ import annotations

import ipaddress
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from shared.base import ShortText, StrictModel, UtcDatetime
from shared.ids import (
    DefenseActionId,
    LiveAppId,
    LiveGrantId,
    LiveIncidentId,
    LiveNotificationId,
    ProjectId,
    SecurityEventId,
)

LIVE_SCHEMA_NOTE = "live-defense 0.1"


class LiveEventKind(StrEnum):
    auth_failure = "auth_failure"
    request = "request"
    not_found = "not_found"
    server_error = "server_error"
    waf_alert = "waf_alert"
    blocked = "blocked"  # the application refused a request because of an active control
    deploy = "deploy"
    config_change = "config_change"


class LiveSeverity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AppEnvironment(StrEnum):
    owned_test = "owned_test"
    staging = "staging"
    production = "production"


class DefenseActionKind(StrEnum):
    increase_logging = "increase_logging"
    rate_limit = "rate_limit"
    block_source = "block_source"
    escalate = "escalate"
    request_reassessment = "request_reassessment"


class LiveIncidentState(StrEnum):
    DETECTED = "DETECTED"
    TRIAGED = "TRIAGED"
    RECOMMENDED = "RECOMMENDED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    ROLLED_BACK = "ROLLED_BACK"


class DefenseActionStatus(StrEnum):
    pending_approval = "pending_approval"
    authorized = "authorized"
    executing = "executing"
    active = "active"
    verified = "verified"
    verification_failed = "verification_failed"
    failed = "failed"
    denied = "denied"
    expired = "expired"
    rollback_requested = "rollback_requested"
    rolled_back = "rolled_back"
    recorded = "recorded"  # internal kinds (escalate, request_reassessment): nothing executed


def _ip(value: str | None) -> str | None:
    if value is None:
        return None
    return str(ipaddress.ip_address(value.strip()))


# ------------------------------------------------------------------ ingestion


class SecurityEventIn(StrictModel):
    event_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,120}$", description="sender id; dedupe key")
    kind: LiveEventKind
    occurred_at: UtcDatetime
    source_ip: str | None = None
    route: str | None = Field(default=None, max_length=300)
    status: int | None = Field(default=None, ge=100, le=599)
    severity: LiveSeverity | None = None
    controlled_test: bool = Field(
        default=False, description="the sender marks traffic it generated for a controlled test"
    )
    detail: str | None = Field(default=None, max_length=500)

    @field_validator("source_ip")
    @classmethod
    def _source_ip(cls, value: str | None) -> str | None:
        return _ip(value)


class SecurityEventBatch(StrictModel):
    events: list[SecurityEventIn] = Field(min_length=1, max_length=200)


class LiveIngestAck(StrictModel):
    accepted: int
    duplicates: int
    job_id: str | None


class SecurityEventView(StrictModel):
    id: SecurityEventId
    seq: int
    app_id: LiveAppId
    app_name: ShortText
    kind: LiveEventKind
    source_ip: str | None
    route: str | None
    status: int | None
    severity: LiveSeverity | None
    controlled_test: bool
    occurred_at: UtcDatetime
    received_at: UtcDatetime
    incident_id: LiveIncidentId | None
    detail: str | None


# ------------------------------------------------------------------ applications


class ActionGrantCreate(StrictModel):
    kind: DefenseActionKind
    max_duration_s: int = Field(ge=60, le=86_400)
    hourly_budget: int = Field(ge=1, le=100)


class ActionGrant(StrictModel):
    id: LiveGrantId
    app_id: LiveAppId
    kind: DefenseActionKind
    max_duration_s: int
    hourly_budget: int
    granted_by: str
    created_at: UtcDatetime
    revoked_at: UtcDatetime | None


class ConnectedAppCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    environment: AppEnvironment
    control_url: str = Field(max_length=500, description="owner endpoint that applies controls")
    notify_url: str | None = Field(default=None, max_length=500)
    auto_response: bool = False
    protected_sources: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("protected_sources")
    @classmethod
    def _sources(cls, values: list[str]) -> list[str]:
        return [str(ipaddress.ip_address(v.strip())) for v in values]


class ConnectedAppUpdate(StrictModel):
    auto_response: bool | None = None
    enabled: bool | None = None


class ConnectedApp(StrictModel):
    id: LiveAppId
    project_id: ProjectId
    name: str
    environment: AppEnvironment
    control_url: str
    notify_url: str | None
    auto_response: bool
    enabled: bool
    protected_sources: list[str]
    grants: list[ActionGrant]
    secret_storage: Literal["encrypted"]
    created_at: UtcDatetime
    last_event_at: UtcDatetime | None


class ConnectedAppCreated(StrictModel):
    app: ConnectedApp
    signing_secret: str = Field(description="shown once; the owner installs it in the app")


# ------------------------------------------------------------------ decisions


class RLActionScore(StrictModel):
    action: str
    node: str | None
    q_value: float


class RLInference(StrictModel):
    """What the learned policy said. Present even when it was not used."""

    status: Literal["ok", "unavailable", "error", "rejected_input"]
    reason: ShortText
    policy_version: str | None = None
    checkpoint_sha256: str | None = None
    action: str | None = None
    node: str | None = None
    q_margin: float | None = None
    top_actions: list[RLActionScore] = Field(default_factory=list)
    mapped_kind: DefenseActionKind | None = None
    mapping_note: ShortText | None = None
    observation_provenance: dict[str, str] = Field(default_factory=dict)
    explanation: dict[str, Any] | None = None
    trained_in: ShortText = "DefenseSimEnv simulation (offline training); live inference only here"


class RuleEvaluation(StrictModel):
    rule_id: str
    minimum_kind: DefenseActionKind | None
    target: str | None
    duration_s: int | None
    rationale: ShortText


class FinalDecision(StrictModel):
    kind: DefenseActionKind | None
    target: str | None
    duration_s: int | None
    selected_by: Literal["rl", "rules", "rl_and_rules", "none"]
    reason: ShortText


class AuthorizationCheck(StrictModel):
    name: str
    passed: bool
    detail: ShortText


class AuthorizationResult(StrictModel):
    outcome: Literal["authorized", "requires_human", "denied", "not_applicable"]
    reason_code: str
    detail: ShortText
    checks: list[AuthorizationCheck] = Field(default_factory=list)


class PolicyDecision(StrictModel):
    rl: RLInference
    rules: RuleEvaluation
    final: FinalDecision
    authorization: AuthorizationResult
    decided_at: UtcDatetime


class VerificationOutcome(StrictModel):
    result: Literal["effective", "ineffective", "inconclusive", "pending"]
    control_state: str
    blocked_after: int
    attempts_after: int
    attempt: int
    checked_at: UtcDatetime
    detail: ShortText


# ------------------------------------------------------------------ incidents and actions


class LiveIncident(StrictModel):
    id: LiveIncidentId
    project_id: ProjectId
    app_id: LiveAppId
    app_name: str
    environment: AppEnvironment
    category: str
    source: str | None
    severity: LiveSeverity
    state: LiveIncidentState
    rationale: ShortText
    rule_id: str
    event_count: int
    controlled_test: bool = Field(description="every evidence event was marked as controlled test")
    opened_at: UtcDatetime
    updated_at: UtcDatetime
    closed_at: UtcDatetime | None
    decision: PolicyDecision | None


class DefenseAction(StrictModel):
    id: DefenseActionId
    incident_id: LiveIncidentId
    app_id: LiveAppId
    kind: DefenseActionKind
    target: str | None
    duration_s: int | None
    status: DefenseActionStatus
    mode: Literal["automatic", "human_approved", "internal"] | None
    decided_by: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    activated_at: UtcDatetime | None
    expires_at: UtcDatetime | None
    ended_at: UtcDatetime | None
    end_reason: ShortText | None
    verification: VerificationOutcome | None
    adapter: dict[str, Any] | None
    error: ShortText | None


class LiveTimelineEntry(StrictModel):
    seq: int
    at: UtcDatetime
    from_state: LiveIncidentState | None
    to_state: LiveIncidentState | None
    event: str
    actor_type: Literal["system", "user", "policy", "worker"]
    actor_id: str
    note: ShortText
    details: dict[str, Any] = Field(default_factory=dict)


class LiveNotification(StrictModel):
    id: LiveNotificationId
    incident_id: LiveIncidentId
    event: str
    status: Literal["pending", "delivered", "failed", "not_configured", "suppressed"]
    attempts: int
    response_status: int | None
    error: ShortText | None
    created_at: UtcDatetime
    delivered_at: UtcDatetime | None


class LiveIncidentDetail(StrictModel):
    incident: LiveIncident
    timeline: list[LiveTimelineEntry]
    events: list[SecurityEventView]
    actions: list[DefenseAction]
    notifications: list[LiveNotification]


class LiveActionDecision(StrictModel):
    reason: str | None = Field(default=None, max_length=500)


# ------------------------------------------------------------------ status


class WorkerHealth(StrictModel):
    worker_id: str
    last_seen: UtcDatetime
    age_s: float
    healthy: bool


class RLStatus(StrictModel):
    configured: bool
    loadable: bool
    policy_version: str | None
    reason: ShortText


class LiveCounts(StrictModel):
    active_incidents: int
    resolved_incidents: int
    escalated_incidents: int
    failed_incidents: int
    automatic_actions_executed: int
    pending_approvals: int
    active_controls: int


class LiveStatus(StrictModel):
    project_id: ProjectId
    monitoring: Literal["active", "inactive", "offline", "stale"]
    monitoring_reason: ShortText
    workers: list[WorkerHealth]
    worker_healthy: bool
    last_event_at: UtcDatetime | None
    stale_after_s: int
    apps: list[ConnectedApp]
    rl: RLStatus
    counts: LiveCounts
    generated_at: UtcDatetime
