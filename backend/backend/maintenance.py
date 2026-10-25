"""Storage maintenance: bounded retention, a storage report, and threshold alerts.

Run as a sidecar next to the API/workers (`deploy/railway/start.sh`):

    python -m backend.maintenance loop     # report hourly, apply retention policy
    python -m backend.maintenance report   # one-shot JSON report (no writes)
    python -m backend.maintenance apply    # apply retention once (dry-run unless
                                           # RETENTION_DRY_RUN=false or --apply)

Design notes (docs/deploy/POSTGRES_STORAGE.md):

- Deletes are bounded: each table class is removed in `retention_batch_limit` batches
  inside short transactions, so a large first cleanup never holds one giant lock.
- `index_payloads`/`index_snapshots` carry FORCE RLS: their pruning runs inside a
  transaction that sets `ari.project_id` first, one project at a time.
- Nothing here touches audit_events (append-only, enforced by DB triggers), findings,
  approvals, authorized_scopes, or active assessments. `retention_assessment_detail_days`
  defaults to 0 (disabled) so pilot transcript evidence is never deleted by ordinary
  cleanup.
- Deleting rows frees space for reuse inside Postgres; it does not shrink the Railway
  volume. The report distinguishes "reclaimable inside Postgres" from disk that only a
  repack/restore could return (docs explain when each applies).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from backend import audit
from backend.db import (
    agent_runs,
    artifacts,
    assessment_events,
    assessments,
    findings,
    get_engine,
    idempotency_keys,
    index_payloads,
    index_snapshots,
    jobs,
    monitoring_events,
    projects,
    reassessment_requests,
    repositories,
    runtime_windows,
    sessions,
    snapshots,
    transaction,
    webhook_deliveries,
)
from backend.services import project_org
from backend.settings import Settings, get_settings
from shared.assessment import TERMINAL_STATES
from shared.audit import ActorType

log = logging.getLogger("backend.maintenance")

ALERT_THRESHOLDS_PCT = (70, 80, 90)

_TERMINAL_JOBS = ("succeeded", "failed", "cancelled", "dead")
# queued/started requests may still be feeding live work; only settled ones are history.
_TERMINAL_RRQ = ("skipped", "blocked_no_scope")


def _batch_delete(
    conn: Connection, table: sa.Table, where: sa.sql.ClauseElement, limit: int
) -> int:
    """Delete at most `limit` rows matching `where` in this transaction (ctid-batched)."""
    ctid = sa.literal_column("ctid")
    result = conn.execute(
        sa.delete(table).where(
            ctid.in_(sa.select(ctid).select_from(table).where(where).limit(limit))
        )
    )
    return result.rowcount or 0


def _days(n: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=n)


def _hours(n: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=n)


def _snapshot_protection_reasons(
    conn: Connection, project_id: str, s: Settings
) -> dict[str, set[str]]:
    from backend.intelligence_memory import expectation_decisions, verified_regression_memory

    def ids(query: sa.Select[Any]) -> set[str]:
        return {sid for sid in conn.execute(query).scalars() if sid}

    terminal = [state.value for state in TERMINAL_STATES]
    active_jobs = jobs.c.status.in_(("queued", "running"))
    snapshot_from_memory = verified_regression_memory.join(
        snapshots, verified_regression_memory.c.snapshot_id == snapshots.c.id
    ).join(repositories, snapshots.c.repo_id == repositories.c.id)
    snapshot_from_decisions = expectation_decisions.join(
        snapshots, expectation_decisions.c.snapshot_id == snapshots.c.id
    ).join(repositories, snapshots.c.repo_id == repositories.c.id)
    assessment_job_join = jobs.join(
        assessments, jobs.c.payload["assessment_id"].as_string() == assessments.c.id
    )
    all_assessments = ids(
        sa.select(assessments.c.doc["snapshot_id"].as_string())
        .where(assessments.c.project_id == project_id)
        .where(assessments.c.doc["snapshot_id"].as_string().is_not(None))
    )
    reasons = {
        "a_findings": ids(
            sa.select(findings.c.doc["snapshot_id"].as_string())
            .where(findings.c.project_id == project_id)
            .where(findings.c.doc["snapshot_id"].as_string().is_not(None))
        ),
        "b_verified_regression_memory": ids(
            sa.select(verified_regression_memory.c.snapshot_id)
            .select_from(snapshot_from_memory)
            .where(repositories.c.project_id == project_id)
        ),
        "c_expectation_decisions": ids(
            sa.select(expectation_decisions.c.snapshot_id)
            .select_from(snapshot_from_decisions)
            .where(repositories.c.project_id == project_id)
        ),
        "d_non_terminal_assessments": ids(
            sa.select(assessments.c.doc["snapshot_id"].as_string())
            .where(assessments.c.project_id == project_id)
            .where(assessments.c.state.notin_(terminal))
            .where(assessments.c.doc["snapshot_id"].as_string().is_not(None))
        ),
        "e_active_jobs": ids(
            sa.select(jobs.c.payload["snapshot_id"].as_string())
            .where(active_jobs)
            .where(jobs.c.payload["snapshot_id"].as_string().is_not(None))
        )
        | ids(
            sa.select(assessments.c.doc["snapshot_id"].as_string())
            .select_from(assessment_job_join)
            .where(active_jobs)
            .where(assessments.c.project_id == project_id)
            .where(assessments.c.doc["snapshot_id"].as_string().is_not(None))
        ),
        "f_all_assessments": (
            all_assessments if s.retention_protect_assessment_snapshots else set()
        ),
    }
    return reasons


def _protected_snapshot_ids(conn: Connection, s: Settings) -> set[str]:
    """Return ready snapshot references that retention must not remove."""
    project_id = conn.execute(
        sa.text("SELECT current_setting('ari.project_id', true)")
    ).scalar_one_or_none()
    if not project_id:
        raise RuntimeError("snapshot protection requires a scoped project transaction")
    reasons = _snapshot_protection_reasons(conn, project_id, s)
    return set().union(*reasons.values())


def _assessment_snapshot_ids(conn: Connection, project_id: str) -> set[str]:
    return {
        sid
        for sid in conn.execute(
            sa.select(assessments.c.doc["snapshot_id"].as_string())
            .where(assessments.c.project_id == project_id)
            .where(assessments.c.doc["snapshot_id"].as_string().is_not(None))
        ).scalars()
        if sid
    }


def _snapshot_is_protected(
    conn: Connection, project_id: str, snapshot_id: str, s: Settings
) -> bool:
    from backend.intelligence_memory import expectation_decisions, verified_regression_memory

    terminal = [state.value for state in TERMINAL_STATES]
    active_jobs = jobs.c.status.in_(("queued", "running"))
    snapshot_from_memory = verified_regression_memory.join(
        snapshots, verified_regression_memory.c.snapshot_id == snapshots.c.id
    ).join(repositories, snapshots.c.repo_id == repositories.c.id)
    snapshot_from_decisions = expectation_decisions.join(
        snapshots, expectation_decisions.c.snapshot_id == snapshots.c.id
    ).join(repositories, snapshots.c.repo_id == repositories.c.id)
    assessment_job_join = jobs.join(
        assessments, jobs.c.payload["assessment_id"].as_string() == assessments.c.id
    )
    checks = [
        sa.exists(
            sa.select(1)
            .select_from(findings)
            .where(
                findings.c.project_id == project_id,
                findings.c.doc["snapshot_id"].as_string() == snapshot_id,
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(snapshot_from_memory)
            .where(
                repositories.c.project_id == project_id,
                verified_regression_memory.c.snapshot_id == snapshot_id,
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(snapshot_from_decisions)
            .where(
                repositories.c.project_id == project_id,
                expectation_decisions.c.snapshot_id == snapshot_id,
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(assessments)
            .where(
                assessments.c.project_id == project_id,
                assessments.c.state.notin_(terminal),
                assessments.c.doc["snapshot_id"].as_string() == snapshot_id,
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(jobs)
            .where(
                active_jobs,
                jobs.c.payload["snapshot_id"].as_string() == snapshot_id,
            )
        ),
        sa.exists(
            sa.select(1)
            .select_from(assessment_job_join)
            .where(
                active_jobs,
                assessments.c.project_id == project_id,
                assessments.c.doc["snapshot_id"].as_string() == snapshot_id,
            )
        ),
    ]
    if s.retention_protect_assessment_snapshots:
        checks.append(
            sa.exists(
                sa.select(1)
                .select_from(assessments)
                .where(
                    assessments.c.project_id == project_id,
                    assessments.c.doc["snapshot_id"].as_string() == snapshot_id,
                )
            )
        )
    return any(conn.execute(sa.select(*checks)).one())


def _scope_tenant(conn: Connection, project_id: str) -> None:
    """Same RLS predicate the payload store uses (backend/intel_store.py)."""
    conn.execute(sa.text("SELECT set_config('ari.project_id', :pid, true)"), {"pid": project_id})


def _payload_prune_targets(
    conn: Connection, project_id: str, s: Settings
) -> tuple[set[str], set[str]]:
    """(orphan snapshot_ids, superseded ready snapshot_ids) for one project.

    Caller must already hold an RLS-scoped transaction (`_scope_tenant`).
    """
    keep = s.retention_snapshots_per_repo
    grace = _days(s.retention_snapshot_grace_days)
    assessment_grace = _days(s.retention_assessment_snapshot_days)
    orphan_grace = _hours(s.retention_orphan_grace_hours)

    ready_ids = set(
        conn.execute(
            sa.select(index_snapshots.c.snapshot_id).where(
                index_snapshots.c.project_id == project_id
            )
        ).scalars()
    )

    # Orphans: payload rows never marked ready and older than the orphan grace window
    # (covers failed/abandoned index jobs; an in-flight index run is younger than this).
    orphan_snapshots = set(
        conn.execute(
            sa.select(index_payloads.c.snapshot_id)
            .where(index_payloads.c.project_id == project_id)
            .where(index_payloads.c.created_at < orphan_grace)
            .where(index_payloads.c.snapshot_id.notin_(ready_ids) if ready_ids else sa.true())
            .distinct()
        ).scalars()
    )

    # Superseded snapshots remain protected by durable findings, memory, decisions,
    # active work, and (by default) any assessment reference.
    repo_ids = (
        conn.execute(
            sa.select(index_snapshots.c.repo_id)
            .where(index_snapshots.c.project_id == project_id)
            .distinct()
        )
        .scalars()
        .all()
    )
    protected = _protected_snapshot_ids(conn, s)
    assessment_ids = _assessment_snapshot_ids(conn, project_id)
    prunable_ready: set[str] = set()
    for rid in repo_ids:
        ranked = conn.execute(
            sa.select(index_snapshots.c.snapshot_id, index_snapshots.c.created_at)
            .where(index_snapshots.c.project_id == project_id)
            .where(index_snapshots.c.repo_id == rid)
            .order_by(index_snapshots.c.created_at.desc())
        ).all()
        for sid, created in ranked[keep:]:
            age_cutoff = assessment_grace if sid in assessment_ids else grace
            if sid not in protected and created < age_cutoff:
                prunable_ready.add(sid)
    return orphan_snapshots, prunable_ready


def _prune_index_payloads(
    engine: Engine,
    project_id: str,
    s: Settings,
    *,
    dry_run: bool,
    confirmed_snapshot_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Prune orphan + superseded ready payloads for one project.

    Every transaction touching index_payloads/index_snapshots re-sets ari.project_id.
    Orphans are batch-deleted; each ready snapshot is locked, rechecked, and deleted in
    its own short transaction.
    """
    batch = s.retention_batch_limit
    with transaction(engine) as conn:
        _scope_tenant(conn, project_id)
        orphans, superseded = _payload_prune_targets(conn, project_id, s)
        if confirmed_snapshot_ids is not None:
            orphans.intersection_update(confirmed_snapshot_ids)
            superseded.intersection_update(confirmed_snapshot_ids)
        targets = sorted(orphans | superseded)
        payload_stats = conn.execute(
            sa.select(
                sa.func.count(),
                sa.func.coalesce(sa.func.sum(index_payloads.c.size_bytes), 0),
            )
            .where(index_payloads.c.project_id == project_id)
            .where(index_payloads.c.snapshot_id.in_(targets))
        ).first()
        orphan_stats = conn.execute(
            sa.select(
                sa.func.count(),
                sa.func.coalesce(sa.func.sum(index_payloads.c.size_bytes), 0),
            )
            .where(index_payloads.c.project_id == project_id)
            .where(index_payloads.c.snapshot_id.in_(orphans))
        ).first()
        ready_ids = set(
            conn.execute(
                sa.select(index_snapshots.c.snapshot_id).where(
                    index_snapshots.c.project_id == project_id
                )
            ).scalars()
        )
        protection_reasons = _snapshot_protection_reasons(conn, project_id, s)
        protected_counts = {
            reason: len(ids & ready_ids) for reason, ids in protection_reasons.items()
        }
        payload_rows, payload_bytes = int(payload_stats[0]), int(payload_stats[1])
        orphan_payload_bytes = int(orphan_stats[1])

    skipped_now_protected = 0
    deleted_payload_rows = 0
    deleted_payload_bytes = 0
    deleted_snapshot_rows = 0
    pruned_snapshot_ids: list[str] = []
    if not dry_run and orphans:
        while True:
            with transaction(engine) as conn:
                _scope_tenant(conn, project_id)
                n = _batch_delete(
                    conn,
                    index_payloads,
                    sa.and_(
                        index_payloads.c.project_id == project_id,
                        index_payloads.c.snapshot_id.in_(orphans),
                    ),
                    batch,
                )
            deleted_payload_rows += n
            if n < batch:
                break
        deleted_payload_bytes += orphan_payload_bytes

    if not dry_run:
        for snapshot_id in sorted(superseded):
            with transaction(engine) as conn:
                _scope_tenant(conn, project_id)
                ready = conn.execute(
                    sa.text(
                        "SELECT 1 FROM index_snapshots "
                        "WHERE project_id = :project_id AND snapshot_id = :snapshot_id "
                        "FOR UPDATE"
                    ),
                    {"project_id": project_id, "snapshot_id": snapshot_id},
                ).first()
                if ready is None:
                    continue
                if _snapshot_is_protected(conn, project_id, snapshot_id, s):
                    skipped_now_protected += 1
                    continue
                payload = conn.execute(
                    sa.select(
                        sa.func.count(),
                        sa.func.coalesce(sa.func.sum(index_payloads.c.size_bytes), 0),
                    ).where(
                        index_payloads.c.project_id == project_id,
                        index_payloads.c.snapshot_id == snapshot_id,
                    )
                ).one()
                payload_result = conn.execute(
                    sa.delete(index_payloads).where(
                        index_payloads.c.project_id == project_id,
                        index_payloads.c.snapshot_id == snapshot_id,
                    )
                )
                snapshot_result = conn.execute(
                    sa.delete(index_snapshots).where(
                        index_snapshots.c.project_id == project_id,
                        index_snapshots.c.snapshot_id == snapshot_id,
                    )
                )
                deleted_payload_rows += payload_result.rowcount or 0
                deleted_payload_bytes += int(payload[1])
                deleted_snapshot_rows += snapshot_result.rowcount or 0
                if snapshot_result.rowcount:
                    pruned_snapshot_ids.append(snapshot_id)

    if not dry_run and targets:
        payload_rows = deleted_payload_rows
        payload_bytes = deleted_payload_bytes
        snap_rows = deleted_snapshot_rows
        with transaction(engine) as conn:
            audit.record(
                conn,
                org_id=project_org(conn, project_id),
                project_id=project_id,
                actor_type=ActorType.system,
                actor_id="maintenance",
                action="maintenance.retention",
                subject_type="project",
                subject_id=project_id,
                details={
                    "dry_run": False,
                    "payload_rows": payload_rows,
                    "payload_bytes": payload_bytes,
                    "orphan_snapshots": len(orphans),
                    "superseded_snapshots": deleted_snapshot_rows,
                    "skipped_now_protected": skipped_now_protected,
                },
            )
    else:
        snap_rows = len(superseded)
    return {
        "payload_rows": payload_rows,
        "payload_bytes": payload_bytes,
        "index_snapshot_rows": snap_rows,
        "orphan_snapshots": len(orphans),
        "superseded_snapshots": (deleted_snapshot_rows if not dry_run else len(superseded)),
        "protected_snapshots": protected_counts,
        "skipped_now_protected": skipped_now_protected,
        "snapshot_ids": targets,
        "pruned_snapshot_ids": pruned_snapshot_ids,
    }


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _prune_assessment_detail(conn: Connection, s: Settings, *, dry_run: bool) -> dict[str, int]:
    """Optional transcript pruning — disabled unless retention_assessment_detail_days > 0."""
    if s.retention_assessment_detail_days <= 0:
        return {}
    cutoff = _days(s.retention_assessment_detail_days)
    terminal_ids = sa.select(assessments.c.id).where(
        assessments.c.state.in_([st.value for st in TERMINAL_STATES])
    )
    out = {}
    for table in (assessment_events, agent_runs):
        if dry_run:
            out[table.name] = conn.execute(
                sa.select(sa.func.count())
                .select_from(table)
                .where(table.c.assessment_id.in_(terminal_ids))
                .where(table.c.created_at < cutoff)
            ).scalar_one()
        else:
            total = 0
            while True:
                n = _batch_delete(
                    conn,
                    table,
                    sa.and_(
                        table.c.assessment_id.in_(terminal_ids),
                        table.c.created_at < cutoff,
                    ),
                    s.retention_batch_limit,
                )
                total += n
                if n < s.retention_batch_limit:
                    break
            out[table.name] = total
    return out


