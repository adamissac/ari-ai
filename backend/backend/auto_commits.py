"""Per-commit push scheduling. Identity comes from GitHub, never a commit's email."""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend import jobs
from backend.db import monitoring_events, reassessment_requests, repositories, transaction
from backend.github import GitHubApp
from backend.services import active_scope_for_repo, create_assessment, project_settings
from backend.settings import get_settings
from backend.worker import JobContext, handler
from shared.assessment import AssessmentTrigger
from shared.base import utcnow
from shared.ids import IdPrefix, new_id
from shared.monitoring import (
    CommitRange,
    EventSource,
    EventStatus,
    EventType,
    MonitoringEvent,
    ReassessmentRequest,
    ReassessmentScope,
    ReassessmentStatus,
)


def authors() -> set[str]:
    return {
        s.strip().lower() for s in get_settings().github_auto_commit_authors.split(",") if s.strip()
    }


def schedule(
    conn: Connection, repo: Any, delivery: Any, payload: dict[str, Any], change: Any
) -> dict[str, Any]:
    if change.event != "push":
        return {"ignored": "automatic commit rollout accepts pushes only"}
    installation = repo["installation_id"]
    if not installation or (payload.get("installation") or {}).get("id") != installation:
        return {"ignored": "push installation does not match connected repository"}
    commits = payload.get("commits") or []
    shas = [c.get("id") for c in commits if isinstance(c, dict)]
    # Compare is paginated; webhook payloads can truncate large pushes.
    if change.base_sha and (len(commits) >= 20 or not commits):
        shas = GitHubApp().compare_commits(
            installation, repo["full_name"], change.base_sha, change.head_sha
        )
    elif not change.base_sha and len(commits) >= 2048:
        raise ValueError("new-branch push exceeds GitHub payload limit; cannot enumerate safely")
    shas.append(change.head_sha)
    if any(
        not isinstance(s, str) or not re.fullmatch(r"[0-9a-f]{40}", s) or s == "0" * 40
        for s in shas
    ):
        raise ValueError("push contains an invalid commit SHA")
    queued = []
    for sha in dict.fromkeys(shas):
        job_id, _ = jobs.enqueue(
            conn,
            "assess_github_commit",
            {
                "repo_id": repo["id"],
                "sha": sha,
                "installation_id": installation,
                "payload_artifact_id": delivery["payload_artifact_id"],
                "ref": change.ref,
            },
            dedupe_key=f"github:commit:{repo['id']}:{sha}",
            priority=60,
        )
        queued.append(job_id)
    return {"commit_jobs": queued}


