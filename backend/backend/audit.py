"""Append-only, per-organization hash-chained audit log."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.db import audit_events, organizations
from backend.redaction import redact
from shared.audit import GENESIS_HASH, ActorType, AuditEvent, audit_hash
from shared.base import utcnow
from shared.ids import IdPrefix, new_id


def record(
    conn: Connection,
    *,
    org_id: str,
    actor_type: ActorType,
    actor_id: str,
    action: str,
    subject_type: str,
    subject_id: str,
    project_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one event. The org row lock serializes the chain within the transaction."""
    org = conn.execute(
        sa.update(organizations)
        .where(organizations.c.id == org_id)
        .values(audit_seq=organizations.c.audit_seq + 1)
        .returning(organizations.c.audit_seq, organizations.c.audit_head)
    ).first()
    if org is None:
        raise LookupError(f"organization {org_id} not found")
    seq, prev_hash = org
    body = {
        "id": new_id(IdPrefix.aud),
        "seq": seq,
        "org_id": org_id,
        "project_id": project_id,
        "actor_type": actor_type.value,
        "actor_id": actor_id,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "at": utcnow().isoformat(),
        "details": redact(details or {}),
    }
    # Hash the canonical serialized form so verify_chain() recomputes byte-identical input.
    draft = AuditEvent.model_validate({**body, "prev_hash": prev_hash, "hash": GENESIS_HASH})
    digest = audit_hash(prev_hash, draft.model_dump(mode="json"))
    event = draft.model_copy(update={"hash": digest})
    conn.execute(
        sa.insert(audit_events).values(
            id=event.id,
            org_id=org_id,
            seq=seq,
            project_id=project_id,
            doc=event.model_dump(mode="json"),
            hash=digest,
        )
    )
    conn.execute(
        sa.update(organizations).where(organizations.c.id == org_id).values(audit_head=digest)
    )
    return event


def verify_chain(conn: Connection, org_id: str) -> tuple[bool, int]:
    """Recompute the chain; returns (ok, events_checked)."""
    prev = GENESIS_HASH
    n = 0
    rows = conn.execute(
        sa.select(audit_events.c.doc)
        .where(audit_events.c.org_id == org_id)
        .order_by(audit_events.c.seq)
    ).scalars()
    for doc in rows:
        body = {k: v for k, v in doc.items() if k not in ("hash", "prev_hash")}
        if doc["prev_hash"] != prev or audit_hash(prev, body) != doc["hash"]:
            return False, n
        prev = doc["hash"]
        n += 1
    return True, n