def _du(path: Path) -> int:
    total = 0
    try:
        for dirpath, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _artifact_root(s: Settings) -> Path | None:
    parsed = urlparse(s.artifact_store_uri)
    if parsed.scheme not in ("file", ""):
        return None
    return Path((parsed.netloc + parsed.path) or ".").expanduser()


def _gc_artifact_orphans(conn: Connection, s: Settings, *, dry_run: bool) -> dict[str, int]:
    """Delete artifact files on disk with no artifacts row, older than the grace window."""
    root = _artifact_root(s)
    if root is None or not root.is_dir():
        return {}
    cutoff = time.time() - s.retention_orphan_artifact_hours * 3600
    files: list[tuple[str, Path]] = []
    base = root / "sha256"
    if base.is_dir():
        for sub in base.iterdir():
            if not sub.is_dir() or len(sub.name) != 2:
                continue
            for f in sub.iterdir():
                if f.is_file() and len(f.name) == 64 and f.stat().st_mtime < cutoff:
                    files.append((f.name, f))
    if not files:
        return {"artifact_orphan_files": 0, "artifact_orphan_bytes": 0}
    known = {
        r[0]
        for r in conn.execute(
            sa.select(artifacts.c.sha256).where(artifacts.c.sha256.in_([h for h, _ in files]))
        )
    }
    orphans = [(h, p) for h, p in files if h not in known]
    nbytes = sum(p.stat().st_size for _, p in orphans)
    if not dry_run:
        for _h, p in orphans:
            try:
                p.unlink()
            except OSError:
                pass
    return {"artifact_orphan_files": len(orphans), "artifact_orphan_bytes": nbytes}