@handler("assess_github_commit")
def assess_commit(ctx: JobContext) -> dict[str, Any]:
    p = ctx.job.payload
    allowed = authors()
    if not allowed:
        return {"ignored": "automatic commit rollout disabled"}
    with transaction() as conn:
        repo = (
            conn.execute(sa.select(repositories).where(repositories.c.id == p["repo_id"]))
            .mappings()
            .one()
        )
    if repo["installation_id"] != p["installation_id"]:
        return {"ignored": "repository installation changed"}
    commit = GitHubApp().commit(repo["installation_id"], repo["full_name"], p["sha"])
    if commit.get("sha") != p["sha"]:
        raise ValueError("GitHub returned a different commit")
    login = (commit.get("author") or {}).get("login", "").lower()
    if not login or ("*" not in allowed and login not in allowed):
        return {"ignored": "commit author is outside the automatic rollout"}
    ctx.check_cancelled()
    with transaction() as conn:
        # Serialize retries, duplicate deliveries, and scope activation for this repo.
        repo = (
            conn.execute(
                sa.select(repositories).where(repositories.c.id == p["repo_id"]).with_for_update()
            )
            .mappings()
            .one()
        )
        if repo["installation_id"] != p["installation_id"]:
            return {"ignored": "repository installation changed"}
        if not project_settings(conn, repo["project_id"]).monitoring_policy.enabled:
            return {"ignored": "monitoring disabled"}
        key = f"github:commit:{repo['id']}:{p['sha']}"
        existing = (
            conn.execute(sa.select(monitoring_events).where(monitoring_events.c.dedupe_key == key))
            .mappings()
            .first()
        )
        rrq = None
        if existing:
            row = conn.execute(
                sa.select(reassessment_requests.c.doc).where(
                    reassessment_requests.c.repo_id == repo["id"],
                    reassessment_requests.c.doc["event_ids"].contains([existing["id"]]),
                )
            ).scalar_one()
            rrq = ReassessmentRequest.model_validate(row)
            if rrq.assessment_id:
                return {"assessment_id": rrq.assessment_id, "idempotent_replay": True}
        scope = active_scope_for_repo(conn, repo["project_id"], repo["id"])
        reason = "automatic commit assessment" if scope else "waiting for repository scope approval"
        if existing is None:
            event = MonitoringEvent(
                id=new_id(IdPrefix.evt),
                project_id=repo["project_id"],
                repo_id=repo["id"],
                source=EventSource.github,
                type=EventType.push,
                occurred_at=utcnow(),
                received_at=utcnow(),
                dedupe_key=key,
                payload_artifact_id=p["payload_artifact_id"],
                commit_range=CommitRange(head_sha=p["sha"]),
                ref=p["ref"],
                status=EventStatus.processed,
                status_reason=reason,
            )
            conn.execute(
                sa.insert(monitoring_events).values(
                    id=event.id,
                    project_id=event.project_id,
                    repo_id=event.repo_id,
                    dedupe_key=key,
                    status=event.status.value,
                    doc=event.model_dump(mode="json"),
                )
            )
            rrq = ReassessmentRequest(
                id=new_id(IdPrefix.rrq),
                project_id=repo["project_id"],
                repo_id=repo["id"],
                event_ids=[event.id],
                scope=ReassessmentScope.full,
                head_sha=p["sha"],
                status=ReassessmentStatus.blocked_no_scope,
                reason=reason,
                created_at=utcnow(),
            )
        assert rrq is not None
        if scope:
            asm, _ = create_assessment(
                conn,
                project_id=repo["project_id"],
                repo_id=repo["id"],
                scope_id=scope.id,
                commit_sha=p["sha"],
                trigger=AssessmentTrigger.monitoring,
                budget=None,
                created_by=None,
                reassessment_request_id=rrq.id,
            )
            rrq = rrq.model_copy(
                update={
                    "assessment_id": asm.id,
                    "status": ReassessmentStatus.started,
                    "reason": reason,
                }
            )
        values = dict(status=rrq.status.value, doc=rrq.model_dump(mode="json"))
        if existing:
            conn.execute(
                sa.update(reassessment_requests)
                .where(reassessment_requests.c.id == rrq.id)
                .values(**values)
            )
        else:
            conn.execute(
                sa.insert(reassessment_requests).values(
                    id=rrq.id, project_id=rrq.project_id, repo_id=rrq.repo_id, **values
                )
            )
        return {
            "reassessment_request_id": rrq.id,
            "assessment_id": rrq.assessment_id,
            "status": rrq.status.value,
        }


def resume_blocked(conn: Connection, project_id: str, scope_id: str) -> None:
    """Scope activation wakes durable blocked commits; eligibility is checked again."""
    from backend.db import jobs as jobs_table

    conn.execute(
        sa.select(repositories.c.id)
        .where(repositories.c.project_id == project_id)
        .order_by(repositories.c.id)
        .with_for_update()
    ).all()
    for row in conn.execute(
        sa.select(jobs_table.c.payload)
        .join(
            repositories,
            jobs_table.c.payload["repo_id"].astext == repositories.c.id,
        )
        .where(
            jobs_table.c.kind == "assess_github_commit",
            repositories.c.project_id == project_id,
            jobs_table.c.dedupe_key.like("github:commit:%"),
        )
    ).scalars():
        blocked = conn.execute(
            sa.select(reassessment_requests.c.id).where(
                reassessment_requests.c.repo_id == row["repo_id"],
                reassessment_requests.c.doc["head_sha"].astext == row["sha"],
                reassessment_requests.c.status == ReassessmentStatus.blocked_no_scope.value,
            )
        ).first()
        if blocked:
            jobs.enqueue(
                conn,
                "assess_github_commit",
                row,
                dedupe_key=f"github:resume:{scope_id}:{row['repo_id']}:{row['sha']}",
                priority=60,
            )
