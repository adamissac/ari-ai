"""GET /repositories/{repo_id} must enforce project membership like every other repo route."""

from helpers import add_member, setup_project

REPO_FIELDS = {
    "id",
    "project_id",
    "full_name",
    "default_branch",
    "installation_id",
    "automatic_assessments",
    "created_at",
}


def _repo_url(repo_id: str) -> str:
    return f"/api/v1/repositories/{repo_id}"


def test_non_member_is_denied_with_same_response_as_missing_repo(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    mallory = client_factory("mallory")

    existing = mallory.get(_repo_url(ids["repo"]))
    missing = mallory.get(_repo_url("rep_does_not_exist"))

    assert existing.status_code == 404, existing.text
    assert missing.status_code == 404, missing.text

    # request_id is per-request; the error code, message and details must be identical
    def error_fields(response):
        error = response.json()["error"]
        return {k: v for k, v in error.items() if k != "request_id"}

    assert error_fields(existing) == error_fields(missing)


def test_project_members_and_owner_can_read_repository(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    carol = client_factory("carol")
    add_member(ids["org"], carol.me["user"]["id"], role="viewer")

    for client in (alice, bob, carol):
        response = client.get(_repo_url(ids["repo"]))
        assert response.status_code == 200, response.text
        body = response.json()
        assert REPO_FIELDS <= set(body)
        assert body["id"] == ids["repo"]
        assert body["project_id"] == ids["project"]
        assert body["full_name"] == "acme/payments-lite"


def test_unauthenticated_repository_read_is_rejected(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    anonymous = client_factory()

    response = anonymous.get(_repo_url(ids["repo"]))

    assert response.status_code == 401, response.text
