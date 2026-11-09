"""A node_http target served in the sandbox, end to end (ADR-0023).

CheckRunner -> LocalProcessDriver -> sandbox/node_stack.mjs (Firebase Auth + Firestore
emulators, seeded identities, the fixture's real Vercel function on firebase-admin) -> the
rendered check over HTTP on loopback. Needs java, node, a cached Firestore emulator JAR,
`npm ci --prefix security-agents/sandbox/node` and registry access the first time the
fixture's lockfile is installed. Skipped with the reason otherwise; nothing is simulated.
"""

import json
import shutil
from pathlib import Path

import pytest

from security_agents.checks.library import AUTHENTICATION, FIRESTORE_OWNER, OWNERSHIP, default_library
from security_agents.contracts import AgentName
from security_agents.sandbox.driver import LocalProcessDriver
from security_agents.sandbox.node import NODE_DIR
from security_agents.tools import CheckRunner

from .conftest import NOW, TARGET_ID, make_ctx, make_scope
from .test_firestore_checks import _missing
from .test_sandbox import ALLOWED

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "notes-firebase-lite"


def missing() -> str | None:
    if reason := _missing():
        return reason
    if not (NODE_DIR / "node_modules" / "firebase-tools").is_dir():
        return "run `npm ci --prefix security-agents/sandbox/node`"
    return None


pytestmark = pytest.mark.skipif(missing() is not None, reason=missing() or "")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SECURITY_WORKDIR", str(tmp_path.parent / "ari-node-cache"))
    ws = tmp_path / "target"
    shutil.copytree(FIXTURE, ws)
    return ws


def run(workspace, intel, ref, params, rules=None):
    if rules is not None:
        (workspace / "firestore.rules").write_text(rules)
    recipe_path = workspace / "build_recipe.json"
    from security_agents import node_recipe

    runner = CheckRunner(
        driver=LocalProcessDriver(allow=True),
        library=default_library(),
        workspace_provider=lambda _ctx: workspace,
        recipe_provider=lambda _ctx, _t: node_recipe.resolved(json.loads(recipe_path.read_text())),
    )
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope(), now=lambda: NOW)
    ctx.artifacts["last_scope_decision"] = ALLOWED
    return runner.run(ctx, ref, TARGET_ID, params)


def test_bola_on_the_real_function_is_confirmed_over_http(workspace, intel):
    result = run(
        workspace,
        intel,
        OWNERSHIP.ref,
        {"route_id": "note_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["matches_expectation"] is False, result
    assert result["transport"] == "http" and result["target_contacted"] is True
    paths = [(r["path"], r["status"]) for r in result["target_requests"]]
    assert paths.count(("/api/notes/note-alice", 200)) == 2, paths  # owner, then bob leaking it


def test_authentication_holds_on_the_real_function(workspace, intel):
    result = run(workspace, intel, AUTHENTICATION.ref, {"route_id": "note_detail", "identity": "alice"})
    assert result["matches_expectation"] is True, result
    statuses = {r["status"] for r in result["target_requests"] if r["path"].startswith("/api/notes/")}
    assert statuses == {200, 401}, result["target_requests"]


def test_rules_check_runs_in_the_sandbox_and_a_rules_patch_flips_it(workspace, intel):
    params = {"path_id": "profile_doc", "owner_identity": "alice", "other_identity": "bob"}
    assert run(workspace, intel, FIRESTORE_OWNER.ref, params)["matches_expectation"] is False
    fixed = (
        (workspace / "firestore.rules")
        .read_text()
        .replace(
            "allow read, write: if request.auth != null;", "allow read, write: if request.auth.uid == uid;"
        )
    )
    assert run(workspace, intel, FIRESTORE_OWNER.ref, params, rules=fixed)["matches_expectation"] is True


def test_node_suite_runs_through_the_test_runner_with_a_test_id_audit(workspace, intel):
    from security_agents import node_recipe
    from security_agents.tools.pytest_audit import compare_pytest_audits
    from security_agents.tools.services import TestRunner

    recipe = node_recipe.resolved(json.loads((workspace / "build_recipe.json").read_text()))
    runner = TestRunner(
        driver=LocalProcessDriver(allow=True),
        workspace_provider=lambda _ctx: workspace,
        node_test=node_recipe.test_command(recipe),
        node_stack=node_recipe.stack_config(recipe, serve=False),
    )
    ctx = make_ctx(AgentName.VERIFY, intel=intel, scope=make_scope(), now=lambda: NOW)
    first = runner.run(ctx, "project_suite", [])
    assert (first["passed"], first["failed"], first["errors"]) == (2, 0, 0), first
    audits = ctx.artifacts["pytest_audits"]
    baseline = audits[first["sandbox_run_id"]]
    assert sorted(baseline["nodeids"]) == [
        "tests/handler.test.js::GET_/api/notes/:id_rejects_other_methods",
        "tests/handler.test.js::GET_/api/notes/:id_requires_a_bearer_token",
    ]
    # Deleting a protected JS test is caught by the same fail-closed audit comparison.
    (workspace / "tests" / "handler.test.js").write_text(
        (workspace / "tests" / "handler.test.js").read_text().split("  it('requires")[0] + "});\n"
    )
    second = runner.run(ctx, "project_suite", [])
    findings = compare_pytest_audits(baseline, audits[second["sandbox_run_id"]])
    assert any("protected tests not collected" in f and "requires_a_bearer_token" in f for f in findings), (
        findings
    )


def test_added_tests_run_with_the_recipe_runner_config(workspace, intel):
    """A test file the default vitest config excludes still runs as an added test (live mypypath run)."""
    from security_agents import node_recipe
    from security_agents.tools.services import TestRunner

    (workspace / "vitest.config.js").write_text("export default { test: { exclude: ['tests/rules/**'] } };\n")
    (workspace / "vitest.rules.config.js").write_text(
        "export default { test: { include: ['tests/rules/**'] } };\n"
    )
    (workspace / "tests" / "rules").mkdir()
    (workspace / "tests" / "rules" / "added.test.js").write_text(
        "import { it, expect } from 'vitest';\nit('runs', () => expect(1).toBe(1));\n"
    )
    recipe = json.loads((workspace / "build_recipe.json").read_text())
    recipe["test_command"] = {"runner": "vitest", "args": ["run", "--config", "vitest.rules.config.js"]}
    recipe = node_recipe.resolved(recipe)
    runner = TestRunner(
        driver=LocalProcessDriver(allow=True),
        workspace_provider=lambda _ctx: workspace,
        node_test=node_recipe.test_command(recipe),
        node_stack=node_recipe.stack_config(recipe, serve=False),
    )
    ctx = make_ctx(AgentName.PATCH, intel=intel, scope=make_scope(), now=lambda: NOW)
    ctx.artifacts["tests_added"] = ["tests/rules/added.test.js"]
    result = runner.run(ctx, "added_tests", [])
    assert (result["passed"], result["failed"], result["errors"]) == (1, 0, 0), result
