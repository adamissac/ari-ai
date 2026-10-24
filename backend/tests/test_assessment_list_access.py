"""Regression: GET /projects/{id}/assessments must enforce project membership."""

from __future__ import annotations


def _project(alice) -> str:
    r = alice.post("/api/v1/projects", json={"name": "payments-lite"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_other_identity_is_denied(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = _project(alice)
    r = bob.get(f"/api/v1/projects/{pid}/assessments")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_owner_retains_access(client_factory) -> None:
    alice = client_factory("alice")
    pid = _project(alice)
    r = alice.get(f"/api/v1/projects/{pid}/assessments")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_unauthenticated_list_assessments_is_401(client_factory) -> None:
    alice = client_factory("alice")
    pid = _project(alice)
    r = client_factory().get(f"/api/v1/projects/{pid}/assessments")
    assert r.status_code == 401
