"""Workstream 1 (execution reliability) compatibility tests — skip-gated.

The separate ``feat/devin-execution-reliability`` branch adds durable job
lifecycle contracts the Live Defense e2e suite will rely on once it merges:

- new ``JobStatus`` values: ``waiting``, ``timed_out``, ``recovery_required``
- ``jobs.enqueue(..., deadline_s=, depends_on=, project_id=)``
- fair, per-project-concurrency-limited ``jobs.claim``
- ``jobs.begin_effect`` / ``end_effect`` effect tracking with
  ``recovery_required`` for uncertain side effects
- ``execution.reconcile`` for stale workers and expired deadlines

Every test here is skipped until that branch lands (detected by the presence
of ``jobs.JobStatus.recovery_required``). They pin the queue contracts this
suite assumes, so integration regressions surface as test failures rather
than silent behavior drift.

Existing e2e scenarios needing review when the branch merges:
- ``test_e_worker_failure`` — requeue/backoff assertions still hold, but a
  step job that declared an effect would land in ``recovery_required`` instead
  of being retried (agent steps currently declare no effects).
- ``test_j_queue_redelivery`` — the terminal-invocation early return is
  unchanged, but ``revive_job`` bypasses the WS1 state machine; a real
  redelivery path is ``lease_expires_at`` expiry + re-claim, which is what the
  compat test below exercises instead of raw status rewriting.
- ``test_i_concurrent_workers`` — claims serialize on an advisory lock once
  per-project limits are enabled; expected single-execution semantics hold.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from backend import jobs, worker
from backend.db import jobs as jobs_t
from backend.db import transaction
from shared.base import utcnow
from shared.ids import IdPrefix, new_id

pytest.importorskip("security_agents")

_HAS_EXEC_RELIABILITY = hasattr(jobs, "JobStatus") and hasattr(jobs.JobStatus, "recovery_required")

pytestmark = [
    pytest.mark.live_defense_e2e,
    pytest.mark.skipif(
        not _HAS_EXEC_RELIABILITY,
        reason="execution-reliability branch not merged: jobs.JobStatus has no new states",
    ),
]

_ORDER: list[str] = []
_KIND = "live_defense_e2e_compat_noop"


@worker.handler(_KIND)
def _noop(ctx: worker.JobContext) -> dict[str, object]:
    _ORDER.append(str(ctx.job.payload["tag"]))
    return {"ok": True}


def _enqueue(conn, tag: str, project_id: str, **kwargs) -> str:
    jid, _created = jobs.enqueue(
        conn, _KIND, {"tag": tag, "project_id": project_id}, project_id=project_id, **kwargs
    )
    return jid


def test_compat_depends_on_waits_for_prerequisite():
    pid = f"prj_compat_{new_id(IdPrefix.prj)[:12]}"
    _ORDER.clear()
    with transaction() as conn:
        a = _enqueue(conn, "a", pid)
        b = _enqueue(conn, "b", pid, depends_on=a)
        status = conn.execute(sa.select(jobs_t.c.status).where(jobs_t.c.id == b)).scalar_one()
        assert status == "waiting"
    worker.drain(max_jobs=10, kinds=[_KIND])
    assert _ORDER == ["a", "b"]


def test_compat_per_project_concurrency_is_fair(settings_override):
    settings_override(job_max_running_per_project=1)
    px = f"prj_compat_x_{new_id(IdPrefix.prj)[:10]}"
    py = f"prj_compat_y_{new_id(IdPrefix.prj)[:10]}"
    with transaction() as conn:
        _enqueue(conn, "x1", px)
        _enqueue(conn, "x2", px)
        _enqueue(conn, "y1", py)
        first = jobs.claim(conn, "compat-w", 60, [_KIND])
        assert first is not None and first.project_id == px
        # X is at its concurrency limit: the next claim must be Y's job, not x2.
        second = jobs.claim(conn, "compat-w", 60, [_KIND])
        assert second is not None
        assert second.project_id == py


def test_compat_execution_deadline_times_out(settings_override):
    from backend import execution

    pid = f"prj_compat_{new_id(IdPrefix.prj)[:12]}"
    with transaction() as conn:
        jid = _enqueue(conn, "deadline", pid, deadline_s=30)
        # Move the deadline into the past, then reconcile.
        conn.execute(sa.update(jobs_t).where(jobs_t.c.id == jid).values(deadline_at=utcnow()))
        execution.reconcile(conn)
        status = conn.execute(sa.select(jobs_t.c.status).where(jobs_t.c.id == jid)).scalar_one()
        assert status == "timed_out"


def test_compat_uncertain_effect_needs_operator():
    pid = f"prj_compat_{new_id(IdPrefix.prj)[:12]}"
    with transaction() as conn:
        jid = _enqueue(conn, "effect", pid)
        job = jobs.claim(conn, "compat-w", 60, [_KIND])
        assert job is not None and job.id == jid
        assert jobs.begin_effect(conn, jid, "compat-w", "side-effect:1") is True
        outcome = jobs.fail(
            conn,
            jid,
            "compat-w",
            {"code": "WORKER_LOST", "message": "simulated worker loss"},
            retryable=True,
        )
        assert outcome == "recovery_required"
        status = conn.execute(sa.select(jobs_t.c.status).where(jobs_t.c.id == jid)).scalar_one()
        assert status == "recovery_required"
        # A job with an uncertain effect is never auto-re-claimed.
        assert jobs.claim(conn, "compat-w2", 60, [_KIND]) is None
