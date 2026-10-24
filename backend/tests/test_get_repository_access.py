"""GET /repositories/{repo_id} must enforce project membership (no metadata leak)."""


def _repo_for_alice(client_factory):
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": "acme/shop"}
    ).json()["id"]
    return alice, rid


def test_non_member_cannot_read_repository(client_factory) -> None:
    alice, rid = _repo_for_alice(client_factory)
    bob = client_factory("bob")
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code in (403, 404), r.text
    assert "full_name" not in r.text


def test_owner_still_reads_repository(client_factory) -> None:
    alice, rid = _repo_for_alice(client_factory)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid


def test_unauthenticated_repository_read_is_rejected(client_factory) -> None:
    _, rid = _repo_for_alice(client_factory)
    anon = client_factory()
    r = anon.get(f"/api/v1/repositories/{rid}")
    assert r.status_code in (401, 403), r.text


def test_missing_repository_returns_404(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404, r.text
