"""`scope_guard`: pure, deterministic authorization decisions (docs/15 §3).

No I/O. The caller loads the scope and passes `now`. Called (a) at SCOPE_CHECK,
(b) before every network-capable tool invocation, (c) by the sandbox driver
before attaching a target network. Model output never reaches this function
except as already-validated typed arguments (a `target_id`, a category string).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .contracts import AgentName, AuthorizedScope, ScopeStatus, StrictModel

# Only these agents may ever trigger execution against a target.
NETWORK_AGENTS: frozenset[AgentName] = frozenset({AgentName.PROBE, AgentName.VERIFY})

ReasonCode = Literal[
    "OK",
    "MISSING_SCOPE",
    "SCOPE_NOT_ACTIVE",
    "SCOPE_EXPIRED",
    "SCOPE_NOT_APPROVED",
    "APPROVER_IS_REQUESTER",
    "TARGET_NOT_IN_SCOPE",
    "UNSUPPORTED_TARGET_KIND",
    "CATEGORY_NOT_ALLOWED",
    "CATEGORY_REQUIRED",
    "AGENT_NOT_PERMITTED",
]


class ActionRequest(StrictModel):
    action: Literal["assessment_start", "run_check", "attach_network", "build_target"]
    target_id: str | None = None
    check_category: str | None = None
    agent: AgentName | None = None


class Decision(StrictModel):
    allowed: bool
    reason_code: ReasonCode
    scope_id: str | None
    evaluated_at: datetime
    detail: str = Field(default="", max_length=300)


def _deny(scope: AuthorizedScope | None, now: datetime, code: ReasonCode, detail: str = "") -> Decision:
    return Decision(
        allowed=False,
        reason_code=code,
        scope_id=scope.id if scope else None,
        evaluated_at=now,
        detail=detail,
    )


def check(
    scope: AuthorizedScope | None,
    request: ActionRequest,
    now: datetime,
    *,
    org_member_count: int = 1,
) -> Decision:
    """Decide whether `request` is allowed under `scope` at time `now`. Fails closed."""
    if scope is None:
        return _deny(None, now, "MISSING_SCOPE")
    if scope.status != ScopeStatus.ACTIVE:
        return _deny(scope, now, "SCOPE_NOT_ACTIVE", f"status={scope.status.value}")
    if now.tzinfo is None or scope.expires_at.tzinfo is None:
        return _deny(scope, now, "SCOPE_EXPIRED", "naive datetime rejected")
    if now >= scope.expires_at:
        return _deny(scope, now, "SCOPE_EXPIRED")
    if scope.approved_by is None or scope.approved_at is None:
        return _deny(scope, now, "SCOPE_NOT_APPROVED")
    if org_member_count > 1 and scope.approved_by == scope.requested_by:
        return _deny(scope, now, "APPROVER_IS_REQUESTER")

    if request.action == "assessment_start":
        return Decision(allowed=True, reason_code="OK", scope_id=scope.id, evaluated_at=now)

    # Every remaining action touches a target.
    if request.agent is not None and request.agent not in NETWORK_AGENTS:
        return _deny(scope, now, "AGENT_NOT_PERMITTED", f"agent={request.agent.value}")
    if request.target_id is None:
        return _deny(scope, now, "TARGET_NOT_IN_SCOPE", "no target id")
    target = next((t for t in scope.targets if t.target_id == request.target_id), None)
    if target is None:
        return _deny(scope, now, "TARGET_NOT_IN_SCOPE", f"target={request.target_id[:80]}")
    if target.kind != "sandbox_build":
        return _deny(scope, now, "UNSUPPORTED_TARGET_KIND")
    if request.action == "run_check":
        if not request.check_category:
            return _deny(scope, now, "CATEGORY_REQUIRED")
        from shared.scope import check_category_allowed

        if not check_category_allowed(request.check_category, scope.allowed_check_categories):
            return _deny(scope, now, "CATEGORY_NOT_ALLOWED", request.check_category[:80])
    return Decision(allowed=True, reason_code="OK", scope_id=scope.id, evaluated_at=now)
