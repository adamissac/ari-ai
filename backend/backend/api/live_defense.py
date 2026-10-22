"""Live Defense shadow-pilot API (Phase 2).

Connected staging apps, ingest-token metadata, recorded health/topology, and
analyst reviews of stored recommendations. Nothing here applies, isolates,
rate-limits, or blocks. ``AnalystReview.accept`` is a recorded opinion.
``DefenseHealth.status`` is always ``unknown``.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Request

from backend import audit
from backend.api.deps import not_found, require_project, require_user
from backend.db import (
    analyst_reviews,
    connected_applications,
    defense_recommendations,
    ingest_tokens,
    jobs,
    monitoring_events,
    runtime_windows,
    transaction,
)
from monitoring.runtime import ANOMALY_EVENT_THRESHOLD
from shared.audit import ActorType
from shared.base import utcnow
from shared.ids import IdPrefix, new_id
from shared.live_defense import (
    AnalystReview,
    AnalystReviewCreate,
    ApplicationVerification,
    ComponentGraph,
    ComponentHealthState,
    ComponentLink,
    ComponentNode,
    ComponentNodeKind,
    ComponentObservation,
    ComponentObservationSource,
    ConnectedApplication,
    ConnectedApplicationCreate,
    DefenseHealth,
    IngestTokenView,
    StagingEnvironment,
)
from shared.monitoring import IngestTokenCreated
from shared.tenancy import MemberRole

router = APIRouter(tags=["live-defense"])


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _token_view(row: sa.RowMapping) -> IngestTokenView:
    return IngestTokenView(
        id=row["id"],
        project_id=row["project_id"],
        application_id=row["application_id"],
        created_at=_aware(row["created_at"]) or utcnow(),
        revoked_at=_aware(row["revoked_at"]),
        last_used_at=_aware(row["last_used_at"]),
    )


def _application_from_rows(
    app_row: sa.RowMapping,
    tokens: list[sa.RowMapping],
    last_ingest_at: datetime | None,
) -> ConnectedApplication:
    active = [t for t in tokens if t["revoked_at"] is None]
    had_any = bool(tokens)
    if last_ingest_at is not None:
        verification = ApplicationVerification.ingest_seen
    elif had_any and not active:
        verification = ApplicationVerification.token_revoked
    else:
        verification = ApplicationVerification.unverified
    return ConnectedApplication(
        id=app_row["id"],
        project_id=app_row["project_id"],
        name=app_row["name"],
        environment=StagingEnvironment(app_row["environment"]),
        ingest_configured=bool(active),
        last_ingest_at=_aware(last_ingest_at),
        verification=verification,
        created_by=app_row["created_by"],
        created_at=_aware(app_row["created_at"]) or utcnow(),
    )


def _load_application(conn: sa.Connection, app_id: str) -> ConnectedApplication:
    row = (
        conn.execute(sa.select(connected_applications).where(connected_applications.c.id == app_id))
        .mappings()
        .first()
    )
    if row is None:
        raise not_found("application")
    tokens = (
        conn.execute(sa.select(ingest_tokens).where(ingest_tokens.c.application_id == app_id))
        .mappings()
        .all()
    )
    last_ingest = conn.execute(
        sa.select(sa.func.max(runtime_windows.c.window_end)).where(
            runtime_windows.c.application_id == app_id
        )
    ).scalar()
    return _application_from_rows(row, list(tokens), last_ingest)


@router.post(
    "/projects/{project_id}/applications", status_code=201, response_model=ConnectedApplication
)
def create_application(
    project_id: str, body: ConnectedApplicationCreate, request: Request
) -> ConnectedApplication:
    with transaction() as conn:
        user = require_user(conn, request)
        org_id, _ = require_project(conn, user, project_id, MemberRole.owner)
        app_id = new_id(IdPrefix.app)
        now = utcnow()
        app = ConnectedApplication(
            id=app_id,
            project_id=project_id,
            name=body.name,
            environment=body.environment,
            ingest_configured=False,
            last_ingest_at=None,
            verification=ApplicationVerification.unverified,
            created_by=user.id,
            created_at=now,
        )
        conn.execute(
            sa.insert(connected_applications).values(
                id=app_id,
                project_id=project_id,
                name=body.name,
                environment=body.environment.value,
                created_by=user.id,
                doc=app.model_dump(mode="json"),
            )
        )
        audit.record(
            conn,
            org_id=org_id,
            project_id=project_id,
            actor_type=ActorType.user,
            actor_id=user.id,
            action="live_defense.application.created",
            subject_type="connected_application",
            subject_id=app_id,
            details={"environment": body.environment.value, "shadow_mode": True},
        )
        return app


@router.get("/projects/{project_id}/applications")
def list_applications(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        rows = (
            conn.execute(
                sa.select(connected_applications)
                .where(connected_applications.c.project_id == project_id)
                .order_by(connected_applications.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        tokens = (
            conn.execute(sa.select(ingest_tokens).where(ingest_tokens.c.project_id == project_id))
            .mappings()
            .all()
        )
        last_by_app = dict(
            conn.execute(
                sa.select(
                    runtime_windows.c.application_id, sa.func.max(runtime_windows.c.window_end)
                )
                .where(
                    runtime_windows.c.project_id == project_id,
                    runtime_windows.c.application_id.is_not(None),
                )
                .group_by(runtime_windows.c.application_id)
            ).all()
        )
        by_app: dict[str, list[sa.RowMapping]] = {}
        for token in tokens:
            if token["application_id"]:
                by_app.setdefault(token["application_id"], []).append(token)
        items = [
            _application_from_rows(
                row, by_app.get(row["id"], []), last_by_app.get(row["id"])
            ).model_dump(mode="json")
            for row in rows
        ]
        return {"items": items, "next_cursor": None}


@router.get("/applications/{app_id}", response_model=ConnectedApplication)
def get_application(app_id: str, request: Request) -> ConnectedApplication:
    with transaction() as conn:
        user = require_user(conn, request)
        app = _load_application(conn, app_id)
        require_project(conn, user, app.project_id)
        return app


@router.post(
    "/applications/{app_id}/ingest-tokens", status_code=201, response_model=IngestTokenCreated
)
def create_application_ingest_token(app_id: str, request: Request) -> IngestTokenCreated:
    with transaction() as conn:
        user = require_user(conn, request)
        app = _load_application(conn, app_id)
        org_id, _ = require_project(conn, user, app.project_id, MemberRole.owner)
        token = "hkt_ing_" + secrets.token_urlsafe(32)
        tid = new_id(IdPrefix.itk)
        now = utcnow()
        conn.execute(
            sa.insert(ingest_tokens).values(
                id=tid,
                project_id=app.project_id,
                token_sha256=_sha(token),
                created_by=user.id,
                application_id=app_id,
            )
        )
        audit.record(
            conn,
            org_id=org_id,
            project_id=app.project_id,
            actor_type=ActorType.user,
            actor_id=user.id,
            action="ingest_token.created",
            subject_type="ingest_token",
            subject_id=tid,
            details={"application_id": app_id, "shown_once": True},
        )
        return IngestTokenCreated(id=tid, project_id=app.project_id, token=token, created_at=now)


@router.get("/projects/{project_id}/ingest-tokens")
def list_ingest_tokens(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id, MemberRole.owner)
        rows = (
            conn.execute(
                sa.select(ingest_tokens)
                .where(ingest_tokens.c.project_id == project_id)
                .order_by(ingest_tokens.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        return {
            "items": [_token_view(row).model_dump(mode="json") for row in rows],
            "next_cursor": None,
        }


@router.get("/projects/{project_id}/defense-health", response_model=DefenseHealth)
def defense_health(project_id: str, request: Request) -> DefenseHealth:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        worker_seen = conn.execute(sa.select(sa.func.max(jobs.c.heartbeat_at))).scalar()
        queued = conn.execute(
            sa.select(sa.func.count()).select_from(jobs).where(jobs.c.status == "queued")
        ).scalar()
        last_ingest = conn.execute(
            sa.select(sa.func.max(runtime_windows.c.window_end)).where(
                runtime_windows.c.project_id == project_id
            )
        ).scalar()
        last_event = conn.execute(
            sa.select(sa.func.max(monitoring_events.c.created_at)).where(
                monitoring_events.c.project_id == project_id,
                monitoring_events.c.doc["source"].astext == "runtime",
            )
        ).scalar()
        return DefenseHealth(
            project_id=project_id,
            worker_seen_at=_aware(worker_seen),
            queue_depth=int(queued) if queued is not None else None,
            last_ingest_at=_aware(last_ingest),
            last_runtime_event_at=_aware(last_event),
        )


@router.get("/projects/{project_id}/defense-graph", response_model=ComponentGraph)
def defense_graph(project_id: str, request: Request) -> ComponentGraph:
    """Recorded apps and ingest routes. Never marks a node healthy from HTTP 200."""
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        apps = (
            conn.execute(
                sa.select(connected_applications).where(
                    connected_applications.c.project_id == project_id
                )
            )
            .mappings()
            .all()
        )
        windows = (
            conn.execute(
                sa.select(runtime_windows)
                .where(runtime_windows.c.project_id == project_id)
                .order_by(runtime_windows.c.window_end.desc())
            )
            .mappings()
            .all()
        )
    nodes: list[ComponentNode] = []
    links: list[ComponentLink] = []
    observations: list[ComponentObservation] = []
    seen_routes: set[tuple[str | None, str]] = set()
    for app in apps:
        nodes.append(
            ComponentNode(
                id=app["id"],
                label=app["name"],
                kind=ComponentNodeKind.application,
            )
        )
        observations.append(
            ComponentObservation(
                node_id=app["id"],
                state=ComponentHealthState.unknown,
                last_checked_at=None,
                source=ComponentObservationSource.none,
                simulated=False,
                note="Applications have no health-check producer; last ingest is on child routes.",
            )
        )
    for window in windows:
        key = (window["application_id"], window["route"])
        if key in seen_routes:
            continue
        seen_routes.add(key)
        node_id = f"{window['application_id'] or 'project'}:{window['route']}"
        nodes.append(
            ComponentNode(
                id=node_id,
                label=window["route"],
                kind=ComponentNodeKind.route,
            )
        )
        if window["application_id"]:
            links.append(ComponentLink(source_id=window["application_id"], target_id=node_id))
        score = window["score"] or {}
        anomaly = float(score.get("anomaly_score") or 0)
        simulated = window["source"] != "runtime_demo"
        attention = anomaly >= ANOMALY_EVENT_THRESHOLD
        observations.append(
            ComponentObservation(
                node_id=node_id,
                state=ComponentHealthState.attention if attention else ComponentHealthState.unknown,
                last_checked_at=_aware(window["window_end"]),
                source=ComponentObservationSource.ingest,
                simulated=simulated,
                note=(
                    "Latest recorded runtime score was anomalous."
                    if attention
                    else "Latest recorded runtime window is not a health check; state stays unknown."
                ),
            )
        )
    return ComponentGraph(
        project_id=project_id,
        nodes=nodes,
        links=links,
        observations=observations,
        generated_at=utcnow(),
    )


def _review_from_row(row: sa.RowMapping) -> AnalystReview:
    return AnalystReview.model_validate(row["doc"])


@router.get("/projects/{project_id}/defense-reviews")
def list_project_reviews(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        rows = (
            conn.execute(
                sa.select(analyst_reviews)
                .where(analyst_reviews.c.project_id == project_id)
                .order_by(analyst_reviews.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        return {
            "items": [_review_from_row(row).model_dump(mode="json") for row in rows],
            "next_cursor": None,
        }


@router.get("/defense-recommendations/{rec_id}/reviews")
def list_recommendation_reviews(rec_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        rec = (
            conn.execute(
                sa.select(defense_recommendations).where(defense_recommendations.c.id == rec_id)
            )
            .mappings()
            .first()
        )
        if rec is None or rec["project_id"] is None:
            raise not_found("recommendation")
        require_project(conn, user, rec["project_id"])
        rows = (
            conn.execute(
                sa.select(analyst_reviews)
                .where(analyst_reviews.c.recommendation_id == rec_id)
                .order_by(analyst_reviews.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        return {
            "items": [_review_from_row(row).model_dump(mode="json") for row in rows],
            "next_cursor": None,
        }


@router.post(
    "/defense-recommendations/{rec_id}/reviews", status_code=201, response_model=AnalystReview
)
def create_recommendation_review(
    rec_id: str, body: AnalystReviewCreate, request: Request
) -> AnalystReview:
    """Record an analyst opinion. Accept does not enqueue work or call adapters."""
    with transaction() as conn:
        user = require_user(conn, request)
        rec = (
            conn.execute(
                sa.select(defense_recommendations).where(defense_recommendations.c.id == rec_id)
            )
            .mappings()
            .first()
        )
        if rec is None or rec["project_id"] is None:
            raise not_found("recommendation")
        org_id, _ = require_project(conn, user, rec["project_id"], MemberRole.member)
        now = utcnow()
        review = AnalystReview(
            id=new_id(IdPrefix.arv),
            project_id=rec["project_id"],
            recommendation_id=rec_id,
            decision=body.decision,
            reason=body.reason,
            reviewed_by=user.id,
            reviewed_at=now,
        )
        conn.execute(
            sa.insert(analyst_reviews).values(
                id=review.id,
                project_id=rec["project_id"],
                recommendation_id=rec_id,
                decision=body.decision.value,
                reviewed_by=user.id,
                doc=review.model_dump(mode="json"),
            )
        )
        audit.record(
            conn,
            org_id=org_id,
            project_id=rec["project_id"],
            actor_type=ActorType.user,
            actor_id=user.id,
            action="live_defense.recommendation.reviewed",
            subject_type="analyst_review",
            subject_id=review.id,
            details={
                "recommendation_id": rec_id,
                "decision": body.decision.value,
                "executes": False,
            },
        )
        return review
