"""GET /repositories/{id} must enforce project membership and not leak existence."""

from helpers import setup_project


def _error_shape(response):
    body = response.json()["error"]
    return response.status_code, body["code"], body["message"], body["details"]


def test_non_member_gets_same_404_as_missing_repository(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    outsider = client_factory("outsider")

    assert alice.get(f"/api/v1/repositories/{ids['repo']}").status_code == 200

    denied = outsider.get(f"/api/v1/repositories/{ids['repo']}")
    missing = outsider.get("/api/v1/repositories/rep_does_not_exist")
    assert denied.status_code == 404
    assert missing.status_code == 404
    assert _error_shape(denied) == _error_shape(missing)


def test_nonexistent_repository_returns_not_found(client_factory):
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/rep_does_not_exist")
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "repository not found"


def test_unauthenticated_get_is_rejected(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401
