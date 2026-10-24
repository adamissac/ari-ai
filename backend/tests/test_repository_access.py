"""GET /repositories/{repo_id} must enforce project membership (no existence leak)."""

from __future__ import annotations

import uuid

from helpers import add_member


def _project_with_repo(alice):
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/payments-lite", "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return pid, r.json()["id"]


def test_owner_gets_repository(client_factory) -> None:
    alice = client_factory("alice")
    _, rid = _project_with_repo(alice)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == rid
    assert body["full_name"] == "acme/payments-lite"


def test_member_gets_same_repository_body(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    _, rid = _project_with_repo(alice)
    owner_body = alice.get(f"/api/v1/repositories/{rid}").json()
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"], "viewer")
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json() == owner_body


def test_non_member_gets_404_without_repository_fields(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    _, rid = _project_with_repo(alice)
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 404, r.text
    body = r.json()
    text = r.text
    assert "full_name" not in text
    assert "acme/payments-lite" not in text
    assert rid not in text
    assert body.get("full_name") is None


def test_unknown_repository_is_404_for_signed_in_user(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get(f"/api/v1/repositories/{uuid.uuid4()}")
    assert r.status_code == 404, r.text


def test_unauthenticated_request_is_401(client_factory) -> None:
    alice = client_factory("alice")
    _, rid = _project_with_repo(alice)
    anon = client_factory()
    r = anon.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 401, r.text