def _gc_checkout_refs(s: Settings, *, dry_run: bool) -> dict[str, Any]:
    """Trim refs/ari/* inside each bare clone and repack so objects stop accumulating."""
    workdir = s.security_workdir
    if workdir is None:
        return {}
    repos_dir = workdir / "repos"
    if not repos_dir.is_dir():
        return {}
    keep = s.retention_checkout_refs_keep
    per_repo: dict[str, dict[str, int]] = {}
    for repo in sorted(repos_dir.iterdir()):
        if not repo.is_dir() or not (repo / "HEAD").exists():
            continue
        try:
            out = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "for-each-ref",
                    "--sort=-committerdate",
                    "--format=%(refname)",
                    "refs/ari/",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            ).stdout.split()
            stale = out[keep:]
            per_repo[repo.name] = {"refs": len(out), "prunable_refs": len(stale)}
            if dry_run or not stale:
                continue
            for ref in stale:
                subprocess.run(
                    ["git", "-C", str(repo), "update-ref", "-d", ref],
                    capture_output=True,
                    timeout=60,
                )
            subprocess.run(
                ["git", "-C", str(repo), "gc", "--prune=now", "--quiet"],
                capture_output=True,
                timeout=1800,
            )
            per_repo[repo.name]["bytes_after"] = _du(repo)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("checkout gc skipped %s: %s", repo, exc)
    return {"checkouts": per_repo}


