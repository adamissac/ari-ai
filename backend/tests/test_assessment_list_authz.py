"""Regression: GET /projects/{id}/assessments must enforce project membership."""

from __future__ import annotations

from helpers import setup_project


def test_other_identity_is_denied(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    r = eve.get(f"/api/v1/projects/{pid}/assessments")
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert "items" not in r.json()


def test_member_can_list_assessments(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    r = bob.get(f"/api/v1/projects/{ids['project']}/assessments")
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []
    assert r.json()["next_cursor"] is None


def test_unauthenticated_list_assessments_is_rejected(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    r = client_factory().get(f"/api/v1/projects/{pid}/assessments")
    assert r.status_code == 401, r.text
