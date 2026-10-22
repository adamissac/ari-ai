"""Background worker: claims jobs from Postgres and runs registered handlers.

    uv run python -m backend.worker            # run forever
    uv run python -m backend.worker --once     # drain available jobs then exit (tests/CI)

Long LLM/agent work never runs in the API process; it runs here. A heartbeat
thread extends the lease while a handler runs and surfaces cancellation.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend import jobs
from backend.db import transaction
from backend.settings import get_settings
from shared.errors import ErrorCode

log = logging.getLogger("backend.worker")


class JobCancelled(Exception):
    pass


class PermanentJobError(Exception):
    """Non-retryable failure (bad input, policy denial). Recorded, not retried."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class JobContext:
    job: jobs.Job
    owner: str
    _cancelled: threading.Event = field(default_factory=threading.Event)
    _lease_lost: threading.Event = field(default_factory=threading.Event)

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise JobCancelled(self.job.id)
        if self._lease_lost.is_set():
            raise JobCancelled(f"{self.job.id}: lease lost")


Handler = Callable[[JobContext], dict[str, Any] | None]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return deco


def _load_handlers() -> None:
    # Importing registers handlers via @handler.
    from backend import pipeline, simulated_attack  # noqa: F401
    from backend.live_defense import engine as _live_defense_engine  # noqa: F401


def _heartbeat_loop(ctx: JobContext, lease_s: int, stop: threading.Event) -> None:
    interval = max(1.0, lease_s / 3)
    while not stop.wait(interval):
        try:
            with transaction() as conn:
                ok = jobs.heartbeat(conn, ctx.job.id, ctx.owner, lease_s)
            if not ok:
                ctx._cancelled.set()
        except Exception:  # pragma: no cover - transient DB errors; lease covers us
            log.exception("heartbeat failed for %s", ctx.job.id)


def run_one(owner: str, kinds: list[str] | None = None) -> str | None:
    """Claim and execute at most one job. Returns the job id or None if queue empty."""
    _load_handlers()
    settings = get_settings()
    with transaction() as conn:
        job = jobs.claim(conn, owner, settings.worker_lease_s, kinds)
    if job is None:
        return None
    ctx = JobContext(job=job, owner=owner)
    stop = threading.Event()
    hb = threading.Thread(
        target=_heartbeat_loop, args=(ctx, settings.worker_lease_s, stop), daemon=True
    )
    hb.start()
    try:
        fn = HANDLERS.get(job.kind)
        if fn is None:
            raise PermanentJobError(ErrorCode.INTERNAL, f"no handler for job kind {job.kind!r}")
        result = fn(ctx)
        with transaction() as conn:
            jobs.complete(conn, job.id, owner, result)
        log.info("job %s (%s) succeeded", job.id, job.kind)
    except JobCancelled as exc:
        with transaction() as conn:
            jobs.fail(
                conn,
                job.id,
                owner,
                {"code": ErrorCode.CANCELLED.value, "message": str(exc)},
                retryable=False,
            )
    except PermanentJobError as exc:
        with transaction() as conn:
            jobs.fail(
                conn, job.id, owner, {"code": exc.code.value, "message": str(exc)}, retryable=False
            )
        log.warning("job %s (%s) failed permanently: %s", job.id, job.kind, exc)
    except Exception as exc:
        with transaction() as conn:
            status = jobs.fail(
                conn,
                job.id,
                owner,
                {
                    "code": ErrorCode.INTERNAL.value,
                    "message": f"{type(exc).__name__}: {exc}"[:500],
                    "trace": traceback.format_exc()[-4000:],
                },
                retryable=True,
            )
        log.exception("job %s (%s) errored; now %s", job.id, job.kind, status)
    finally:
        stop.set()
        hb.join(timeout=5)
    return job.id


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def drain(max_jobs: int = 100, kinds: list[str] | None = None) -> list[str]:
    done = []
    owner = worker_id()
    for _ in range(max_jobs):
        jid = run_one(owner, kinds)
        if jid is None:
            break
        done.append(jid)
    return done


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if a.once:
        print(f"processed {len(drain())} jobs")
        return 0
    owner = worker_id()
    log.info("worker %s started", owner)
    while True:
        if run_one(owner) is None:
            time.sleep(get_settings().worker_poll_interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
