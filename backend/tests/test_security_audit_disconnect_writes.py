"""Security audit 2026-10-27: owner disconnect must stop GitHub writes already queued.

A Verify-accepted fix enqueues ``deliver_verified_patch`` with only assessment and
verification ids, so the disconnect kill-switch's repo-linked job cancellation does not
reach it. The handler itself must refuse a disconnected repository before minting a
write token or pushing.
"""

from __future__ import annotations

import sqlalchemy as sa
from test_auto_commits import automatic, seed_pr_assessment  # noqa: F401
from test_auto_delivery import FakeApp, _actions, reference, wired  # noqa: F401
from test_build_recipes import github  # noqa: F401

from backend import worker
from backend.db import jobs, transaction


def test_disconnect_stops_a_queued_verified_fix_delivery(wired) -> None:  # noqa: F811
    alice, ids, _ = wired("auto")
    with transaction() as conn:
        queued = conn.execute(
            sa.select(jobs.c.status).where(jobs.c.kind == "deliver_verified_patch")
        ).scalar_one()
    assert queued == "queued"

    resp = alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect")
    assert resp.status_code == 200, resp.text

    worker.drain(kinds=["deliver_verified_patch"])
    assert FakeApp.calls == []
    assert "delivery.pushed" not in _actions()
    assert "delivery.pr_opened" not in _actions()


def test_disconnect_skips_a_queued_delivery_with_an_audit_reason(wired) -> None:  # noqa: F811
    alice, ids, _ = wired("pull_request")
    assert alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect").status_code == 200

    worker.drain(kinds=["deliver_verified_patch"])
    assert FakeApp.calls == []
    assert "delivery.skipped" in _actions()
    with transaction() as conn:
        status = conn.execute(
            sa.select(jobs.c.status).where(jobs.c.kind == "deliver_verified_patch")
        ).scalar_one()
    assert status == "succeeded"


def test_disconnect_during_delivery_stops_before_the_github_write(wired, monkeypatch) -> None:  # noqa: F811
    from backend import delivery

    alice, ids, _ = wired("pull_request")
    real_fetch = delivery.fetch_commit

    def fetch_then_owner_disconnects(*a, **k):
        assert alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect").status_code == 200
        return real_fetch(*a, **k)

    monkeypatch.setattr(delivery, "fetch_commit", fetch_then_owner_disconnects)
    worker.drain(kinds=["deliver_verified_patch"])
    assert FakeApp.calls == []
    assert "delivery.pr_opened" not in _actions()


def test_disconnect_stops_a_queued_pull_request_review_comment(automatic, monkeypatch) -> None:  # noqa: F811
    alice, bob, ids, _ = automatic
    seed_pr_assessment(ids, bob)
    calls: list[tuple] = []

    class GitHub:
        def post_pull_request_review(self, *args):
            calls.append(args)

    monkeypatch.setattr("backend.auto_commits.GitHubApp", GitHub)
    assert alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect").status_code == 200
    worker.drain(kinds=["post_pr_review"])
    assert calls == []


# --- Codex release review (2026-10-28): the race window and installation detachment -------------


def _installation_deleted(installation_id: int, *names: str) -> dict:
    return {
        "action": "deleted",
        "installation": {"id": installation_id, "account": {"login": "acme"}},
        "repositories": [{"full_name": n} for n in names],
        "sender": {"login": "acme"},
    }


def _detach(installation_id: int, full_name: str) -> None:
    from backend.installations import apply_lifecycle

    with transaction() as conn:
        apply_lifecycle(conn, "installation", _installation_deleted(installation_id, full_name))


