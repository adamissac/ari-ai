"""What the API says about repositories, history, quotas and delivery matches the database."""

from __future__ import annotations

import threading
import time

import sqlalchemy as sa
from helpers import setup_project

from backend.api.github_repos import store_repo_access
from backend.db import assessments, repositories, transaction
from backend.quota import check_project_quota
from backend.services import create_assessment
from shared.assessment import AssessmentTrigger
from shared.base import utcnow

ACME = {"full_name": "acme/shop", "installation_id": 42, "default_branch": "main", "private": True}


def _project(client, name="p"):
    r = client.post("/api/v1/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _connect(client, pid, full_name="acme/truth"):
    return client.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": full_name, "installation_id": None},
    )


def test_repeated_connect_in_the_same_project_returns_the_same_repository(client_factory):
    alice = client_factory("alice")
    pid = _project(alice)
    first, second = _connect(alice, pid), _connect(alice, pid)
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    with transaction() as conn:
        count = conn.execute(
            sa.select(sa.func.count()).where(repositories.c.full_name == "acme/truth")
        ).scalar_one()
    assert count == 1


def test_connect_of_a_disconnected_or_foreign_repository_conflicts(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = _project(alice)
    rid = _connect(alice, pid).json()["id"]
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    again = _connect(alice, pid)
    assert again.status_code == 409 and "reconnect" in again.text
    foreign = _connect(bob, _project(bob))
    assert foreign.status_code == 409 and rid not in foreign.text


def test_picker_marks_a_disconnected_repository(client_factory, monkeypatch):
    class NoInstallation:
        def user_installation(self, login):
            return None

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", NoInstallation)
    alice = client_factory("alice")
    with transaction() as conn:
        store_repo_access(conn, alice.me["user"]["id"], [ACME])
    pid = _project(alice)
    rid = _connect(alice, pid, "acme/shop").json()["id"]

    def listed():
        return alice.get("/api/v1/github/repositories").json()["items"][0]

    assert listed()["connected_repo_id"] == rid and listed()["disconnected"] is False
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    assert listed()["connected_repo_id"] == rid and listed()["disconnected"] is True
    assert alice.post(f"/api/v1/repositories/{rid}/reconnect").status_code == 200
    assert listed()["disconnected"] is False


def _seed(ids, user_id, repo_id, n, offset=0):
    """n assessments for repo_id (created under the scoped repo, then re-pointed)."""
    with transaction() as conn:
        for i in range(n):
            asm, _ = create_assessment(
                conn,
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=f"{offset + i:040x}",
                trigger=AssessmentTrigger.manual,
                budget=None,
                created_by=user_id,
            )
            if repo_id != ids["repo"]:
                doc = conn.execute(
                    sa.select(assessments.c.doc).where(assessments.c.id == asm.id)
                ).scalar_one()
                conn.execute(
                    sa.update(assessments)
                    .where(assessments.c.id == asm.id)
                    .values(repo_id=repo_id, doc={**doc, "repo_id": repo_id})
                )


def test_assessment_history_filters_by_repository_on_the_server(client_factory, settings_override):
    settings_override(project_assessments_per_hour="1000", project_assessments_per_day="1000")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    other = _connect(alice, ids["project"], "acme/other").json()["id"]
    uid = alice.me["user"]["id"]
    _seed(ids, uid, ids["repo"], 3)
    _seed(ids, uid, other, 60, offset=100)  # pushes the first repo off an unfiltered first page
    url = f"/api/v1/projects/{ids['project']}/assessments"
    unfiltered = alice.get(url).json()["items"]
    assert all(a["repo_id"] == other for a in unfiltered)
    mine = alice.get(url, params={"repo_id": ids["repo"]}).json()
    assert len(mine["items"]) == 3 and mine["next_cursor"] is None
    assert {a["repo_id"] for a in mine["items"]} == {ids["repo"]}


def test_concurrent_starts_cannot_overshoot_the_project_quota(client_factory, settings_override):
    settings_override(project_assessments_per_hour="1")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    uid = alice.me["user"]["id"]
    results: list[bool] = []

    def start(index: int) -> None:
        with transaction() as conn:
            if check_project_quota(conn, ids["project"], utcnow(), manual=True) is not None:
                results.append(False)
                return
            time.sleep(0.3)  # widen the race window between the check and the insert
            create_assessment(
                conn,
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=f"{index:040x}",
                trigger=AssessmentTrigger.manual,
                budget=None,
                created_by=uid,
            )
            results.append(True)

    threads = [threading.Thread(target=start, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1, results
    with transaction() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(assessments)).scalar_one() == 1


def test_direct_default_branch_delivery_is_refused_when_the_deployment_forbids_it(
    client_factory, settings_override
):
    settings_override(allow_auto_delivery="false")
    alice = client_factory("alice")
    pid = _project(alice)
    project = alice.get(f"/api/v1/projects/{pid}").json()
    settings = {**project["settings"], "delivery_mode": "auto"}
    r = alice.patch(f"/api/v1/projects/{pid}", json={"settings": settings})
    assert r.status_code == 422 and "pull request" in r.text
    created = alice.post(
        "/api/v1/projects", json={"name": "q", "settings": {"delivery_mode": "auto"}}
    )
    assert created.json()["settings"]["delivery_mode"] == "pull_request"
    ok = alice.patch(
        f"/api/v1/projects/{pid}",
        json={"settings": {**project["settings"], "delivery_mode": "manual"}},
    )
    assert ok.status_code == 200
