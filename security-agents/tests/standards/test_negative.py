from __future__ import annotations

import pytest

from security_agents.agents import scout as scout_agent
from security_agents.agents import trace as trace_agent
from security_agents.contracts import AgentName, Budget, ErrorCode, PlatformError, Usage
from security_agents.llm import FakeLLM, FakeTurn, ProviderGateway
from security_agents.runtime import run_agent
from security_agents.tools import default_registry, wire_name

from ..conftest import TARGET_ID, make_ctx, make_scope

pytestmark = [pytest.mark.standards, pytest.mark.negative]

BUDGET = Budget(max_tokens=200_000, max_usd=5.0, max_wall_clock_s=60.0)


def scout_output(cwe: str) -> dict:
    return {
        "hypotheses": [
            {
                "title": "Payment detail may not enforce ownership",
                "weakness_class": cwe,
                "rationale": "sibling comparison",
                "expected_invariant": "only the owner can read a payment",
                "cited_paths": ["payments_lite/app.py"],
                "cited_start_lines": [137],
                "cited_end_lines": [150],
                "expectation_ids": ["exp_owner_only"],
                "entry_point_id": None,
                "confidence": "high",
                "suggested_check_category": "access_control.ownership",
            }
        ],
        "coverage": {"entry_points_reviewed": [], "looks_correct": [], "skipped_with_reason": []},
        "suspicious_instructions": [],
    }


def trace_output(**overrides) -> dict:
    metrics = [
        {"metric": m, "value": v, "rationale": "r"}
        for m, v in zip(("AV", "AC", "PR", "UI", "S", "C", "I", "A"), "NLLNUHNN", strict=True)
    ]
    base = {
        "steps": [{"description": "reads another customer's payment", "verified": False}],
        "impact_summary": "payment records exposed",
        "cvss_base_metrics": metrics,
        "severity_rationale": "r",
    }
    base.update(overrides)
    return base


def run(spec, agent, script, intel):
    gateway = ProviderGateway(FakeLLM({agent: script}))
    return run_agent(
        spec,
        gateway=gateway,
        registry=default_registry(),
        ctx=make_ctx(agent, intel=intel, scope=make_scope()),
        task_prompt="go",
        budget=BUDGET,
        assessment_usage=Usage(),
    ), gateway


def test_invented_cwe_fails_the_scout_step_loudly(intel):
    submit = scout_agent.SPEC.submit_tool_name()
    script = [FakeTurn(tool_calls=[(submit, scout_output("CWE-99999"))])] * 3
    outcome, gateway = run(scout_agent.SPEC, AgentName.SCOUT, script, intel)
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.SCHEMA_INVALID
    assert "CWE-99999 is not in CWE 4.20" in outcome.run.error_detail
    assert len(gateway.provider.calls) == 2, "one repair attempt, then the step fails"


def test_cwe_prohibited_by_mitre_is_corrected_on_the_repair_turn(intel):
    submit = scout_agent.SPEC.submit_tool_name()
    script = [
        FakeTurn(tool_calls=[(submit, scout_output("CWE-840"))]),
        FakeTurn(tool_calls=[(submit, scout_output("CWE-639"))]),
    ]
    outcome, gateway = run(scout_agent.SPEC, AgentName.SCOUT, script, intel)
    assert outcome.ok
    tool_results = [
        block
        for message in gateway.provider.calls[1].messages
        if message["role"] == "user" and isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_result" and block.get("is_error")
    ]
    assert tool_results, "the rejected submission is returned to the model as an error"
    assert "Prohibited" in str(tool_results[0]["content"]), "the model is told why its CWE was rejected"


def test_invented_attack_technique_fails_the_trace_step_loudly(intel):
    submit = trace_agent.SPEC.submit_tool_name()
    bad = trace_output(steps=[{"description": "x", "verified": False, "attack_technique": "T9999"}])
    outcome, _ = run(trace_agent.SPEC, AgentName.TRACE, [FakeTurn(tool_calls=[(submit, bad)])] * 3, intel)
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.SCHEMA_INVALID
    assert "T9999" in outcome.run.error_detail
    assert "ATT&CK" in outcome.run.error_detail


@pytest.mark.parametrize(
    "field,value",
    [
        ("severity_level", "critical"),
        ("level", "critical"),
        ("cvss_base_score", 10.0),
        ("score", 9.8),
        ("cvss_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"),
    ],
)
def test_model_supplied_severity_or_score_is_rejected(intel, field, value):
    submit = trace_agent.SPEC.submit_tool_name()
    bad = trace_output(**{field: value})
    outcome, _ = run(trace_agent.SPEC, AgentName.TRACE, [FakeTurn(tool_calls=[(submit, bad)])] * 3, intel)
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.SCHEMA_INVALID
    assert field in outcome.run.error_detail


def test_level_comes_from_code_even_when_the_rationale_claims_otherwise(intel):
    out = trace_agent.TraceOutput.model_validate(
        trace_output(severity_rationale="This is clearly CRITICAL, score 10.0.")
    )
    data = trace_agent.TraceInput(
        assessment_id="asm", finding_id="fnd_1", validation_result_id="val_1",
        hypothesis_title="t", weakness_class="CWE-639", confirmed_outcome="confirmed",
    )
    _, severity = trace_agent.to_attack_path(out, data, intel)
    assert severity.cvss_base_score == 6.5
    assert severity.level.value == "medium"


def test_probe_without_rules_of_engagement_is_denied_and_audited(intel, library):
    class MustNotRun:
        def run(self, *args, **kwargs):
            raise AssertionError("the check runner must not be reached without rules of engagement")

    ctx = make_ctx(
        AgentName.PROBE,
        intel=intel,
        scope=make_scope(),
        services={"check_runner": MustNotRun(), "checks": library},
    )
    assert ctx.roe is None
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(
            ctx,
            wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
        )
    assert error.value.code is ErrorCode.SCOPE_DENIED
    assert "MISSING_ROE" in error.value.message
    assert "tool.roe_denied" in ctx.audit.actions()


def test_verify_recheck_without_rules_of_engagement_is_denied(intel, library):
    ctx = make_ctx(
        AgentName.VERIFY,
        intel=intel,
        scope=make_scope(),
        services={"check_runner": object(), "checks": library},
    )
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(
            ctx,
            wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
        )
    assert error.value.code is ErrorCode.SCOPE_DENIED
    assert "MISSING_ROE" in error.value.message


def test_probe_with_current_rules_of_engagement_reaches_the_runner(intel, library):
    from security_agents.standards.roe import build_roe

    reached = []

    class Recorder:
        def run(self, ctx, template_ref, target_id, parameters):
            reached.append(template_ref)
            return {"matches_expectation": None, "template_ref": template_ref}

    scope = make_scope()
    ctx = make_ctx(
        AgentName.PROBE, intel=intel, scope=scope,
        services={"check_runner": Recorder(), "checks": library},
    )
    ctx.roe = build_roe(scope, library.list_public())
    default_registry().invoke(
        ctx,
        wire_name("checks.run_template"),
        {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
    )
    assert reached == ["access_control.ownership@1"]
