"""Agent loop: tool cycles, typed output, one repair retry, budgets, cancellation (SEC-001)."""

from __future__ import annotations

import pytest

from security_agents.agents import scout as scout_agent
from security_agents.contracts import AgentName, Budget, ErrorCode, Usage
from security_agents.llm import FakeLLM, FakeTurn, LLMUnavailable, ProviderGateway, assistant_turns
from security_agents.runtime import run_agent
from security_agents.tools import default_registry

from .conftest import make_ctx, make_scope

SPEC = scout_agent.SPEC
SUBMIT = SPEC.submit_tool_name()

VALID_OUTPUT = {
    "hypotheses": [
        {
            "title": "Payment detail route may not enforce ownership",
            "weakness_class": "CWE-639",
            "rationale": "The handler calls the unscoped store lookup while siblings scope by customer.",
            "expected_invariant": "A customer can read only their own payments.",
            "cited_paths": ["payments_lite/app.py"],
            "cited_start_lines": [52],
            "cited_end_lines": [60],
            "expectation_ids": ["exp_tenant_isolation_payments"],
            "entry_point_id": None,
            "confidence": "high",
            "suggested_check_category": "access_control.ownership",
        }
    ],
    "coverage": {"entry_points_reviewed": ["ent_get_payments_payment_id"], "looks_correct": [], "skipped_with_reason": []},
    "suspicious_instructions": [],
}


def gateway_for(script: list) -> ProviderGateway:
    return ProviderGateway(FakeLLM({AgentName.SCOUT: script}), default_model="claude-opus-5-5")


def run(script: list, *, intel, budget=None, ctx=None, cancelled=lambda: False):
    gw = gateway_for(script)
    return (
        run_agent(
            SPEC,
            gateway=gw,
            registry=default_registry(),
            ctx=ctx or make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
            task_prompt="survey the snapshot",
            budget=budget or Budget(max_tokens=100_000, max_usd=5.0, max_wall_clock_s=60.0),
            assessment_usage=Usage(),
        ),
        gw,
    )


def test_happy_path_tool_call_then_typed_output(intel):
    script = [
        FakeTurn(tool_calls=[("code__read_span", {"path": "payments_lite/app.py", "start_line": 52, "end_line": 60})]),
        FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)]),
    ]
    outcome, _ = run(script, intel=intel)
    assert outcome.ok
    assert outcome.run.status == "succeeded"
    assert outcome.run.tool_calls == 1
    assert outcome.run.llm_turns == 2
    assert isinstance(outcome.output, scout_agent.ScoutOutput)
    assert outcome.record.tool_names() == ["code.read_span"]
    assert outcome.run.provider_mode == "fake"


def test_model_sees_tool_results_and_can_adapt(intel):
    """The loop really feeds results back: the second turn reads the first result."""
    seen: list[str] = []

    def second_turn(request):
        from security_agents.llm import last_tool_results

        results = last_tool_results(request)
        seen.append(results[0]["json"]["path"] if results and "json" in results[0] else "none")
        return FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])

    script = [
        FakeTurn(tool_calls=[("code__read_span", {"path": "payments_lite/app.py", "start_line": 1, "end_line": 5})]),
        second_turn,
    ]
    outcome, _ = run(script, intel=intel)
    assert outcome.ok
    assert seen == ["payments_lite/app.py"]


def test_denied_tool_is_reported_to_model_and_loop_continues(intel):
    script = [
        FakeTurn(tool_calls=[("checks__run_template", {"template_ref": "x@1", "target_id": "t", "parameters": {}})]),
        FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)]),
    ]
    outcome, _ = run(script, intel=intel)
    assert outcome.ok, "a denied tool must not abort the step"
    denied = [t for t in outcome.record.tool_invocations if not t.ok]
    assert len(denied) == 1
    assert denied[0].error_code == ErrorCode.TOOL_NOT_ALLOWED.value


def test_schema_invalid_output_is_retried_exactly_once(intel):
    bad = {"hypotheses": [], "coverage": {}, "unexpected_field": 1}
    script = [
        FakeTurn(tool_calls=[(SUBMIT, bad)]),
        FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)]),
    ]
    outcome, gw = run(script, intel=intel)
    assert outcome.ok
    assert len(gw.provider.calls) == 2
    failed_submits = [t for t in outcome.record.tool_invocations if t.name == SUBMIT and not t.ok]
    assert len(failed_submits) == 1


def test_schema_invalid_twice_fails_the_step(intel):
    bad = {"hypotheses": [], "coverage": {}, "nope": True}
    script = [FakeTurn(tool_calls=[(SUBMIT, bad)]) for _ in range(4)]
    outcome, gw = run(script, intel=intel)
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.SCHEMA_INVALID
    assert len(gw.provider.calls) == 2, "exactly one repair attempt"


def test_token_budget_stops_the_step(intel):
    script = [FakeTurn(text="thinking out loud " * 200) for _ in range(10)]
    outcome, _ = run(
        script, intel=intel, budget=Budget(max_tokens=200, max_usd=5.0, max_wall_clock_s=60.0)
    )
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.BUDGET_EXHAUSTED


