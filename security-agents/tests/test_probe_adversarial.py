from __future__ import annotations

import json

import pytest

from security_agents.agents import probe as probe_agent
from security_agents.checks.library import default_library
from security_agents.contracts import AgentName, ErrorCode, PlatformError, ScopeStatus, ValidationOutcome
from security_agents.llm import FakeTurn
from security_agents.standards.roe import build_roe
from security_agents.tools import CheckRunner, default_registry, recipe_from_snapshot, wire_name
from security_agents.workflow import AssessmentState

from . import fake_agents
from .conftest import TARGET_ID, make_ctx, make_scope
from .fake_agents import _last_json, _target_id
from .test_e2e_replay import EXPECTED_AGENT_ORDER, build
from .test_host_adapter import host_and_orchestrator  # noqa: F401

OWNERSHIP = "access_control.ownership@1"
BOUNDS = "input_validation.bounds@1"
PAYMENT = "GET /payments/{payment_id}"
SECRET_SHAPES = ("fixture-token", "Bearer ", "auth_header")


def run(route: str, matches, method: str = "GET", path: str | None = None, **kw) -> dict:
    paths = {"payment_detail": "/payments/{payment_id}", "customer_detail": "/customers/{customer_id}"}
    return {
        "sandbox_run_id": f"sbx_{route}_{matches}",
        "template_ref": OWNERSHIP,
        "template_id": "access_control.ownership",
        "template_version": "1",
        "parameters": {"route_id": route},
        "route": {"id": route, "method": method, "path_template": path or paths.get(route)},
        "matches_expectation": matches,
        **kw,
    }


def reconcile(runs, subject=(PAYMENT,), claimed="refuted"):
    out = probe_agent.ProbeOutput.model_construct(
        outcome=claimed, observations=[], interpretation="", missing_capability=""
    )
    data = probe_agent.ProbeInput.model_construct(
        hypothesis_id="hyp_adversarial01", subject_routes=list(subject)
    )
    return probe_agent.to_validation_result(out, data, None, runs)


@pytest.mark.parametrize(
    ("runs", "subject", "expected", "route"),
    [
        (
            [run("customer_detail", True), run("payment_detail", False)],
            (PAYMENT,),
            "confirmed",
            "payment_detail",
        ),
        (
            [run("payment_detail", False), run("customer_detail", True)],
            (PAYMENT,),
            "confirmed",
            "payment_detail",
        ),
        (
            [run("payment_detail", None), run("customer_detail", True)],
            (PAYMENT,),
            "inconclusive",
            "payment_detail",
        ),
        ([run("customer_detail", True)], (PAYMENT,), "inconclusive", None),
        ([run("customer_detail", False)], (PAYMENT,), "inconclusive", None),
        ([run("payment_detail", True)], (PAYMENT,), "refuted", "payment_detail"),
        (
            [run("payment_detail", True), run("payment_detail", False)],
            (PAYMENT,),
            "confirmed",
            "payment_detail",
        ),
        (
            [run("payment_detail", False), {**run("customer_detail", True), "error": "SCOPE_DENIED"}],
            (PAYMENT,),
            "confirmed",
            "payment_detail",
        ),
        ([run("payment_detail", False), run("customer_detail", True)], (), "inconclusive", "customer_detail"),
        ([run("payment_detail", False)], (), "confirmed", "payment_detail"),
        ([run("customer_detail", True)], (), "refuted", "customer_detail"),
    ],
)
def test_reconciliation_matrix(runs, subject, expected, route):
    result = reconcile(runs, subject)
    assert result.outcome.value == expected, result.observations
    assert (result.parameters or {}).get("route_id") == route


def test_a_check_on_another_route_never_becomes_the_confirmation_evidence():
    result = reconcile([run("customer_detail", False)])
    assert result.outcome is ValidationOutcome.INCONCLUSIVE
    assert result.sandbox_run_id is None and result.evidence == []
    assert result.observations["routes_outside_subject"] == ["GET /customers/{customer_id}"]


