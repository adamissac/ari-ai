"""GET /projects/{id} must authenticate and authorize on every request, even after a warm read."""

from __future__ import annotations


def test_non_member_is_denied_after_member_warmed_read(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    assert alice.get(f"/api/v1/projects/{pid}").status_code == 200  # warm any read cache
    assert eve.get(f"/api/v1/projects/{pid}").status_code == 404  # no existence leak


def test_unauthenticated_read_is_rejected_after_member_warmed_read(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    assert alice.get(f"/api/v1/projects/{pid}").status_code == 200
    assert client_factory().get(f"/api/v1/projects/{pid}").status_code == 401


def test_owner_read_reflects_patched_name(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "before"}).json()["id"]
    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "before"
    assert alice.patch(f"/api/v1/projects/{pid}", json={"name": "after"}).status_code == 200
    r = alice.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200 and r.json()["name"] == "after"
