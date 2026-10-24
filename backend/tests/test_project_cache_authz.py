"""GET /projects/{id} must check membership on every read (no process-global cache bypass)."""

from __future__ import annotations


def _create_project(owner, name: str = "authz-cache") -> dict:
    r = owner.post("/api/v1/projects", json={"name": name}, headers={"Idempotency-Key": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_owner_read_returns_project(client_factory):
    owner = client_factory("alice")
    project = _create_project(owner, "owner-read")
    r = owner.get(f"/api/v1/projects/{project['id']}")
    assert r.status_code == 200, r.text
    assert r.json() == project


def test_non_member_denied_after_owner_read(client_factory):
    owner = client_factory("alice")
    project = _create_project(owner, "cross-tenant")
    # Owner reads first; this used to populate the shared cache.
    assert owner.get(f"/api/v1/projects/{project['id']}").status_code == 200
    mallory = client_factory("mallory")
    r = mallory.get(f"/api/v1/projects/{project['id']}")
    assert r.status_code == 404, r.text


def test_non_member_denied_on_first_read(client_factory):
    owner = client_factory("alice")
    project = _create_project(owner, "first-read")
    mallory = client_factory("mallory")
    r = mallory.get(f"/api/v1/projects/{project['id']}")
    assert r.status_code == 404, r.text


def test_unauthenticated_read_is_401(client_factory):
    owner = client_factory("alice")
    project = _create_project(owner, "unauth")
    anon = client_factory()
    r = anon.get(f"/api/v1/projects/{project['id']}")
    assert r.status_code == 401, r.text
