"""Incident decisions and replayable evidence timeline; no automatic real-system actions."""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from backend import incidents as service
from backend.api.deps import idempotent_finish, idempotent_replay, require_project, require_user
from backend.db import defense_recommendations, findings, incidents, transaction
from shared.incident import Incident, IncidentAction, IncidentCreate, IncidentDetail
from shared.tenancy import MemberRole

router = APIRouter(tags=["incidents"])


@router.get("/projects/{project_id}/incidents")
def list_incidents(project_id: str, request: Request) -> dict:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        return {
            "items": list(
                conn.execute(
                    sa.select(incidents.c.doc)
                    .where(incidents.c.project_id == project_id)
                    .order_by(incidents.c.created_at.desc())
                ).scalars()
            ),
            "next_cursor": None,
        }


@router.post("/projects/{project_id}/incidents", status_code=201, response_model=Incident)
def create_incident(
    project_id: str,
    body: IncidentCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    with transaction() as conn:
        user = require_user(conn, request)
        require_project(conn, user, project_id, MemberRole.owner)
        retry = {
            "route": "create_incident",
            "project_id": project_id,
            "body": body.model_dump(mode="json"),
        }
        if replay := idempotent_replay(conn, user.id, idempotency_key, retry):
            return replay
        created = service.create(conn, project_id, body, user.id)
        return idempotent_finish(conn, user.id, idempotency_key, retry, 201, created)


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: str, request: Request) -> dict:
    with transaction() as conn:
        incident = service.load(conn, incident_id)
        require_project(conn, require_user(conn, request), incident.project_id)
        finding_docs = list(
            conn.execute(
                sa.select(findings.c.doc).where(
                    findings.c.id.in_(incident.finding_ids),
                    findings.c.project_id == incident.project_id,
                )
            ).scalars()
        )
        recommendations = list(
            conn.execute(
                sa.select(defense_recommendations.c.doc).where(
                    defense_recommendations.c.id.in_(incident.recommendation_ids),
                    defense_recommendations.c.project_id == incident.project_id,
                )
            ).scalars()
        )
        return {
            "incident": incident.model_dump(mode="json"),
            "standards": {
                "alignment": "NIST SP 800-61 Rev. 3 / CSF 2.0; local workflow labels; not certification",
                "findings": [
                    {
                        "id": f["id"],
                        "standards": f.get("standards"),
                    }
                    for f in finding_docs
                ],
                "recommendations": [
                    {"id": r["id"], "d3fend": r.get("d3fend", []), "simulation_derived": True}
                    for r in recommendations
                ],
            },
        }


@router.post("/incidents/{incident_id}/actions", response_model=Incident)
@router.post(
    "/incidents/{incident_id}/transition", response_model=Incident, include_in_schema=False
)
def incident_action(
    incident_id: str,
    body: IncidentAction,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    with transaction() as conn:
        user = require_user(conn, request)
        incident = service.load(conn, incident_id, lock=True)
        require_project(conn, user, incident.project_id, MemberRole.owner)
        retry = {
            "route": "incident_action",
            "incident_id": incident_id,
            "body": body.model_dump(mode="json"),
        }
        if replay := idempotent_replay(conn, user.id, idempotency_key, retry):
            return replay
        acted = service.act(conn, incident, body, user.id)
        return idempotent_finish(conn, user.id, idempotency_key, retry, 200, acted)


@router.get("/incidents/{incident_id}/events")
def incident_events(
    incident_id: str,
    request: Request,
    after: int = Query(0, ge=0),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Finite durable SSE replay. Reconnect with Last-Event-ID for subsequent decisions."""
    with transaction() as conn:
        incident = service.load(conn, incident_id)
        require_project(conn, require_user(conn, request), incident.project_id)
    try:
        cursor = max(0, int(last_event_id)) if last_event_id else after
    except ValueError:
        cursor = after
    chunks = []
    for seq, entry in enumerate(incident.timeline, 1):
        if seq > cursor:
            chunks.append(
                f"id: {seq}\nevent: {entry.action.value}\ndata: "
                f"{json.dumps(entry.model_dump(mode='json'))}\n\n"
            )
    return StreamingResponse(
        iter(chunks), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
