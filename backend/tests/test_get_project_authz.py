"""Regression: GET /projects/{id} must enforce org membership (require_project)."""

from __future__ import annotations


def test_other_identity_is_denied(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    r = bob.get(f"/api/v1/projects/{pid}")
    assert r.status_code in (403, 404), r.text
    assert "secret" not in r.text
    # same response as a nonexistent project: no existence leak
    missing = bob.get("/api/v1/projects/prj_does_not_exist")
    assert missing.status_code == 404


def test_member_still_gets_project(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "payments"}).json()["id"]
    r = alice.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == pid and r.json()["name"] == "payments"


def test_signed_out_gets_401(client_factory) -> None:
    anon = client_factory()
    assert anon.get("/api/v1/projects/prj_does_not_exist").status_code == 401
