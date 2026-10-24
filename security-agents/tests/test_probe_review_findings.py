from __future__ import annotations

import json

import pytest

from security_agents.agents import probe as probe_agent
from security_agents.agents import scout as scout_agent
from security_agents.checks.library import default_library
from security_agents.contracts import AgentName, ErrorCode, PlatformError, ScopeStatus, ValidationOutcome
from security_agents.llm import FakeTurn
from security_agents.runtime.loop import result_summary
from security_agents.standards.roe import build_roe
from security_agents.tools import CheckRunner, default_registry, recipe_from_snapshot, wire_name
from security_agents.workflow import AssessmentState

from . import fake_agents
from .conftest import TARGET_ID, make_ctx, make_scope
from .fake_agents import _last_json, _target_id
from .test_e2e_replay import assert_agent_order, build

OWNERSHIP = "access_control.ownership@1"


def _params(route: str) -> dict:
    return {"route_id": route, "owner_identity": "alice", "other_identity": "bob"}


def probe_running(routes: list[str], claimed: str) -> list:
    submit = probe_agent.SPEC.submit_tool_name()
    turns: list = [lambda _r: FakeTurn(tool_calls=[("checks__list_templates", {})])]
    for route in routes:
        turns.append(
            lambda request, route=route: FakeTurn(
                tool_calls=[
                    (
                        "checks__run_template",
                        {
                            "template_ref": OWNERSHIP,
                            "target_id": _target_id(request),
                            "parameters": _params(route),
                        },
                    )
                ]
            )
        )

    def finish(request) -> FakeTurn:
        last = _last_json(request)
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "outcome": claimed,
                        "check_template_ref": OWNERSHIP,
                        "sandbox_run_id": last.get("sandbox_run_id"),
                        "observations": ["scripted"],
                        "interpretation": "scripted",
                        "missing_capability": "",
                    },
                )
            ]
        )

    turns.append(finish)
    return turns


def _run_with_probe(intel, driver, library, tmp_path, routes, claimed):
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    scripts[AgentName.PROBE] = probe_running(routes, claimed)
    orch, _ = build(intel, driver, library, tmp_path, scripts=scripts)
    return orch.run()


def test_f1_a_later_check_on_a_protected_route_cannot_refute_the_hypothesis(intel, driver, library, tmp_path):
    res = _run_with_probe(intel, driver, library, tmp_path, ["payment_detail", "customer_detail"], "refuted")
    finding = next(f for f in res.findings if f.validation is not None)
    assert finding.validation.outcome is ValidationOutcome.CONFIRMED, finding.validation.observations
    assert finding.validation.parameters["route_id"] == "payment_detail"
    assert res.state is AssessmentState.COMPLETED
    assert_agent_order([r.agent.value for r in res.runs])


def test_f1_a_check_only_on_an_unrelated_route_is_inconclusive_not_refuted(intel, driver, library, tmp_path):
    res = _run_with_probe(intel, driver, library, tmp_path, ["customer_detail"], "refuted")
    finding = next(f for f in res.findings if f.validation is not None)
    assert finding.validation.outcome is ValidationOutcome.INCONCLUSIVE, finding.validation.observations
    assert "outside the hypothesis" in json.dumps(finding.validation.observations)


def _listing(intel, scope, roe=None):
    runner = CheckRunner(
        driver=None,
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=scope, services={"check_runner": runner})
    ctx.roe = roe
    return default_registry().invoke(ctx, wire_name("checks.list_templates"), {}).payload


def test_f2_recipe_values_need_an_active_scope_and_issued_roe(intel):
    scope = make_scope()
    roe = build_roe(scope, default_library().list_public())
    granted = _listing(intel, scope, roe)
    assert all("parameter_values" in t for t in granted["templates"])
    for denied in (
        _listing(intel, scope, None),
        _listing(intel, make_scope(status=ScopeStatus.REVOKED), roe),
    ):
        assert all("parameter_values" not in t for t in denied["templates"]), denied
        assert "parameter_values_withheld" in denied


def test_f3_bounded_summary_keeps_the_complete_discovery_index(intel):
    scope = make_scope()
    listing = _listing(intel, scope, build_roe(scope, default_library().list_public()))
    summary = json.dumps(result_summary(listing))
    for value in ("payment_detail", "customer_detail", "create_refund", "alice", "bob"):
        assert value in summary, summary


def test_f4_list_templates_accepts_a_legacy_category_alias(intel):
    scope = make_scope(categories=["authorization.ownership"])
    runner = CheckRunner(
        driver=None,
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=scope, services={"check_runner": runner})
    listing = (
        default_registry()
        .invoke(ctx, wire_name("checks.list_templates"), {"category": "authorization.ownership"})
        .payload
    )
    assert [t["ref"] for t in listing["templates"]] == [OWNERSHIP]


def test_f4_scout_is_told_the_canonical_categories_of_an_aliased_scope(intel, driver, library, tmp_path):
    from .conftest import live_scope

    seen: list[str] = []
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    first = scripts[AgentName.SCOUT][0]

    def recording(request):
        seen.append(json.dumps(request.messages, default=str))
        return first(request)

    scripts[AgentName.SCOUT] = [recording, *scripts[AgentName.SCOUT][1:]]
    orch, _ = build(intel, driver, library, tmp_path, scripts=scripts)
    orch.config.scope = live_scope(categories=["authorization.ownership", "input.bounds"])
    res = orch.run()
    assert "access_control.ownership" in seen[0] and "input_validation.bounds" in seen[0]
    assert res.state is AssessmentState.COMPLETED


def test_f4_scout_keeps_a_hypothesis_named_with_an_alias(intel):
    data = scout_agent.ScoutInput(
        assessment_id="asm",
        snapshot_id="snp_test",
        commit_sha="sha",
        available_check_categories=["access_control.ownership"],
        max_hypotheses=5,
    )
    item = scout_agent.HypothesisOut(
        title="Payment detail may not enforce ownership",
        weakness_class="CWE-639",
        rationale="Handler reads a payment by id without an owner check.",
        expected_invariant="Owner only",
        cited_paths=["payments_lite/app.py"],
        cited_start_lines=[131],
        cited_end_lines=[141],
        confidence="high",
        suggested_check_category="authorization.ownership",
    )
    out = scout_agent.ScoutOutput.model_construct(hypotheses=[item], coverage=None)
    kept = scout_agent.to_hypotheses(out, data, intel)
    assert [h.suggested_check_category for h in kept] == ["access_control.ownership"]


def test_f5_recipe_discovery_is_bound_to_a_scoped_target(intel):
    provider = recipe_from_snapshot(intel)
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope())
    assert provider(ctx, TARGET_ID)["app_factory"]
    with pytest.raises(PlatformError) as error:
        provider(ctx, "tgt_someone_else")
    assert error.value.code is ErrorCode.SCOPE_DENIED
