"""NIST SP 800-61r3 incident lifecycle: pure, deterministic rules.

``apply_action`` takes the current ``Incident``, one ``IncidentAction`` and the acting
user's role, and returns the next ``Incident`` or raises ``IncidentRuleError``. The
backend persists the result and writes the audit chain; it never decides gates itself.

Consequential transitions (containment, eradication, recovery, closure) require an
approved ``IncidentApproval`` for that gate, decided by a project owner who is not the
requester. Eradication additionally requires an *accepted* independent
``VerificationResult`` linked to the incident; closure requires every closure criterion
to be satisfied with evidence and lessons learned recorded with evidence. The platform
records these decisions; it never executes containment or recovery against any system.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from shared.incident import (
    GATED_TRANSITIONS,
    INCIDENT_TERMINAL,
    STATE_CSF,
    ApprovalGate,
    ClosureCriterion,
    CommunicationRecord,
    Incident,
    IncidentAction,
    IncidentActionKind,
    IncidentApproval,
    IncidentCreate,
    IncidentState,
    IncidentTimelineAction,
    IncidentTimelineEntry,
    TriageDecision,
    TriageDecisionKind,
    can_transition_incident,
)

K = IncidentActionKind
S = IncidentState

GATE_SOURCE: dict[ApprovalGate, IncidentState] = {
    ApprovalGate.containment: S.analysis,
    ApprovalGate.eradication: S.containment,
    ApprovalGate.recovery: S.eradication,
    ApprovalGate.closure: S.recovery,
}
MEMBER_ACTIONS = frozenset(K) - {K.decide_approval}
ALLOWED_AFTER_TERMINAL = frozenset({K.record_communication, K.record_lessons_learned})


class IncidentRuleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _deny(code: str, message: str) -> IncidentRuleError:
    return IncidentRuleError(code, message)


def open_incident(
    data: IncidentCreate,
    *,
    incident_id: str,
    project_id: str,
    opened_by: str,
    now: datetime,
    simulated: bool,
) -> Incident:
    function, refs = STATE_CSF[S.reported]
    return Incident(
        id=incident_id,
        project_id=project_id,
        title=data.title,
        state=S.reported,
        csf_function=function,  # type: ignore[arg-type]
        simulated=simulated or data.simulated,
        severity=data.severity,
        monitoring_event_ids=list(data.monitoring_event_ids),
        finding_ids=list(data.finding_ids),
        recommendation_ids=list(data.recommendation_ids),
        timeline=[
            IncidentTimelineEntry(
                at=now,
                actor=opened_by,
                action=IncidentTimelineAction.reported,
                to_state=S.reported,
                note=data.note or "Potential incident reported for triage",
                csf_refs=list(refs),
            )
        ],
        opened_by=opened_by,
        opened_at=now,
    )


def _merge(existing: Iterable[str], new: Iterable[str]) -> list[str]:
    out = list(existing)
    for item in new:
        if item not in out:
            out.append(item)
    return out


def _approved(incident: Incident, gate: ApprovalGate) -> IncidentApproval | None:
    return next((a for a in incident.approvals if a.gate is gate and a.status == "approved"), None)


def apply_action(
    incident: Incident,
    action: IncidentAction,
    *,
    actor_user_id: str,
    actor_role: str,
    now: datetime,
    accepted_verification_ids: frozenset[str] = frozenset(),
) -> tuple[Incident, IncidentTimelineEntry]:
    """Return the next incident state and the timeline entry recorded for this action."""
    actor = f"user:{actor_user_id}"
    if actor_role not in ("owner", "member"):
        raise _deny("FORBIDDEN", "viewers cannot act on incidents")
    if action.kind not in MEMBER_ACTIONS and actor_role != "owner":
        raise _deny("FORBIDDEN", f"{action.kind.value} requires the project owner role")
    if incident.state in INCIDENT_TERMINAL and action.kind not in ALLOWED_AFTER_TERMINAL:
        raise _deny("CONFLICT_STATE", f"incident is {incident.state.value}")

    doc = incident.model_dump()
    entry: dict[str, object] = {"at": now, "actor": actor, "note": action.note or action.kind.value}

    if action.kind is K.triage:
        if incident.state is not S.reported:
            raise _deny("CONFLICT_STATE", "only a reported incident can be triaged")
        if action.triage_decision is None or not action.category or not action.note:
            raise _deny(
                "VALIDATION_FAILED", "triage needs a decision, a category and a rationale note"
            )
        decision = TriageDecision(
            decision=action.triage_decision,
            category=action.category,
            rationale=action.note,
            decided_by=actor_user_id,
            decided_at=now,
            evidence=list(action.evidence),
        )
        target = (
            S.triaged
            if action.triage_decision is TriageDecisionKind.confirmed_incident
            else S.rejected
        )
        doc["triage"] = decision.model_dump()
        if action.business_priority:
            doc["business_priority"] = action.business_priority
        entry |= {
            "action": IncidentTimelineAction.triaged,
            "from_state": incident.state,
            "to_state": target,
            "csf_refs": ["RS.MA-02", "RS.MA-03"],
            "evidence": list(action.evidence),
        }
        doc["state"] = target
        doc["csf_function"] = STATE_CSF[target][0]
        if target is S.rejected:
            doc["closed_at"] = now

    elif action.kind is K.assign_owner:
        if not action.owner:
            raise _deny("VALIDATION_FAILED", "assign_owner needs an owner user id")
        doc["owner"] = action.owner
        entry |= {"action": IncidentTimelineAction.owner_assigned, "note": f"owner {action.owner}"}

    elif action.kind is K.escalate:
        if not action.note:
            raise _deny("VALIDATION_FAILED", "escalation needs a reason")
        if incident.escalation_level >= 5:
            raise _deny("CONFLICT_STATE", "already at the highest escalation level")
        doc["escalation_level"] = incident.escalation_level + 1
        entry |= {"action": IncidentTimelineAction.escalated, "csf_refs": ["RS.MA-04"]}

    elif action.kind is K.link:
        doc["finding_ids"] = _merge(incident.finding_ids, action.finding_ids)
        doc["monitoring_event_ids"] = _merge(
            incident.monitoring_event_ids, action.monitoring_event_ids
        )
        doc["recommendation_ids"] = _merge(incident.recommendation_ids, action.recommendation_ids)
        doc["verification_ids"] = _merge(incident.verification_ids, action.verification_ids)
        entry |= {
            "action": IncidentTimelineAction.evidence_linked,
            "csf_refs": ["RS.AN-07"],
            "evidence": list(action.evidence),
        }

    elif action.kind is K.record_communication:
        if not (action.audience and action.channel and action.csf_ref and action.note):
            raise _deny(
                "VALIDATION_FAILED",
                "a communication needs audience, channel, csf_ref and a summary",
            )
        record = CommunicationRecord(
            at=now,
            audience=action.audience,
            channel=action.channel,
            summary=action.note,
            recorded_by=actor_user_id,
            csf_ref=action.csf_ref,
        )
        doc["communications"] = [*doc["communications"], record.model_dump()]
        entry |= {
            "action": IncidentTimelineAction.communication_recorded,
            "csf_refs": [action.csf_ref],
        }

    elif action.kind is K.add_closure_criterion:
        if not (action.criterion_key and action.note):
            raise _deny("VALIDATION_FAILED", "a closure criterion needs a key and a description")
        if any(c.key == action.criterion_key for c in incident.closure_criteria):
            raise _deny("CONFLICT_STATE", f"criterion {action.criterion_key} already exists")
        crit = ClosureCriterion(key=action.criterion_key, description=action.note)
        doc["closure_criteria"] = [*doc["closure_criteria"], crit.model_dump()]
        entry |= {
            "action": IncidentTimelineAction.closure_criterion_updated,
            "csf_refs": ["RC.RP-06"],
        }

    elif action.kind is K.satisfy_closure_criterion:
        idx = next(
            (i for i, c in enumerate(incident.closure_criteria) if c.key == action.criterion_key),
            None,
        )
        if idx is None:
            raise _deny("NOT_FOUND", f"no closure criterion {action.criterion_key}")
        if not action.evidence:
            raise _deny("VALIDATION_FAILED", "satisfying a closure criterion requires evidence")
        crit = incident.closure_criteria[idx].model_copy(
            update={
                "satisfied": True,
                "evidence": list(action.evidence),
                "satisfied_by": actor_user_id,
            }
        )
        criteria = list(doc["closure_criteria"])
        criteria[idx] = ClosureCriterion.model_validate(crit.model_dump()).model_dump()
        doc["closure_criteria"] = criteria
        entry |= {
            "action": IncidentTimelineAction.closure_criterion_updated,
            "csf_refs": ["RC.RP-06"],
            "evidence": list(action.evidence),
        }

    elif action.kind is K.record_lessons_learned:
        if not (action.note and action.evidence):
            raise _deny(
                "VALIDATION_FAILED",
                "lessons learned need text and evidence (e.g. regression tests)",
            )
        doc["lessons_learned"] = action.note
        doc["lessons_learned_evidence"] = [e.model_dump() for e in action.evidence]
        entry |= {
            "action": IncidentTimelineAction.lessons_learned_recorded,
            "csf_refs": ["ID.IM-03"],
            "evidence": list(action.evidence),
        }

    elif action.kind is K.request_approval:
        if action.gate is None or not action.action_summary:
            raise _deny(
                "VALIDATION_FAILED", "an approval request needs a gate and an action summary"
            )
        if incident.state is not GATE_SOURCE[action.gate]:
            raise _deny(
                "CONFLICT_STATE",
                f"{action.gate.value} approval can only be requested in {GATE_SOURCE[action.gate].value}",
            )
        if any(
            a.gate is action.gate and a.status in ("pending", "approved")
            for a in incident.approvals
        ):
            raise _deny(
                "CONFLICT_STATE", f"a {action.gate.value} approval is already pending or approved"
            )
        approval = IncidentApproval(
            gate=action.gate,
            status="pending",
            action_summary=action.action_summary,
            requested_by=actor_user_id,
            requested_at=now,
        )
        doc["approvals"] = [*doc["approvals"], approval.model_dump()]
        entry |= {
            "action": IncidentTimelineAction.approval_requested,
            "note": f"{action.gate.value}: {action.action_summary}",
        }

    elif action.kind is K.decide_approval:
        if action.gate is None or action.approve is None:
            raise _deny("VALIDATION_FAILED", "a decision needs a gate and approve true/false")
        idx = next(
            (
                i
                for i, a in enumerate(incident.approvals)
                if a.gate is action.gate and a.status == "pending"
            ),
            None,
        )
        if idx is None:
            raise _deny("NOT_FOUND", f"no pending {action.gate.value} approval")
        pending = incident.approvals[idx]
        if pending.requested_by == actor_user_id:
            raise _deny("FORBIDDEN", "the requester cannot decide their own approval")
        decided = IncidentApproval.model_validate(
            {
                **pending.model_dump(),
                "status": "approved" if action.approve else "declined",
                "decided_by": actor_user_id,
                "decided_at": now,
                "reason": action.note or None,
            }
        )
        approvals = list(doc["approvals"])
        approvals[idx] = decided.model_dump()
        doc["approvals"] = approvals
        entry |= {
            "action": IncidentTimelineAction.approval_decided,
            "note": f"{action.gate.value} {'approved' if action.approve else 'declined'}",
        }

    elif action.kind is K.transition:
        to_state = action.target_state
        if to_state is None:
            raise _deny("VALIDATION_FAILED", "transition needs target_state")
        if not can_transition_incident(incident.state, to_state):
            raise _deny(
                "CONFLICT_STATE", f"{incident.state.value} -> {to_state.value} is not allowed"
            )
        if to_state is S.triaged:
            raise _deny("VALIDATION_FAILED", "use the triage action to record a triage decision")
        if to_state is S.rejected and not action.note:
            raise _deny("VALIDATION_FAILED", "rejecting an incident needs a reason")
        if to_state is S.analysis and not incident.owner:
            raise _deny("APPROVAL_REQUIRED", "assign an incident owner before analysis")
        gate = GATED_TRANSITIONS.get(to_state)
        if gate is not None and _approved(incident, gate) is None:
            raise _deny(
                "APPROVAL_REQUIRED", f"{to_state.value} requires an approved {gate.value} approval"
            )
        if to_state is S.eradication and not (
            set(incident.verification_ids) & accepted_verification_ids
        ):
            raise _deny(
                "APPROVAL_REQUIRED",
                "eradication requires a linked, accepted independent verification of the remediation",
            )
        if to_state is S.closed:
            if not incident.closure_criteria or not all(
                c.satisfied for c in incident.closure_criteria
            ):
                raise _deny(
                    "APPROVAL_REQUIRED", "every closure criterion must be satisfied with evidence"
                )
            if not (incident.lessons_learned and incident.lessons_learned_evidence):
                raise _deny(
                    "APPROVAL_REQUIRED", "lessons learned with evidence are required before closure"
                )
        doc["state"] = to_state
        doc["csf_function"] = STATE_CSF[to_state][0]
        if to_state in INCIDENT_TERMINAL:
            doc["closed_at"] = now
        entry |= {
            "action": IncidentTimelineAction.state_changed,
            "from_state": incident.state,
            "to_state": to_state,
            "csf_refs": list(STATE_CSF[to_state][1]),
            "evidence": list(action.evidence),
        }
    else:  # pragma: no cover - exhaustive over IncidentActionKind
        raise _deny("VALIDATION_FAILED", f"unsupported action {action.kind}")

    timeline_entry = IncidentTimelineEntry.model_validate(entry)
    doc["timeline"] = [*doc["timeline"], timeline_entry.model_dump()]
    return Incident.model_validate(doc), timeline_entry
