"""Path-traversal template, executed for real.

A small statements package is written per test in a vulnerable and a fixed variant. The
vulnerable route joins the caller-supplied filename straight onto a base directory (so
``../../etc/passwd`` and an absolute path escape it); the fixed route confines reads to
the base directory with ``os.path.basename``. The template must confirm the vulnerable
variant (the real file /etc/passwd leaks) and clear the fixed one."""

from __future__ import annotations

import pytest

from security_agents.checks.library import PATH_TRAVERSAL, default_library
from security_agents.contracts import ErrorCode, PlatformError
from security_agents.tools import CheckRunner

from .conftest import TARGET_ID
from .test_checks import probe_ctx

STATEMENTS = """
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

VULNERABLE = {vulnerable}
BASE = {base!r}


def create_app():
    app = FastAPI()

    def who(authorization: str = Header()):
        if authorization != "Bearer t-alice":
            raise HTTPException(401)
        return "alice"

    @app.get("/statements", response_class=PlainTextResponse)
    def statements(file: str, user: str = Depends(who)):
        full = os.path.join(BASE, file if VULNERABLE else os.path.basename(file))
        try:
            with open(full) as handle:
                return handle.read()
        except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
            raise HTTPException(404)

    return app
"""


def _recipe():
    return {
        "recipe_version": 1,
        "kind": "python_asgi",
        "app_factory": "statements.app:create_app",
        "identities": {"alice": {"auth_header": "Bearer t-alice"}},
        "routes": [
            {
                "id": "get_statements",
                "method": "GET",
                "path_template": "/statements",
                "query_param": "file",
                "sample_file": "2024-01.txt",
            }
        ],
    }


PARAMS = {"route_id": "get_statements", "identity": "alice"}


def _runner(driver, tmp_path, *, vulnerable: bool) -> tuple[CheckRunner, dict]:
    base = tmp_path / "docs"
    base.mkdir()
    (base / "2024-01.txt").write_text("January statement: opening balance 100.00")
    pkg = tmp_path / "ws" / "statements"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "app.py").write_text(STATEMENTS.format(vulnerable=vulnerable, base=str(base)))
    recipe = _recipe()
    runner = CheckRunner(
        driver=driver,
        library=default_library(),
        workspace_provider=lambda _ctx: tmp_path / "ws",
        recipe_provider=lambda _ctx, _target: recipe,
    )
    return runner, recipe


def test_traversal_template_confirms_an_unconfined_file_route(driver, intel, tmp_path):
    runner, _ = _runner(driver, tmp_path, vulnerable=True)
    result = runner.run(probe_ctx(intel), PATH_TRAVERSAL.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["category"] == "input_validation.path"


def test_traversal_template_clears_a_confined_file_route(driver, intel, tmp_path):
    runner, _ = _runner(driver, tmp_path, vulnerable=False)
    result = runner.run(probe_ctx(intel), PATH_TRAVERSAL.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is True, result.get("stdout_tail")


def test_traversal_template_is_inconclusive_when_the_sample_file_is_unavailable(driver, intel, tmp_path):
    """A route that cannot serve its in-scope file proves nothing about traversal."""
    runner, recipe = _runner(driver, tmp_path, vulnerable=True)
    recipe["identities"]["alice"] = {"auth_header": "Bearer nope"}
    result = runner.run(probe_ctx(intel), PATH_TRAVERSAL.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is None, result.get("stdout_tail")


def test_traversal_render_binds_the_canary_and_the_sample_file(tmp_path):
    src = default_library().render(PATH_TRAVERSAL.ref, _recipe(), PARAMS)
    assert "'root:'" in src and "2024-01.txt" in src and "/etc/passwd" in src


def test_traversal_render_rejects_a_non_get_route(tmp_path):
    recipe = _recipe()
    recipe["routes"][0]["method"] = "POST"
    with pytest.raises(PlatformError) as e:
        default_library().render(PATH_TRAVERSAL.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_traversal_render_rejects_a_path_parameter(tmp_path):
    recipe = _recipe()
    recipe["routes"][0]["path_template"] = "/statements/{year}"
    with pytest.raises(PlatformError) as e:
        default_library().render(PATH_TRAVERSAL.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_traversal_render_rejects_a_route_without_a_sample_file(tmp_path):
    recipe = _recipe()
    del recipe["routes"][0]["sample_file"]
    with pytest.raises(PlatformError) as e:
        default_library().render(PATH_TRAVERSAL.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID
