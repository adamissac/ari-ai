"""Live defense jobs: process telemetry → detect → respond → execute → verify → expire.

Every step is a durable job (retries, leases, dedupe keys). Incidents and actions are
advanced under ``SELECT ... FOR UPDATE``; each state change is checked against
``state.check`` and appended to ``live_timeline``. Network calls to the application are
made outside database transactions; their results are written afterwards, and a retried
apply reuses the action id as the control id, so a crash between the call and the write
cannot create a second control.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from backend import audit, jobs
from backend.db import (
    LIVE_OPEN_STATES,
    defense_actions,
    live_apps,
    live_grants,
    live_incidents,
    live_timeline,
    security_events,
    transaction,
)
from backend.live_defense import adapters, authorize, notify, policy, state
from backend.services import project_org
from backend.settings import get_settings
from backend.worker import JobContext, handler
from monitoring.detect import Event, Thresholds, detect
from shared.audit import ActorType
from shared.base import utcnow
from shared.ids import new_id
from shared.live_defense import (
    DefenseActionKind,
    LiveIncidentState,
    PolicyDecision,
    VerificationOutcome,
)

log = logging.getLogger(__name__)
S = LiveIncidentState
K = DefenseActionKind

CATEGORY_KINDS = {
    "credential_attack": ("auth_failure",),
    "scanning": ("not_found",),
    "waf_alert": ("waf_alert",),
    "error_spike": ("server_error", "deploy", "config_change"),
}
# Requests from a blocked source that the application still served would mean the
# control did not work.
SERVED_KINDS = ("auth_failure", "not_found", "waf_alert", "request", "server_error")
LIVE_ACTIVE = ("active", "verified", "verification_failed")


# ------------------------------------------------------------------ helpers


def timeline(
    conn: Connection,
    incident_id: str,
    event: str,
    note: str,
    *,
    actor_type: str = "system",
    actor_id: str = "live_defense",
    from_state: str | None = None,
    to_state: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        sa.insert(live_timeline).values(
            incident_id=incident_id,
            event=event,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
            actor_id=actor_id,
            note=note[:500],
            details=details or {},
        )
    )


def lock_incident(conn: Connection, incident_id: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            sa.select(live_incidents).where(live_incidents.c.id == incident_id).with_for_update()
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def lock_action(conn: Connection, action_id: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            sa.select(defense_actions).where(defense_actions.c.id == action_id).with_for_update()
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def load_app(conn: Connection, app_id: str) -> dict[str, Any]:
    return dict(conn.execute(sa.select(live_apps).where(live_apps.c.id == app_id)).mappings().one())


def transition(
    conn: Connection,
    incident: dict[str, Any],
    to: LiveIncidentState,
    note: str,
    *,
    actor_type: str = "system",
    actor_id: str = "live_defense",
    details: dict[str, Any] | None = None,
) -> None:
    current = S(incident["state"])
    state.check(current, to)
    values: dict[str, Any] = {"state": to.value, "updated_at": sa.func.now()}
    if to in state.TERMINAL:
        values["closed_at"] = sa.func.now()
    conn.execute(
        sa.update(live_incidents).where(live_incidents.c.id == incident["id"]).values(**values)
    )
    timeline(
        conn,
        incident["id"],
        "state_changed",
        note,
        actor_type=actor_type,
        actor_id=actor_id,
        from_state=current.value,
        to_state=to.value,
        details=details,
    )
    incident["state"] = to.value
    if to in (
        S.DETECTED,
        S.AWAITING_APPROVAL,
        S.RESOLVED,
        S.ESCALATED,
        S.FAILED,
        S.DENIED,
        S.ROLLED_BACK,
    ):
        notify.record(
            conn,
            incident_id=incident["id"],
            app_id=incident["app_id"],
            event=f"incident.{to.value.lower()}",
            payload={
                "state": to.value,
                "category": incident["category"],
                "source": incident["source"],
                "severity": incident["severity"],
                "note": note[:300],
            },
        )


def _audit(
    conn: Connection, incident: dict[str, Any], action: str, details: dict[str, Any]
) -> None:
    audit.record(
        conn,
        org_id=project_org(conn, incident["project_id"]),
        project_id=incident["project_id"],
        actor_type=ActorType.system,
        actor_id="live_defense",
        action=action,
        subject_type="live_incident",
        subject_id=incident["id"],
        details=details,
    )


def _row_event(r: Any) -> Event:
    return Event(
        id=r.id,
        kind=r.kind,
        occurred_at=r.occurred_at,
        source_ip=r.source_ip,
        route=r.route,
        status=r.status,
        severity=r.severity,
        controlled_test=r.controlled_test,
    )


# ------------------------------------------------------------------ process telemetry


@handler("live_defense_process")
def process(ctx: JobContext) -> dict[str, Any]:
    app_id = ctx.job.payload["app_id"]
    now = utcnow()
    thresholds = Thresholds()
    opened: list[str] = []
    with transaction() as conn:
        claimed = [
            r.id
            for r in conn.execute(
                sa.select(security_events.c.id)
                .where(security_events.c.app_id == app_id, security_events.c.processed_at.is_(None))
                .order_by(security_events.c.seq)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
        ]
        if not claimed:
            return {"processed": 0}
        conn.execute(
            sa.update(security_events)
            .where(security_events.c.id.in_(claimed))
            .values(processed_at=now)
        )
        app = load_app(conn, app_id)

        # 1. Fold new evidence into incidents that are already open.
        for open_inc in conn.execute(
            sa.select(live_incidents).where(
                live_incidents.c.app_id == app_id, live_incidents.c.state.in_(LIVE_OPEN_STATES)
            )
        ).mappings():
            kinds = CATEGORY_KINDS.get(open_inc["category"], ())
            cond = [
                security_events.c.app_id == app_id,
                security_events.c.incident_id.is_(None),
                security_events.c.id.in_(claimed),
                security_events.c.kind.in_(kinds),
            ]
            if open_inc["source"]:
                cond.append(security_events.c.source_ip == open_inc["source"])
            n = conn.execute(
                sa.update(security_events).where(*cond).values(incident_id=open_inc["id"])
            ).rowcount
            if n:
                timeline(conn, open_inc["id"], "evidence_added", f"{n} more matching event(s) received")

        # 2. Blocked requests are evidence for the incident whose control blocked them.
        for act in conn.execute(
            sa.select(defense_actions.c.incident_id, defense_actions.c.target).where(
                defense_actions.c.app_id == app_id,
                defense_actions.c.status.in_(LIVE_ACTIVE),
                defense_actions.c.target.is_not(None),
            )
        ):
            conn.execute(
                sa.update(security_events)
                .where(
                    security_events.c.id.in_(claimed),
                    security_events.c.kind == "blocked",
                    security_events.c.incident_id.is_(None),
                    sa.or_(
                        security_events.c.source_ip == act.target,
                        security_events.c.route == act.target,
                    ),
                )
                .values(incident_id=act.incident_id)
            )

        # 3. Run the rules over recent unassigned events and open incidents.
        recent = conn.execute(
            sa.select(security_events).where(
                security_events.c.app_id == app_id,
                security_events.c.incident_id.is_(None),
                security_events.c.occurred_at >= now - thresholds.window,
            )
        ).all()
        for d in detect([_row_event(r) for r in recent], now, thresholds):
            iid = new_id("lin")
            created = conn.execute(
                pg_insert(live_incidents)
                .values(
                    id=iid,
                    project_id=app["project_id"],
                    app_id=app_id,
                    correlation_key=d.correlation_key,
                    category=d.category,
                    source=d.source,
                    severity=d.severity,
                    state=S.DETECTED.value,
                    rule_id=d.rule_id,
                    rationale=d.rationale[:500],
                )
                .on_conflict_do_nothing(
                    index_elements=["app_id", "correlation_key"],
                    index_where=live_incidents.c.state.in_(LIVE_OPEN_STATES),
                )
                .returning(live_incidents.c.id)
            ).scalar()
            if not created:
                continue  # an open incident with this key exists (folded in step 1 next time)
            conn.execute(
                sa.update(security_events)
                .where(
                    security_events.c.id.in_(d.event_ids), security_events.c.incident_id.is_(None)
                )
                .values(incident_id=iid)
            )
            inc = lock_incident(conn, iid)
            assert inc is not None
            timeline(
                conn,
                iid,
                "state_changed",
                d.rationale,
                actor_id=d.rule_id,
                to_state=S.DETECTED.value,
                details={"rule_id": d.rule_id, "events": len(d.event_ids)},
            )
            notify.record(
                conn,
                incident_id=iid,
                app_id=app_id,
                event="incident.detected",
                payload={
                    "category": d.category,
                    "source": d.source,
                    "severity": d.severity,
                    "note": d.rationale,
                },
            )
            _audit(
                conn,
                inc,
                "live_incident.detected",
                {"rule_id": d.rule_id, "events": len(d.event_ids)},
            )
            # Triage: evidence must come from authenticated ingest of this application.
            transition(
                conn,
                inc,
                S.TRIAGED,
                f"evidence accepted: {len(d.event_ids)} authenticated event(s) from the connected "
                f"application ({app['environment']})",
            )
            jobs.enqueue(
                conn, "live_defense_respond", {"incident_id": iid}, dedupe_key=f"ld:respond:{iid}"
            )
            opened.append(iid)
    return {"processed": len(claimed), "opened": opened}


# ------------------------------------------------------------------ respond


def _incident_facts(conn: Connection, inc: dict[str, Any]) -> policy.IncidentFacts:
    rows = conn.execute(
        sa.select(security_events.c.route, security_events.c.occurred_at).where(
            security_events.c.incident_id == inc["id"], security_events.c.kind != "blocked"
        )
    ).all()
    routes = tuple(sorted({r.route for r in rows if r.route}))
    last = max((r.occurred_at for r in rows), default=inc["opened_at"])
    return policy.IncidentFacts(
        project_id=inc["project_id"],
        category=inc["category"],
        source=inc["source"],
        severity=inc["severity"],
        event_count=len(rows),
        routes=routes,
        last_event_at=last,
        now=utcnow(),
    )


def _grants(conn: Connection, app_id: str) -> dict[DefenseActionKind, authorize.Grant]:
    out: dict[DefenseActionKind, authorize.Grant] = {}
    for g in conn.execute(
        sa.select(live_grants).where(
            live_grants.c.app_id == app_id, live_grants.c.revoked_at.is_(None)
        )
    ).mappings():
        out[K(g["kind"])] = authorize.Grant(g["max_duration_s"], g["hourly_budget"])
    return out


def _used_last_hour(conn: Connection, app_id: str) -> dict[DefenseActionKind, int]:
    rows = conn.execute(
        sa.select(defense_actions.c.kind, sa.func.count())
        .where(
            defense_actions.c.app_id == app_id,
            defense_actions.c.mode == "automatic",
            defense_actions.c.created_at > utcnow() - timedelta(hours=1),
        )
        .group_by(defense_actions.c.kind)
    ).all()
    return {K(k): n for k, n in rows}


def app_facts(app: dict[str, Any]) -> authorize.AppFacts:
    return authorize.AppFacts(
        enabled=app["enabled"],
        auto_response=app["auto_response"],
        protected_sources=frozenset(app["protected_sources"] or []),
    )


@handler("live_defense_respond")
def respond(ctx: JobContext) -> dict[str, Any]:
    iid = ctx.job.payload["incident_id"]
    with transaction() as conn:
        inc = lock_incident(conn, iid)
        if inc is None or inc["state"] != S.TRIAGED.value:
            return {"skipped": True}
        facts = _incident_facts(conn, inc)
    # Inference may load a checkpoint; keep it outside the row lock.
    rl, rule, final = policy.decide(facts)
    with transaction() as conn:
        inc = lock_incident(conn, iid)
        if inc is None or inc["state"] != S.TRIAGED.value:
            return {"skipped": True}
        app = load_app(conn, inc["app_id"])
        transition(
            conn,
            inc,
            S.RECOMMENDED,
            f"final proposal {final.kind or 'none'} selected by {final.selected_by}; "
            f"learned policy: {rl.status}" + (f" ({rl.action})" if rl.action else ""),
            actor_type="policy",
            actor_id=rl.policy_version or "deterministic-rules",
            details={
                "rl_status": rl.status,
                "rl_action": rl.action,
                "selected_by": final.selected_by,
            },
        )
        auth = authorize.check(
            authorize.Proposal(final.kind, final.target, final.duration_s),
            app_facts(app),
            _grants(conn, app["id"]),
            _used_last_hour(conn, app["id"]),
            "automatic",
        )
        decision = PolicyDecision(
            rl=rl, rules=rule, final=final, authorization=auth, decided_at=utcnow()
        )
        conn.execute(
            sa.update(live_incidents)
            .where(live_incidents.c.id == iid)
            .values(decision=decision.model_dump(mode="json"), updated_at=sa.func.now())
        )
        _audit(
            conn,
            inc,
            "live_incident.decided",
            {
                "rl_status": rl.status,
                "rl_action": rl.action,
                "policy_version": rl.policy_version,
                "rule_id": rule.rule_id,
                "final_kind": final.kind,
                "selected_by": final.selected_by,
                "authorization": auth.outcome,
                "reason_code": auth.reason_code,
            },
        )
        if final.kind is None:
            transition(conn, inc, S.RESOLVED, "no control proposed; recorded for review")
            return {"decision": "none"}
        status = {
            "authorized": "authorized",
            "requires_human": "pending_approval",
            "denied": "denied",
        }.get(auth.outcome, "denied")
        internal = final.kind in authorize.INTERNAL_KINDS
        if internal and auth.outcome == "authorized":
            status = "recorded"
        aid = new_id("dac")
        conn.execute(
            pg_insert(defense_actions)
            .values(
                id=aid,
                incident_id=iid,
                app_id=app["id"],
                kind=final.kind.value,
                target=final.target,
                duration_s=final.duration_s,
                status=status,
                mode="internal" if internal else ("automatic" if status == "authorized" else None),
                decided_by="authorization-gate" if status in ("authorized", "recorded") else None,
                error=auth.detail if status == "denied" else None,
            )
            .on_conflict_do_nothing(constraint="uq_defense_actions_incident_kind")
        )
        if status == "authorized":
            transition(
                conn,
                inc,
                S.AUTHORIZED,
                f"gate: {auth.reason_code} — {auth.detail}",
                actor_id="authorization-gate",
            )
            jobs.enqueue(
                conn, "live_defense_execute", {"action_id": aid}, dedupe_key=f"ld:execute:{aid}"
            )
        elif status == "pending_approval":
            transition(
                conn,
                inc,
                S.AWAITING_APPROVAL,
                f"a person must approve: {auth.detail}",
                actor_id="authorization-gate",
            )
        elif status == "recorded":
            note = (
                "escalated to a person (no automatic control for this pattern)"
                if final.kind is K.escalate
                else "reassessment requested; a person starts it from the project"
            )
            transition(conn, inc, S.ESCALATED, note, actor_id="authorization-gate")
        else:
            transition(
                conn,
                inc,
                S.ESCALATED,
                f"gate denied the control: {auth.detail}",
                actor_id="authorization-gate",
            )
        return {"action_id": aid, "status": status}


# ------------------------------------------------------------------ execute


@handler("live_defense_execute")
def execute(ctx: JobContext) -> dict[str, Any]:
    aid = ctx.job.payload["action_id"]
    with transaction() as conn:
        act = lock_action(conn, aid)
        if act is None or act["status"] not in ("authorized", "executing"):
            return {"skipped": True}
        inc = lock_incident(conn, act["incident_id"])
        assert inc is not None
        duration = int(act["duration_s"] or 0)
        expires = act["expires_at"] or utcnow() + timedelta(seconds=duration)
        if act["status"] == "authorized":
            conn.execute(
                sa.update(defense_actions)
                .where(defense_actions.c.id == aid)
                .values(status="executing", expires_at=expires, updated_at=sa.func.now())
            )
            transition(
                conn, inc, S.EXECUTING, f"applying {act['kind']} on {act['target']} for {duration}s"
            )
        app = load_app(conn, act["app_id"])
    payload = {**act, "expires_at": expires.isoformat()}
    result = adapters.apply(app, payload)
    last_try = ctx.job.attempts >= ctx.job.max_attempts
    with transaction() as conn:
        act = lock_action(conn, aid)
        inc = lock_incident(conn, act["incident_id"]) if act else None
        if act is None or inc is None or act["status"] != "executing":
            return {"skipped": True}
        if result.ok and result.state == "active":
            now = utcnow()
            conn.execute(
                sa.update(defense_actions)
                .where(defense_actions.c.id == aid)
                .values(
                    status="active",
                    activated_at=now,
                    adapter=result.summary(),
                    updated_at=sa.func.now(),
                )
            )
            timeline(
                conn,
                inc["id"],
                "control_applied",
                f"{act['kind']} on {act['target']} confirmed active by the application "
                f"(HTTP {result.http_status}); expires {expires.isoformat()}",
                actor_type="worker",
                actor_id="control-adapter",
                details={"action_id": aid, **result.summary()},
            )
            transition(
                conn, inc, S.VERIFYING, "waiting for new telemetry to confirm the control works"
            )
            settings = get_settings()
            jobs.enqueue(
                conn,
                "live_defense_verify",
                {"action_id": aid, "attempt": 1},
                dedupe_key=f"ld:verify:{aid}:1",
                delay_s=settings.live_defense_verify_interval_s,
            )
            jobs.enqueue(
                conn,
                "live_defense_expire",
                {"action_id": aid},
                dedupe_key=f"ld:expire:{aid}",
                delay_s=max(0.0, (expires - now).total_seconds()),
            )
            notify.record(
                conn,
                incident_id=inc["id"],
                app_id=inc["app_id"],
                event="control.active",
                payload={
                    "action_id": aid,
                    "kind": act["kind"],
                    "target": act["target"],
                    "expires_at": expires.isoformat(),
                },
            )
            return {"active": True}
        conn.execute(
            sa.update(defense_actions)
            .where(defense_actions.c.id == aid)
            .values(adapter=result.summary(), error=result.detail[:500], updated_at=sa.func.now())
        )
        if result.retryable and not last_try:
            timeline(conn, inc["id"], "control_retry", f"apply failed, will retry: {result.detail}")
        else:
            conn.execute(
                sa.update(defense_actions)
                .where(defense_actions.c.id == aid)
                .values(status="failed", ended_at=sa.func.now())
            )
            transition(conn, inc, S.FAILED, f"control could not be applied: {result.detail}")
            return {"active": False}
    raise RuntimeError(f"control apply failed (retryable): {result.detail}")


# ------------------------------------------------------------------ verify


@handler("live_defense_verify")
def verify(ctx: JobContext) -> dict[str, Any]:
    aid = ctx.job.payload["action_id"]
    attempt = int(ctx.job.payload.get("attempt", 1))
    settings = get_settings()
    with transaction() as conn:
        snap = (
            conn.execute(sa.select(defense_actions).where(defense_actions.c.id == aid))
            .mappings()
            .first()
        )
        if snap is None or snap["status"] != "active":
            return {"skipped": True}
        app = load_app(conn, snap["app_id"])
    probe = adapters.status(app, aid)
    with transaction() as conn:
        act = lock_action(conn, aid)
        if act is None or act["status"] != "active":
            return {"skipped": True}
        inc = lock_incident(conn, act["incident_id"])
        assert inc is not None
        activated = act["activated_at"]
        target = act["target"]
        match = sa.or_(security_events.c.source_ip == target, security_events.c.route == target)

        def count(kinds: tuple[str, ...], grace_s: float) -> int:
            return conn.execute(
                sa.select(sa.func.count())
                .select_from(security_events)
                .where(
                    security_events.c.app_id == act["app_id"],
                    security_events.c.kind.in_(kinds),
                    security_events.c.occurred_at >= activated + timedelta(seconds=grace_s),
                    match,
                )
            ).scalar_one()

        # A refusal is proof the control acted. A served request counts against it only
        # after a 1 s grace for requests already in flight when the control went on.
        blocked = count(("blocked",), 0)
        served = count(SERVED_KINDS, 1) if act["kind"] == K.block_source.value else 0
        control_state = probe.state if probe.ok else f"unreadable: {probe.detail}"
        result: str
        if not probe.ok or probe.state != "active":
            result, detail = (
                "ineffective",
                f"the application does not report the control as active ({control_state})",
            )
        elif served > 0:
            result, detail = (
                "ineffective",
                f"{served} request(s) from {target} were still served after the control",
            )
        elif act["kind"] == K.increase_logging.value:
            result, detail = (
                "effective",
                "control confirmed active; logging has no blocking effect to measure",
            )
        elif blocked > 0:
            result, detail = (
                "effective",
                f"{blocked} request(s) from {target} refused by the control, none served",
            )
        elif attempt < settings.live_defense_verify_attempts:
            result, detail = (
                "pending",
                f"control active; no new traffic from {target} yet (check {attempt})",
            )
        else:
            result, detail = (
                "inconclusive",
                (
                    f"control active but no new traffic from {target} arrived within "
                    f"{attempt} checks, so its effect is unproven"
                ),
            )
        outcome = VerificationOutcome(
            result=result,  # type: ignore[arg-type]
            control_state=control_state[:100],
            blocked_after=blocked,
            attempts_after=served,
            attempt=attempt,
            checked_at=utcnow(),
            detail=detail,
        )
        values: dict[str, Any] = {
            "verification": outcome.model_dump(mode="json"),
            "updated_at": sa.func.now(),
        }
        if result == "effective":
            values["status"] = "verified"
        elif result == "ineffective":
            values["status"] = "verification_failed"
        conn.execute(sa.update(defense_actions).where(defense_actions.c.id == aid).values(**values))
        if result == "pending":
            jobs.enqueue(
                conn,
                "live_defense_verify",
                {"action_id": aid, "attempt": attempt + 1},
                dedupe_key=f"ld:verify:{aid}:{attempt + 1}",
                delay_s=settings.live_defense_verify_interval_s,
            )
            return {"result": result}
        timeline(
            conn,
            inc["id"],
            "verification",
            detail,
            actor_type="worker",
            actor_id="verifier",
            details=outcome.model_dump(mode="json"),
        )
        if inc["state"] == S.VERIFYING.value:
            if result == "effective":
                transition(conn, inc, S.RESOLVED, f"verified by new telemetry: {detail}")
            else:
                transition(
                    conn, inc, S.ESCALATED, f"verification {result}: {detail}; a person must review"
                )
        return {"result": result}


# ------------------------------------------------------------------ expire and roll back


def _end_control(aid: str, *, final_status: str, reason: str, actor: str) -> dict[str, Any]:
    with transaction() as conn:
        snap = (
            conn.execute(sa.select(defense_actions).where(defense_actions.c.id == aid))
            .mappings()
            .first()
        )
        if snap is None:
            return {"skipped": True}
        app = load_app(conn, snap["app_id"])
    result = adapters.remove(app, aid, reason)
    with transaction() as conn:
        act = lock_action(conn, aid)
        if act is None or act["status"] in ("expired", "rolled_back"):
            return {"skipped": True}
        inc = lock_incident(conn, act["incident_id"])
        assert inc is not None
        if not result.ok:
            conn.execute(
                sa.update(defense_actions)
                .where(defense_actions.c.id == aid)
                .values(error=f"removal failed: {result.detail}"[:500], updated_at=sa.func.now())
            )
            timeline(
                conn,
                inc["id"],
                "control_removal_failed",
                f"removal failed, will retry: {result.detail}",
            )
            raise RuntimeError(f"control removal failed: {result.detail}")
        conn.execute(
            sa.update(defense_actions)
            .where(defense_actions.c.id == aid)
            .values(
                status=final_status,
                ended_at=sa.func.now(),
                end_reason=reason[:500],
                updated_at=sa.func.now(),
            )
        )
        event = "control_expired" if final_status == "expired" else "control_rolled_back"
        timeline(
            conn,
            inc["id"],
            event,
            f"{act['kind']} on {act['target']} removed: {reason}",
            actor_type="user" if actor.startswith("usr_") else "worker",
            actor_id=actor,
            details={"action_id": aid, **result.summary()},
        )
        notify.record(
            conn,
            incident_id=inc["id"],
            app_id=inc["app_id"],
            event=f"control.{final_status}",
            payload={
                "action_id": aid,
                "kind": act["kind"],
                "target": act["target"],
                "reason": reason[:200],
            },
        )
        if final_status == "rolled_back" and state.can(S(inc["state"]), S.ROLLED_BACK):
            transition(
                conn,
                inc,
                S.ROLLED_BACK,
                f"rolled back by a person: {reason}",
                actor_type="user",
                actor_id=actor,
            )
        return {"removed": True}


@handler("live_defense_expire")
def expire(ctx: JobContext) -> dict[str, Any]:
    aid = ctx.job.payload["action_id"]
    with transaction() as conn:
        act = (
            conn.execute(sa.select(defense_actions).where(defense_actions.c.id == aid))
            .mappings()
            .first()
        )
        if act is None or act["status"] not in LIVE_ACTIVE:
            return {"skipped": True}
        if act["expires_at"] and act["expires_at"] > utcnow() + timedelta(seconds=1):
            jobs.enqueue(
                conn,
                "live_defense_expire",
                {"action_id": aid},
                dedupe_key=f"ld:expire:{aid}:{int(act['expires_at'].timestamp())}",
                delay_s=(act["expires_at"] - utcnow()).total_seconds(),
            )
            return {"rescheduled": True}
    return _end_control(
        aid,
        final_status="expired",
        reason="expired at the end of its authorized duration",
        actor="expiry",
    )


@handler("live_defense_rollback")
def rollback(ctx: JobContext) -> dict[str, Any]:
    aid = ctx.job.payload["action_id"]
    with transaction() as conn:
        act = (
            conn.execute(sa.select(defense_actions).where(defense_actions.c.id == aid))
            .mappings()
            .first()
        )
        if act is None or act["status"] != "rollback_requested":
            return {"skipped": True}
    return _end_control(
        aid,
        final_status="rolled_back",
        reason=ctx.job.payload.get("reason") or "rollback requested",
        actor=ctx.job.payload.get("user_id", "unknown"),
    )


@handler("live_defense_notify")
def deliver_notification(ctx: JobContext) -> dict[str, Any]:
    return notify.deliver(transaction, ctx.job.payload["notification_id"])


# ------------------------------------------------------------------ reconcile


@handler("live_defense_reconcile")
def reconcile(ctx: JobContext | None = None) -> dict[str, Any]:
    """Re-drive controls a stalled worker left behind. Safe to run any time."""
    now = utcnow()
    bucket = int(now.timestamp() // 60)
    out = {"expire": 0, "execute": 0, "rollback": 0}
    with transaction() as conn:
        for (aid,) in conn.execute(
            sa.select(defense_actions.c.id).where(
                defense_actions.c.status.in_(LIVE_ACTIVE),
                defense_actions.c.expires_at < now - timedelta(seconds=15),
            )
        ):
            _, created = jobs.enqueue(
                conn,
                "live_defense_expire",
                {"action_id": aid},
                dedupe_key=f"ld:expire:{aid}:r{bucket}",
            )
            out["expire"] += int(created)
        for (aid,) in conn.execute(
            sa.select(defense_actions.c.id).where(
                defense_actions.c.status == "executing",
                defense_actions.c.updated_at < now - timedelta(minutes=2),
            )
        ):
            _, created = jobs.enqueue(
                conn,
                "live_defense_execute",
                {"action_id": aid},
                dedupe_key=f"ld:execute:{aid}:r{bucket}",
            )
            out["execute"] += int(created)
        for row in conn.execute(
            sa.select(defense_actions.c.id, defense_actions.c.decided_by).where(
                defense_actions.c.status == "rollback_requested",
                defense_actions.c.updated_at < now - timedelta(minutes=1),
            )
        ):
            _, created = jobs.enqueue(
                conn,
                "live_defense_rollback",
                {"action_id": row.id, "user_id": row.decided_by or "unknown"},
                dedupe_key=f"ld:rollback:{row.id}:r{bucket}",
            )
            out["rollback"] += int(created)
    return out