def _table_stats(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        sa.text(
            """
            SELECT t.relname,
                   pg_total_relation_size(t.oid) AS total_bytes,
                   pg_relation_size(t.oid) AS relation_bytes,
                   pg_indexes_size(t.oid) AS indexes_bytes,
                   s.n_live_tup, s.n_dead_tup,
                   s.last_vacuum, s.last_autovacuum, s.last_analyze, s.last_autoanalyze
            FROM pg_stat_user_tables s
            JOIN pg_class t ON t.oid = s.relid
            ORDER BY total_bytes DESC
            """
        )
    ).mappings()
    return [
        {
            "table": r["relname"],
            "total_bytes": int(r["total_bytes"]),
            "relation_bytes": int(r["relation_bytes"]),
            "indexes_bytes": int(r["indexes_bytes"]),
            "live_tuples": int(r["n_live_tup"]),
            "dead_tuples": int(r["n_dead_tup"]),
            "last_vacuum": r["last_vacuum"].isoformat() if r["last_vacuum"] else None,
            "last_autovacuum": (r["last_autovacuum"].isoformat() if r["last_autovacuum"] else None),
        }
        for r in rows
    ]


def _try_scalar(conn: Connection, sql: str) -> int | None:
    try:
        with conn.begin_nested():
            return int(conn.execute(sa.text(sql)).scalar_one())
    except sa.exc.SQLAlchemyError:
        return None


