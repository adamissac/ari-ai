"""GET /repositories/{repo_id} must enforce project membership (tenant isolation)."""

from __future__ import annotations

from helpers import setup_project


def test_non_member_cannot_read_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    eve = client_factory("eve")
    ids = setup_project(alice, bob)
    url = f"/api/v1/repositories/{ids['repo']}"

    resp = eve.get(url)
    assert resp.status_code in (403, 404), resp.text
    assert "full_name" not in resp.text


def test_member_can_read_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)

    resp = alice.get(f"/api/v1/repositories/{ids['repo']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == ids["repo"]
    assert body["project_id"] == ids["project"]


def test_unauthenticated_read_is_rejected(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()

    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401


def test_missing_repository_is_404(client_factory) -> None:
    alice = client_factory("alice")
    assert alice.get("/api/v1/repositories/repo_does_not_exist").status_code == 404
