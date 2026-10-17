"""Hash-chained audit events (docs/12 "Audit")."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import Field

from shared.base import JsonObject, Sha256Hex, ShortText, StrictModel, UtcDatetime
from shared.ids import AuditEventId, OrgId, ProjectId

GENESIS_HASH = "0" * 64


class ActorType(StrEnum):
    user = "user"
    system = "system"
    agent = "agent"
    github = "github"


class AuditEvent(StrictModel):
    id: AuditEventId
    seq: int = Field(ge=1, description="Per-org monotonically increasing sequence")
    org_id: OrgId
    project_id: ProjectId | None = None
    actor_type: ActorType
    actor_id: ShortText
    action: ShortText = Field(description="dotted verb, e.g. 'scope.approved'")
    subject_type: ShortText
    subject_id: ShortText
    at: UtcDatetime
    details: JsonObject = Field(default_factory=dict, description="Redacted JSON")
    prev_hash: Sha256Hex
    hash: Sha256Hex


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def audit_hash(prev_hash: str, body: dict[str, Any]) -> str:
    """``sha256(prev_hash || canonical_json(event_without_hash_fields))``."""
    payload = {k: v for k, v in body.items() if k not in {"hash", "prev_hash"}}
    return hashlib.sha256((prev_hash + canonical_json(payload)).encode()).hexdigest()