def _jobs_breakdown(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(
        sa.text(
            """
            SELECT status, count(*) AS n,
                   COALESCE(sum(pg_column_size(payload) + pg_column_size(result)
                                + pg_column_size(last_error)), 0) AS doc_bytes
            FROM jobs GROUP BY status ORDER BY n DESC
            """
        )
    )
    return {r[0]: {"rows": int(r[1]), "doc_bytes": int(r[2])} for r in rows}


def _payload_stats(engine: Engine, project_ids: list[str]) -> list[dict[str, Any]]:
    """Payload bytes by kind, aggregated per project under RLS scoping."""
    agg: dict[str, dict[str, int]] = {}
    for pid in project_ids:
        with transaction(engine) as conn:
            conn.execute(sa.text("SELECT set_config('ari.project_id', :pid, true)"), {"pid": pid})
            rows = conn.execute(
                sa.select(
                    index_payloads.c.kind,
                    sa.func.count(),
                    sa.func.coalesce(sa.func.sum(index_payloads.c.size_bytes), 0),
                ).group_by(index_payloads.c.kind)
            )
            for kind, n, nbytes in rows:
                e = agg.setdefault(kind, {"rows": 0, "bytes": 0})
                e["rows"] += int(n)
                e["bytes"] += int(nbytes)
    return [{"kind": k, **v} for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["bytes"])]


