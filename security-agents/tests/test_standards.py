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
    data = TraceInput(check_category="access_control.ownership",assessment_id="a",finding_id="f",
        validation_result_id="v",hypothesis_title="Owner-boundary failure",weakness_class="CWE-639",confirmed_outcome="confirmed")
    refs = _reviewed_attack(data, trace_output(), [EvidenceRef(artifact_id="sbx_executed",provenance="check_run")])
    assert refs and all(ref.review_status == "proposed" and ref.mapped_via == "check_template_rule" and ref.observation == "observed_in_sandbox" for ref in refs)
