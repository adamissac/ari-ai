"""Research-only payment-read decisions; no gateway or serving registration.

Inputs are trusted fixture/operator observations, never traffic-generator labels or
request-supplied grants. This is an internal experimental type, not a shared API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ReadGrant:
    """Exact-resource fixture grant with explicit validity and revocation."""

    principal: str
    owner: str
    resource: str
    valid_from: int
    expires_at: int
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.principal or not self.owner or not self.resource:
            raise ValueError("grant identity and resource must be present")
        if type(self.valid_from) is not int or type(self.expires_at) is not int:
            raise ValueError("grant validity uses integer fixture ticks")
        if self.expires_at <= self.valid_from or type(self.revoked) is not bool:
            raise ValueError("invalid grant interval or revocation")


@dataclass(frozen=True)
class ReadContext:
    """An atomic fixture snapshot; None grants means unknown, not no grants."""

    principal: str | None
    owner: str | None
    resource: str
    grants: tuple[ReadGrant, ...] | None
    observed_at: int
    fresh_until: int
    contradictory: bool = False


@dataclass(frozen=True)
class ReadDecision:
    outcome: Literal["allow", "deny", "abstain"]
    reason: str


def authorize_read(context: ReadContext, *, now: int) -> ReadDecision:
    """Pure, stateless exact-resource check with half-open validity intervals.

    Abstention must not forward a request. The research fixture maps deny to 404
    and abstain to 503; neither represents an authorized production control.
    """
    if (
        type(now) is not int
        or type(context.observed_at) is not int
        or type(context.fresh_until) is not int
        or context.contradictory is not False
        or not context.observed_at <= now < context.fresh_until
        or not context.principal
        or not context.owner
        or not context.resource
        or context.grants is None
    ):
        return ReadDecision("abstain", "missing, stale or contradictory context")
    if context.principal == context.owner:
        return ReadDecision("allow", "owner")
    for grant in context.grants:
        if (
            grant.principal == context.principal
            and grant.owner == context.owner
            and grant.resource == context.resource
            and grant.valid_from <= now < grant.expires_at
            and not grant.revoked
        ):
            return ReadDecision("allow", "explicit resource grant")
    return ReadDecision("deny", "no valid resource grant")
