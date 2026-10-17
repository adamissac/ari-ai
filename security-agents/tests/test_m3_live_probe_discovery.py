from __future__ import annotations

from security_agents.agents import probe as probe_agent
from security_agents.contracts import ValidationOutcome
from security_agents.llm import FakeTurn
from security_agents.workflow import AssessmentState

from . import fake_agents
from .fake_agents import _last_json, _target_id
from .test_e2e_replay import EXPECTED_AGENT_ORDER, build

OWNERSHIP = "access_control.ownership"


def discovering_probe_script() -> list:
    submit = probe_agent.SPEC.submit_tool_name()
    state: dict = {}

    def turn0(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("checks__list_templates", {"category": OWNERSHIP})])

    def turn1(request) -> FakeTurn:
        listing = _last_json(request)
        template = next(t for t in listing["templates"] if t["category"] == OWNERSHIP)
        values = template.get("parameter_values") or {}
        routes = [
            r["id"]
            for r in values.get("route_id", [])
            if r.get("method") == "GET" and r.get("path_template") == "/payments/{payment_id}"
        ]
        identities = values.get("owner_identity") or []
        parameters = {
            "route_id": routes[0] if routes else "GET /payments/{payment_id}",
            "owner_identity": identities[0] if identities else "cus_alice",
            "other_identity": identities[1] if len(identities) > 1 else "cus_bob",
        }
        state["parameters"] = parameters
        return FakeTurn(
            tool_calls=[
                (
                    "checks__run_template",
                    {
                        "template_ref": template["ref"],
                        "target_id": _target_id(request),
                        "parameters": parameters,
                    },
                )
            ]
        )

    def turn2(request) -> FakeTurn:
        result = _last_json(request)
        matches = result.get("matches_expectation")
        outcome = "confirmed" if matches is False else "refuted" if matches is True else "inconclusive"
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "outcome": outcome,
                        "check_template_ref": result.get("template_ref"),
                        "sandbox_run_id": result.get("sandbox_run_id"),
                        "observations": [f"matches_expectation={matches}", f"error={result.get('error')}"],
                        "interpretation": "Outcome taken from the executed check.",
                        "missing_capability": "" if matches is not None else str(result.get("detail") or ""),
                    },
                )
            ]
        )

    return [turn0, turn1, turn2]


def test_a_probe_that_only_uses_tool_output_reaches_all_seven_roles(intel, driver, library, tmp_path):
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    scripts[probe_agent.SPEC.name] = discovering_probe_script()
    orch, _ = build(intel, driver, library, tmp_path, scripts=scripts)
    res = orch.run()
    finding = next(f for f in res.findings if f.validation is not None)
    assert finding.validation.outcome is ValidationOutcome.CONFIRMED, finding.validation.observations
    assert finding.validation.parameters["route_id"] == "payment_detail"
    assert res.state is AssessmentState.COMPLETED, res.error_detail
    assert [r.agent.value for r in res.runs] == EXPECTED_AGENT_ORDER


def _probe_ctx(intel, scope):
    from security_agents.checks.library import default_library
    from security_agents.tools import CheckRunner, recipe_from_snapshot

    from .conftest import make_ctx

    runner = CheckRunner(
        driver=None,
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    from security_agents.contracts import AgentName

    return make_ctx(AgentName.PROBE, intel=intel, scope=scope, services={"check_runner": runner})


def test_listing_exposes_recipe_values_but_never_credentials(intel):
    import json

    from security_agents.tools import default_registry, wire_name

    from .conftest import make_scope

    result = default_registry().invoke(
        _probe_ctx(intel, make_scope()), wire_name("checks.list_templates"), {}
    )
    listing = result.payload
    ownership = next(t for t in listing["templates"] if t["category"] == OWNERSHIP)
    routes = {r["id"] for r in ownership["parameter_values"]["route_id"]}
    assert {"payment_detail", "customer_detail"} <= routes
    assert "create_refund" not in routes and "payment_list" not in routes
    assert ownership["parameter_values"]["owner_identity"] == ["alice", "bob"]
    bounds = next(t for t in listing["templates"] if t["category"] == "input_validation.bounds")
    assert [r["id"] for r in bounds["parameter_values"]["route_id"]] == ["create_refund"]
    text = json.dumps(listing)
    assert "fixture-token" not in text and "auth_header" not in text and "Bearer" not in text


def test_an_unknown_route_error_names_the_valid_ids(intel):
    import pytest

    from security_agents.checks.library import default_library
    from security_agents.contracts import PlatformError
    from security_agents.tools import recipe_from_snapshot

    recipe = recipe_from_snapshot(intel)(None, "tgt_payments_lite")
    with pytest.raises(PlatformError) as error:
        default_library().render(
            "access_control.ownership@1",
            recipe,
            {"route_id": "GET /payments/{payment_id}", "owner_identity": "alice", "other_identity": "bob"},
        )
    assert "payment_detail" in error.value.message and "customer_detail" in error.value.message


def test_rules_of_engagement_honour_check_category_aliases_without_widening_scope(intel):
    from security_agents.checks.library import default_library
    from security_agents.standards.roe import build_roe

    from .conftest import make_scope

    templates = default_library().list_public()
    aliased = build_roe(make_scope(categories=["authorization.ownership"]), templates)
    assert aliased.permitted_check_templates == ["access_control.ownership@1"]
    both = build_roe(make_scope(categories=["authorization.ownership", "input.bounds"]), templates)
    assert both.permitted_check_templates == ["access_control.ownership@1", "input_validation.bounds@1"]


def test_aliased_scope_lets_probe_reach_the_runner_only_through_issued_roe(intel):
    import pytest

    from security_agents.checks.library import default_library
    from security_agents.contracts import ErrorCode, PlatformError
    from security_agents.standards.roe import build_roe
    from security_agents.tools import default_registry, wire_name

    from .conftest import TARGET_ID, make_scope

    reached = []

    class Recorder:
        recipe_provider = None

        def run(self, ctx, template_ref, target_id, parameters):
            reached.append(template_ref)
            return {"matches_expectation": None, "template_ref": template_ref}

    scope = make_scope(categories=["authorization.ownership"])
    ctx = _probe_ctx(intel, scope)
    ctx.services["check_runner"] = Recorder()
    args = {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}}
    with pytest.raises(PlatformError) as missing:
        default_registry().invoke(ctx, wire_name("checks.run_template"), args)
    assert missing.value.code is ErrorCode.SCOPE_DENIED and reached == []
    ctx.roe = build_roe(scope, default_library().list_public())
    default_registry().invoke(ctx, wire_name("checks.run_template"), args)
    assert reached == ["access_control.ownership@1"]
    with pytest.raises(PlatformError) as outside:
        default_registry().invoke(
            ctx, wire_name("checks.run_template"), {**args, "template_ref": "input_validation.bounds@1"}
        )
    assert outside.value.code is ErrorCode.SCOPE_DENIED
