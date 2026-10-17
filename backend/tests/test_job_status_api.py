"""Accepted assessment job identifiers must resolve with project authorization."""

from helpers import HEAD, setup_project


def test_assessment_job_is_readable_only_by_its_project_members(client_factory):
    alice, bob, eve = client_factory("alice"), client_factory("bob"), client_factory("eve")
    ids = setup_project(alice, bob)
    accepted = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD},
    )
    assert accepted.status_code == 202, accepted.text
    url = f"/api/v1/jobs/{accepted.json()['job_id']}"
    for member in (alice, bob):
        response = member.get(url)
        assert response.status_code == 200, response.text
        job = response.json()
        assert job["id"] == accepted.json()["job_id"]
        assert job["kind"] == "run_assessment" and job["status"] == "queued"
    assert eve.get(url).status_code == 404
    assert client_factory().get(url).status_code == 401
