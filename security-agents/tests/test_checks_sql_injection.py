"""SQL-injection template, executed for real.

A small notes package is written per test in a vulnerable and a fixed variant, both
backed by a real sqlite3 table. The vulnerable search builds its WHERE clause with an
f-string (so a tautology payload drops the owner filter); the fixed search binds
parameters. The template must confirm the vulnerable variant and clear the fixed one."""

from __future__ import annotations

import pytest

from security_agents.checks.library import SQL_INJECTION, default_library
from security_agents.contracts import ErrorCode, PlatformError
from security_agents.tools import CheckRunner

from .conftest import TARGET_ID
from .test_checks import probe_ctx

NOTES = """
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException

VULNERABLE = {vulnerable}


def create_app():
    app = FastAPI()
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE notes (id TEXT, owner TEXT, body TEXT)")
    db.executemany(
        "INSERT INTO notes VALUES (?, ?, ?)",
        [
            ("note_a1", "alice", "note_a1 alice grocery list"),
            ("note_b1", "bob", "note_b1 bob private password hint"),
        ],
    )
    db.commit()

    def who(authorization: str = Header()):
        name = {{"Bearer t-alice": "alice", "Bearer t-bob": "bob"}}.get(authorization)
        if name is None:
            raise HTTPException(401)
        return name

    @app.get("/notes/search")
    def search(q: str, user: str = Depends(who)):
        if VULNERABLE:
            sql = f"SELECT id, body FROM notes WHERE owner = '{{user}}' AND body LIKE '%{{q}}%'"
            cur = db.execute(sql)
        else:
            cur = db.execute(
                "SELECT id, body FROM notes WHERE owner = ? AND body LIKE ?",
                (user, f"%{{q}}%"),
            )
        return [{{"id": r[0], "body": r[1]}} for r in cur.fetchall()]

    return app
"""

RECIPE = {
    "recipe_version": 1,
    "kind": "python_asgi",
    "app_factory": "notes.app:create_app",
    "identities": {
        "alice": {"auth_header": "Bearer t-alice"},
        "bob": {"auth_header": "Bearer t-bob"},
    },
    "resources": {"note": {"alice": {"id": "note_a1"}, "bob": {"id": "note_b1"}}},
    "routes": [
        {
            "id": "search_notes",
            "method": "GET",
            "path_template": "/notes/search",
            "resource": "note",
            "query_param": "q",
        }
    ],
}

PARAMS = {"route_id": "search_notes", "owner_identity": "alice", "other_identity": "bob"}


def _runner(driver, tmp_path, *, vulnerable: bool) -> CheckRunner:
    pkg = tmp_path / "ws" / "notes"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "app.py").write_text(NOTES.format(vulnerable=vulnerable))
    return CheckRunner(
        driver=driver,
        library=default_library(),
        workspace_provider=lambda _ctx: tmp_path / "ws",
        recipe_provider=lambda _ctx, _target: RECIPE,
    )


def test_sqli_template_confirms_a_tautology_leak(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, vulnerable=True)
    result = runner.run(probe_ctx(intel), SQL_INJECTION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["category"] == "input_validation.injection"


def test_sqli_template_clears_a_parameterised_search(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, vulnerable=False)
    result = runner.run(probe_ctx(intel), SQL_INJECTION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is True, result.get("stdout_tail")


def test_sqli_template_is_inconclusive_when_the_owner_cannot_search(driver, intel, tmp_path):
    """A benign query the API refuses proves nothing about injection: never 'confirmed'."""
    runner = _runner(driver, tmp_path, vulnerable=True)
    recipe = {**RECIPE, "identities": {**RECIPE["identities"], "alice": {"auth_header": "Bearer nope"}}}
    runner.recipe_provider = lambda _ctx, _target: recipe
    result = runner.run(probe_ctx(intel), SQL_INJECTION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is None, result.get("stdout_tail")


def test_sqli_render_binds_the_canary_and_nothing_free_form():
    src = default_library().render(SQL_INJECTION.ref, RECIPE, PARAMS)
    assert "'note_b1'" in src and "ari-probe-no-such-term" in src


def test_sqli_render_rejects_a_non_get_route():
    recipe = {**RECIPE, "routes": [{**RECIPE["routes"][0], "method": "POST"}]}
    with pytest.raises(PlatformError) as e:
        default_library().render(SQL_INJECTION.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_sqli_render_rejects_a_path_parameter():
    recipe = {**RECIPE, "routes": [{**RECIPE["routes"][0], "path_template": "/notes/{note_id}/search"}]}
    with pytest.raises(PlatformError) as e:
        default_library().render(SQL_INJECTION.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_sqli_render_rejects_the_same_identity_twice():
    with pytest.raises(PlatformError) as e:
        default_library().render(SQL_INJECTION.ref, RECIPE, {**PARAMS, "other_identity": "alice"})
    assert e.value.code is ErrorCode.SCHEMA_INVALID
