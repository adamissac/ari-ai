"""NFR-07: LLM_MAX_USD_PER_ASSESSMENT / LLM_MAX_TOKENS_PER_ASSESSMENT are operator caps.
No request or project setting can approve a larger budget than the operator allows."""

from __future__ import annotations

import sqlalchemy as sa
from helpers import HEAD, setup_project

from backend.db import projects, transaction


def test_request_budget_over_operator_cap_is_rejected(client_factory, settings_override) -> None:
    settings_override(llm_max_usd_per_assessment="2", llm_max_tokens_per_assessment="50000")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    url = f"/api/v1/projects/{ids['project']}/assessments"
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}

    r = alice.post(url, json={**body, "budget": {"max_usd": 500.0}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "LLM_MAX_USD_PER_ASSESSMENT" in r.json()["error"]["message"]
    r = alice.post(url, json={**body, "budget": {"max_usd": 1.0, "max_tokens": 10**6}})
    assert r.status_code == 422 and "LLM_MAX_TOKENS" in r.json()["error"]["message"]
    assert alice.get(url).json()["items"] == []

    ok = alice.post(url, json={**body, "budget": {"max_usd": 1.5, "max_tokens": 40000}})
    assert ok.status_code == 202, ok.text
    assert ok.json()["assessment"]["budget"]["max_usd"] == 1.5


def test_project_budgets_are_checked_on_save_and_clamped_on_use(
    client_factory, settings_override
) -> None:
    settings_override(llm_max_usd_per_assessment="2", llm_max_tokens_per_assessment="50000")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    project = alice.get(f"/api/v1/projects/{ids['project']}").json()
    rich = {**project["settings"], "default_budget": {"max_usd": 99.0, "max_tokens": 1000}}

    r = alice.patch(f"/api/v1/projects/{ids['project']}", json={"settings": rich})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"
    r = alice.post("/api/v1/projects", json={"name": "rich", "settings": rich})
    assert r.status_code == 422

    # A budget saved before the operator lowered the cap is clamped, not honoured.
    with transaction() as conn:
        conn.execute(
            sa.update(projects).where(projects.c.id == ids["project"]).values(settings=rich)
        )
    url = f"/api/v1/projects/{ids['project']}/assessments"
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    r = alice.post(url, json=body)
    assert r.status_code == 202, r.text
    budget = r.json()["assessment"]["budget"]
    assert budget["max_usd"] == 2.0 and budget["max_tokens"] == 1000
