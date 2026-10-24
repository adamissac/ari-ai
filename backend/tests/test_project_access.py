"""GET /projects/{id} must enforce org membership, like PATCH does."""

from __future__ import annotations


def _create_project(alice) -> str:
    r = alice.post("/api/v1/projects", json={"name": "secret"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_other_identity_is_denied(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = _create_project(alice)
    r = eve.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert "secret" not in r.text


def test_owner_identity_is_allowed(client_factory) -> None:
    alice = client_factory("alice")
    pid = _create_project(alice)
    r = alice.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == pid and body["name"] == "secret"


def test_unauthenticated_project_get_is_401(client_factory) -> None:
    alice = client_factory("alice")
    pid = _create_project(alice)
    r = client_factory().get(f"/api/v1/projects/{pid}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_unknown_project_returns_404_same_as_non_member(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = _create_project(alice)
    non_member = eve.get(f"/api/v1/projects/{pid}")
    unknown = eve.get("/api/v1/projects/prj_does_not_exist")
    assert non_member.status_code == unknown.status_code == 404
    assert non_member.json()["error"]["code"] == unknown.json()["error"]["code"]
    assert non_member.json()["error"]["message"] == unknown.json()["error"]["message"]
