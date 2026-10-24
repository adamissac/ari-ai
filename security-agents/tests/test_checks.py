"""Check templates: rendering from the recipe and real execution (SEC-004, SEC-005).

These tests actually run the templates against the owned payments-lite target,
so they prove the planted authorization weakness is detected and the sibling
look-alike routes are not falsely flagged.
"""

from __future__ import annotations

import pytest

from security_agents.checks.library import (
    AUTHENTICATION,
    BOUNDS,
    OWNERSHIP,
    ROLE,
    default_library,
    empty_library,
)
from security_agents.contracts import AgentName, ErrorCode, PlatformError
from security_agents.scope_guard import Decision
from security_agents.tools import CheckRunner, recipe_from_snapshot

from .conftest import NOW, TARGET_ID, make_ctx, make_scope

ALLOWED = Decision(allowed=True, reason_code="OK", scope_id="scp_test", evaluated_at=NOW)


def runner_for(driver, intel, library=None) -> CheckRunner:
    return CheckRunner(
        driver=driver,
        library=library or default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )


def probe_ctx(intel, scope=None):
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=scope or make_scope())
    ctx.artifacts["last_scope_decision"] = ALLOWED
    return ctx


# --------------------------------------------------------------------------- rendering


def test_library_lists_runnable_templates(library):
    refs = {t["ref"] for t in library.list_public()}
    assert refs == {OWNERSHIP.ref, BOUNDS.ref, AUTHENTICATION.ref, ROLE.ref}
    assert all(t["runnable"] for t in library.list_public())
    assert library.categories() == {
        "access_control.ownership",
        "access_control.authentication",
        "access_control.role",
        "input_validation.bounds",
    }


def test_unreviewed_library_is_not_runnable():
    assert not empty_library().runnable(OWNERSHIP.ref)


def test_render_rejects_unknown_route(library, recipe):
    with pytest.raises(PlatformError) as exc:
        library.render(
            OWNERSHIP.ref,
            recipe,
            {"route_id": "no_such_route", "owner_identity": "alice", "other_identity": "bob"},
        )
    assert exc.value.code is ErrorCode.SCHEMA_INVALID


def test_render_rejects_unknown_identity(library, recipe):
    with pytest.raises(PlatformError):
        library.render(
            OWNERSHIP.ref,
            recipe,
            {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "mallory"},
        )


def test_render_rejects_same_identity_twice(library, recipe):
    with pytest.raises(PlatformError):
        library.render(
            OWNERSHIP.ref,
            recipe,
            {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "alice"},
        )


def test_role_render_rejects_a_non_mutating_route(library, recipe):
    """Role checks only apply to mutating routes; a GET route cannot carry the check."""
    with pytest.raises(PlatformError) as exc:
        library.render(
            ROLE.ref,
            recipe,
            {
                "route_id": "payment_detail",
                "restricted_identity": "bob",
                "permitted_identity": "alice",
            },
        )
    assert exc.value.code is ErrorCode.SCHEMA_INVALID


def test_role_render_rejects_the_same_identity(library, recipe):
    with pytest.raises(PlatformError) as exc:
        library.render(
            ROLE.ref,
            recipe,
            {
                "route_id": "create_refund",
                "restricted_identity": "alice",
                "permitted_identity": "alice",
            },
        )
    assert exc.value.code is ErrorCode.SCHEMA_INVALID


def test_role_render_rejects_an_unknown_identity(library, recipe):
    with pytest.raises(PlatformError):
        library.render(
            ROLE.ref,
            recipe,
            {
                "route_id": "create_refund",
                "restricted_identity": "mallory",
                "permitted_identity": "alice",
            },
        )


def test_render_rejects_unknown_parameter(library, recipe):
    with pytest.raises(PlatformError):
        library.render(
            OWNERSHIP.ref,
            recipe,
            {
                "route_id": "payment_detail",
                "owner_identity": "alice",
                "other_identity": "bob",
                "shell_command": "whoami",
            },
        )


def test_render_rejects_missing_parameter(library, recipe):
    with pytest.raises(PlatformError):
        library.render(OWNERSHIP.ref, recipe, {"route_id": "payment_detail"})


