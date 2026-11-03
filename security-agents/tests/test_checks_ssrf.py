"""SSRF template, executed for real.

A small webhook package is written per test in a vulnerable and a fixed variant. The
vulnerable route accepts any URL without validating its destination; the fixed route
rejects internal and cloud-metadata hosts with 400 before doing anything. The template
must confirm the vulnerable variant and clear the fixed one. No real network call is
made: the run network is target-only with no egress, so the template's signal is that
the endpoint refuses the destination, which the vulnerable app fails to do."""

from __future__ import annotations

import pytest

from security_agents.checks.library import SSRF, default_library
from security_agents.contracts import ErrorCode, PlatformError
from security_agents.tools import CheckRunner

from .conftest import TARGET_ID
from .test_checks import probe_ctx

WEBHOOK = """
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

VULNERABLE = {vulnerable}
BLOCKED = {{"127.0.0.1", "localhost", "0.0.0.0", "169.254.169.254"}}


class WebhookIn(BaseModel):
    url: str


def create_app():
    app = FastAPI()

    def who(authorization: str = Header()):
        if authorization != "Bearer t-alice":
            raise HTTPException(401)
        return "alice"

    @app.post("/webhooks/test")
    def test_webhook(body: WebhookIn, user: str = Depends(who)):
        if not VULNERABLE:
            host = (urlparse(body.url).hostname or "").lower()
            if host in BLOCKED or host.endswith(".internal"):
                raise HTTPException(400, "destination not allowed")
        # Vulnerable: no destination validation; the endpoint would fetch body.url.
        return {{"ok": True}}

    return app
"""

RECIPE = {
    "recipe_version": 1,
    "kind": "python_asgi",
    "app_factory": "webhooks.app:create_app",
    "identities": {"alice": {"auth_header": "Bearer t-alice"}},
    "routes": [
        {
            "id": "test_webhook",
            "method": "POST",
            "path_template": "/webhooks/test",
            "body_template": {"url": "{url}"},
        }
    ],
}

PARAMS = {"route_id": "test_webhook", "identity": "alice"}


def _runner(driver, tmp_path, *, vulnerable: bool) -> CheckRunner:
    pkg = tmp_path / "ws" / "webhooks"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "app.py").write_text(WEBHOOK.format(vulnerable=vulnerable))
    return CheckRunner(
        driver=driver,
        library=default_library(),
        workspace_provider=lambda _ctx: tmp_path / "ws",
        recipe_provider=lambda _ctx, _target: RECIPE,
    )


def test_ssrf_template_confirms_an_unvalidated_fetch_route(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, vulnerable=True)
    result = runner.run(probe_ctx(intel), SSRF.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["category"] == "input_validation.ssrf"


def test_ssrf_template_clears_a_destination_allowlist(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, vulnerable=False)
    result = runner.run(probe_ctx(intel), SSRF.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is True, result.get("stdout_tail")


def test_ssrf_template_is_inconclusive_when_unauthenticated(driver, intel, tmp_path):
    """A 401 means the request never reached destination validation: never 'confirmed'."""
    runner = _runner(driver, tmp_path, vulnerable=True)
    recipe = {**RECIPE, "identities": {"alice": {"auth_header": "Bearer nope"}}}
    runner.recipe_provider = lambda _ctx, _target: recipe
    result = runner.run(probe_ctx(intel), SSRF.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is None, result.get("stdout_tail")


def test_ssrf_render_binds_internal_payloads_and_nothing_free_form():
    src = default_library().render(SSRF.ref, RECIPE, PARAMS)
    assert "169.254.169.254" in src and "127.0.0.1" in src


def test_ssrf_render_rejects_a_non_post_route():
    recipe = {**RECIPE, "routes": [{**RECIPE["routes"][0], "method": "GET"}]}
    with pytest.raises(PlatformError) as e:
        default_library().render(SSRF.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_ssrf_render_rejects_a_body_without_a_url_placeholder():
    recipe = {**RECIPE, "routes": [{**RECIPE["routes"][0], "body_template": {"callback": "{resource_id}"}}]}
    with pytest.raises(PlatformError) as e:
        default_library().render(SSRF.ref, recipe, PARAMS)
    assert e.value.code is ErrorCode.SCHEMA_INVALID
