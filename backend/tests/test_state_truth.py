"""What the API says about repositories, history, quotas and delivery matches the database."""

from __future__ import annotations

import threading
import time

import sqlalchemy as sa
from helpers import setup_project

from backend.api.github_repos import store_repo_access
from backend.db import assessments, github_repo_access, jobs, repositories, transaction
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
        requested_at = utcnow()  # captured before waiting on the lock, as routes do
        with transaction() as conn:
            if check_project_quota(conn, ids["project"], requested_at) is not None:
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


def _app_repo(client):
    pid = _project(client, "shop")
    with transaction() as conn:
        conn.execute(
            sa.insert(github_repo_access).values(
                user_id=client.me["user"]["id"], full_name="acme/shop", installation_id=7,
                default_branch="main", private=True,
            )
        )  # fmt: skip
    r = client.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/shop", "installation_id": 7},
    )
    assert r.status_code == 201, r.text
    with transaction() as conn:
        conn.execute(sa.delete(jobs))  # drop the connect-time proposal
    return r.json()["id"]


def _recipe_jobs():
    with transaction() as conn:
        return conn.execute(sa.select(jobs.c.id).where(jobs.c.kind == "propose_build_recipe")).all()


def test_owner_can_retry_a_build_recipe_once_at_a_time(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    rid = _app_repo(alice)
    url = f"/api/v1/repositories/{rid}/recipe/retry"
    assert bob.post(url).status_code == 404  # another tenant cannot see it
    first = alice.post(url)
    assert first.status_code == 202 and first.json()["queued"] is True
    with transaction() as conn:  # counted against its project's queue limits
        assert (
            conn.execute(
                sa.select(jobs.c.project_id).where(jobs.c.id == first.json()["job_id"])
            ).scalar_one()
            == conn.execute(
                sa.select(repositories.c.project_id).where(repositories.c.id == rid)
            ).scalar_one()
        )
    again = alice.post(url)  # double click joins the pending run
    assert again.json() == {"job_id": first.json()["job_id"], "queued": False}
    assert len(_recipe_jobs()) == 1
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    assert alice.post(url).status_code == 409


def test_recipe_retry_needs_the_github_app(client_factory):
    alice = client_factory("alice")
    rid = _connect(alice, _project(alice)).json()["id"]
    assert alice.post(f"/api/v1/repositories/{rid}/recipe/retry").status_code == 422
    assert _recipe_jobs() == []


def test_installation_events_never_queue_a_disconnected_repository(client_factory):
    from helpers import post_webhook

    from backend import worker

    alice = client_factory("alice")
    rid = _app_repo(alice)
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    added = {
        "action": "added",
        "installation": {"id": 7},
        "repositories_added": [{"full_name": "acme/shop"}],
    }
    assert post_webhook(alice, added, event="installation_repositories").status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    assert _recipe_jobs() == []


def _access(user_id):
    with transaction() as conn:
        return sorted(
            conn.execute(
                sa.select(github_repo_access.c.full_name).where(
                    github_repo_access.c.user_id == user_id
                )
            ).scalars()
        )


def test_uninstalling_the_app_removes_its_repositories_from_the_picker(client_factory):
    from helpers import post_webhook

    from backend import worker

    alice = client_factory("alice")
    uid = alice.me["user"]["id"]
    org = {**ACME, "installation_id": 7}
    other = {**ACME, "full_name": "beta/api", "installation_id": 9}
    with transaction() as conn:
        store_repo_access(conn, uid, [org, other])
    deleted = {"action": "deleted", "installation": {"id": 7}}
    assert post_webhook(alice, deleted, event="installation").status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    assert _access(uid) == ["beta/api"]
    removed = {
        "action": "removed",
        "installation": {"id": 9},
        "repositories_removed": [{"full_name": "beta/api"}],
    }
    post_webhook(alice, removed, event="installation_repositories")
    worker.drain(kinds=["process_github_delivery"])
    assert _access(uid) == []


def test_a_removed_personal_installation_clears_the_users_own_repositories(
    client_factory, monkeypatch
):
    from backend.settings import Settings

    alice = client_factory("alice")
    uid = alice.me["user"]["id"]
    with transaction() as conn:
        store_repo_access(conn, uid, [{**ACME, "full_name": "Alice/app"}, ACME])
    monkeypatch.setattr(
        "backend.api.github_repos.get_settings",
        lambda: Settings(auth_dev_login_enabled=False),
    )

    class Uninstalled:
        def user_installation(self, login):
            return None

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", Uninstalled)
    body = alice.get("/api/v1/github/repositories").json()
    assert [r["full_name"] for r in body["items"]] == ["acme/shop"]  # org access stays
    assert body["live_checked"] is False


def test_automation_status_names_every_reason_a_push_would_not_be_reviewed(
    client_factory, settings_override
):
    settings_override(github_auto_commit_authors="")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)  # scope approved, repo automatic, monitoring on
    url = f"/api/v1/repositories/{ids['repo']}/automation-status"
    with transaction() as conn:
        conn.execute(
            sa.update(repositories)
            .where(repositories.c.id == ids["repo"])
            .values(installation_id=5)
        )
    status = alice.get(url).json()
    assert status["state"] == "ready" and status["reasons"] == []
    alice.patch(f"/api/v1/repositories/{ids['repo']}", json={"automatic_assessments": False})
    status = alice.get(url).json()
    assert status["state"] == "off" and status["reasons"][0]["code"] == "repository_off"
    settings_override(github_auto_commit_authors="someone")
    assert "author_allowlist" in [r["code"] for r in alice.get(url).json()["reasons"]]
    alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect")
    status = alice.get(url).json()
    assert status["state"] == "blocked" and status["reasons"][0]["code"] == "disconnected"
    assert client_factory("mallory").get(url).status_code == 404