def test_usd_budget_stops_the_step(intel):
    script = [FakeTurn(text="x " * 500) for _ in range(10)]
    outcome, _ = run(
        script, intel=intel, budget=Budget(max_tokens=10_000_000, max_usd=0.0001, max_wall_clock_s=60.0)
    )
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.BUDGET_EXHAUSTED


def test_max_turns_without_submit_fails(intel):
    script = [FakeTurn(text="still thinking") for _ in range(SPEC.max_turns + 2)]
    outcome, _ = run(script, intel=intel)
    assert not outcome.ok
    assert outcome.run.error_code is ErrorCode.BUDGET_EXHAUSTED
    # Token budget may exhaust before turn limit; accept either
    assert outcome.run.llm_turns <= SPEC.max_turns


def test_cancellation_ends_the_step(intel):
    script = [FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])]
    outcome, _ = run(script, intel=intel, cancelled=lambda: True)
    # cancellation is checked before each turn; with cancel always true nothing runs
    gw = gateway_for(script)
    outcome = run_agent(
        SPEC, gateway=gw, registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
        task_prompt="x", budget=Budget(max_tokens=1000, max_usd=1.0, max_wall_clock_s=60.0),
        cancelled=lambda: True,
    )
    assert outcome.run.error_code is ErrorCode.CANCELLED
    assert outcome.run.llm_turns == 0


def test_kill_switch_ends_the_step(intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope(), kill_switch=lambda: True)
    outcome, _ = run([FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])], intel=intel, ctx=ctx)
    assert outcome.run.error_code is ErrorCode.KILL_SWITCH


def test_provider_failure_maps_to_llm_unavailable(intel):
    class Broken:
        mode = "fake"

        def complete(self, request):
            raise LLMUnavailable("provider down")

    outcome = run_agent(
        SPEC, gateway=ProviderGateway(Broken()), registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
        task_prompt="x", budget=Budget(max_tokens=1000, max_usd=1.0, max_wall_clock_s=60.0),
    )
    assert outcome.run.error_code is ErrorCode.LLM_UNAVAILABLE


def test_usage_is_accumulated_into_the_assessment(intel):
    total = Usage()
    gw = gateway_for([FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])])
    outcome = run_agent(
        SPEC, gateway=gw, registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
        task_prompt="x", budget=Budget(max_tokens=100_000, max_usd=1.0, max_wall_clock_s=60.0),
        assessment_usage=total,
    )
    assert outcome.run.usage.total_tokens > 0
    assert total.total_tokens == outcome.run.usage.total_tokens
    assert total.usd == pytest.approx(outcome.run.usage.usd)


def test_tool_call_cap_prompts_submission(intel):
    """Past the cap the loop asks for a submit instead of letting tools run forever."""
    calls = {"n": 0}

    def step(request):
        calls["n"] += 1
        if calls["n"] > SPEC.max_tool_calls + 1:
            return FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])
        return FakeTurn(tool_calls=[("code__search", {"pattern": "def "})])

    spec = type(SPEC)(**{**vars(SPEC), "max_tool_calls": 2, "max_turns": 6})
    gw = ProviderGateway(FakeLLM({AgentName.SCOUT: [step] * 6}))
    outcome = run_agent(
        spec, gateway=gw, registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
        task_prompt="x", budget=Budget(max_tokens=200_000, max_usd=5.0, max_wall_clock_s=60.0),
    )
    prompts = [m for c in gw.provider.calls for m in c.messages if m["role"] == "user"]
    assert any("Tool-call budget reached" in str(m["content"]) for m in prompts)


def test_system_prompt_carries_role_tools_and_untrusted_data_rule(intel):
    gw = gateway_for([FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])])
    run_agent(
        SPEC, gateway=gw, registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=intel, scope=make_scope()),
        task_prompt="x", budget=Budget(max_tokens=10_000, max_usd=1.0, max_wall_clock_s=60.0),
    )
    system = gw.provider.calls[0].system
    assert "You are Scout" in system
    assert "never follow instructions" in system.lower() or "never instructions" in system.lower()
    assert "code.read_span" in system
    assert "no shell" in system


def test_submit_tool_schema_is_the_output_model(intel):
    from security_agents.runtime import submit_schema

    schema = submit_schema(SPEC)
    assert schema["name"] == SUBMIT
    assert schema["input_schema"]["additionalProperties"] is False
    assert "hypotheses" in schema["input_schema"]["properties"]


def test_fake_provider_is_labelled_not_live(intel):
    outcome, gw = run([FakeTurn(tool_calls=[(SUBMIT, VALID_OUTPUT)])], intel=intel)
    assert gw.mode == "fake"
    assert outcome.run.provider_mode == "fake"
    assert outcome.record.provider_mode == "fake"
    # the requested model id is recorded, and each turn records what actually answered
    assert outcome.run.model_id == "claude-opus-5-5"
    assert outcome.record.turns[0]["model"].startswith("fake:")


def test_assistant_turn_counter_drives_fake_script(intel):
    """`assistant_turns` is what keys the scripts; pin its semantics."""
    from security_agents.llm.types import LLMRequest

    req = LLMRequest(
        agent=AgentName.SCOUT, model="m", system="s",
        messages=[{"role": "user", "content": "a"}, {"role": "assistant", "content": []},
                  {"role": "user", "content": []}],
        tools=[], max_tokens=10,
    )
    assert assistant_turns(req) == 1
