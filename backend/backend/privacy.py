"""Tenant data purge — the functioning retention/deletion workflow.

``purge_project`` removes everything a project created, in FK-safe order:

- DB rows: findings (with records, patch candidates, verification results),
  assessment runs + events, scopes, approvals, snapshots + code-intelligence
  payloads (RLS: the transaction is scoped to the tenant being purged, so the
  delete can never reach another tenant's source), memory rows keyed by the
  project's snapshot refs, incidents, live-defense state, ingest tokens,
  monitoring/RL/live-defense rows, webhook deliveries, jobs bound to the
  project, artifact rows, and the repositories + project rows themselves.
- Filesystem: bare clones under ``SECURITY_WORKDIR/repos/{repo_id}.git`` and
  refcount-zero content-addressed artifact objects (objects still referenced
  by another project are kept — the store dedupes by content hash).

Retained by design: the hash-chained audit trail (append-only; it records
actions, not source bytes) gains no new entries from the purge — run it inside
``maintenance`` tooling and record the purge in the operator logbook.

Session rows and user accounts are out of scope: users can belong to many
orgs, so a project purge never deletes them.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from backend import jobs as jobq  # noqa: F401  (keeps table import co-located)
from backend.db import (
    agent_runs,
    analyst_handoffs,
    analyst_reviews,
    approvals,
    artifacts,
    assessment_events,
    assessments,
    audit_events,  # noqa: F401  documented: append-only, intentionally retained
    authorized_scopes,
    connected_applications,
    control_channels,
    control_grants,
    defense_recommendations,
    deploy_commit_mappings,
    emergency_stops,
    finding_records,
    findings,
    first_responder_decisions,
    first_responder_invocations,
    first_responder_modes,
    incidents,
    index_payloads,
    index_snapshots,
    ingest_tokens,
    jobs,
    live_controls,
    live_policy_decisions,
    monitoring_events,
    patch_candidates,
    projects,
    reassessment_requests,
    repositories,
    rl_evaluations,
    runtime_windows,
    snapshots,
    verification_results,
    webhook_deliveries,
)
from backend.intelligence_memory import (
    _key as _ref_key,
)
from backend.intelligence_memory import (
    expectation_decisions,
    verified_regression_memory,
)
from backend.settings import get_settings
from shared.intelligence import SnapshotRef


def _artifact_root(uri: str | None = None) -> Path | None:
    uri = uri or get_settings().artifact_store_uri
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path((parsed.netloc + parsed.path) or ".").expanduser().resolve()


def purge_project(
    engine: Engine,
    project_id: str,
    *,
    artifact_root: Path | None = None,
    workdir: Path | None = None,
) -> dict[str, Any]:
    """Delete every row and file belonging to ``project_id``. Returns counts.

    Database deletion is one transaction; filesystem cleanup runs only after
    the commit succeeds, so a partial purge never leaves an inconsistent DB.
    """
    counts: dict[str, int] = {}
    artifact_hashes: list[str] = []
    repo_ids: list[str] = []
    root = artifact_root or _artifact_root()
    workdir = workdir or get_settings().security_workdir

    with engine.begin() as conn:
        # Scope RLS to the tenant being purged: the policy guarantees deletes
        # cannot touch other tenants' payload/index rows.
        conn.execute(sa.text("SELECT set_config('ari.project_id', :p, true)"), {"p": project_id})

        repo_ids = list(
            conn.execute(
                sa.select(repositories.c.id).where(repositories.c.project_id == project_id)
            ).scalars()
        )
        asm_ids = list(
            conn.execute(
                sa.select(assessments.c.id).where(assessments.c.project_id == project_id)
            ).scalars()
        )
        fnd_ids = list(
            conn.execute(
                sa.select(findings.c.id).where(findings.c.project_id == project_id)
            ).scalars()
        )
        pat_ids = list(
            conn.execute(
                sa.select(patch_candidates.c.id).where(
                    patch_candidates.c.finding_id.in_(fnd_ids or [""])
                )
            ).scalars()
        )
        job_ids = list(
            conn.execute(
                sa.select(jobs.c.id).where(jobs.c.payload["project_id"].astext == project_id)
            ).scalars()
        )
        # webhook payload artifacts carry project_id NULL; find them via the
        # deliveries bound to this project's jobs so purge is still complete.
        wh_art_ids = list(
            conn.execute(
                sa.select(webhook_deliveries.c.payload_artifact_id).where(
                    webhook_deliveries.c.job_id.in_(job_ids or [""]),
                    webhook_deliveries.c.payload_artifact_id.is_not(None),
                )
            ).scalars()
        )
        artifact_hashes = list(
            conn.execute(
                sa.select(artifacts.c.sha256).where(
                    sa.or_(
                        artifacts.c.project_id == project_id,
                        artifacts.c.id.in_(wh_art_ids or [""]),
                    )
                )
            ).scalars()
        )
        snap_rows = conn.execute(
            sa.select(
                snapshots.c.id,
                snapshots.c.repo_id,
                snapshots.c.commit_sha,
                snapshots.c.index_version,
            ).where(snapshots.c.repo_id.in_(repo_ids or [""]))
        ).all()
        ref_keys = [
            _ref_key(
                SnapshotRef(
                    project_id=project_id,
                    repo_id=r.repo_id,
                    commit_sha=r.commit_sha,
                    snapshot_id=r.id,
                    index_version=r.index_version,
                )
            )
            for r in snap_rows
        ]

        def delete(table: sa.Table, where: Any, label: str) -> None:
            counts[label] = conn.execute(sa.delete(table).where(where)).rowcount

        # finding -> patch -> verification chain, then record/doc children
        delete(
            verification_results,
            verification_results.c.patch_id.in_(pat_ids or [""]),
            "verification_results",
        )
        delete(
            patch_candidates, patch_candidates.c.finding_id.in_(fnd_ids or [""]), "patch_candidates"
        )
        delete(
            finding_records, finding_records.c.finding_id.in_(fnd_ids or [""]), "finding_records"
        )
        delete(findings, findings.c.project_id == project_id, "findings")
        delete(agent_runs, agent_runs.c.assessment_id.in_(asm_ids or [""]), "agent_runs")
        delete(
            assessment_events,
            assessment_events.c.assessment_id.in_(asm_ids or [""]),
            "assessment_events",
        )
        delete(assessments, assessments.c.project_id == project_id, "assessments")

        # memory rows keyed by this project's snapshot refs
        delete(
            expectation_decisions,
            expectation_decisions.c.ref_key.in_(ref_keys or [""]),
            "expectation_decisions",
        )
        delete(
            verified_regression_memory,
            verified_regression_memory.c.ref_key.in_(ref_keys or [""]),
            "verified_regression_memory",
        )

        # code-intelligence source payloads + snapshot indexes (RLS-scoped)
        delete(index_payloads, index_payloads.c.project_id == project_id, "index_payloads")
        delete(index_snapshots, index_snapshots.c.project_id == project_id, "index_snapshots")

        # every other project-scoped table
        for table, label in (
            (monitoring_events, "monitoring_events"),
            (reassessment_requests, "reassessment_requests"),
            (live_policy_decisions, "live_policy_decisions"),
            (live_controls, "live_controls"),
            (control_grants, "control_grants"),
            (control_channels, "control_channels"),
            (emergency_stops, "emergency_stops"),
            (first_responder_modes, "first_responder_modes"),
            (first_responder_decisions, "first_responder_decisions"),
            (first_responder_invocations, "first_responder_invocations"),
            (deploy_commit_mappings, "deploy_commit_mappings"),
            (analyst_handoffs, "analyst_handoffs"),
            (analyst_reviews, "analyst_reviews"),
            (connected_applications, "connected_applications"),
            (ingest_tokens, "ingest_tokens"),
            (runtime_windows, "runtime_windows"),
            (defense_recommendations, "defense_recommendations"),
            (authorized_scopes, "authorized_scopes"),
            (approvals, "approvals"),
            (snapshots, None),
        ):
            if table is snapshots:
                delete(snapshots, snapshots.c.repo_id.in_(repo_ids or [""]), "snapshots")
            else:
                delete(table, table.c.project_id == project_id, label)  # type: ignore[attr-defined]

        # webhook deliveries reference jobs + artifact ids, not project_id
        delete(
            webhook_deliveries,
            webhook_deliveries.c.job_id.in_(job_ids or [""]),
            "webhook_deliveries",
        )
        delete(
            artifacts,
            sa.or_(
                artifacts.c.project_id == project_id,
                artifacts.c.id.in_(wh_art_ids or [""]),
            ),
            "artifacts",
        )

        # jobs + RL evaluations bind the project inside their JSON payload/doc
        delete(jobs, jobs.c.payload["project_id"].astext == project_id, "jobs")
        delete(
            rl_evaluations,
            rl_evaluations.c.doc["project_id"].astext == project_id,
            "rl_evaluations",
        )
        delete(incidents, incidents.c.project_id == project_id, "incidents")
        # per-user idempotency response caches may embed the project's API
        # responses — delete any cached body that mentions the id (best-effort)
        from backend.db import idempotency_keys

        delete(
            idempotency_keys,
            sa.cast(idempotency_keys.c.response_body, sa.Text).contains(project_id),
            "idempotency_keys",
        )

        delete(repositories, repositories.c.project_id == project_id, "repositories")
        delete(projects, projects.c.id == project_id, "projects")

    # ---- filesystem cleanup (post-commit only) ----
    removed_files = 0
    if root is not None:
        for sha in set(artifact_hashes):
            still = False
            with engine.begin() as conn:
                still = bool(
                    conn.execute(
                        sa.select(artifacts.c.id).where(artifacts.c.sha256 == sha).limit(1)
                    ).scalar()
                )
            if still:
                continue
            obj = root / "sha256" / sha[:2] / sha
            if obj.exists():
                obj.unlink()
                removed_files += 1
    if workdir is not None:
        for rid in repo_ids:
            clone = Path(workdir) / "repos" / f"{rid}.git"
            if clone.exists():
                shutil.rmtree(clone)
                removed_files += 1
    counts["files_removed"] = removed_files
    return counts
