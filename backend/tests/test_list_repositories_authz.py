"""GET /projects/{id}/repositories must enforce project org membership (tenant isolation)."""

from helpers import REPO, add_member


def _project_with_repo(alice):
    p = alice.post(
        "/api/v1/projects",
        json={"name": "payments-lite", "settings": {"delivery_mode": "manual"}},
    )
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": REPO, "installation_id": None}
    )
    assert r.status_code == 201, r.text
    return pid, r.json()["id"]


def test_other_identity_is_denied(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    pid, rid = _project_with_repo(alice)

    denied = bob.get(f"/api/v1/projects/{pid}/repositories")
    assert denied.status_code == 404, denied.text
    body = denied.json()
    assert "items" not in body
    assert rid not in denied.text
    assert REPO not in denied.text

    owner = alice.get(f"/api/v1/projects/{pid}/repositories")
    assert owner.status_code == 200, owner.text
    assert [item["id"] for item in owner.json()["items"]] == [rid]
    assert owner.json()["next_cursor"] is None


def test_viewer_member_of_project_org_can_list(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    pid, rid = _project_with_repo(alice)
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, bob.me["user"]["id"], role="viewer")

    resp = bob.get(f"/api/v1/projects/{pid}/repositories")
    assert resp.status_code == 200, resp.text
    assert [item["id"] for item in resp.json()["items"]] == [rid]


def test_unauthenticated_list_is_401(client_factory):
    alice = client_factory("alice")
    pid, _ = _project_with_repo(alice)
    anon = client_factory()
    assert anon.get(f"/api/v1/projects/{pid}/repositories").status_code == 401
