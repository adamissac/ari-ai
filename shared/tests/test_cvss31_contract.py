from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import SeverityAssessment, SeverityFactors
from shared.standards import CVSS31Assessment, CVSS31MetricEvidence

SPAN = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app/routes.py",
    commit_sha="a" * 40,
    span=SourceSpan(start_line=1, end_line=2),
    provenance="test",
)
VECTOR = "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
KIND = "CVSS v3.1 base score only (severity, not risk)"


def metrics(vector: str = VECTOR) -> list[CVSS31MetricEvidence]:
    pairs = [part.split(":") for part in vector.split("/")[1:]]
    return [
        CVSS31MetricEvidence(
            metric=name, value=value, status="cited", evidence=[SPAN], rationale="r"
        )
        if name in ("AV", "C")
        else CVSS31MetricEvidence(metric=name, value=value, status="unverified")
        for name, value in pairs
    ]


def assessment(**overrides) -> CVSS31Assessment:
    data = dict(
        vector=VECTOR,
        base_score=6.5,
        rating="medium",
        score_kind=KIND,
        metric_evidence=metrics(),
        assessor="system:standards.cvss31",
    )
    data.update(overrides)
    return CVSS31Assessment(**data)


def test_valid_assessment_round_trips_on_severity():
    severity = SeverityAssessment(
        level="medium",
        factors=SeverityFactors(
            reachability="authenticated",
            privileges_required="low",
            data_sensitivity="financial",
            verified_path=True,
        ),
        rationale="r",
        cvss_v31=assessment(),
    )
    again = SeverityAssessment.model_validate_json(severity.model_dump_json())
    assert again.cvss_v31 is not None and again.cvss_v31.base_score == 6.5


@pytest.mark.parametrize(
    "overrides",
    [
        {"base_score": 9.8},
        {"rating": "high"},
        {"score_kind": "CVSS v3.1 risk score"},
        {"vector": "CVSS:3.1/AC:L/AV:N/PR:L/UI:N/S:U/C:H/I:N/A:N"},
        {"vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:X/I:N/A:N"},
        {"metric_evidence": metrics("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N")},
        {"metric_evidence": metrics()[:7] + [metrics()[0]]},
    ],
)
def test_model_supplied_or_inconsistent_scores_are_rejected(overrides):
    with pytest.raises(ValidationError):
        assessment(**overrides)


def test_cited_metric_needs_evidence_and_unverified_has_none():
    with pytest.raises(ValidationError):
        CVSS31MetricEvidence(metric="AV", value="N", status="cited")
    with pytest.raises(ValidationError):
        CVSS31MetricEvidence(metric="AV", value="N", status="unverified", evidence=[SPAN])