def storage_report(engine: Engine | None = None, s: Settings | None = None) -> dict[str, Any]:
    """Full storage report: database, WAL, tables, jobs, payloads, filesystem, alerts."""
    s = s or get_settings()
    engine = engine or get_engine()
    with engine.connect() as conn:
        db_bytes = _try_scalar(conn, "SELECT pg_database_size(current_database())") or 0
        wal_bytes = _try_scalar(conn, "SELECT COALESCE(sum(size),0) FROM pg_ls_waldir()")
        autovacuum = conn.execute(sa.text("SHOW autovacuum")).scalar()
        long_running = _try_scalar(
            conn,
            "SELECT count(*) FROM pg_stat_activity WHERE state <> 'idle'"
            " AND now() - xact_start > interval '10 minutes'",
        )
        slots = _try_scalar(conn, "SELECT count(*) FROM pg_replication_slots")
        tables = _table_stats(conn)
        job_stats = _jobs_breakdown(conn)
        project_ids = [r[0] for r in conn.execute(sa.select(projects.c.id))]
        assessments_by_state = {
            r[0]: int(r[1])
            for r in conn.execute(
                sa.select(assessments.c.state, sa.func.count()).group_by(assessments.c.state)
            )
        }

    payload_stats = _payload_stats(engine, project_ids)
    fs: dict[str, Any] = {}
    root = _artifact_root(s)
    if root is not None:
        fs["artifact_root"] = str(root)
        fs["artifact_bytes"] = _du(root)
    if s.security_workdir is not None:
        fs["security_workdir"] = str(s.security_workdir)
        fs["workdir_bytes"] = _du(s.security_workdir)
        checkouts = _gc_checkout_refs(s, dry_run=True).get("checkouts", {})
        fs["checkouts"] = checkouts

    limit = s.postgres_volume_bytes
    used = db_bytes + (wal_bytes or 0)
    pct = round(100.0 * used / limit, 2) if limit > 0 else None
    alerts = [
        f"postgres usage at {pct:.1f}% of configured volume ({used}/{limit} bytes)"
        for t in ALERT_THRESHOLDS_PCT
        if pct is not None and pct >= t
    ]
    data_volume_limit = s.data_volume_bytes
    data_volume_used = _du(s.data_volume_path) if s.data_volume_path.is_dir() else None
    data_volume_pct = (
        round(100.0 * data_volume_used / data_volume_limit, 2)
        if data_volume_limit > 0 and data_volume_used is not None
        else None
    )
    alerts.extend(
        f"data volume usage at {data_volume_pct:.1f}% of configured volume "
        f"({data_volume_used}/{data_volume_limit} bytes)"
        for t in ALERT_THRESHOLDS_PCT
        if data_volume_pct is not None and data_volume_pct >= t
    )
    reclaim = run_retention(engine=engine, s=s, dry_run=True)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": {"name": engine.url.database, "size_bytes": db_bytes},
        "postgres_disk_bytes": used,
        "wal_bytes": wal_bytes,
        "autovacuum": autovacuum,
        "replication_slots": slots,
        "long_running_transactions": long_running,
        "volume": {"limit_bytes": limit or None, "used_bytes": used, "pct_used": pct},
        "data_volume": {
            "path": str(s.data_volume_path),
            "limit_bytes": data_volume_limit or None,
            "used_bytes": data_volume_used,
            "pct_used": data_volume_pct,
        },
        "alerts": alerts,
        "tables": tables,
        "jobs": job_stats,
        "assessments_by_state": assessments_by_state,
        "payloads_by_kind": payload_stats,
        "filesystem": fs,
        "reclaimable": reclaim["deleted"],
    }


