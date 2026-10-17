"""Offline producer classifications preserve catalog provenance and evidence."""

import pytest
from pydantic import ValidationError
from shared.standards import CVSSAssessment

from security_agents.agents.probe import ProbeInput
from security_agents.agents.scout import HypothesisOut
from security_agents.agents.trace import TraceOutput, _cvss
from security_agents.contracts import EvidenceRef, ValidationResult, export

METRICS = dict(AV="N", AC="L", AT="N", PR="L", UI="N", VC="H", VI="N", VA="N", SC="N", SI="N", SA="N")


def trace_output(**kwargs):
    return TraceOutput(
        steps=[dict(description="Protected data is reachable", verified=False)],
        impact_summary="Cross-owner access",
        reachability="authenticated",
        privileges_required="low",
        data_sensitivity="financial",
        severity_rationale="Executed owner-boundary check",
        **kwargs,
    )


def test_unknown_cwe_rejected_before_probe():
    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        ProbeInput(
            assessment_id="a",
            hypothesis_id="h",
            scope_id="s",
            target_id="t",
            hypothesis_title="Finding",
            weakness_class="CWE-99999",
            expected_invariant="Owner only",
            suggested_check_category="authorization",
        )


def test_unknown_model_cwe_rejected():
    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        HypothesisOut(
            title="Finding",
            weakness_class="CWE-99999",
            rationale="Evidence",
            expected_invariant="Owner only",
            cited_paths=["app.py"],
            cited_start_lines=[1],
            cited_end_lines=[2],
            confidence="high",
            suggested_check_category="authorization",
        )


def test_coarse_catalog_chain_is_not_automatically_a_mapping():
    assert export.attack_refs("CWE-639", evidence=[], confidence=0.5) == []


def test_factors_alone_do_not_create_cvss():
    assert _cvss(trace_output(), None) is None


def test_explicit_evidenced_cvss_is_scored_and_exported():
    run = "sbx_evidenced"
    output = trace_output(cvss_metrics=METRICS, cvss_metric_artifacts=dict.fromkeys(METRICS, run))
    validation = ValidationResult(
        hypothesis_id="hyp_test",
        outcome="confirmed",
        check_template_id="owner",
        check_template_version="1",
        sandbox_run_id=run,
        evidence=[EvidenceRef(artifact_id=run, provenance="check_run")],
    )
    assessment = _cvss(output, validation)
    assert assessment is not None
    assert len(assessment.assumptions) == 11
    assert all(metric.basis == "assumption" for metric in assessment.metrics)
    assert assessment.vector.startswith("CVSS:4.0/")
    assert {m.metric for m in assessment.metrics} == set(METRICS)
    payload = assessment.model_dump()
    payload["score"] = 0 if assessment.score else 10
    with pytest.raises(ValidationError, match="score"):
        CVSSAssessment.model_validate(payload)
    output.cvss_metric_artifacts["AV"] = "invented-run"
    assert _cvss(output, validation) is None


def test_reviewed_check_rule_attaches_proposed_sandbox_mapping():
    from security_agents.agents.trace import TraceInput, _reviewed_attack

    data = TraceInput(
        check_category="access_control.ownership",
        assessment_id="a",
        finding_id="f",
        validation_result_id="v",
        hypothesis_title="Owner-boundary failure",
        weakness_class="CWE-639",
        confirmed_outcome="confirmed",
    )
    refs = _reviewed_attack(
        data, trace_output(), [EvidenceRef(artifact_id="sbx_executed", provenance="check_run")]
    )
    assert refs and all(
        ref.review_status == "proposed"
        and ref.mapped_via == "check_template_rule"
        and ref.observation == "observed_in_sandbox"
        for ref in refs
    )


def test_scout_rejects_mapping_prohibited_cwe():
    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        HypothesisOut(
            title="Finding",
            weakness_class="CWE-840",
            rationale="Evidence",
            expected_invariant="Owner only",
            cited_paths=["app.py"],
            cited_start_lines=[1],
            cited_end_lines=[2],
            confidence="high",
            suggested_check_category="access_control.ownership",
        )


def test_finding_standards_derive_cvss_from_recorded_facts_not_llm_metrics():
    from datetime import UTC, datetime

    from security_agents.agents.scout import Hypothesis
    from security_agents.contracts import (
        AttackPath,
        PathStep,
        SeverityAssessment,
        SeverityFactors,
        SeverityLevel,
        SourceSpan,
        ValidationOutcome,
        ValidationResult,
    )
    from security_agents.standards_bridge import CLASSIFIER, finding_standards
    from security_agents.workflow import FindingRecord

    span = EvidenceRef(
        path="payments_lite/app.py",
        sha="a" * 40,
        span=SourceSpan(start_line=10, end_line=14),
        provenance="code",
    )
    run = EvidenceRef(artifact_id="sbx_probe1", provenance="check_run")
    finding = FindingRecord(
        finding_id="fnd_test01",
        hypothesis=Hypothesis(
            weakness_class="CWE-639",
            title="payment detail ownership",
            rationale="missing owner check",
            cited_spans=[span],
            confidence="high",
            suggested_check_category="access_control.ownership",
        ),
        validation=ValidationResult(
            hypothesis_id="hyp_test",
            outcome=ValidationOutcome.CONFIRMED,
            check_template_id="access_control.ownership",
            check_template_version="1",
            sandbox_run_id="sbx_probe1",
            evidence=[run],
        ),
        attack_path=AttackPath(
            finding_id="fnd_test01",
            steps=[PathStep(order=1, description="GET payment", verified=True, evidence=[run])],
            impact_summary="cross-owner read",
        ),
        severity=SeverityAssessment(
            level=SeverityLevel.HIGH,
            factors=SeverityFactors(
                reachability="authenticated",
                privileges_required="low",
                data_sensitivity="financial",
                verified_path=True,
            ),
            rationale="executed ownership check",
        ),
    )
    std = finding_standards(finding, now=datetime(2026, 10, 17, tzinfo=UTC))
    assert std.cwe and std.cwe.id == "CWE-639"
    assert [m.id for m in std.attack] == ["T1190"]
    assert std.cvss and std.cvss.complete and std.cvss.score is not None
    assert std.classified_by == CLASSIFIER
    assert "provisional" not in std.cvss.assessor
    assert "FIRST cvss-v4-calculator" in std.cvss.scoring_engine
    finding.severity = None
    incomplete = finding_standards(finding, now=datetime(2026, 10, 17, tzinfo=UTC))
    assert incomplete.cvss and not incomplete.cvss.complete and incomplete.cvss.score is None


def test_system_prompts_hold_no_secret_shaped_values():
    import re

    from security_agents.agents import ALL_SPECS

    shapes = [
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ]
    for name, spec in ALL_SPECS.items():
        for pat in shapes:
            assert not pat.search(spec.system_prompt), (name.value, pat.pattern)
