"""GET /projects/{id} must authorize every request; no cross-request project cache."""

from __future__ import annotations

import sqlalchemy as sa
from helpers import add_member

from backend.db import memberships, transaction


def _create_project(alice, name: str = "secret") -> str:
    r = alice.post("/api/v1/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_non_member_gets_404_after_member_warmed_the_cache(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = _create_project(alice)
    assert alice.get(f"/api/v1/projects/{pid}").status_code == 200  # warm
    r = bob.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404
    assert "secret" not in r.text


def test_unauthenticated_get_is_401_after_member_warmed_the_cache(client_factory) -> None:
    alice = client_factory("alice")
    pid = _create_project(alice)
    assert alice.get(f"/api/v1/projects/{pid}").status_code == 200
    anon = client_factory()
    r = anon.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 401
    assert "secret" not in r.text


def test_member_gets_project_body_on_repeated_requests(client_factory) -> None:
    alice = client_factory("alice")
    pid = _create_project(alice)
    for _ in range(3):
        r = alice.get(f"/api/v1/projects/{pid}")
        assert r.status_code == 200
        assert r.json()["id"] == pid and r.json()["name"] == "secret"


def test_removed_member_loses_read_access_on_next_request(client_factory) -> None:
    alice, carol = client_factory("alice"), client_factory("carol")
    pid = _create_project(alice)
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, carol.me["user"]["id"], "viewer")
    assert carol.get(f"/api/v1/projects/{pid}").status_code == 200  # warm as member
    with transaction() as conn:
        conn.execute(
            sa.delete(memberships).where(
                memberships.c.org_id == org_id,
                memberships.c.user_id == carol.me["user"]["id"],
            )
        )
    assert carol.get(f"/api/v1/projects/{pid}").status_code == 404


def test_patch_then_get_returns_updated_name(client_factory) -> None:
    alice = client_factory("alice")
    pid = _create_project(alice)
    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "secret"
    r = alice.patch(f"/api/v1/projects/{pid}", json={"name": "renamed"})
    assert r.status_code == 200, r.text
    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "renamed"
