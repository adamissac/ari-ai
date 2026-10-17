"""Incident records aligned with NIST SP 800-61 Rev. 3 and CSF 2.0 (contract 0.7.0, additive).

An incident is a separate entity from a vulnerability ``Finding``: a finding says a
weakness exists (possibly reproduced in a sandbox); an incident says an adverse event
affecting the organisation is being handled. Findings may be *linked* to an incident as
context, but no finding becomes an incident by itself (DE.AE-08: incidents are declared
when adverse events meet the defined incident criteria, by a person).

The state names are this platform's; each maps to the CSF 2.0 Function/subcategories it
records (``STATE_CSF``). The pure transition rules and approval gates live here so every
consumer enforces the same table; persistence and role checks live in the backend.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shared.base import ShortText, StrictModel, UtcDatetime
from shared.evidence import EvidenceRef
from shared.ids import (
    AuditEventId,
    FindingId,
    IncidentId,
    MonitoringEventId,
    ProjectId,
    RecommendationId,
    UserId,
    VerificationId,
)
from shared.standards import StandardMapping


class IncidentState(StrEnum):
    reported = "reported"
    triaged = "triaged"
    analysis = "analysis"
    containment = "containment"
    eradication = "eradication"
    recovery = "recovery"
    closed = "closed"
    rejected = "rejected"


_I = IncidentState
INCIDENT_TERMINAL: frozenset[IncidentState] = frozenset({_I.closed, _I.rejected})
INCIDENT_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    _I.reported: frozenset({_I.triaged, _I.rejected}),
    _I.triaged: frozenset({_I.analysis, _I.rejected}),
    _I.analysis: frozenset({_I.containment}),
    _I.containment: frozenset({_I.eradication}),
    _I.eradication: frozenset({_I.recovery}),
    _I.recovery: frozenset({_I.closed}),
    _I.closed: frozenset(),
    _I.rejected: frozenset(),
}

STATE_CSF: dict[IncidentState, tuple[str, tuple[str, ...]]] = {
    _I.reported: ("DE", ("DE.AE-02",)),
    _I.triaged: ("RS", ("RS.MA-02", "RS.MA-03")),
    _I.analysis: ("RS", ("RS.AN-03",)),
    _I.containment: ("RS", ("RS.MI-01",)),
    _I.eradication: ("RS", ("RS.MI-02",)),
    _I.recovery: ("RC", ("RC.RP-01", "RC.RP-02", "RC.RP-05")),
    _I.closed: ("RC", ("RC.RP-06", "ID.IM-03")),
    _I.rejected: ("RS", ("RS.MA-02",)),
}


class ApprovalGate(StrEnum):
    containment = "containment"
    eradication = "eradication"
    recovery = "recovery"
    closure = "closure"


GATED_TRANSITIONS: dict[IncidentState, ApprovalGate] = {
    _I.containment: ApprovalGate.containment,
    _I.eradication: ApprovalGate.eradication,
    _I.recovery: ApprovalGate.recovery,
    _I.closed: ApprovalGate.closure,
}


def can_transition_incident(current: IncidentState, target: IncidentState) -> bool:
    return target in INCIDENT_TRANSITIONS[current]


class TriageDecisionKind(StrEnum):
    confirmed_incident = "confirmed_incident"
    not_an_incident = "not_an_incident"
    duplicate = "duplicate"


class TriageDecision(StrictModel):
    decision: TriageDecisionKind
    category: ShortText
    rationale: ShortText
    decided_by: UserId
    decided_at: UtcDatetime
    evidence: list[EvidenceRef] = Field(default_factory=list)


class IncidentApproval(StrictModel):
    """Two-person rule: the decider must differ from the requester and hold the owner role."""

    gate: ApprovalGate
    status: Literal["pending", "approved", "declined"]
    action_summary: ShortText = Field(
        description="What a human will do (containment/eradication are never executed by the platform)"
    )
    requested_by: UserId
    requested_at: UtcDatetime
    decided_by: UserId | None = None
    decided_at: UtcDatetime | None = None
    reason: ShortText | None = None

    @model_validator(mode="after")
    def _decided(self) -> IncidentApproval:
        if self.status != "pending" and not (self.decided_by and self.decided_at):
            raise ValueError("a decided approval names the decider and time")
        if self.decided_by is not None and self.decided_by == self.requested_by:
            raise ValueError("the requester cannot decide their own approval")
        return self


class CommunicationRecord(StrictModel):
    at: UtcDatetime
    audience: Literal["internal", "external", "customer", "regulator", "law_enforcement"]
    channel: ShortText
    summary: ShortText
    recorded_by: UserId
    csf_ref: Literal["RS.CO-02", "RS.CO-03", "RC.CO-03"]


class ClosureCriterion(StrictModel):
    key: ShortText
    description: ShortText
    satisfied: bool = False
    evidence: list[EvidenceRef] = Field(default_factory=list)
    satisfied_by: UserId | None = None

    @model_validator(mode="after")
    def _evidence_when_satisfied(self) -> ClosureCriterion:
        if self.satisfied and not (self.evidence and self.satisfied_by):
            raise ValueError(
                "a satisfied closure criterion needs evidence and the user who checked it"
            )
        return self


class IncidentTimelineAction(StrEnum):
    reported = "reported"
    triaged = "triaged"
    owner_assigned = "owner_assigned"
    escalated = "escalated"
    state_changed = "state_changed"
    approval_requested = "approval_requested"
    approval_decided = "approval_decided"
    evidence_linked = "evidence_linked"
    communication_recorded = "communication_recorded"
    closure_criterion_updated = "closure_criterion_updated"
    lessons_learned_recorded = "lessons_learned_recorded"
    denied = "denied"


class IncidentTimelineEntry(StrictModel):
    at: UtcDatetime
    actor: ShortText = Field(description="'user:<usr_id>' or 'system'")
    action: IncidentTimelineAction
    from_state: IncidentState | None = None
    to_state: IncidentState | None = None
    note: ShortText
    csf_refs: list[ShortText] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    audit_event_id: AuditEventId | None = None


class Incident(StrictModel):
    id: IncidentId
    project_id: ProjectId
    title: ShortText
    state: IncidentState
    csf_function: Literal["GV", "ID", "PR", "DE", "RS", "RC"]
    simulated: bool = Field(description="True when opened only from demo/replay/simulated signals")
    severity: Literal["info", "low", "medium", "high", "critical"] | None = None
    business_priority: Literal["unset", "p1", "p2", "p3", "p4"] = "unset"
    owner: UserId | None = None
    escalation_level: int = Field(default=0, ge=0, le=5)
    triage: TriageDecision | None = None
    monitoring_event_ids: list[MonitoringEventId] = Field(default_factory=list)
    finding_ids: list[FindingId] = Field(default_factory=list)
    recommendation_ids: list[RecommendationId] = Field(default_factory=list)
    verification_ids: list[VerificationId] = Field(default_factory=list)
    attack: list[StandardMapping] = Field(default_factory=list)
    approvals: list[IncidentApproval] = Field(default_factory=list)
    communications: list[CommunicationRecord] = Field(default_factory=list)
    closure_criteria: list[ClosureCriterion] = Field(default_factory=list)
    lessons_learned: ShortText | None = None
    lessons_learned_evidence: list[EvidenceRef] = Field(default_factory=list)
    timeline: list[IncidentTimelineEntry] = Field(min_length=1)
    opened_by: ShortText
    opened_at: UtcDatetime
    closed_at: UtcDatetime | None = None


class IncidentCreate(StrictModel):
    title: ShortText
    simulated: bool = False
    severity: Literal["info", "low", "medium", "high", "critical"] | None = None
    monitoring_event_ids: list[MonitoringEventId] = Field(default_factory=list)
    finding_ids: list[FindingId] = Field(default_factory=list)
    recommendation_ids: list[RecommendationId] = Field(default_factory=list)
    note: ShortText = ""


class IncidentActionKind(StrEnum):
    triage = "triage"
    assign_owner = "assign_owner"
    escalate = "escalate"
    transition = "transition"
    request_approval = "request_approval"
    decide_approval = "decide_approval"
    link = "link"
    record_communication = "record_communication"
    add_closure_criterion = "add_closure_criterion"
    satisfy_closure_criterion = "satisfy_closure_criterion"
    record_lessons_learned = "record_lessons_learned"


class IncidentAction(StrictModel):
    """One API action on an incident. Fields not relevant to ``kind`` must be left unset."""

    kind: IncidentActionKind
    note: ShortText = ""
    target_state: IncidentState | None = None
    triage_decision: TriageDecisionKind | None = None
    category: ShortText | None = None
    business_priority: Literal["unset", "p1", "p2", "p3", "p4"] | None = None
    owner: UserId | None = None
    gate: ApprovalGate | None = None
    approve: bool | None = None
    action_summary: ShortText | None = None
    finding_ids: list[FindingId] = Field(default_factory=list)
    monitoring_event_ids: list[MonitoringEventId] = Field(default_factory=list)
    recommendation_ids: list[RecommendationId] = Field(default_factory=list)
    verification_ids: list[VerificationId] = Field(default_factory=list)
    audience: Literal["internal", "external", "customer", "regulator", "law_enforcement"] | None = (
        None
    )
    channel: ShortText | None = None
    csf_ref: Literal["RS.CO-02", "RS.CO-03", "RC.CO-03"] | None = None
    criterion_key: ShortText | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class IncidentDetail(StrictModel):
    incident: Incident
    standards: dict[str, object] = Field(default_factory=dict)
