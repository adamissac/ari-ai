"""NIST SP 800-61r3 incident lifecycle: transitions, gates, permissions, audit timeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.incident import (
    ApprovalGate,
    Incident,
    IncidentAction,
    IncidentActionKind,
    IncidentCreate,
    IncidentState,
    IncidentTimelineAction,
    TriageDecisionKind,
)
from standards.incident import IncidentRuleError, apply_action, open_incident

K = IncidentActionKind
S = IncidentState
T0 = datetime(2026, 10, 17, tzinfo=UTC)
SPAN = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app/routes.py",
    commit_sha="a" * 40,
    span=SourceSpan(start_line=10, end_line=14),
    provenance="test",
)
TEST_RUN = EvidenceRef(
    kind=EvidenceKind.test_run, artifact_id="art_87654321", sha256="c" * 64, provenance="test"
)
VER = "ver_00000001"
OWNER_A, OWNER_B, MEMBER = "usr_ownera01", "usr_ownerb01", "usr_member01"


class Driver:
    def __init__(self) -> None:
        self.now = T0
        self.incident = open_incident(
            IncidentCreate(title="Cross-tenant payment read", finding_ids=["fnd_00000001"]),
            incident_id="inc_00000001",
            project_id="prj_00000001",
            opened_by="user:usr_member01",
            now=self.now,
            simulated=True,
        )

    def do(
        self,
        kind: K,
        *,
        user: str = MEMBER,
        role: str = "member",
        verified: frozenset[str] = frozenset(),
        **fields: object,
    ) -> Incident:
        self.now += timedelta(minutes=1)
        self.incident, _ = apply_action(
            self.incident,
            IncidentAction(kind=kind, **fields),  # type: ignore[arg-type]
            actor_user_id=user,
            actor_role=role,
            now=self.now,
            accepted_verification_ids=verified,
        )
        return self.incident

    def approve(self, gate: ApprovalGate) -> None:
        self.do(
            K.request_approval,
            user=OWNER_A,
            role="owner",
            gate=gate,
            action_summary=f"{gate.value} plan",
        )
        self.do(K.decide_approval, user=OWNER_B, role="owner", gate=gate, approve=True, note="ok")

    def to(self, state: S, **kw: object) -> Incident:
        return self.do(K.transition, target_state=state, **kw)  # type: ignore[arg-type]


def triaged() -> Driver:
    d = Driver()
    d.do(
        K.triage,
        triage_decision=TriageDecisionKind.confirmed_incident,
        category="unauthorized access",
        note="reproduced",
        evidence=[SPAN],
    )
    d.do(K.assign_owner, owner=OWNER_A)
    d.to(S.analysis)
    return d


def in_recovery() -> Driver:
    d = triaged()
    d.approve(ApprovalGate.containment)
    d.to(S.containment)
    d.approve(ApprovalGate.eradication)
    d.do(K.link, verification_ids=[VER], evidence=[TEST_RUN])
    d.to(S.eradication, verified=frozenset({VER}))
    d.approve(ApprovalGate.recovery)
    d.to(S.recovery)
    return d


def deny(code: str, fn, *a, **kw) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(IncidentRuleError) as info:
        fn(*a, **kw)
    assert info.value.code == code, info.value.message


def test_open_incident_starts_reported_with_a_timeline_entry() -> None:
    inc = Driver().incident
    assert inc.state is S.reported and inc.simulated
    assert inc.timeline[0].action is IncidentTimelineAction.reported and inc.timeline[0].csf_refs


def test_full_lifecycle_with_gates_verification_and_closure() -> None:
    d = in_recovery()
    d.do(K.add_closure_criterion, criterion_key="regression", note="regression test passes on main")
    d.do(K.satisfy_closure_criterion, criterion_key="regression", evidence=[TEST_RUN])
    d.do(K.record_lessons_learned, note="centralize ownership checks", evidence=[TEST_RUN])
    d.do(
        K.record_communication,
        audience="internal",
        channel="email",
        csf_ref="RS.CO-02",
        note="status",
    )
    d.approve(ApprovalGate.closure)
    inc = d.to(S.closed)
    assert inc.state is S.closed and inc.closed_at is not None
    assert [
        e.to_state for e in inc.timeline if e.action is IncidentTimelineAction.state_changed
    ] == [S.analysis, S.containment, S.eradication, S.recovery, S.closed]
    assert all(e.actor.startswith("user:") for e in inc.timeline)
    assert [e.at for e in inc.timeline] == sorted(e.at for e in inc.timeline)


def test_disallowed_transitions_are_conflicts() -> None:
    d = triaged()
    deny("CONFLICT_STATE", d.to, S.recovery)
    deny("CONFLICT_STATE", d.to, S.closed)
    deny("VALIDATION_FAILED", d.do, K.transition)


def test_triage_requires_decision_category_and_rationale() -> None:
    d = Driver()
    deny("VALIDATION_FAILED", d.do, K.triage, triage_decision=TriageDecisionKind.confirmed_incident)
    deny("VALIDATION_FAILED", d.to, S.triaged)
    inc = d.do(
        K.triage,
        triage_decision=TriageDecisionKind.not_an_incident,
        category="vuln",
        note="a vulnerability finding, not an incident",
    )
    assert inc.state is S.rejected and inc.closed_at is not None


def test_analysis_needs_an_owner() -> None:
    d = Driver()
    d.do(K.triage, triage_decision=TriageDecisionKind.confirmed_incident, category="c", note="n")
    deny("APPROVAL_REQUIRED", d.to, S.analysis)


def test_gated_transitions_need_a_second_humans_approval() -> None:
    d = triaged()
    deny("APPROVAL_REQUIRED", d.to, S.containment)
    d.do(
        K.request_approval,
        user=OWNER_A,
        role="owner",
        gate=ApprovalGate.containment,
        action_summary="isolate host",
    )
    deny("APPROVAL_REQUIRED", d.to, S.containment)
    deny(
        "FORBIDDEN",
        d.do,
        K.decide_approval,
        user=OWNER_A,
        role="owner",
        gate=ApprovalGate.containment,
        approve=True,
    )
    deny(
        "FORBIDDEN",
        d.do,
        K.decide_approval,
        user=MEMBER,
        role="member",
        gate=ApprovalGate.containment,
        approve=True,
    )
    d.do(
        K.decide_approval,
        user=OWNER_B,
        role="owner",
        gate=ApprovalGate.containment,
        approve=False,
        note="not yet",
    )
    deny("APPROVAL_REQUIRED", d.to, S.containment)
    d.approve(ApprovalGate.containment)
    assert d.to(S.containment).state is S.containment


def test_approvals_only_in_their_source_state_and_not_twice() -> None:
    d = triaged()
    deny(
        "CONFLICT_STATE",
        d.do,
        K.request_approval,
        user=OWNER_A,
        role="owner",
        gate=ApprovalGate.recovery,
        action_summary="x",
    )
    d.do(
        K.request_approval,
        user=OWNER_A,
        role="owner",
        gate=ApprovalGate.containment,
        action_summary="x",
    )
    deny(
        "CONFLICT_STATE",
        d.do,
        K.request_approval,
        user=OWNER_A,
        role="owner",
        gate=ApprovalGate.containment,
        action_summary="x",
    )
    deny(
        "NOT_FOUND",
        d.do,
        K.decide_approval,
        user=OWNER_B,
        role="owner",
        gate=ApprovalGate.closure,
        approve=True,
    )


def test_eradication_requires_accepted_independent_verification() -> None:
    d = triaged()
    d.approve(ApprovalGate.containment)
    d.to(S.containment)
    d.approve(ApprovalGate.eradication)
    deny("APPROVAL_REQUIRED", d.to, S.eradication)
    d.do(K.link, verification_ids=[VER])
    deny("APPROVAL_REQUIRED", d.to, S.eradication)
    deny("APPROVAL_REQUIRED", d.to, S.eradication, verified=frozenset({"ver_99999999"}))
    assert d.to(S.eradication, verified=frozenset({VER})).state is S.eradication


def test_closure_requires_evidenced_criteria_and_lessons_learned() -> None:
    d = in_recovery()
    d.approve(ApprovalGate.closure)
    deny("APPROVAL_REQUIRED", d.to, S.closed)
    d.do(K.add_closure_criterion, criterion_key="k", note="d")
    deny("VALIDATION_FAILED", d.do, K.satisfy_closure_criterion, criterion_key="k")
    deny("NOT_FOUND", d.do, K.satisfy_closure_criterion, criterion_key="nope", evidence=[TEST_RUN])
    d.do(K.satisfy_closure_criterion, criterion_key="k", evidence=[TEST_RUN])
    deny("APPROVAL_REQUIRED", d.to, S.closed)
    deny("VALIDATION_FAILED", d.do, K.record_lessons_learned, note="no evidence")
    d.do(K.record_lessons_learned, note="lesson", evidence=[TEST_RUN])
    assert d.to(S.closed).state is S.closed


def test_terminal_incidents_only_accept_communications_and_lessons() -> None:
    d = Driver()
    d.do(K.triage, triage_decision=TriageDecisionKind.not_an_incident, category="c", note="n")
    deny("CONFLICT_STATE", d.do, K.assign_owner, owner=OWNER_A)
    d.do(
        K.record_communication,
        audience="internal",
        channel="ticket",
        csf_ref="RS.CO-02",
        note="closed as not an incident",
    )
    d.do(K.record_lessons_learned, note="tune the trigger", evidence=[SPAN])


def test_viewers_cannot_act_and_members_cannot_decide() -> None:
    d = Driver()
    deny("FORBIDDEN", d.do, K.escalate, role="viewer", note="x")
    deny("FORBIDDEN", d.do, K.decide_approval, gate=ApprovalGate.containment, approve=True)


def test_escalation_and_links_are_audited() -> None:
    d = triaged()
    n = len(d.incident.timeline)
    deny("VALIDATION_FAILED", d.do, K.escalate)
    inc = d.do(K.escalate, note="customer impact")
    inc = d.do(K.link, finding_ids=["fnd_00000001", "fnd_00000002"])
    assert inc.escalation_level == 1 and inc.finding_ids == ["fnd_00000001", "fnd_00000002"]
    assert [e.action for e in inc.timeline[n:]] == [
        IncidentTimelineAction.escalated,
        IncidentTimelineAction.evidence_linked,
    ]
    assert len(inc.timeline) == n + 2
