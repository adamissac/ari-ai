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