def protected_first_then_retry() -> list:
    submit = probe_agent.SPEC.submit_tool_name()

    def check(route):
        return lambda request: FakeTurn(
            tool_calls=[
                (
                    "checks__run_template",
                    {
                        "template_ref": OWNERSHIP,
                        "target_id": _target_id(request),
                        "parameters": {"route_id": route, "owner_identity": "alice", "other_identity": "bob"},
                    },
                )
            ]
        )

    def retry_if_told(request):
        prompt = json.dumps(request.messages, default=str)
        assert "Routes handled by the cited code: GET /payments/{payment_id}" in prompt
        assert _last_json(request).get("matches_expectation") is True
        return check("payment_detail")(request)

    def finish(request):
        last = _last_json(request)
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "outcome": "refuted",
                        "check_template_ref": OWNERSHIP,
                        "sandbox_run_id": last.get("sandbox_run_id"),
                        "observations": ["scripted"],
                        "interpretation": "scripted",
                        "missing_capability": "",
                    },
                )
            ]
        )

    return [check("customer_detail"), retry_if_told, finish]


def test_protected_route_first_then_retry_on_the_subject_route_reaches_seven_roles(
    intel, driver, library, tmp_path
):
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    scripts[AgentName.PROBE] = protected_first_then_retry()
    orch, _ = build(intel, driver, library, tmp_path, scripts=scripts)
    res = orch.run()
    finding = next(f for f in res.findings if f.validation is not None)
    assert finding.validation.outcome is ValidationOutcome.CONFIRMED
    assert finding.validation.parameters["route_id"] == "payment_detail"
    assert finding.validation.observations["disagreement"].startswith("agent claimed refuted")
    assert (
        res.state is AssessmentState.COMPLETED and [r.agent.value for r in res.runs] == EXPECTED_AGENT_ORDER
    )
    verify = finding.verifications[-1]
    assert verify.verdict == "accepted"


