"""Project membership gate: non-members get 404 (no existence leak); members keep role-level access."""

from __future__ import annotations

from helpers import add_member


def test_non_member_gets_404_and_cannot_modify_project(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]

    r = eve.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404
    assert "secret" not in r.text

    r = eve.patch(f"/api/v1/projects/{pid}", json={"name": "hijacked"})
    assert r.status_code == 404

    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "secret"


def test_viewer_member_reads_but_cannot_update_owner_can(client_factory) -> None:
    alice, vera = client_factory("alice"), client_factory("vera")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, vera.me["user"]["id"], "viewer")
    pid = alice.post("/api/v1/projects", json={"name": "payments"}).json()["id"]

    assert vera.get(f"/api/v1/projects/{pid}").status_code == 200
    assert vera.patch(f"/api/v1/projects/{pid}", json={"name": "x"}).status_code == 403
    assert alice.get(f"/api/v1/projects/{pid}").status_code == 200
    assert alice.patch(f"/api/v1/projects/{pid}", json={"name": "renamed"}).status_code == 200
