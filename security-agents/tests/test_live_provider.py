"""Tier 3: opt-in LIVE provider smoke. Nothing here runs in CI by default.

Requires BOTH:
  * `RUN_LIVE_LLM_EVAL=1`
  * credentials the Anthropic SDK can resolve (ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN)

These tests make real Claude requests against the owned payments-lite fixture
and assert on observable live behaviour: each role issues its own request, the
model chooses tools itself, tool results come back into the conversation, and
the submitted artifact validates against that role's schema. Results are
written to `tests/artifacts/live/` so a run can be inspected afterwards.

A skipped run proves nothing. Never report live evidence from a skipped or
fake-provider run.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from security_agents.agents import probe as probe_agent
from security_agents.agents import scout as scout_agent
from security_agents.contracts import Budget, Usage
from security_agents.llm import live_gateway_from_env
from security_agents.llm.providers import RecordingProvider
from security_agents.runtime import run_agent
from security_agents.tools import CheckRunner, default_registry, recipe_from_snapshot

from .conftest import TARGET_ID, make_ctx, make_scope

LIVE = os.environ.get("RUN_LIVE_LLM_EVAL") == "1"
HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not LIVE, reason="set RUN_LIVE_LLM_EVAL=1 to run the live provider smoke"),
    pytest.mark.skipif(not HAS_KEY, reason="no Anthropic credentials in the environment"),
]

ARTIFACTS = Path(__file__).parent / "artifacts" / "live"


def _write_artifact(name: str, payload: dict) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ARTIFACTS / f"{stamp}-{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def live_gateway():
    return live_gateway_from_env()


def test_live_scout_uses_real_tools_and_returns_a_typed_artifact(live_gateway, intel):
    """Scout must investigate with its own tool calls, then submit a valid ScoutOutput."""
    recorded = ARTIFACTS / "recordings" / "scout.jsonl"
    gateway = live_gateway
    gateway.provider = RecordingProvider(gateway.provider, recorded)
    data = scout_agent.ScoutInput(
        assessment_id="asm_live",
        snapshot_id=intel.snapshot.snapshot_id,
        commit_sha=intel.snapshot.commit_sha,
        expectation_ids=[e.id for e in intel.expectations()],
        max_hypotheses=3,
        available_check_categories=["access_control.ownership", "input_validation.bounds"],
    )
    ctx = make_ctx(scout_agent.SPEC.name, intel=intel, scope=make_scope())
    outcome = run_agent(
        scout_agent.SPEC,
        gateway=gateway,
        registry=default_registry(),
        ctx=ctx,
        task_prompt=scout_agent.build_prompt(data, intel),
        budget=Budget(max_tokens=200_000, max_usd=3.0, max_wall_clock_s=420.0),
        assessment_usage=Usage(),
    )
    artifact = _write_artifact(
        "scout",
        {
            "provider_mode": outcome.run.provider_mode,
            "model_id": outcome.run.model_id,
            "turns": outcome.run.llm_turns,
            "tool_calls": [t.name for t in outcome.record.tool_invocations],
            "usage": outcome.run.usage.model_dump(mode="json"),
            "output": outcome.output.model_dump(mode="json") if outcome.output else None,
            "error": outcome.run.error_code.value if outcome.run.error_code else None,
            "transcript": outcome.record.to_json(),
        },
    )
    assert outcome.run.provider_mode == "live", "this test must not run on a fake provider"
    assert outcome.ok, f"live Scout step failed: {outcome.run.error_code} {outcome.run.error_detail}"
    assert outcome.run.llm_turns >= 2, "a single completion is not a tool-use loop"
    assert outcome.record.tool_invocations, "the model made no tool call"
    assert outcome.run.usage.input_tokens > 0 and outcome.run.usage.output_tokens > 0
    assert isinstance(outcome.output, scout_agent.ScoutOutput)
    hypotheses = scout_agent.to_hypotheses(outcome.output, data, intel)
    # Citations are validated against the snapshot, so surviving hypotheses are real.
    for h in hypotheses:
        assert h.cited_spans and intel.snapshot.exists(h.cited_spans[0].path)
    print(f"\nlive Scout artifact: {artifact}")


def test_live_probe_executes_a_real_check_and_reports_the_executed_outcome(
    live_gateway, intel, driver, library
):
    """Probe must pick a template itself and run it; the outcome comes from the run."""
    data = probe_agent.ProbeInput(
        assessment_id="asm_live",
        hypothesis_id="hyp_live",
        scope_id="scp_test",
        target_id=TARGET_ID,
        hypothesis_title="The payment-detail route may not enforce payment ownership",
        weakness_class="CWE-639",
        expected_invariant=(
            "A customer can read only payments they own; another customer's payment must be "
            "reported as not found. The detail handler resolves payments by id alone while its "
            "sibling routes scope the lookup to the authenticated customer."
        ),
        suggested_check_category="access_control.ownership",
        cited_paths=["payments_lite/app.py"],
        expectation_ids=["exp_tenant_isolation_payments"],
    )
    ctx = make_ctx(
        probe_agent.SPEC.name,
        intel=intel,
        scope=make_scope(),
        services={
            "check_runner": CheckRunner(
                driver=driver,
                library=library,
                workspace_provider=lambda _c: intel.snapshot.root,
                recipe_provider=recipe_from_snapshot(intel),
            )
        },
    )
    outcome = run_agent(
        probe_agent.SPEC,
        gateway=live_gateway,
        registry=default_registry(),
        ctx=ctx,
        task_prompt=probe_agent.build_prompt(data, intel),
        budget=Budget(max_tokens=120_000, max_usd=2.0, max_wall_clock_s=300.0),
        assessment_usage=Usage(),
    )
    check_runs = list(ctx.artifacts.get("check_runs") or [])
    validation = (
        probe_agent.to_validation_result(outcome.output, data, outcome.record, check_runs)
        if isinstance(outcome.output, probe_agent.ProbeOutput)
        else None
    )
    artifact = _write_artifact(
        "probe",
        {
            "provider_mode": outcome.run.provider_mode,
            "model_id": outcome.run.model_id,
            "tool_calls": [t.name for t in outcome.record.tool_invocations],
            "check_runs": check_runs,
            "validation": validation.model_dump(mode="json") if validation else None,
            "transcript": outcome.record.to_json(),
        },
    )
    assert outcome.run.provider_mode == "live"
    assert outcome.ok, f"live Probe step failed: {outcome.run.error_code} {outcome.run.error_detail}"
    assert "checks.run_template" in [t.name for t in outcome.record.tool_invocations]
    assert check_runs, "no check template was executed"
    assert check_runs[-1]["sandbox_run_id"]
    assert validation is not None
    assert validation.observations["outcome_source"] == "executed_check"
    assert validation.outcome.value == "confirmed", (
        f"the planted weakness should be confirmed by the executed check; got {validation.outcome.value}"
    )
    print(f"\nlive Probe artifact: {artifact}")


def test_live_roles_issue_separate_requests_with_distinct_prompts(live_gateway, intel):
    """Two different roles must reach the provider as two different conversations."""
    from security_agents.agents import trace as trace_agent
    from security_agents.llm.providers import FakeLLM  # noqa: F401 - imported to assert absence

    seen: list[tuple[str, str]] = []
    inner = live_gateway.provider

    class Watcher:
        mode = inner.mode

        def complete(self, request):
            seen.append((request.agent.value, request.system[:80]))
            return inner.complete(request)

    live_gateway.provider = Watcher()
    try:
        scout_data = scout_agent.ScoutInput(
            assessment_id="asm_live2",
            snapshot_id=intel.snapshot.snapshot_id,
            commit_sha=intel.snapshot.commit_sha,
            max_hypotheses=1,
            available_check_categories=["access_control.ownership"],
        )
        run_agent(
            scout_agent.SPEC,
            gateway=live_gateway,
            registry=default_registry(),
            ctx=make_ctx(scout_agent.SPEC.name, intel=intel, scope=make_scope()),
            task_prompt=scout_agent.build_prompt(scout_data, intel),
            budget=Budget(max_tokens=60_000, max_usd=1.0, max_wall_clock_s=180.0),
        )
        trace_data = trace_agent.TraceInput(
            assessment_id="asm_live2",
            finding_id="fnd_live",
            validation_result_id="val_live",
            hypothesis_title="payment detail ownership",
            weakness_class="CWE-639",
            confirmed_outcome="confirmed",
            affected_paths=["payments_lite/app.py"],
            affected_symbol="get_payment",
            expectation_ids=["exp_tenant_isolation_payments"],
        )
        run_agent(
            trace_agent.SPEC,
            gateway=live_gateway,
            registry=default_registry(),
            ctx=make_ctx(trace_agent.SPEC.name, intel=intel, scope=make_scope()),
            task_prompt=trace_agent.build_prompt(trace_data, intel),
            budget=Budget(max_tokens=60_000, max_usd=1.0, max_wall_clock_s=180.0),
        )
    finally:
        live_gateway.provider = inner

    roles = {role for role, _ in seen}
    systems = {system for _, system in seen}
    assert roles == {"scout", "trace"}, roles
    assert len(systems) == 2, "each role must send its own system instruction"
    _write_artifact("role_separation", {"requests": seen})


SEVEN_ROLES = ("scout", "probe", "trace", "diagnose", "patch", "verify", "fortify")


def test_live_seven_roles_end_to_end(tmp_path):
    from security_agents import cli

    cap = os.environ.get("LIVE_SEVEN_MAX_USD", "8")
    report_path = tmp_path / "live_report.json"
    code = cli.main(
        [
            "--target",
            str(Path(__file__).resolve().parents[2] / "examples" / "payments-lite"),
            "--mode",
            "live",
            "--i-have-authorization",
            "--auto-approve",
            "--max-hypotheses",
            "2",
            "--validate",
            "1",
            "--max-usd",
            cap,
            "--report",
            str(report_path),
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    per_role = {role: [run for run in report["runs"] if run["agent"] == role] for role in SEVEN_ROLES}
    summary = {
        "exit_code": code,
        "state": report["state"],
        "states": report["states"],
        "usage": report["usage"],
        "per_role": {
            role: [
                {
                    key: run[key]
                    for key in (
                        "status",
                        "provider_mode",
                        "model_id",
                        "llm_turns",
                        "tool_calls",
                        "tokens",
                        "usd",
                        "tool_trace",
                    )
                }
                for run in runs
            ]
            for role, runs in per_role.items()
        },
        "findings": report["findings"],
    }
    path = _write_artifact("seven_roles_end_to_end", summary)
    missing = [role for role, runs in per_role.items() if not runs]
    assert not missing, f"roles with no run: {missing}; trace written to {path}"
    for role, runs in per_role.items():
        live = [run for run in runs if run["provider_mode"] == "live" and run["llm_turns"] >= 1]
        assert live, f"{role} made no live model turn; trace written to {path}"
    assert report["state"] == "completed", f"state={report['state']}; trace written to {path}"