def test_rendered_check_contains_no_free_form_values(library, recipe):
    src = library.render(
        OWNERSHIP.ref,
        recipe,
        {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    # Only fixture identities and recipe-declared ids ever appear.
    assert "fixture-token-alice" in src and "fixture-token-bob" in src
    assert "pay_a1" in src
    # the generated module imports nothing that could reach outside the target
    import ast

    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"json", "decimal", "fastapi", "payments_lite"}, imported
    # compare executable code only: drop the module docstring and comments
    body = tree.body[1:] if ast.get_docstring(tree) else tree.body
    code = "\n".join(ast.unparse(node) for node in body)
    for forbidden in ("subprocess", "socket", "http://", "https://", "requests.", "os.system"):
        assert forbidden not in code, forbidden


def test_params_hash_is_stable(library):
    params = {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"}
    assert library.params_hash(OWNERSHIP.ref, params) == library.params_hash(
        OWNERSHIP.ref, dict(reversed(list(params.items())))
    )
    assert library.params_hash(OWNERSHIP.ref, params) != library.params_hash(BOUNDS.ref, params)


# --------------------------------------------------------------------------- execution


def test_ownership_check_detects_the_planted_weakness(driver, intel):
    """The planted route does not enforce ownership: matches_expectation is False."""
    ctx = probe_ctx(intel)
    result = runner_for(driver, intel).run(
        ctx,
        OWNERSHIP.ref,
        TARGET_ID,
        {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["failed"] >= 1
    assert result["network"] == "target-only"
    assert result["sandbox_run_id"]
    assert "sandbox.check_run" in ctx.audit.actions()


def test_ownership_check_clears_the_sibling_lookalike_route(driver, intel):
    """A negative from labels.yaml: GET /customers/{id} calls require_owner, so the
    expectation holds and a hypothesis about it must be refuted (precision)."""
    result = runner_for(driver, intel).run(
        probe_ctx(intel),
        OWNERSHIP.ref,
        TARGET_ID,
        {"route_id": "customer_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["matches_expectation"] is True, result.get("stdout_tail")
    assert result["failed"] == 0


def test_role_check_proves_the_owner_guard_on_create_refund(driver, intel):
    """labels.yaml marks POST /refunds as correctly owner-guarded: bob acting on alice's
    payment must be denied while alice keeps access — expectation holds (precision)."""
    result = runner_for(driver, intel).run(
        probe_ctx(intel),
        ROLE.ref,
        TARGET_ID,
        {
            "route_id": "create_refund",
            "restricted_identity": "bob",
            "permitted_identity": "alice",
        },
    )
    assert result["matches_expectation"] is True, result.get("stdout_tail")
    assert result["category"] == "access_control.role"
    assert result["failed"] == 0


def test_bounds_check_detects_the_planted_functional_defect(driver, intel):
    result = runner_for(driver, intel).run(
        probe_ctx(intel),
        BOUNDS.ref,
        TARGET_ID,
        {
            "route_id": "create_refund",
            "read_route_id": "payment_detail",
            "owner_identity": "alice",
            "over_by": "1.00",
        },
    )
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["category"] == "input_validation.bounds"


def test_check_runs_are_reproducible(driver, intel):
    runner = runner_for(driver, intel)
    params = {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"}
    first = runner.run(probe_ctx(intel), OWNERSHIP.ref, TARGET_ID, params)
    second = runner.run(probe_ctx(intel), OWNERSHIP.ref, TARGET_ID, params)
    assert first["matches_expectation"] == second["matches_expectation"]
    assert first["params_hash"] == second["params_hash"]
    assert first["sandbox_run_id"] != second["sandbox_run_id"], "each run is a fresh sandbox"


def test_check_does_not_mutate_the_snapshot(driver, intel):
    from security_agents.sandbox.workspace import tree_digest

    before = tree_digest(intel.snapshot.root)
    runner_for(driver, intel).run(
        probe_ctx(intel),
        BOUNDS.ref,
        TARGET_ID,
        {"route_id": "create_refund", "read_route_id": "payment_detail", "owner_identity": "alice"},
    )
    assert tree_digest(intel.snapshot.root) == before


@pytest.mark.boundary
def test_check_runner_refuses_without_a_scope_decision(driver, intel):
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope())  # no decision recorded
    with pytest.raises(PlatformError) as exc:
        runner_for(driver, intel).run(
            ctx,
            OWNERSHIP.ref,
            TARGET_ID,
            {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"},
        )
    assert exc.value.code is ErrorCode.SCOPE_DENIED


@pytest.mark.boundary
def test_check_runner_refuses_a_denied_scope_decision(driver, intel):
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope())
    ctx.artifacts["last_scope_decision"] = Decision(
        allowed=False, reason_code="TARGET_NOT_IN_SCOPE", scope_id="scp_test", evaluated_at=NOW
    )
    with pytest.raises(PlatformError) as exc:
        runner_for(driver, intel).run(ctx, OWNERSHIP.ref, TARGET_ID, {})
    assert exc.value.code is ErrorCode.SCOPE_DENIED


def test_unknown_template_is_reported_not_raised(driver, intel):
    result = runner_for(driver, intel).run(probe_ctx(intel), "made.up@9", TARGET_ID, {})
    assert result["error"] == "UNKNOWN_TEMPLATE"


def test_unreviewed_template_fails_closed(driver, intel):
    lib = empty_library()
    lib.register(OWNERSHIP.__class__(**{**vars(OWNERSHIP), "reviewed_by": None}))
    result = runner_for(driver, intel, library=lib).run(probe_ctx(intel), OWNERSHIP.ref, TARGET_ID, {})
    assert result["error"] == "TEMPLATE_NOT_RUNNABLE"
    assert result["matches_expectation"] is None


def test_bad_parameters_are_reported_with_a_code(driver, intel):
    result = runner_for(driver, intel).run(
        probe_ctx(intel),
        OWNERSHIP.ref,
        TARGET_ID,
        {"route_id": "ghost", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["error"] == ErrorCode.SCHEMA_INVALID.value
    assert result["matches_expectation"] is None


# --------------------------------------------------------------------------- any customer app


def test_app_factory_comes_from_the_recipe_and_is_strictly_validated(library, recipe):
    params = {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"}
    src = library.render(OWNERSHIP.ref, {**recipe, "app_factory": "acme_billing.api.main:build"}, params)
    assert "from acme_billing.api.main import build as create_app" in src
    assert "payments_lite" not in src
    assert "from payments_lite.app import create_app" in library.render(OWNERSHIP.ref, recipe, params)
    # The recipe is repository content: anything but package.module:callable is refused.
    for bad in (
        "os:system; import os",
        "acme.app:create_app()",
        "acme app:create_app",
        "acme.app",
        "acme.app:create_app\nimport os",
        "../x:y",
        "",
    ):
        if bad == "":
            continue  # empty falls back to the default factory
        with pytest.raises(PlatformError) as e:
            library.render(OWNERSHIP.ref, {**recipe, "app_factory": bad}, params)
        assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_checks_run_against_a_differently_named_customer_package(driver, intel, recipe, tmp_path):
    """A real customer repository is not called payments_lite: the same planted IDOR is
    found when the package and factory have other names."""
    import shutil

    ws = tmp_path / "ws"
    shutil.copytree(intel.snapshot.root, ws)
    for p in (ws, *ws.rglob("*")):
        p.chmod(0o755 if p.is_dir() else 0o644)  # snapshots are read-only
    shutil.move(ws / "payments_lite", ws / "acme_billing")
    for f in (ws / "acme_billing").glob("*.py"):
        f.write_text(f.read_text().replace("payments_lite", "acme_billing"))
    with (ws / "acme_billing" / "app.py").open("a") as fh:
        fh.write("\n\nbuild = create_app\n")
    custom = {**recipe, "app_factory": "acme_billing.app:build"}
    runner = CheckRunner(
        driver=driver,
        library=default_library(),
        workspace_provider=lambda _ctx: ws,
        recipe_provider=lambda _ctx, _target: custom,
    )
    params = {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"}
    planted = runner.run(probe_ctx(intel), OWNERSHIP.ref, TARGET_ID, params)
    assert planted["matches_expectation"] is False, planted.get("stdout_tail")
    sibling = runner.run(
        probe_ctx(intel), OWNERSHIP.ref, TARGET_ID, {**params, "route_id": "customer_detail"}
    )
    assert sibling["matches_expectation"] is True, sibling.get("stdout_tail")
