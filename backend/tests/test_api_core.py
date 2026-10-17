"""Tier 2: auth/session/CSRF, authorization, scopes + approvals, assessments, audit chain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helpers import HEAD, setup_project


def test_health_and_readiness(client_factory) -> None:
    c = client_factory()
    assert c.get("/healthz").json()["status"] == "ok"
    r = c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] and body["queue"]
    assert body["llm_mode"] == "unavailable"  # no key in tests: never pretends to be live
    assert body["webhook_secret_configured"] is True


def test_unauthenticated_requests_get_error_envelope(client_factory) -> None:
    r = client_factory().get("/api/v1/projects")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "UNAUTHENTICATED" and err["request_id"].startswith("req_")
    assert r.headers["X-Request-ID"] == err["request_id"]


def test_dev_login_can_be_disabled(client_factory, settings_override) -> None:
    settings_override(auth_dev_login_enabled="false")
    r = client_factory().post("/api/v1/auth/dev/login", json={"github_login": "mallory"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


def test_csrf_required_for_state_changes(client_factory) -> None:
    alice = client_factory("alice")
    token = alice.headers.pop("X-CSRF-Token")
    r = alice.post("/api/v1/projects", json={"name": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"
    alice.headers["X-CSRF-Token"] = token
    assert alice.post("/api/v1/projects", json={"name": "x"}).status_code == 201


def test_projects_are_isolated_between_orgs(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    assert eve.get(f"/api/v1/projects/{pid}").status_code == 404  # no existence leak
    assert eve.get("/api/v1/projects").json()["items"] == []
    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "secret"
    r = alice.post("/api/v1/projects", json={"name": "x", "unexpected": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_scope_approval_requires_a_different_owner(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    r = alice.post(f"/api/v1/scopes/{ids['scope']}/approve")
    assert r.status_code == 403 and "differ" in r.json()["error"]["message"]
    r = bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    assert (
        r.status_code == 200
        and r.json()["status"] == "active"
        and r.json()["approved_by"] == bob.me["user"]["id"]
    )
    assert bob.post(f"/api/v1/scopes/{ids['scope']}/approve").status_code == 409
    approvals = alice.get(f"/api/v1/projects/{ids['project']}/approvals").json()["items"]
    assert approvals[0]["status"] == "approved"


def test_scope_rejects_foreign_repo_and_bad_expiry(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    other = alice.post("/api/v1/projects", json={"name": "other"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{other}/scopes",
        json={
            "name": "x",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [{"kind": "sandbox_build", "repo_id": ids["repo"], "build_recipe_ref": "r"}],
        },
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "SCOPE_DENIED"
    r = alice.post(
        f"/api/v1/projects/{ids['project']}/scopes",
        json={
            "name": "x",
            "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
            "targets": [{"kind": "sandbox_build", "repo_id": ids["repo"], "build_recipe_ref": "r"}],
        },
    )
    assert r.status_code == 422
    r = alice.post(
        f"/api/v1/projects/{ids['project']}/scopes",
        json={
            "name": "x",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [{"kind": "staging_url", "repo_id": ids["repo"], "build_recipe_ref": "r"}],
        },
    )
    assert r.status_code == 422, "only sandbox_build targets are allowed in MVP"


def test_assessment_requires_active_scope_and_is_idempotent(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    url = f"/api/v1/projects/{ids['project']}/assessments"
    r = alice.post(url, json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "SCOPE_DENIED"
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    r1 = alice.post(url, json=body, headers={"Idempotency-Key": "k1"})
    assert r1.status_code == 202, r1.text
    r2 = alice.post(url, json=body, headers={"Idempotency-Key": "k1"})
    assert r2.json() == r1.json()
    r3 = alice.post(url, json={**body, "commit_sha": "c" * 40}, headers={"Idempotency-Key": "k1"})
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    asm = r1.json()["assessment"]
    assert asm["state"] == "CREATED" and asm["trigger"] == "manual"
    assert (
        alice.get(f"/api/v1/projects/{ids['project']}/assessments").json()["items"][0]["id"]
        == asm["id"]
    )
    assert alice.post(url, json={**body, "commit_sha": "abc"}).status_code == 422


def test_cancel_before_start_and_revoke_stops_assessments(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    url = f"/api/v1/projects/{ids['project']}/assessments"
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    a1 = alice.post(url, json=body).json()["assessment"]["id"]
    r = alice.post(f"/api/v1/assessments/{a1}/cancel")
    assert r.json()["cancelled"] is True
    assert alice.get(f"/api/v1/assessments/{a1}").json()["assessment"]["state"] == "CANCELLED"
    assert alice.post(f"/api/v1/assessments/{a1}/cancel").status_code == 409
    a2 = alice.post(url, json=body).json()["assessment"]["id"]
    assert alice.post(f"/api/v1/scopes/{ids['scope']}/revoke").json()["status"] == "revoked"
    assert alice.get(f"/api/v1/assessments/{a2}").json()["assessment"]["state"] == "CANCELLED"
    assert alice.post(url, json=body).json()["error"]["code"] == "SCOPE_DENIED"


def test_audit_log_is_hash_chained_and_append_only(client_factory) -> None:
    import pytest
    import sqlalchemy as sa

    from backend.db import get_engine

    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    r = alice.get("/api/v1/audit", params={"project_id": ids["project"]})
    body = r.json()
    actions = [e["action"] for e in body["items"]]
    assert {"project.created", "repository.connected", "scope.requested", "scope.approved"} <= set(
        actions
    )
    assert body["chain_verified"] is True and body["chain_events_checked"] >= 5
    with pytest.raises(sa.exc.DBAPIError, match="append-only"), get_engine().begin() as c:
        c.execute(sa.text("UPDATE audit_events SET hash = 'x'"))
    with pytest.raises(sa.exc.DBAPIError, match="append-only"), get_engine().begin() as c:
        c.execute(sa.text("DELETE FROM audit_events"))


def test_viewer_cannot_change_state(client_factory) -> None:
    from helpers import add_member

    alice, vic = client_factory("alice"), client_factory("vic")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    add_member(alice.me["memberships"][0]["organization"]["id"], vic.me["user"]["id"], "viewer")
    assert vic.get(f"/api/v1/projects/{pid}").status_code == 200
    r = vic.patch(f"/api/v1/projects/{pid}", json={"name": "pwned"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


def test_placeholder_settings_mean_unconfigured() -> None:
    from backend.settings import Settings

    s = Settings(
        _env_file=None,
        rl_checkpoint_path="",
        rl_topology_path="  ",
        github_app_id="replace-me",
        github_webhook_secret="replace-me",
        anthropic_api_key="",
        anthropic_model_fast="replace-me",
    )
    assert s.rl_checkpoint_path is None and s.rl_topology_path is None
    assert s.github_app_id is None and s.github_webhook_secret is None
    assert s.anthropic_api_key is None and s.anthropic_model_fast is None
