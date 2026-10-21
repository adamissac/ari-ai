"""Signed pushes exercise real queue/DB scheduling with GitHub identity reads stubbed."""

import pytest
import sqlalchemy as sa
from helpers import HEAD, post_webhook, push_payload, setup_project

from backend import worker
from backend.db import assessments, jobs, repositories, transaction


@pytest.fixture
def automatic(client_factory, settings_override, monkeypatch):
    settings_override(github_auto_commit_authors="adamissac")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    with transaction() as conn:
        conn.execute(
            sa.update(repositories)
            .where(repositories.c.id == ids["repo"])
            .values(installation_id=99)
        )
    identity = {"login": "adamissac"}

    class GitHub:
        def commit(self, installation, repo, sha):
            return {"sha": sha, "author": identity}

    monkeypatch.setattr("backend.auto_commits.GitHubApp", GitHub)
    return alice, bob, ids, identity


def push(client, *shas):
    p = push_payload(["README.md"], head=shas[-1])
    p["commits"] = [
        {"id": sha, "modified": ["README.md"], "author": {"username": "adamissac"}} for sha in shas
    ]
    assert post_webhook(client, p).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    worker.drain(kinds=["assess_github_commit"])


def records():
    with transaction() as conn:
        return list(conn.execute(sa.select(assessments.c.commit_sha)).scalars())


def test_each_commit_runs_even_docs_only_active_and_duplicate_delivery(automatic):
    alice, bob, ids, _ = automatic
    assert bob.post(f"/api/v1/scopes/{ids['scope']}/approve").status_code == 200
    push(alice, HEAD, "c" * 40)
    push(alice, HEAD, "c" * 40)
    push(alice, "d" * 40)
    assert sorted(records()) == [HEAD, "c" * 40, "d" * 40]


def test_scope_approval_resumes_without_run_button(automatic):
    alice, bob, ids, _ = automatic
    push(alice, HEAD)
    assert records() == []
    rrqs = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]
    assert rrqs[0]["status"] == "blocked_no_scope"
    assert bob.post(f"/api/v1/scopes/{ids['scope']}/approve").status_code == 200
    worker.drain(kinds=["assess_github_commit"])
    assert records() == [HEAD]
    rrqs = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]
    assert len(rrqs) == 1 and rrqs[0]["status"] == "started"
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    assert events[0]["status_reason"] == "automatic commit assessment"


@pytest.mark.parametrize("login", ["someone-else", ""])
def test_payload_author_cannot_bypass_verified_author(automatic, login):
    alice, bob, ids, identity = automatic
    identity["login"] = login
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD)
    assert records() == []


def test_rollout_configurable_for_other_accounts(automatic, settings_override):
    alice, bob, ids, identity = automatic
    identity["login"] = "AnotherUser"
    settings_override(github_auto_commit_authors="anotheruser")
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD)
    assert records() == [HEAD]


def test_disabled_monitoring_stays_disabled(automatic):
    alice, bob, ids, _ = automatic
    settings = alice.get(f"/api/v1/projects/{ids['project']}").json()["settings"]
    settings["monitoring_policy"]["enabled"] = False
    assert (
        alice.patch(f"/api/v1/projects/{ids['project']}", json={"settings": settings}).status_code
        == 200
    )
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD)
    assert records() == []


def test_identity_api_failure_retries_without_starting(automatic, monkeypatch):
    alice, bob, ids, _ = automatic

    def fail(*args):
        raise RuntimeError("GitHub unavailable")

    monkeypatch.setattr("backend.auto_commits.GitHubApp.commit", fail)
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD)
    assert records() == []
    with transaction() as conn:
        row = (
            conn.execute(sa.select(jobs).where(jobs.c.kind == "assess_github_commit"))
            .mappings()
            .one()
        )
        assert row["status"] == "queued" and row["attempts"] == 1


def test_wrong_installation_never_enqueues(automatic):
    alice, _, _, _ = automatic
    p = push_payload(["app.py"])
    p["commits"][0]["id"] = HEAD
    p["installation"]["id"] = 101
    assert post_webhook(alice, p).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    with transaction() as conn:
        assert not conn.execute(
            sa.select(jobs.c.id).where(jobs.c.kind == "assess_github_commit")
        ).first()


def test_truncated_push_enumerates_all_commits(automatic, monkeypatch):
    alice, bob, ids, _ = automatic
    shas = [f"{i:040x}" for i in range(1, 26)]
    monkeypatch.setattr(
        "backend.auto_commits.GitHubApp.compare_commits", lambda *args: shas, raising=False
    )
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    p = push_payload(["app.py"], head=shas[-1])
    p["commits"] = [{"id": sha} for sha in shas[:20]]
    assert post_webhook(alice, p).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    worker.drain(kinds=["assess_github_commit"])
    assert sorted(records()) == shas


def test_compare_reads_subsequent_pages(monkeypatch):
    from backend.github import GitHubApp

    app = object.__new__(GitHubApp)
    pages = []

    def get(installation, path, **params):
        pages.append(params["page"])
        shas = ["a" * 40, "b" * 40] if params["page"] == 1 else ["c" * 40]
        return {"total_commits": 3, "commits": [{"sha": s} for s in shas]}

    monkeypatch.setattr(app, "_get", get)
    assert app.compare_commits(99, "acme/repo", "d" * 40, "c" * 40) == [
        "a" * 40,
        "b" * 40,
        "c" * 40,
    ]
    assert pages == [1, 2]


def test_full_run_uses_project_budget_clamped_to_operator_cap(automatic, settings_override):
    alice, bob, ids, _ = automatic
    settings_override(llm_max_tokens_per_assessment="200000", llm_max_usd_per_assessment="4")
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD)
    with transaction() as conn:
        doc = conn.execute(sa.select(assessments.c.doc)).scalar_one()
        assert doc["budget"]["max_tokens"] == 200000
        assert doc["budget"]["max_usd"] == 4


def test_mixed_author_push_runs_only_allowed_commits_even_when_head_is_other_author(
    automatic, monkeypatch
):
    alice, bob, ids, _ = automatic

    def commit(self, installation, repo, sha):
        return {"sha": sha, "author": {"login": "adamissac" if sha == HEAD else "teammate"}}

    monkeypatch.setattr("backend.auto_commits.GitHubApp.commit", commit)
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    push(alice, HEAD, "c" * 40)
    assert records() == [HEAD]