def test_approvals_can_be_listed_for_one_repository(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)  # one scope approval targeting ids["repo"]
    other = _connect(alice, ids["project"], "acme/other").json()["id"]
    url = f"/api/v1/projects/{ids['project']}/approvals"
    everything = alice.get(url).json()["items"]
    assert everything and all(a["subject_type"] == "scope" for a in everything)
    mine = alice.get(url, params={"repo_id": ids["repo"]}).json()["items"]
    assert [a["id"] for a in mine] == [a["id"] for a in everything]
    assert alice.get(url, params={"repo_id": other}).json()["items"] == []


def test_reconnecting_a_detached_repository_needs_a_current_app_grant(client_factory, monkeypatch):
    from backend.settings import get_settings

    alice = client_factory("alice")
    pid = _project(alice)
    rid = _connect(alice, pid, "acme/shop").json()["id"]  # name-only: no installation
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    production = get_settings().model_copy(update={"app_env": "production"})
    monkeypatch.setattr("backend.api.routes.get_settings", lambda: production)
    url = f"/api/v1/repositories/{rid}/reconnect"

    refused = alice.post(url)
    assert refused.status_code == 403 and "install the App" in refused.text
    assert alice.get(f"/api/v1/repositories/{rid}").json()["disconnected"] is True

    with transaction() as conn:
        store_repo_access(conn, alice.me["user"]["id"], [ACME])  # the App reaches it again
    assert alice.post(url).status_code == 200
    repo = alice.get(f"/api/v1/repositories/{rid}").json()
    assert repo["disconnected"] is False and repo["installation_id"] == 42


def test_a_start_that_waited_for_the_lock_counts_runs_committed_meanwhile(
    client_factory, settings_override
):
    settings_override(project_assessments_per_hour="1")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    uid = alice.me["user"]["id"]
    allowed: dict[str, bool] = {}

    def first() -> None:  # starts after the second captured its time, holds the lock
        time.sleep(0.05)
        with transaction() as conn:
            allowed["first"] = check_project_quota(conn, ids["project"], utcnow()) is None
            time.sleep(0.3)
            create_assessment(
                conn, project_id=ids["project"], repo_id=ids["repo"], scope_id=ids["scope"],
                commit_sha="a" * 40, trigger=AssessmentTrigger.manual, budget=None, created_by=uid,
            )  # fmt: skip

    def second() -> None:  # captured `now` before the first run existed, then waits
        requested_at = utcnow()
        time.sleep(0.1)
        with transaction() as conn:
            allowed["second"] = check_project_quota(conn, ids["project"], requested_at) is None

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert allowed == {"first": True, "second": False}


def test_reconnect_outside_dev_refuses_when_github_cannot_verify(client_factory, monkeypatch):
    from backend.settings import get_settings

    alice = client_factory("alice")
    rid = _connect(alice, _project(alice), "acme/shop").json()["id"]
    alice.post(f"/api/v1/repositories/{rid}/disconnect")
    with transaction() as conn:
        store_repo_access(conn, alice.me["user"]["id"], [ACME])  # only the sign-in snapshot
    production = get_settings().model_copy(update={"app_env": "production"})
    monkeypatch.setattr("backend.api.routes.get_settings", lambda: production)
    monkeypatch.setattr("backend.api.github_repos.get_settings", lambda: production)
    r = alice.post(f"/api/v1/repositories/{rid}/reconnect")
    assert r.status_code == 503, r.text  # App not configured in tests: never trust the snapshot
    assert alice.get(f"/api/v1/repositories/{rid}").json()["disconnected"] is True


def test_personal_installation_is_never_trusted_by_login_alone_outside_dev(
    client_factory, monkeypatch
):
    from backend.api.github_repos import _refresh_personal_installation_repositories
    from backend.settings import Settings

    alice = client_factory("alice")
    uid = alice.me["user"]["id"]
    with transaction() as conn:
        store_repo_access(conn, uid, [{**ACME, "full_name": "alice/app"}])
    production = Settings(app_env="production")
    monkeypatch.setattr("backend.api.github_repos.get_settings", lambda: production)

    class Anyone:
        def user_installation(self, login):
            raise AssertionError("must not ask GitHub without an account id")

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", Anyone)
    assert _refresh_personal_installation_repositories(uid, "alice", None) is False
    assert _access(uid) == ["alice/app"]  # nothing refreshed or deleted on a name match


