"""Read routes on repositories and snapshots enforce project membership (cross-tenant -> 404)."""

from __future__ import annotations

from helpers import REPO, add_member


def _org_id(client) -> str:
    return client.me["memberships"][0]["organization"]["id"]


def test_read_routes_are_tenant_scoped_and_viewers_can_read(client_factory) -> None:
    alice = client_factory("alice")  # owner of org A
    vic = client_factory("vic")  # viewer member of org A
    carol = client_factory("carol")  # unrelated tenant, not a member of org A

    add_member(_org_id(alice), vic.me["user"]["id"], role="viewer")

    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": REPO, "installation_id": None},
    ).json()["id"]
    snap = alice.post(
        f"/api/v1/repositories/{rid}/snapshots", json={"commit_sha": "c" * 40}
    ).json()["id"]

    repo_url = f"/api/v1/repositories/{rid}"
    snaps_url = f"/api/v1/repositories/{rid}/snapshots"
    snap_url = f"/api/v1/snapshots/{snap}"

    # Non-member of the repository's project: 404, no existence leak.
    assert carol.get(repo_url).status_code == 404
    assert carol.get(snaps_url).status_code == 404
    assert carol.get(snap_url).status_code == 404

    # Same-org viewer keeps read access.
    assert vic.get(repo_url).status_code == 200
    assert vic.get(snaps_url).status_code == 200
    assert vic.get(snap_url).status_code == 200

    # Writes keep their role requirements.
    assert vic.patch(repo_url, json={"automatic_assessments": False}).status_code == 403
    assert vic.post(snaps_url, json={"commit_sha": "d" * 40}).status_code == 403
