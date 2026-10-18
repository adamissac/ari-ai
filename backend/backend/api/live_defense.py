"""Live defense API: connect apps, grant controls, ingest telemetry, read incidents, decide.

Authorization: session + CSRF for people (owner role for anything that changes what the
platform may do to an application), ``Authorization: Bearer <ingest token>`` for
telemetry. Signing secrets are returned exactly once, at creation; every other response
reports only ``secret_storage: "encrypted"``.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from backend import audit, jobs
from backend.api.deps import (
    ApiError,
    CurrentUser,
    idempotent_finish,
    idempotent_replay,
    limiter,
    not_found,
    require_project,
    require_user,
)
from backend.api.runtime import _authenticate
from backend.api.webhooks import _read_bounded
from backend.db import (
    LIVE_OPEN_STATES,
    defense_actions,
    live_apps,
    live_grants,
    live_incidents,
    live_notifications,
    live_timeline,
    security_events,
    transaction,
    worker_heartbeats,
)
from backend.live_defense import authorize, engine, netguard, policy, vault
from backend.settings import get_settings
from shared.audit import ActorType
from shared.base import utcnow
from shared.errors import ErrorCode
from shared.ids import new_id
from shared.live_defense import (
    ActionGrant,
    ActionGrantCreate,
    ConnectedApp,
    ConnectedAppCreate,
    ConnectedAppCreated,
    ConnectedAppUpdate,
    DefenseAction,
    DefenseActionKind,
    LiveActionDecision,
    LiveCounts,
    LiveIncident,
    LiveIncidentDetail,
    LiveIncidentState,
    LiveIngestAck,
    LiveNotification,
    LiveStatus,
    LiveTimelineEntry,
    RLStatus,
    SecurityEventBatch,
    SecurityEventView,
    WorkerHealth,
)
from shared.tenancy import MemberRole

router = APIRouter(tags=["live-defense"])
MAX_BODY = 256 * 1024
WORKER_STALE_S = 30
S = LiveIncidentState


def _reader(conn: Connection, request: Request) -> CurrentUser:
    # The console polls these every few seconds; give reads their own, larger budget.
    user = require_user(conn, request)
    limiter.check(f"live-read:{user.id}", 900, 60)
    return user


def _writer(conn: Connection, request: Request) -> CurrentUser:
    user = require_user(conn, request)
    limiter.check(f"user:{user.id}", get_settings().rate_limit_per_minute, 60)
    return user


def _audit(
    conn: Connection,
    org_id: str,
    project_id: str,
    user: CurrentUser,
    action: str,
    sid: str,
    **details: Any,
) -> None:
    audit.record(
        conn,
        org_id=org_id,
        project_id=project_id,
        actor_type=ActorType.user,
        actor_id=user.id,
        action=action,
        subject_type="live_defense",
        subject_id=sid,
        details=details,
    )


# ------------------------------------------------------------------ views


def _grant_view(r: Any) -> ActionGrant:
    return ActionGrant(
        id=r["id"],
        app_id=r["app_id"],
        kind=r["kind"],
        max_duration_s=r["max_duration_s"],
        hourly_budget=r["hourly_budget"],
        granted_by=r["granted_by"],
        created_at=r["created_at"],
        revoked_at=r["revoked_at"],
    )


def _app_view(conn: Connection, r: Any) -> ConnectedApp:
    grants = conn.execute(
        sa.select(live_grants)
        .where(live_grants.c.app_id == r["id"], live_grants.c.revoked_at.is_(None))
        .order_by(live_grants.c.created_at)
    ).mappings()
    last = conn.execute(
        sa.select(sa.func.max(security_events.c.received_at)).where(
            security_events.c.app_id == r["id"]
        )
    ).scalar()
    return ConnectedApp(
        id=r["id"],
        project_id=r["project_id"],
        name=r["name"],
        environment=r["environment"],
        control_url=r["control_url"],
        notify_url=r["notify_url"],
        auto_response=r["auto_response"],
        enabled=r["enabled"],
        protected_sources=list(r["protected_sources"] or []),
        grants=[_grant_view(g) for g in grants],
        secret_storage="encrypted",
        created_at=r["created_at"],
        last_event_at=last,
    )


def _event_view(r: Any, app_name: str) -> SecurityEventView:
    return SecurityEventView(
        id=r["id"],
        seq=r["seq"],
        app_id=r["app_id"],
        app_name=app_name,
        kind=r["kind"],
        source_ip=r["source_ip"],
        route=r["route"],
        status=r["status"],
        severity=r["severity"],
        controlled_test=r["controlled_test"],
        occurred_at=r["occurred_at"],
        received_at=r["received_at"],
        incident_id=r["incident_id"],
        detail=r["detail"],
    )


def _incident_view(conn: Connection, r: Any, app: Any) -> LiveIncident:
    counts = conn.execute(
        sa.select(
            sa.func.count(),
            sa.func.bool_and(security_events.c.controlled_test),
        ).where(security_events.c.incident_id == r["id"], security_events.c.kind != "blocked")
    ).one()
    return LiveIncident(
        id=r["id"],
        project_id=r["project_id"],
        app_id=r["app_id"],
        app_name=app["name"],
        environment=app["environment"],
        category=r["category"],
        source=r["source"],
        severity=r["severity"],
        state=r["state"],
        rationale=r["rationale"],
        rule_id=r["rule_id"],
        event_count=counts[0],
        controlled_test=bool(counts[1]),
        opened_at=r["opened_at"],
        updated_at=r["updated_at"],
        closed_at=r["closed_at"],
        decision=r["decision"],
    )


def _action_view(r: Any) -> DefenseAction:
    return DefenseAction(
        id=r["id"],
        incident_id=r["incident_id"],
        app_id=r["app_id"],
        kind=r["kind"],
        target=r["target"],
        duration_s=r["duration_s"],
        status=r["status"],
        mode=r["mode"],
        decided_by=r["decided_by"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        activated_at=r["activated_at"],
        expires_at=r["expires_at"],
        ended_at=r["ended_at"],
        end_reason=r["end_reason"],
        verification=r["verification"],
        adapter=r["adapter"],
        error=r["error"],
    )


def _app_or_404(conn: Connection, app_id: str) -> Any:
    row = conn.execute(sa.select(live_apps).where(live_apps.c.id == app_id)).mappings().first()
    if row is None:
        raise not_found("application")
    return row


def _unsafe(field: str, exc: Exception) -> ApiError:
    return ApiError(ErrorCode.VALIDATION_FAILED, f"{field}: {exc}", 422, {"field": field})


# ------------------------------------------------------------------ applications and grants


@router.post(
    "/projects/{project_id}/live/apps", status_code=201, response_model=ConnectedAppCreated
)
def create_app(project_id: str, body: ConnectedAppCreate, request: Request) -> ConnectedAppCreated:
    for field, url in (("control_url", body.control_url), ("notify_url", body.notify_url)):
        if url:
            try:
                netguard.check_url(url)
            except netguard.UnsafeDestination as exc:
                raise _unsafe(field, exc) from exc
    secret = vault.new_signing_secret()
    try:
        ciphertext = vault.encrypt(secret)
    except vault.SecretKeyUnavailable as exc:
        raise ApiError(ErrorCode.SUBSYSTEM_UNAVAILABLE, str(exc), 503) from exc
    with transaction() as conn:
        user = _writer(conn, request)
        org_id, _ = require_project(conn, user, project_id, MemberRole.owner)
        app_id = new_id("lap")
        conn.execute(
            sa.insert(live_apps).values(
                id=app_id,
                project_id=project_id,
                name=body.name,
                environment=body.environment.value,
                control_url=body.control_url,
                notify_url=body.notify_url,
                secret_ciphertext=ciphertext,
                auto_response=body.auto_response,
                protected_sources=body.protected_sources,
                created_by=user.id,
            )
        )
        _audit(
            conn,
            org_id,
            project_id,
            user,
            "live_app.created",
            app_id,
            environment=body.environment.value,
        )
        app = _app_view(conn, _app_or_404(conn, app_id))
    return ConnectedAppCreated(app=app, signing_secret=secret)


@router.get("/projects/{project_id}/live/apps")
def list_apps(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, _reader(conn, request), project_id)
        rows = conn.execute(
            sa.select(live_apps)
            .where(live_apps.c.project_id == project_id)
            .order_by(live_apps.c.created_at)
        ).mappings()
        return {
            "items": [_app_view(conn, r).model_dump(mode="json") for r in rows],
            "next_cursor": None,
        }


@router.patch("/live/apps/{app_id}", response_model=ConnectedApp)
def update_app(app_id: str, body: ConnectedAppUpdate, request: Request) -> ConnectedApp:
    with transaction() as conn:
        user = _writer(conn, request)
        app = _app_or_404(conn, app_id)
        org_id, _ = require_project(conn, user, app["project_id"], MemberRole.owner)
        values = {k: v for k, v in body.model_dump().items() if v is not None}
        if values:
            conn.execute(sa.update(live_apps).where(live_apps.c.id == app_id).values(**values))
            _audit(conn, org_id, app["project_id"], user, "live_app.updated", app_id, **values)
        return _app_view(conn, _app_or_404(conn, app_id))


@router.post("/live/apps/{app_id}/grants", status_code=201, response_model=ActionGrant)
def create_grant(app_id: str, body: ActionGrantCreate, request: Request) -> ActionGrant:
    if body.kind in authorize.INTERNAL_KINDS:
        raise ApiError(ErrorCode.VALIDATION_FAILED, f"{body.kind} needs no grant", 422)
    with transaction() as conn:
        user = _writer(conn, request)
        app = _app_or_404(conn, app_id)
        org_id, _ = require_project(conn, user, app["project_id"], MemberRole.owner)
        conn.execute(
            sa.update(live_grants)
            .where(
                live_grants.c.app_id == app_id,
                live_grants.c.kind == body.kind.value,
                live_grants.c.revoked_at.is_(None),
            )
            .values(revoked_at=sa.func.now())
        )
        gid = new_id("lgr")
        conn.execute(
            sa.insert(live_grants).values(
                id=gid,
                app_id=app_id,
                kind=body.kind.value,
                max_duration_s=body.max_duration_s,
                hourly_budget=body.hourly_budget,
                granted_by=user.id,
            )
        )
        _audit(
            conn,
            org_id,
            app["project_id"],
            user,
            "live_grant.created",
            gid,
            kind=body.kind.value,
            max_duration_s=body.max_duration_s,
            hourly_budget=body.hourly_budget,
        )
        return _grant_view(
            conn.execute(sa.select(live_grants).where(live_grants.c.id == gid)).mappings().one()
        )


@router.post("/live/grants/{grant_id}/revoke", status_code=204)
def revoke_grant(grant_id: str, request: Request) -> None:
    with transaction() as conn:
        user = _writer(conn, request)
        g = (
            conn.execute(sa.select(live_grants).where(live_grants.c.id == grant_id))
            .mappings()
            .first()
        )
        if g is None:
            raise not_found("grant")
        app = _app_or_404(conn, g["app_id"])
        org_id, _ = require_project(conn, user, app["project_id"], MemberRole.owner)
        conn.execute(
            sa.update(live_grants)
            .where(live_grants.c.id == grant_id, live_grants.c.revoked_at.is_(None))
            .values(revoked_at=sa.func.now())
        )
        _audit(conn, org_id, app["project_id"], user, "live_grant.revoked", grant_id)


# ------------------------------------------------------------------ ingestion


def _ingest(app_id: str, header: str | None, batch: SecurityEventBatch) -> LiveIngestAck:
    with transaction() as conn:
        app = conn.execute(sa.select(live_apps).where(live_apps.c.id == app_id)).mappings().first()
        if app is None:
            raise ApiError(ErrorCode.UNAUTHENTICATED, "invalid or revoked ingest token", 401)
        token_id = _authenticate(conn, app["project_id"], header)
        if not app["enabled"]:
            raise ApiError(
                ErrorCode.CONFLICT_STATE, "application is disabled for live defense", 409
            )
        limiter.check(f"live-ingest:{token_id}", 600, 60)
        accepted = 0
        for e in batch.events:
            created = conn.execute(
                pg_insert(security_events)
                .values(
                    id=new_id("sev"),
                    app_id=app_id,
                    project_id=app["project_id"],
                    event_key=e.event_id,
                    kind=e.kind.value,
                    source_ip=e.source_ip,
                    route=e.route,
                    status=e.status,
                    severity=e.severity.value if e.severity else None,
                    controlled_test=e.controlled_test,
                    detail=e.detail,
                    occurred_at=e.occurred_at,
                    ingest_token_id=token_id,
                )
                .on_conflict_do_nothing(constraint="uq_security_events_app_event_key")
                .returning(security_events.c.id)
            ).scalar()
            accepted += int(bool(created))
        job_id = None
        if accepted:
            job_id, _ = jobs.enqueue(conn, "live_defense_process", {"app_id": app_id}, priority=10)
        return LiveIngestAck(
            accepted=accepted, duplicates=len(batch.events) - accepted, job_id=job_id
        )


@router.post("/ingest/live/{app_id}", status_code=202, response_model=LiveIngestAck)
async def ingest_events(app_id: str, request: Request) -> JSONResponse:
    raw = await _read_bounded(request, MAX_BODY)
    try:
        batch = SecurityEventBatch.model_validate_json(raw)
    except ValidationError as exc:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            "invalid security event batch",
            422,
            {"errors": json.loads(exc.json(include_url=False, include_input=False))[:20]},
        ) from exc
    ack = await run_in_threadpool(_ingest, app_id, request.headers.get("Authorization"), batch)
    return JSONResponse(ack.model_dump(mode="json"), status_code=202)


# ------------------------------------------------------------------ reads


@router.get("/projects/{project_id}/live/status", response_model=LiveStatus)
def live_status(project_id: str, request: Request) -> LiveStatus:
    settings = get_settings()
    configured, loadable, version, reason = policy.rl_status()
    with transaction() as conn:
        require_project(conn, _reader(conn, request), project_id)
        now = utcnow()
        workers = [
            WorkerHealth(
                worker_id=w.worker_id,
                last_seen=w.last_seen,
                age_s=round((now - w.last_seen).total_seconds(), 1),
                healthy=(now - w.last_seen).total_seconds() <= WORKER_STALE_S,
            )
            for w in conn.execute(
                sa.select(worker_heartbeats)
                .where(worker_heartbeats.c.last_seen > now - timedelta(hours=1))
                .order_by(worker_heartbeats.c.last_seen.desc())
                .limit(10)
            )
        ]
        apps = [
            _app_view(conn, r)
            for r in conn.execute(
                sa.select(live_apps).where(live_apps.c.project_id == project_id)
            ).mappings()
        ]
        last_event = max((a.last_event_at for a in apps if a.last_event_at), default=None)
        inc = live_incidents.c

        def n(*cond: Any) -> int:
            return conn.execute(
                sa.select(sa.func.count())
                .select_from(live_incidents)
                .where(inc.project_id == project_id, *cond)
            ).scalar_one()

        act = defense_actions.c
        app_ids = [a.id for a in apps] or ["-"]

        def a(*cond: Any) -> int:
            return conn.execute(
                sa.select(sa.func.count())
                .select_from(defense_actions)
                .where(act.app_id.in_(app_ids), *cond)
            ).scalar_one()

        counts = LiveCounts(
            active_incidents=n(inc.state.in_(LIVE_OPEN_STATES)),
            resolved_incidents=n(inc.state == S.RESOLVED.value),
            escalated_incidents=n(inc.state == S.ESCALATED.value),
            failed_incidents=n(
                inc.state.in_([S.FAILED.value, S.DENIED.value, S.ROLLED_BACK.value])
            ),
            automatic_actions_executed=a(act.mode == "automatic", act.activated_at.is_not(None)),
            pending_approvals=a(act.status == "pending_approval"),
            active_controls=a(act.status.in_(engine.LIVE_ACTIVE)),
        )
    worker_ok = any(w.healthy for w in workers)
    enabled = [x for x in apps if x.enabled]
    stale = settings.live_defense_stale_after_s
    if not enabled:
        mon, why = "inactive", "no enabled connected application"
    elif not worker_ok:
        mon, why = (
            "offline",
            (
                "no worker heartbeat in the last 30 s: events are stored but not processed"
                if workers
                else "no worker has reported a heartbeat"
            ),
        )
    elif last_event is None:
        mon, why = "stale", "no security event has been received yet"
    elif (now - last_event).total_seconds() > stale:
        mon, why = (
            "stale",
            f"last event {int((now - last_event).total_seconds())} s ago (limit {stale} s)",
        )
    else:
        mon, why = "active", "worker healthy and telemetry current"
    return LiveStatus(
        project_id=project_id,
        monitoring=mon,
        monitoring_reason=why,
        workers=workers,
        worker_healthy=worker_ok,
        last_event_at=last_event,
        stale_after_s=stale,
        apps=apps,
        rl=RLStatus(
            configured=configured, loadable=loadable, policy_version=version, reason=reason[:500]
        ),
        counts=counts,
        generated_at=now,
    )


@router.get("/projects/{project_id}/live/events")
def list_events(
    project_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    before: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, _reader(conn, request), project_id)
        q = (
            sa.select(security_events, live_apps.c.name)
            .join(live_apps, live_apps.c.id == security_events.c.app_id)
            .where(security_events.c.project_id == project_id)
        )
        if before:
            q = q.where(security_events.c.seq < before)
        rows = (
            conn.execute(q.order_by(security_events.c.seq.desc()).limit(limit + 1)).mappings().all()
        )
        items = [_event_view(r, r["name"]).model_dump(mode="json") for r in rows[:limit]]
        cursor = str(rows[limit - 1]["seq"]) if len(rows) > limit else None
        return {"items": items, "next_cursor": cursor}


@router.get("/projects/{project_id}/live/incidents")
def list_incidents(
    project_id: str, request: Request, limit: int = Query(50, ge=1, le=200)
) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, _reader(conn, request), project_id)
        apps = {
            r["id"]: r
            for r in conn.execute(
                sa.select(live_apps).where(live_apps.c.project_id == project_id)
            ).mappings()
        }
        rows = conn.execute(
            sa.select(live_incidents)
            .where(live_incidents.c.project_id == project_id)
            .order_by(live_incidents.c.opened_at.desc())
            .limit(limit)
        ).mappings()
        return {
            "items": [
                _incident_view(conn, r, apps[r["app_id"]]).model_dump(mode="json") for r in rows
            ],
            "next_cursor": None,
        }


@router.get("/live/incidents/{incident_id}", response_model=LiveIncidentDetail)
def incident_detail(incident_id: str, request: Request) -> LiveIncidentDetail:
    with transaction() as conn:
        user = _reader(conn, request)
        r = (
            conn.execute(sa.select(live_incidents).where(live_incidents.c.id == incident_id))
            .mappings()
            .first()
        )
        if r is None:
            raise not_found("incident")
        require_project(conn, user, r["project_id"])
        app = _app_or_404(conn, r["app_id"])
        timeline = [
            LiveTimelineEntry(
                seq=t["seq"],
                at=t["at"],
                from_state=t["from_state"],
                to_state=t["to_state"],
                event=t["event"],
                actor_type=t["actor_type"],
                actor_id=t["actor_id"],
                note=t["note"],
                details=t["details"] or {},
            )
            for t in conn.execute(
                sa.select(live_timeline)
                .where(live_timeline.c.incident_id == incident_id)
                .order_by(live_timeline.c.seq)
            ).mappings()
        ]
        events = [
            _event_view(e, app["name"])
            for e in conn.execute(
                sa.select(security_events)
                .where(security_events.c.incident_id == incident_id)
                .order_by(security_events.c.seq.desc())
                .limit(200)
            ).mappings()
        ]
        actions = [
            _action_view(x)
            for x in conn.execute(
                sa.select(defense_actions)
                .where(defense_actions.c.incident_id == incident_id)
                .order_by(defense_actions.c.created_at)
            ).mappings()
        ]
        notes = [
            LiveNotification(
                id=x["id"],
                incident_id=x["incident_id"],
                event=x["event"],
                status=x["status"],
                attempts=x["attempts"],
                response_status=x["response_status"],
                error=x["error"],
                created_at=x["created_at"],
                delivered_at=x["delivered_at"],
            )
            for x in conn.execute(
                sa.select(live_notifications)
                .where(live_notifications.c.incident_id == incident_id)
                .order_by(live_notifications.c.created_at)
            ).mappings()
        ]
        return LiveIncidentDetail(
            incident=_incident_view(conn, r, app),
            timeline=timeline,
            events=events,
            actions=actions,
            notifications=notes,
        )


# ------------------------------------------------------------------ human decisions


def _decide(
    action_id: str,
    request: Request,
    idempotency_key: str | None,
    body: LiveActionDecision,
    verb: str,
) -> Any:
    with transaction() as conn:
        user = _writer(conn, request)
        act = engine.lock_action(conn, action_id)
        if act is None:
            raise not_found("action")
        app = _app_or_404(conn, act["app_id"])
        org_id, _ = require_project(conn, user, app["project_id"], MemberRole.owner)
        retry = {
            "route": f"live_action_{verb}",
            "action_id": action_id,
            "body": body.model_dump(mode="json"),
        }
        if replay := idempotent_replay(conn, user.id, idempotency_key, retry):
            return replay
        inc = engine.lock_incident(conn, act["incident_id"])
        assert inc is not None
        reason = (body.reason or "").strip()
        status = act["status"]
        if verb in ("approve", "deny"):
            if status != "pending_approval" or inc["state"] != S.AWAITING_APPROVAL.value:
                raise ApiError(
                    ErrorCode.CONFLICT_STATE,
                    f"this action is {status} (incident {inc['state']}); only a pending approval can be decided",
                    409,
                )
            if verb == "approve":
                auth = authorize.check(
                    authorize.Proposal(
                        DefenseActionKind(act["kind"]), act["target"], act["duration_s"]
                    ),
                    engine.app_facts(app),
                    {},
                    {},
                    "human",
                )
                if auth.outcome != "authorized":
                    raise ApiError(
                        ErrorCode.SCOPE_DENIED,
                        f"the gate still refuses this control: {auth.detail}",
                        403,
                    )
                conn.execute(
                    sa.update(defense_actions)
                    .where(defense_actions.c.id == action_id)
                    .values(
                        status="authorized",
                        mode="human_approved",
                        decided_by=user.id,
                        updated_at=sa.func.now(),
                    )
                )
                engine.transition(
                    conn,
                    inc,
                    S.AUTHORIZED,
                    f"approved by a person{': ' + reason if reason else ''}",
                    actor_type="user",
                    actor_id=user.id,
                    details={"checks": [c.model_dump() for c in auth.checks]},
                )
                jobs.enqueue(
                    conn,
                    "live_defense_execute",
                    {"action_id": action_id},
                    dedupe_key=f"ld:execute:{action_id}",
                )
            else:
                conn.execute(
                    sa.update(defense_actions)
                    .where(defense_actions.c.id == action_id)
                    .values(
                        status="denied",
                        decided_by=user.id,
                        end_reason=reason or "denied by a person",
                        ended_at=sa.func.now(),
                        updated_at=sa.func.now(),
                    )
                )
                engine.transition(
                    conn,
                    inc,
                    S.DENIED,
                    f"denied by a person{': ' + reason if reason else ''}",
                    actor_type="user",
                    actor_id=user.id,
                )
        else:  # rollback
            if status not in engine.LIVE_ACTIVE:
                raise ApiError(
                    ErrorCode.CONFLICT_STATE,
                    f"this control is {status}; only an active control can be rolled back",
                    409,
                )
            conn.execute(
                sa.update(defense_actions)
                .where(defense_actions.c.id == action_id)
                .values(status="rollback_requested", decided_by=user.id, updated_at=sa.func.now())
            )
            engine.timeline(
                conn,
                inc["id"],
                "rollback_requested",
                f"rollback requested by a person{': ' + reason if reason else ''}",
                actor_type="user",
                actor_id=user.id,
                details={"action_id": action_id},
            )
            jobs.enqueue(
                conn,
                "live_defense_rollback",
                {
                    "action_id": action_id,
                    "user_id": user.id,
                    "reason": reason or "rollback requested by a person",
                },
                dedupe_key=f"ld:rollback:{action_id}",
                priority=5,
            )
        _audit(
            conn,
            org_id,
            app["project_id"],
            user,
            f"live_action.{verb}",
            action_id,
            reason=reason or None,
        )
        fresh = engine.lock_action(conn, action_id)
        return idempotent_finish(conn, user.id, idempotency_key, retry, 200, _action_view(fresh))


@router.post("/live/actions/{action_id}/approve", response_model=DefenseAction)
def approve_action(
    action_id: str,
    body: LiveActionDecision,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    return _decide(action_id, request, idempotency_key, body, "approve")


@router.post("/live/actions/{action_id}/deny", response_model=DefenseAction)
def deny_action(
    action_id: str,
    body: LiveActionDecision,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    return _decide(action_id, request, idempotency_key, body, "deny")


@router.post("/live/actions/{action_id}/rollback", response_model=DefenseAction)
def rollback_action(
    action_id: str,
    body: LiveActionDecision,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    return _decide(action_id, request, idempotency_key, body, "rollback")