def run_retention(
    engine: Engine | None = None,
    s: Settings | None = None,
    *,
    dry_run: bool | None = None,
    confirmed_snapshot_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Apply bounded retention. `dry_run=None` uses settings.retention_dry_run."""
    s = s or get_settings()
    engine = engine or get_engine()
    if dry_run is None:
        dry_run = s.retention_dry_run
    batch = s.retention_batch_limit
    deleted: dict[str, Any] = {}

    classes: list[tuple[str, sa.Table, sa.sql.ClauseElement]] = [
        ("expired_sessions", sessions, sessions.c.expires_at < sa.func.now()),
        (
            "idempotency_keys",
            idempotency_keys,
            idempotency_keys.c.created_at < _days(s.retention_idempotency_days),
        ),
        (
            "terminal_jobs",
            jobs,
            sa.and_(
                jobs.c.status.in_(_TERMINAL_JOBS),
                jobs.c.updated_at < _days(s.retention_jobs_days),
            ),
        ),
        (
            "webhook_deliveries",
            webhook_deliveries,
            webhook_deliveries.c.received_at < _days(s.retention_webhook_deliveries_days),
        ),
        (
            "monitoring_events",
            monitoring_events,
            monitoring_events.c.created_at < _days(s.retention_monitoring_events_days),
        ),
        (
            "reassessment_requests",
            reassessment_requests,
            sa.and_(
                reassessment_requests.c.status.in_(_TERMINAL_RRQ),
                reassessment_requests.c.created_at < _days(s.retention_reassessment_requests_days),
            ),
        ),
        (
            "runtime_windows",
            runtime_windows,
            runtime_windows.c.window_end < _days(s.retention_runtime_windows_days),
        ),
    ]
    for name, table, where in classes:
        if dry_run:
            with transaction(engine) as conn:
                deleted[name] = conn.execute(
                    sa.select(sa.func.count()).select_from(table).where(where)
                ).scalar_one()
            continue
        total = 0
        while True:
            with transaction(engine) as conn:
                n = _batch_delete(conn, table, where, batch)
            total += n
            if n < batch:
                break
        deleted[name] = total

    # RLS-scoped payload pruning, one project at a time, batches committing per batch.
    with transaction(engine) as conn:
        project_ids = [r[0] for r in conn.execute(sa.select(projects.c.id))]
    payload_totals: dict[str, dict[str, Any]] = {}
    for pid in project_ids:
        res = _prune_index_payloads(
            engine,
            pid,
            s,
            dry_run=dry_run,
            confirmed_snapshot_ids=confirmed_snapshot_ids,
        )
        payload_totals[pid] = res

    with transaction(engine) as conn:
        detail = _prune_assessment_detail(conn, s, dry_run=dry_run)
        if detail:
            deleted.update(detail)
        orphans = _gc_artifact_orphans(conn, s, dry_run=dry_run)
        if orphans:
            deleted.update(orphans)
    if payload_totals:
        deleted["index_payloads"] = payload_totals
    checkouts = _gc_checkout_refs(s, dry_run=dry_run)
    if checkouts:
        deleted.update(checkouts)
    snapshot_ids = sorted(
        sid for result in payload_totals.values() for sid in result["snapshot_ids"]
    )
    stable_deleted = _without_byte_counts(deleted)
    plan_json = json.dumps(
        {"deleted": stable_deleted, "snapshot_ids": snapshot_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "dry_run": dry_run,
        "deleted": deleted,
        "snapshot_ids": snapshot_ids,
        "plan_digest": hashlib.sha256(plan_json.encode()).hexdigest(),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _without_byte_counts(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_byte_counts(item)
            for key, item in value.items()
            if "byte" not in key.lower()
        }
    if isinstance(value, list):
        return [_without_byte_counts(item) for item in value]
    return value


def _post_alert(url: str, payload: dict[str, Any]) -> None:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as exc:  # alerting must never take maintenance down
        log.warning("alert webhook post failed: %s", exc)


def run_once(engine: Engine | None = None, s: Settings | None = None) -> dict[str, Any]:
    """Report + retention + alerting; one maintenance cycle."""
    s = s or get_settings()
    engine = engine or get_engine()
    report = storage_report(engine, s)
    pct = report["volume"]["pct_used"]
    level = 0
    if pct is not None:
        for t in ALERT_THRESHOLDS_PCT:
            if pct >= t:
                level = t
    if level:
        log.warning(
            "postgres storage alert: %.1f%% of %d-byte volume used (level %d%%)",
            pct,
            s.postgres_volume_bytes,
            level,
        )
    if s.ops_alert_webhook_url and level:
        _post_alert(
            s.ops_alert_webhook_url,
            {
                "service": "ari-ai-backend",
                "kind": "postgres_storage",
                "pct_used": pct,
                "used_bytes": report["postgres_disk_bytes"],
                "limit_bytes": s.postgres_volume_bytes,
                "level": level,
                "top_tables": [
                    {"table": t["table"], "total_bytes": t["total_bytes"]}
                    for t in report["tables"][:5]
                ],
                "reclaimable": report["reclaimable"],
                "at": report["generated_at"],
            },
        )
    data_volume = report["data_volume"]
    data_pct = data_volume["pct_used"]
    data_level = 0
    if data_pct is not None:
        for t in ALERT_THRESHOLDS_PCT:
            if data_pct >= t:
                data_level = t
    if data_level:
        log.warning(
            "data volume storage alert: %.1f%% of %d-byte volume used (level %d%%)",
            data_pct,
            s.data_volume_bytes,
            data_level,
        )
    if s.ops_alert_webhook_url and data_level:
        _post_alert(
            s.ops_alert_webhook_url,
            {
                "service": "ari-ai-backend",
                "kind": "data_volume_storage",
                "path": data_volume["path"],
                "pct_used": data_pct,
                "used_bytes": data_volume["used_bytes"],
                "limit_bytes": data_volume["limit_bytes"],
                "level": data_level,
                "filesystem": {
                    key: value for key, value in report["filesystem"].items() if key != "checkouts"
                },
                "at": report["generated_at"],
            },
        )
    retention = run_retention(engine=engine, s=s)
    if retention["deleted"]:
        log.info("retention %s", json.dumps(retention["deleted"], default=str)[:4000])
    report["retention"] = retention
    return report


def _loop(s: Settings) -> None:
    while True:
        try:
            run_once(s=s)
        except Exception:
            log.exception("maintenance cycle failed; retrying in %ds", s.maintenance_interval_s)
        time.sleep(s.maintenance_interval_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.maintenance")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report")
    ap = sub.add_parser("apply", help="run retention once")
    ap.add_argument("--apply", action="store_true", help="override RETENTION_DRY_RUN")
    ap.add_argument("--dry-run", action="store_true", help="force dry-run")
    sub.add_parser("loop")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    if args.cmd == "report":
        print(json.dumps(storage_report(s=s), indent=2, default=str))
        return 0
    if args.cmd == "apply":
        dry = s.retention_dry_run
        if args.apply:
            dry = False
        if args.dry_run:
            dry = True
        print(json.dumps(run_retention(s=s, dry_run=dry), indent=2, default=str))
        return 0
    if args.cmd == "loop":
        if not s.maintenance_enabled:
            log.info("MAINTENANCE_ENABLED is false; exiting")
            return 0
        _loop(s)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
