"""Real PostgreSQL/API regressions for duplicate assessment starts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
import sqlalchemy as sa
from helpers import HEAD, setup_project

from backend import audit
from backend.db import assessments, get_engine, jobs


def test_assessment_retry_key_cannot_replay_another_project(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    other = alice.post("/api/v1/projects", json={"name": "other"}).json()["id"]
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    headers = {"Idempotency-Key": "same-action"}
    first = alice.post(f"/api/v1/projects/{ids['project']}/assessments", json=body, headers=headers)
    assert first.status_code == 202, first.text
    replay = alice.post(f"/api/v1/projects/{other}/assessments", json=body, headers=headers)
    assert replay.status_code == 409, replay.text
    assert replay.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert alice.get(f"/api/v1/projects/{other}/assessments").json()["items"] == []


@pytest.mark.parametrize("conflicting", [False, True])
def test_overlapping_retries_create_one_assessment_job_and_audit(
    client_factory, monkeypatch, conflicting
) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    retry_client = client_factory("alice")
    url = f"/api/v1/projects/{ids['project']}/assessments"
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    headers = {"Idempotency-Key": "overlapping-action"}
    # Hold the original request after its lookup and before commit. An overlapping
    # retry must wait and replay, rather than pass its own empty-cache lookup.
    first_at_audit, release_first, second_dispatched = Event(), Event(), Event()
    record = audit.record

    def paused_record(conn, **kwargs):
        if kwargs.get("action") == "assessment.created" and not first_at_audit.is_set():
            first_at_audit.set()
            assert release_first.wait(10), "test did not release the first transaction"
        return record(conn, **kwargs)

    monkeypatch.setattr(audit, "record", paused_record)

    def retry():
        second_dispatched.set()
        return retry_client.post(
            url, json={**body, "commit_sha": "c" * 40} if conflicting else body, headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(alice.post, url, json=body, headers=headers)
        try:
            assert first_at_audit.wait(10)
            second = pool.submit(retry)
            assert second_dispatched.wait(10)
            # Observe the second transaction waiting inside PostgreSQL, rather than
            # relying on sleeps or thread scheduling to demonstrate overlap.
            with get_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                for _ in range(100):
                    waiting = conn.execute(
                        sa.text(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                            "AND pid <> pg_backend_pid() AND wait_event_type = 'Lock'"
                        )
                    ).scalar_one()
                    if waiting or second.done():
                        break
                    Event().wait(0.02)
                assert waiting or second.done(), "second request never reached the database"
        finally:
            release_first.set()
        first_response, second_response = first.result(timeout=10), second.result(timeout=10)
    assert first_response.status_code == 202
    if conflicting:
        assert second_response.status_code == 409
        assert second_response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    else:
        assert second_response.status_code == 202
        assert first_response.json() == second_response.json()
    with get_engine().connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(assessments)).scalar_one() == 1
        assert (
            conn.execute(
                sa.select(sa.func.count()).select_from(jobs).where(jobs.c.kind == "run_assessment")
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                sa.text(
                    "SELECT count(*) FROM audit_events WHERE doc->>'action' = 'assessment.created'"
                )
            ).scalar_one()
            == 1
        )


def test_failed_start_releases_retry_key_for_authorized_retry(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    url = f"/api/v1/projects/{ids['project']}/assessments"
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": HEAD}
    headers = {"Idempotency-Key": "retry-after-approval"}
    denied = alice.post(url, json=body, headers=headers)
    assert denied.status_code == 403
    assert bob.post(f"/api/v1/scopes/{ids['scope']}/approve").status_code == 200
    started = alice.post(url, json=body, headers=headers)
    assert started.status_code == 202, started.text
    assert alice.post(url, json=body, headers=headers).json() == started.json()
