"""Owner notifications: one persisted row per (incident, event), delivered as a signed webhook.

``record`` runs inside the caller's transaction, deduplicates by key and applies a
per-application storm limit. ``deliver`` (a job) posts the payload to the owner's
notification URL through ``netguard`` with the same signature scheme as control calls.
Without a notification URL the row stays ``not_configured``: recorded, not delivered,
and shown that way.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from backend import jobs
from backend.db import live_apps, live_notifications
from backend.live_defense import netguard, vault
from backend.live_defense.adapters import canonical
from shared.base import utcnow
from shared.ids import new_id

STORM_LIMIT_PER_HOUR = 30


def record(
    conn: Connection,
    *,
    incident_id: str,
    app_id: str,
    event: str,
    payload: dict[str, Any],
    dedupe_suffix: str = "",
) -> str | None:
    key = f"{incident_id}:{event}:{dedupe_suffix}"[:200]
    recent = conn.execute(
        sa.select(sa.func.count())
        .select_from(live_notifications)
        .where(
            live_notifications.c.app_id == app_id,
            live_notifications.c.created_at > utcnow() - timedelta(hours=1),
            live_notifications.c.status != "suppressed",
        )
    ).scalar_one()
    notify_url = conn.execute(
        sa.select(live_apps.c.notify_url).where(live_apps.c.id == app_id)
    ).scalar()
    status = (
        "suppressed"
        if recent >= STORM_LIMIT_PER_HOUR
        else "pending"
        if notify_url
        else "not_configured"
    )
    nid = new_id("lnt")
    created = conn.execute(
        pg_insert(live_notifications)
        .values(
            id=nid,
            incident_id=incident_id,
            app_id=app_id,
            event=event,
            dedupe_key=key,
            status=status,
            payload={"event": event, "incident_id": incident_id, **payload},
            error="storm limit: over 30 notifications in the last hour"
            if status == "suppressed"
            else None,
        )
        .on_conflict_do_nothing(index_elements=[live_notifications.c.dedupe_key])
        .returning(live_notifications.c.id)
    ).scalar()
    if created and status == "pending":
        jobs.enqueue(
            conn, "live_defense_notify", {"notification_id": nid}, dedupe_key=f"ld:notify:{nid}"
        )
    return created


def deliver(conn_factory: Any, notification_id: str) -> dict[str, Any]:
    with conn_factory() as conn:
        row = (
            conn.execute(
                sa.select(live_notifications, live_apps.c.notify_url, live_apps.c.secret_ciphertext)
                .join(live_apps, live_apps.c.id == live_notifications.c.app_id)
                .where(live_notifications.c.id == notification_id)
            )
            .mappings()
            .first()
        )
    if row is None or row["status"] not in ("pending", "failed"):
        return {"skipped": True}
    error: str | None = None
    code: int | None = None
    retry = False
    try:
        secret = vault.decrypt(row["secret_ciphertext"])
        body = json.dumps(row["payload"], sort_keys=True, separators=(",", ":")).encode()
        ts = str(int(time.time()))
        path = urlsplit(row["notify_url"]).path or "/"
        resp = netguard.request(
            "POST",
            row["notify_url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Ari-App": row["app_id"],
                "X-Ari-Timestamp": ts,
                "X-Ari-Signature": vault.sign(secret, ts, canonical("POST", path, body)),
                "X-Ari-Event": row["event"],
            },
        )
        code = resp.status_code
        if not 200 <= code < 300:
            error = f"HTTP {code}"
            retry = code >= 500
    except (netguard.UnsafeDestination, vault.SecretKeyUnavailable) as exc:
        error = f"not delivered: {exc}"[:500]
    except httpx.HTTPError as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
        retry = True
    with conn_factory() as conn:
        conn.execute(
            sa.update(live_notifications)
            .where(live_notifications.c.id == notification_id)
            .values(
                status="failed" if error else "delivered",
                attempts=live_notifications.c.attempts + 1,
                response_status=code,
                error=error,
                delivered_at=None if error else utcnow(),
            )
        )
    if retry:
        raise RuntimeError(f"notification delivery failed: {error}")  # retried by the queue
    return {"delivered": error is None, "status": code}