def _ctx(intel, scope, roe=None, agent=AgentName.PROBE, runner=None):
    runner = runner or CheckRunner(
        driver=None,
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    ctx = make_ctx(agent, intel=intel, scope=scope, services={"check_runner": runner})
    ctx.roe = roe
    ctx.artifacts["last_scope_decision"] = None
    return ctx


ARGS = {
    "template_ref": OWNERSHIP,
    "target_id": TARGET_ID,
    "parameters": {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"},
}


@pytest.mark.parametrize(
    "case",
    ["missing_roe", "revoked_scope", "wrong_target", "out_of_scope_category", "invalid_route_unauthorized"],
)
def test_unauthorized_check_calls_are_denied_without_revealing_the_recipe(intel, case):
    scope = make_scope()
    roe = build_roe(scope, default_library().list_public())
    args = dict(ARGS)
    if case == "missing_roe":
        ctx = _ctx(intel, scope, None)
    elif case == "revoked_scope":
        ctx = _ctx(intel, make_scope(status=ScopeStatus.REVOKED), roe)
    elif case == "wrong_target":
        ctx, args = _ctx(intel, scope, roe), {**args, "target_id": "tgt_someone_else"}
    elif case == "out_of_scope_category":
        narrow = make_scope(categories=["access_control.ownership"])
        ctx = _ctx(intel, narrow, build_roe(narrow, default_library().list_public()))
        args = {
            **args,
            "template_ref": BOUNDS,
            "parameters": {"route_id": "nope", "read_route_id": "nope", "owner_identity": "x"},
        }
    else:
        ctx = _ctx(intel, scope, None)
        args = {
            **args,
            "parameters": {"route_id": "GET /payments/x", "owner_identity": "x", "other_identity": "y"},
        }
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(ctx, wire_name("checks.run_template"), args)
    assert error.value.code is ErrorCode.SCOPE_DENIED
    for value in ("payment_detail", "customer_detail", "create_refund", "alice", "bob", *SECRET_SHAPES):
        assert value not in error.value.message, (case, error.value.message)


@pytest.mark.parametrize(
    ("parameters", "named"),
    [
        (
            {"route_id": "GET /payments/{payment_id}", "owner_identity": "alice", "other_identity": "bob"},
            "payment_detail",
        ),
        ({"route_id": "payment_detail", "owner_identity": "mallory", "other_identity": "bob"}, "alice"),
    ],
)
def test_authorized_invalid_values_get_a_correctable_error_without_credentials(intel, parameters, named):
    scope = make_scope()
    ctx = _ctx(intel, scope, build_roe(scope, default_library().list_public()))
    ctx.artifacts["last_scope_decision"] = None
    result = (
        default_registry()
        .invoke(ctx, wire_name("checks.run_template"), {**ARGS, "parameters": parameters})
        .payload
    )
    assert result["error"] == "SCHEMA_INVALID" and named in result["detail"]
    assert result["matches_expectation"] is None
    assert not any(s in json.dumps(result) for s in SECRET_SHAPES)


def test_listing_shows_recipe_values_only_for_templates_the_roe_permits(intel):
    narrow = make_scope(categories=["access_control.ownership"])
    ctx = _ctx(intel, narrow, build_roe(narrow, default_library().list_public()))
    listing = default_registry().invoke(ctx, wire_name("checks.list_templates"), {}).payload
    by_ref = {t["ref"]: t for t in listing["templates"]}
    assert "parameter_values" in by_ref[OWNERSHIP]
    assert "parameter_values" not in by_ref[BOUNDS], by_ref[BOUNDS]
    assert list(listing["parameter_index"]) == [OWNERSHIP]


def test_scout_cannot_use_the_listing_tool(intel):
    scope = make_scope()
    ctx = _ctx(intel, scope, build_roe(scope, default_library().list_public()), agent=AgentName.SCOUT)
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(ctx, wire_name("checks.list_templates"), {})
    assert error.value.code is ErrorCode.TOOL_NOT_ALLOWED


def test_recipe_binding_does_not_depend_on_the_free_text_recipe_reference(intel):
    from security_agents.contracts import AuthorizedScope

    scope = make_scope()
    target = scope.targets[0].model_copy(update={"build_recipe_ref": "examples/payments-lite/sandbox.yaml"})
    scope = AuthorizedScope.model_validate({**scope.model_dump(), "targets": [target.model_dump()]})
    provider = recipe_from_snapshot(intel)
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=scope)
    assert provider(ctx, TARGET_ID)["app_factory"]


def test_recipe_binding_never_reads_outside_the_snapshot(intel):
    from security_agents.contracts import AuthorizedScope

    scope = make_scope()
    target = scope.targets[0].model_copy(update={"build_recipe_ref": "../../../etc/passwd"})
    scope = AuthorizedScope.model_construct(**{**scope.__dict__, "targets": [target]})
    provider = recipe_from_snapshot(intel)
    recipe = provider(make_ctx(AgentName.PROBE, intel=intel, scope=scope), TARGET_ID)
    assert recipe["app_factory"] == "payments_lite.app:create_app"


def test_hosted_probe_transcript_evidence(host_and_orchestrator):  # noqa: F811
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    probe_runs = [r for r in host.runs if r["agent"] == "probe"]
    assert probe_runs
    transcripts = [json.dumps(f.get("transcript"), default=str) for f in host.finished]
    probe_transcript = next(t for t in transcripts if "checks.run_template" in t)
    assert "matches_expectation" in probe_transcript and "route" in probe_transcript
    assert not any(s in t for t in transcripts for s in SECRET_SHAPES)


# Issue #236: a designated entry point wins over a cited comparison sibling.
def _entry(eid: str, start: int, end: int, template: str):
    from security_agents.contracts.models import EntryPoint, SourceSpan

    return EntryPoint(
        id=eid,
        snapshot_id="snap_1",
        kind="http_route",
        handler_symbol=eid,
        path="app/main.py",
        span=SourceSpan(start_line=start, end_line=end),
        method="get",
        path_template=template,
    )


def _hyp(entry_point_id, cited=((30, 40),)):
    from types import SimpleNamespace

    from security_agents.contracts.models import Hypothesis

    spans = [
        SimpleNamespace(path="app/main.py", span=SimpleNamespace(start_line=a, end_line=b)) for a, b in cited
    ]
    return Hypothesis.model_construct(entry_point_id=entry_point_id, cited_spans=spans)


def _intel():
    from types import SimpleNamespace

    entries = [
        _entry("ep_pay", 10, 20, "/payments/{payment_id}"),
        _entry("ep_cust", 30, 40, "/customers/{customer_id}"),
    ]
    return SimpleNamespace(entry_points=lambda: entries)


def test_designated_entry_point_is_the_only_subject_even_when_a_sibling_is_cited():
    # Scout names the vulnerable payment handler and cites the correct customer handler for comparison.
    assert probe_agent.subject_routes(_hyp("ep_pay"), _intel()) == [PAYMENT]


def test_cited_span_overlap_is_used_only_without_a_resolvable_entry_point():
    assert probe_agent.subject_routes(_hyp(None), _intel()) == ["GET /customers/{customer_id}"]
    assert probe_agent.subject_routes(_hyp("ep_unknown"), _intel()) == ["GET /customers/{customer_id}"]


def test_passing_check_on_the_cited_sibling_never_refutes_the_entry_point():
    subject = probe_agent.subject_routes(_hyp("ep_pay"), _intel())
    result = reconcile([run("customer_detail", True)], subject=subject, claimed="refuted")
    assert result.outcome is ValidationOutcome.INCONCLUSIVE
