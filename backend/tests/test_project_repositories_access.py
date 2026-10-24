"""GET /projects/{id}/repositories must enforce project membership."""

from __future__ import annotations

from helpers import add_member

REPO = "acme/shop"


def _project_with_repo(alice) -> str:
    pid = alice.post("/api/v1/projects", json={"name": "shop"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": REPO, "installation_id": None}
    )
    assert r.status_code == 201, r.text
    return pid


def test_other_identity_is_denied(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = _project_with_repo(alice)
    r = bob.get(f"/api/v1/projects/{pid}/repositories")
    assert r.status_code == 404, r.text
    assert REPO not in r.text


def test_owner_still_lists_own_repositories(client_factory) -> None:
    alice = client_factory("alice")
    pid = _project_with_repo(alice)
    r = alice.get(f"/api/v1/projects/{pid}/repositories")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [item["full_name"] for item in body["items"]] == [REPO]
    assert body["next_cursor"] is None


def test_unauthenticated_list_is_rejected(client_factory) -> None:
    alice = client_factory("alice")
    pid = _project_with_repo(alice)
    assert client_factory().get(f"/api/v1/projects/{pid}/repositories").status_code == 401


def test_viewer_member_can_list(client_factory) -> None:
    alice, carol = client_factory("alice"), client_factory("carol")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    pid = _project_with_repo(alice)
    add_member(org_id, carol.me["user"]["id"], role="viewer")
    r = carol.get(f"/api/v1/projects/{pid}/repositories")
    assert r.status_code == 200, r.text
    assert [item["full_name"] for item in r.json()["items"]] == [REPO]
