"""Authorization for listing a project's repositories (GET /projects/{id}/repositories)."""

from __future__ import annotations

from helpers import add_member


def _project_with_repo(alice) -> tuple[str, str, str]:
    org_id = alice.me["memberships"][0]["organization"]["id"]
    pid = alice.post("/api/v1/projects", json={"name": "repo-authz"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/repo-authz", "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return org_id, pid, r.json()["id"]


def test_org_members_can_list_project_repositories(client_factory) -> None:
    alice, viewer = client_factory("alice"), client_factory("viewer-listing")
    org_id, pid, rid = _project_with_repo(alice)

    owner_list = alice.get(f"/api/v1/projects/{pid}/repositories")
    assert owner_list.status_code == 200, owner_list.text
    assert [item["id"] for item in owner_list.json()["items"]] == [rid]
    assert owner_list.json()["next_cursor"] is None

    add_member(org_id, viewer.me["user"]["id"], role="viewer")
    viewer_list = viewer.get(f"/api/v1/projects/{pid}/repositories")
    assert viewer_list.status_code == 200, viewer_list.text
    assert [item["id"] for item in viewer_list.json()["items"]] == [rid]


def test_non_member_cannot_list_project_repositories(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    _, pid, _ = _project_with_repo(alice)

    denied = bob.get(f"/api/v1/projects/{pid}/repositories")
    unknown = bob.get("/api/v1/projects/prj_does_not_exist/repositories")
    assert denied.status_code == 404
    assert unknown.status_code == 404
    assert denied.json()["error"]["code"] == unknown.json()["error"]["code"]
    assert denied.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert "items" not in denied.json()


def test_unauthenticated_cannot_list_project_repositories(client_factory) -> None:
    alice = client_factory("alice")
    _, pid, _ = _project_with_repo(alice)

    anon = client_factory()
    assert anon.get(f"/api/v1/projects/{pid}/repositories").status_code == 401