def test_installation_detached_during_delivery_stops_before_the_github_write(
    wired,  # noqa: F811
    monkeypatch,
) -> None:
    from backend import delivery

    alice, ids, _ = wired("auto")
    real_fetch = delivery.fetch_commit

    def fetch_then_github_uninstalls(*a, **k):
        _detach(7, "acme/payments-lite")
        return real_fetch(*a, **k)

    monkeypatch.setattr(delivery, "fetch_commit", fetch_then_github_uninstalls)
    worker.drain(kinds=["deliver_verified_patch"])
    assert FakeApp.calls == []
    assert "delivery.pushed" not in _actions()
    assert "delivery.skipped" in _actions()


def _pr_review_recorder(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []

    class GitHub:
        def post_pull_request_review(self, *args):
            calls.append(args)

    monkeypatch.setattr("backend.auto_commits.GitHubApp", GitHub)
    return calls


def test_disconnect_right_before_the_pr_review_post_stops_it(automatic, monkeypatch) -> None:  # noqa: F811
    from backend import auto_commits

    alice, bob, ids, _ = automatic
    seed_pr_assessment(ids, bob)
    calls = _pr_review_recorder(monkeypatch)
    real_org = auto_commits.project_org

    def owner_disconnects_then(conn, project_id):
        assert alice.post(f"/api/v1/repositories/{ids['repo']}/disconnect").status_code == 200
        return real_org(conn, project_id)

    monkeypatch.setattr(auto_commits, "project_org", owner_disconnects_then)
    worker.drain(kinds=["post_pr_review"])
    assert calls == []


def test_installation_detached_before_the_pr_review_post_stops_it(automatic, monkeypatch) -> None:  # noqa: F811
    from backend import auto_commits

    _, bob, ids, _ = automatic
    seed_pr_assessment(ids, bob)
    calls = _pr_review_recorder(monkeypatch)
    real_org = auto_commits.project_org

    def github_uninstalls_then(conn, project_id):
        _detach(99, "acme/payments-lite")
        return real_org(conn, project_id)

    monkeypatch.setattr(auto_commits, "project_org", github_uninstalls_then)
    worker.drain(kinds=["post_pr_review"])
    assert calls == []


def _recipe_branch(bare) -> str:
    from test_build_recipes import _git

    return _git("branch", "--list", "ari/build-recipe", cwd=bare)


def test_disconnect_during_recipe_drafting_stops_the_push_and_pr(
    client_factory,
    github,  # noqa: F811
    monkeypatch,
) -> None:
    from test_build_recipes import SHOP, _audit, _connect
    from test_build_recipes import FakeApp as RecipeApp

    from backend import recipes

    bare = github(SHOP)
    alice = client_factory("alice")
    repo_id = _connect(alice)
    real_draft = recipes.draft

    def owner_disconnects_while_drafting(*a, **k):
        assert alice.post(f"/api/v1/repositories/{repo_id}/disconnect").status_code == 200
        return real_draft(*a, **k)

    monkeypatch.setattr(recipes, "draft", owner_disconnects_while_drafting)
    worker.drain(kinds=["propose_build_recipe"])
    assert RecipeApp.prs == []
    assert _recipe_branch(bare) == ""
    assert _audit("recipe.pr_opened") == []
    assert _audit("recipe.skipped")[0]["reason"] == "repository is disconnected"


def test_installation_detached_during_recipe_drafting_stops_the_push_and_pr(
    client_factory,
    github,  # noqa: F811
    monkeypatch,
) -> None:
    from test_build_recipes import SHOP, _audit, _connect
    from test_build_recipes import FakeApp as RecipeApp

    from backend import recipes

    bare = github(SHOP)
    _connect(client_factory("alice"))
    real_draft = recipes.draft

    def github_uninstalls_while_drafting(*a, **k):
        _detach(7, "acme/shop")
        return real_draft(*a, **k)

    monkeypatch.setattr(recipes, "draft", github_uninstalls_while_drafting)
    worker.drain(kinds=["propose_build_recipe"])
    assert RecipeApp.prs == []
    assert _recipe_branch(bare) == ""
    assert _audit("recipe.pr_opened") == []
    assert _audit("recipe.skipped")[0]["reason"] == "GitHub App installation was detached"