def test_automation_status_reads_the_quota_without_locking_the_project(client_factory):
    from backend.db import projects

    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    with transaction() as conn:  # hold the start lock, as a start in flight would
        conn.execute(
            sa.select(projects.c.id).where(projects.c.id == ids["project"]).with_for_update()
        )
        status = alice.get(f"/api/v1/repositories/{ids['repo']}/automation-status")
        assert status.status_code == 200


def test_reconnect_reattaches_a_live_repository_whose_grant_was_detached(
    client_factory, monkeypatch
):
    from backend.settings import get_settings

    alice = client_factory("alice")
    rid = _connect(alice, _project(alice), "acme/shop").json()["id"]  # live, no installation
    with transaction() as conn:
        store_repo_access(conn, alice.me["user"]["id"], [ACME])  # the App reaches it again
    production = get_settings().model_copy(update={"app_env": "production"})
    monkeypatch.setattr("backend.api.routes.get_settings", lambda: production)
    assert alice.post(f"/api/v1/repositories/{rid}/reconnect").status_code == 200
    repo = alice.get(f"/api/v1/repositories/{rid}").json()
    assert repo["disconnected"] is False and repo["installation_id"] == 42


def test_connect_rechecks_the_users_own_github_access_live(client_factory, monkeypatch):
    from backend.db import users
    from backend.settings import get_settings

    alice = client_factory("alice")
    with transaction() as conn:
        store_repo_access(conn, alice.me["user"]["id"], [ACME])  # sign-in snapshot says yes
        conn.execute(
            sa.update(users).where(users.c.id == alice.me["user"]["id"]).values(github_id=4242)
        )
    production = get_settings().model_copy(update={"app_env": "production"})
    monkeypatch.setattr("backend.api.github_repos.get_settings", lambda: production)
    seen: dict[str, object] = {"permission": "read"}

    class GitHub:
        def user_installation(self, login):
            return None

        def installation_repositories(self, installation_id):
            return [ACME]  # the App still reaches the repository

        def collaborator_permission(self, installation_id, full_name, login, github_id):
            seen["login"], seen["github_id"] = login, github_id
            return seen["permission"]

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", GitHub)
    pid = _project(alice)
    body = {"full_name": "acme/shop", "installation_id": 42, "default_branch": "main"}
    refused = alice.post(f"/api/v1/projects/{pid}/repositories", json=body)
    assert refused.status_code == 403 and "write access" in refused.text
    assert seen["login"] == "alice" and seen["github_id"] == 4242
    seen["permission"] = "write"
    assert alice.post(f"/api/v1/projects/{pid}/repositories", json=body).status_code == 201


def test_collaborator_permission_uses_the_base_permission_not_a_custom_role_name(monkeypatch):
    import httpx

    from backend.github import GitHubApp

    app = GitHubApp.__new__(GitHubApp)
    answers = {
        "custom": {"permission": "write", "role_name": "security-engineer", "user": {"id": 7}},
        "renamed": {"permission": "admin", "user": {"id": 8}},  # the login now names account 8
        "nobody": None,
    }

    def get(installation_id, path, **params):
        body = answers[path.rsplit("/", 2)[-2]]
        if body is None:
            raise httpx.HTTPStatusError("404", request=None, response=httpx.Response(404))
        return body

    monkeypatch.setattr(app, "_get", get, raising=False)
    assert app.collaborator_permission(1, "acme/shop", "custom", 7) == "write"
    assert app.collaborator_permission(1, "acme/shop", "renamed", 7) == "none"
    assert app.collaborator_permission(1, "acme/shop", "nobody", 7) == "none"


def test_rows_for_a_login_now_owned_by_another_account_are_dropped(client_factory, monkeypatch):
    from backend.api.github_repos import _refresh_personal_installation_repositories
    from backend.settings import Settings

    alice = client_factory("alice")
    uid = alice.me["user"]["id"]
    with transaction() as conn:
        store_repo_access(conn, uid, [{**ACME, "full_name": "alice/app"}, ACME])
    monkeypatch.setattr(
        "backend.api.github_repos.get_settings", lambda: Settings(app_env="production")
    )

    class Renamed:
        def user_installation(self, login):  # "alice" now belongs to account 999
            return {"id": 5, "account": {"type": "User", "id": 999, "login": "alice"}}

        def installation_repositories(self, installation_id):
            raise AssertionError("must not list another account's repositories")

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", Renamed)
    assert _refresh_personal_installation_repositories(uid, "alice", 123) is False
    assert _access(uid) == ["acme/shop"]  # organization access stays; old personal rows gone
