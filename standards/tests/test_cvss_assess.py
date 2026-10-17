"""Evidence -> CVSS assessment: complete only when evidence determines every base metric."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.standards import (
    CVSSAssessment,
    CVSSMetricBasis,
    CVSSMetricValue,
    FindingStandards,
    LegacyScore,
)
from standards import cvss4
from standards.cvss_assess import ASSESSOR, Fact, assess

T = datetime(2026, 10, 17, tzinfo=UTC)
SPAN = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app/routes.py",
    commit_sha="a" * 40,
    span=SourceSpan(start_line=10, end_line=14),
    provenance="test",
)
RUN = EvidenceRef(
    kind=EvidenceKind.sandbox_run, artifact_id="art_12345678", sha256="b" * 64, provenance="test"
)


def facts(**drop: bool) -> dict[str, Fact]:
    full = {
        "reachability": Fact("authenticated", [SPAN]),
        "check_outcome": Fact("confirmed", [RUN]),
        "attack_preconditions": Fact("none_recorded", [SPAN]),
        "privileges_required": Fact("low", [SPAN]),
        "check_interaction": Fact("direct_request", [RUN]),
        "check_category": Fact("access_control.ownership", [RUN]),
        "data_sensitivity": Fact("financial", [SPAN]),
        "subsequent_impact": Fact("not_exercised", [RUN]),
    }
    return {k: v for k, v in full.items() if not drop.get(k)}


def test_complete_evidence_yields_a_reference_score() -> None:
    a = assess(facts(), now=T)
    assert a.complete and a.missing_metrics == []
    assert a.vector and a.score == cvss4.score(a.vector).score
    assert a.severity == cvss4.score(a.vector).severity
    assert a.assessor == ASSESSOR and "FIRST cvss-v4-calculator@c5b0d409ae9f" in a.scoring_engine
    assert {m.metric for m in a.metrics} == set(cvss4.BASE_METRICS)
    evidence_based = [m for m in a.metrics if m.basis is CVSSMetricBasis.evidence]
    assert evidence_based and all(m.evidence for m in evidence_based)


def test_assumptions_are_listed_explicitly() -> None:
    a = assess(facts(), now=T)
    assumed = {m.metric for m in a.metrics if m.basis is CVSSMetricBasis.assumption}
    assert assumed and len(a.assumptions) == len(assumed)
    assert all(any(s.startswith(f"{m}:") for s in a.assumptions) for m in assumed)


@pytest.mark.parametrize("missing", ["reachability", "privileges_required", "data_sensitivity"])
def test_missing_fact_gives_incomplete_assessment_without_score(missing: str) -> None:
    a = assess(facts(**{missing: True}), now=T)
    assert not a.complete and a.score is None and a.vector is None and a.severity is None
    assert a.missing_metrics and "Incomplete" in a.rationale


def test_fact_without_a_reviewed_case_is_not_guessed() -> None:
    f = facts()
    f["reachability"] = Fact("maybe_internet", [SPAN])
    a = assess(f, now=T)
    assert not a.complete and a.missing_metrics == ["AV"]


def test_human_override_completes_an_assessment() -> None:
    override = CVSSMetricValue(
        metric="AV", value="N", basis=CVSSMetricBasis.human, rationale="owner: public route"
    )
    a = assess(facts(reachability=True), now=T, overrides={"AV": override})
    assert a.complete and "AV:N" in (a.vector or "")


def test_contract_forbids_scores_on_incomplete_assessments() -> None:
    a = assess(facts(reachability=True), now=T)
    with pytest.raises(ValidationError):
        CVSSAssessment.model_validate({**a.model_dump(), "score": 5.0})


def test_severity_priority_exploitation_and_legacy_scores_stay_separate() -> None:
    a = assess(facts(), now=T)
    legacy = LegacyScore(
        version="3.1",
        vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
        score=6.5,
        source="imported scanner report",
        imported_at=T,
    )
    fs = FindingStandards(
        cvss=a, legacy_scores=[legacy], classified_by="system:test", classified_at=T
    )
    dumped = FindingStandards.model_validate(fs.model_dump())
    assert dumped.legacy_scores[0].version == "3.1" and dumped.legacy_scores[0].score == 6.5
    assert dumped.cvss and dumped.cvss.version == "4.0"
    assert dumped.business_priority.value == "unset"
    assert dumped.exploit_status.value == "not_tested"
