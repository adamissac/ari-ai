"""Finding lifecycle at the trusted host boundary: agents report a status, the host applies
it only along docs/12 edges and only when the persisted evidence supports it."""

from __future__ import annotations

import pytest
from helpers import setup_project

from backend.host import AssessmentHost, HostError
from shared.base import utcnow
from shared.errors import ErrorCode
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import Finding, FindingKind, FindingStatus, ValidationResult
from shared.ids import IdPrefix, new_id

EV = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app.py",
    commit_sha="b" * 40,
    span=SourceSpan(start_line=1, end_line=2),
    provenance="test",
)


@pytest.fixture
def host_and_finding(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    asm = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]
    host = AssessmentHost(asm["id"])
    now = utcnow()
    fid = new_id(IdPrefix.fnd)
    host.record_finding(
        Finding(
            id=fid,
            assessment_id=asm["id"],
            commit_sha="b" * 40,
            kind=FindingKind.security,
            title="ownership check missing",
            status=FindingStatus.hypothesis,
            confidence=0.6,
            evidence=[EV],
            created_at=now,
            updated_at=now,
        ),
        actor="agent:scout",
    )
    return alice, host, fid


def _validation(fid: str, outcome: str) -> ValidationResult:
    return ValidationResult(
        id=new_id(IdPrefix.val),
        hypothesis_id=new_id(IdPrefix.hyp),
        outcome=outcome,
        check_template_id="access_control.ownership",
        check_template_version="1",
        sandbox_run_id="sbx_test",
        evidence=[EV],
    )


def test_transition_needs_evidence_then_records_history(host_and_finding) -> None:
    alice, host, fid = host_and_finding
    with pytest.raises(HostError) as no_evidence:
        host.set_finding_status(fid, "validated", actor="agent:orchestrator")
    assert no_evidence.value.code is ErrorCode.VALIDATION_FAILED

    host.record(fid, _validation(fid, "confirmed"))
    host.set_finding_status(fid, "validated", actor="agent:orchestrator", reason="probe confirmed")
    host.set_finding_status(fid, "validated", actor="agent:orchestrator")  # idempotent
    host.set_finding_status(fid, "diagnosed", actor="agent:orchestrator")

    body = alice.get(f"/api/v1/findings/{fid}").json()["finding"]
    assert body["status"] == "diagnosed"
    assert [(h["from_status"], h["to_status"], h["actor"]) for h in body["history"]] == [
        ("hypothesis", "validated", "agent:orchestrator"),
        ("validated", "diagnosed", "agent:orchestrator"),
    ]
    assert body["history"][0]["reason"] == "probe confirmed"


def test_illegal_edges_and_unbacked_claims_are_refused(host_and_finding) -> None:
    _, host, fid = host_and_finding
    with pytest.raises(HostError) as skip:
        host.set_finding_status(fid, "hardened", actor="agent:orchestrator")
    assert skip.value.code is ErrorCode.CONFLICT_STATE
    host.record(fid, _validation(fid, "refuted"))
    with pytest.raises(HostError):  # a refuted check cannot back "validated"
        host.set_finding_status(fid, "validated", actor="agent:orchestrator")
    host.set_finding_status(fid, "refuted", actor="agent:orchestrator")
    host.set_finding_status(fid, "accepted_risk", actor="user:usr_reviewer1")  # human, any time
    with pytest.raises(HostError):
        host.set_finding_status("fnd_notmine000", "closed", actor="agent:orchestrator")
