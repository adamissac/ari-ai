"""GET /projects/{id}/repositories must enforce org membership (no cross-tenant listing)."""

from helpers import add_member


def _project_with_repo(client, name: str) -> tuple[str, str]:
    p = client.post("/api/v1/projects", json={"name": name})
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    r = client.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": f"acme/{name}", "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return pid, r.json()["id"]


def test_non_member_cannot_list_repositories_of_another_org(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    bob_pid, bob_rid = _project_with_repo(bob, "bob-private")

    r = alice.get(f"/api/v1/projects/{bob_pid}/repositories")
    assert r.status_code == 404, r.text
    assert bob_rid not in r.text
    assert "items" not in r.json()


def test_org_member_with_viewer_role_can_list_own_project_repositories(client_factory):
    alice, carol = client_factory("alice"), client_factory("carol")
    pid, rid = _project_with_repo(alice, "alice-proj")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, carol.me["user"]["id"], role="viewer")

    r = carol.get(f"/api/v1/projects/{pid}/repositories")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [item["id"] for item in body["items"]] == [rid]
    assert body["next_cursor"] is None


def test_unauthenticated_repository_listing_is_rejected(client_factory):
    alice = client_factory("alice")
    pid, _ = _project_with_repo(alice, "alice-anon")

    anon = client_factory()
    r = anon.get(f"/api/v1/projects/{pid}/repositories")
    assert r.status_code == 401, r.text
