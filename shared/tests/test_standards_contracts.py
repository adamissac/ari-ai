"""Invariants of the 0.7.0 standards and incident contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.incident import (
    GATED_TRANSITIONS,
    INCIDENT_TERMINAL,
    INCIDENT_TRANSITIONS,
    STATE_CSF,
    ClosureCriterion,
    IncidentApproval,
    IncidentState,
    can_transition_incident,
)
from shared.standards import (
    CVSSAssessment,
    CVSSMetricValue,
    DefensiveMapping,
    FindingStandards,
    StandardMapping,
)

T = datetime(2026, 10, 17, tzinfo=UTC)
SPAN = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app/routes.py",
    commit_sha="a" * 40,
    span=SourceSpan(start_line=1, end_line=2),
    provenance="test",
)
RUN = EvidenceRef(
    kind=EvidenceKind.sandbox_run, artifact_id="art_12345678", sha256="b" * 64, provenance="test"
)


def mapping(**kw: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        framework="attack",
        id="T1190",
        name="Exploit Public-Facing Application",
        catalog_version="20.0",
        mapped_via="check_template_rule",
        observation="hypothesis",
        rationale="r",
        confidence=0.5,
        evidence=[SPAN],
    )
    base.update(kw)
    return base


def test_mapping_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        StandardMapping.model_validate(mapping(evidence=[]))


def test_observed_in_sandbox_requires_executed_evidence() -> None:
    with pytest.raises(ValidationError, match="observed_in_sandbox"):
        StandardMapping.model_validate(mapping(observation="observed_in_sandbox"))
    StandardMapping.model_validate(mapping(observation="observed_in_sandbox", evidence=[RUN]))


def test_deprecated_ids_only_on_legacy_imports() -> None:
    with pytest.raises(ValidationError, match="legacy"):
        StandardMapping.model_validate(mapping(catalog_status="revoked"))
    StandardMapping.model_validate(mapping(catalog_status="revoked", legacy=True))


def test_accepted_mapping_names_reviewer() -> None:
    with pytest.raises(ValidationError, match="reviewer"):
        StandardMapping.model_validate(mapping(review_status="accepted"))


def test_tested_control_needs_test_evidence_and_simulation_stays_proposed() -> None:
    d3 = mapping(framework="d3fend", id="D3-AMED", name="Access Mediation")
    with pytest.raises(ValidationError, match="tested"):
        DefensiveMapping.model_validate({**d3, "control_status": "tested"})
    DefensiveMapping.model_validate({**d3, "control_status": "tested", "evidence": [RUN]})
    with pytest.raises(ValidationError, match="simulation"):
        DefensiveMapping.model_validate(
            {**d3, "control_status": "implemented", "simulation_derived": True}
        )
    with pytest.raises(ValidationError, match="D3FEND"):
        DefensiveMapping.model_validate(mapping())


def test_cvss_complete_iff_scored() -> None:
    common = dict(rationale="r", assessor="system:x", scoring_engine="e", assessed_at=T)
    with pytest.raises(ValidationError):
        CVSSAssessment.model_validate({**common, "complete": True})
    with pytest.raises(ValidationError):
        CVSSAssessment.model_validate({**common, "complete": False, "score": 5.0})
    with pytest.raises(ValidationError):
        CVSSAssessment.model_validate({**common, "complete": False})
    CVSSAssessment.model_validate({**common, "complete": False, "missing_metrics": ["AV"]})


def test_metric_from_evidence_must_cite_it() -> None:
    with pytest.raises(ValidationError):
        CVSSMetricValue(metric="AV", value="N", basis="evidence", rationale="r")
    CVSSMetricValue(metric="AV", value="N", basis="assumption", rationale="r")


def test_finding_standards_attack_list_only_attack() -> None:
    with pytest.raises(ValidationError):
        FindingStandards.model_validate(
            dict(
                attack=[mapping(framework="cwe", id="CWE-639", name="x")],
                classified_by="system",
                classified_at=T,
            )
        )


def test_incident_transition_table_is_closed_and_mapped() -> None:
    assert set(INCIDENT_TRANSITIONS) == set(IncidentState)
    assert set(STATE_CSF) == set(IncidentState)
    for state in INCIDENT_TERMINAL:
        assert INCIDENT_TRANSITIONS[state] == frozenset()
    assert not can_transition_incident(IncidentState.reported, IncidentState.containment)
    assert not can_transition_incident(IncidentState.closed, IncidentState.reported)
    assert set(GATED_TRANSITIONS) == {
        IncidentState.containment,
        IncidentState.eradication,
        IncidentState.recovery,
        IncidentState.closed,
    }


def test_approval_two_person_rule_and_closure_evidence() -> None:
    with pytest.raises(ValidationError, match="requester"):
        IncidentApproval(
            gate="containment",
            status="approved",
            action_summary="block route",
            requested_by="usr_aaaaaaaa",
            requested_at=T,
            decided_by="usr_aaaaaaaa",
            decided_at=T,
        )
    with pytest.raises(ValidationError, match="evidence"):
        ClosureCriterion(key="k", description="d", satisfied=True, satisfied_by="usr_aaaaaaaa")
