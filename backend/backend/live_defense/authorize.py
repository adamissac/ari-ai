"""Independent authorization gate for defensive controls. Pure: no I/O, ``now`` passed in.

The policy (learned or rule-based) only *proposes*. This gate reads the proposal's kind,
target and duration, the owner's grants and the recorded action history, and nothing
else; model output never reaches it beyond those typed values.

Outcomes:
  * ``denied``          a hard rule failed (not allowlisted, unsafe target, protected
                        source, disabled application, duration over the hard cap);
  * ``requires_human``  allowed in principle, but automatic execution is not permitted
                        (auto-response off, no owner grant, budget used, duration above
                        the grant) — a person must approve;
  * ``authorized``      every check passed for the requested mode;
  * ``not_applicable``  there is nothing to execute.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Literal

from shared.live_defense import AuthorizationCheck, AuthorizationResult, DefenseActionKind

EXTERNAL_KINDS = frozenset(
    {
        DefenseActionKind.block_source,
        DefenseActionKind.rate_limit,
        DefenseActionKind.increase_logging,
    }
)
INTERNAL_KINDS = frozenset({DefenseActionKind.escalate, DefenseActionKind.request_reassessment})
HARD_MAX_DURATION_S = 24 * 3600
ROUTE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /[^\s]{0,290}$")


@dataclass(frozen=True)
class Proposal:
    kind: DefenseActionKind | None
    target: str | None
    duration_s: int | None


@dataclass(frozen=True)
class Grant:
    max_duration_s: int
    hourly_budget: int


@dataclass(frozen=True)
class AppFacts:
    enabled: bool
    auto_response: bool
    protected_sources: frozenset[str] = field(default_factory=frozenset)


def _target_problem(
    kind: DefenseActionKind, target: str | None, protected: frozenset[str]
) -> str | None:
    if kind is DefenseActionKind.block_source:
        if not target or "/" in target:
            return "block_source needs exactly one address (no ranges)"
        try:
            ip = ipaddress.ip_address(target)
        except ValueError:
            return f"{target!r} is not an IP address"
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return f"{ip} is loopback, link-local, multicast or unspecified"
        if str(ip) in protected:
            return f"{ip} is on the owner's protected list"
        return None
    if kind is DefenseActionKind.rate_limit:
        return None if target and ROUTE.match(target) else "rate_limit needs one 'METHOD /route'"
    if kind is DefenseActionKind.increase_logging:
        return None if target is None or ROUTE.match(target) else "logging target must be a route"
    return None


def check(
    proposal: Proposal,
    app: AppFacts,
    grants: dict[DefenseActionKind, Grant],
    used_last_hour: dict[DefenseActionKind, int],
    mode: Literal["automatic", "human"],
) -> AuthorizationResult:
    checks: list[AuthorizationCheck] = []

    def add(name: str, passed: bool, detail: str) -> bool:
        checks.append(AuthorizationCheck(name=name, passed=passed, detail=detail[:500]))
        return passed

    def result(outcome: str, code: str, detail: str) -> AuthorizationResult:
        return AuthorizationResult(
            outcome=outcome,  # type: ignore[arg-type]
            reason_code=code,
            detail=detail[:500],
            checks=checks,
        )

    kind = proposal.kind
    if kind is None:
        return result("not_applicable", "NO_ACTION", "the decision was to take no action")
    if not add(
        "allowlist",
        kind in EXTERNAL_KINDS | INTERNAL_KINDS,
        f"{kind} is {'on' if kind in EXTERNAL_KINDS | INTERNAL_KINDS else 'not on'} the allowlist",
    ):
        return result("denied", "NOT_ALLOWLISTED", f"{kind} has no adapter")
    if kind in INTERNAL_KINDS:
        add("internal", True, "recorded and notified inside the platform; nothing is executed")
        return result("authorized", "INTERNAL_ONLY", f"{kind} only records and notifies")
    if not add("app_enabled", app.enabled, "application enabled" if app.enabled else "disabled"):
        return result("denied", "APP_DISABLED", "the application is disabled for live defense")
    problem = _target_problem(kind, proposal.target, app.protected_sources)
    if not add("blast_radius", problem is None, problem or f"single target {proposal.target}"):
        return result("denied", "UNSAFE_TARGET", problem or "")
    duration = proposal.duration_s or 0
    if not add(
        "duration_cap",
        0 < duration <= HARD_MAX_DURATION_S,
        f"{duration}s (hard cap {HARD_MAX_DURATION_S}s, every control expires)",
    ):
        return result("denied", "DURATION_INVALID", "a control must expire within 24 hours")

    if mode == "human":
        add("human_decision", True, "a person with owner role approved this control")
        return result("authorized", "HUMAN_APPROVED", "approved by a person; hard checks passed")

    soft: list[tuple[str, str]] = []
    if not add(
        "auto_response", app.auto_response, f"auto-response {'on' if app.auto_response else 'off'}"
    ):
        soft.append(("AUTO_RESPONSE_OFF", "automatic response is off for this application"))
    grant = grants.get(kind)
    if not add(
        "owner_grant", grant is not None, f"owner grant for {kind}: {'yes' if grant else 'none'}"
    ):
        soft.append(("NO_GRANT", f"the owner has not pre-authorized {kind}"))
    if grant is not None:
        if not add(
            "grant_duration",
            duration <= grant.max_duration_s,
            f"{duration}s requested, grant allows {grant.max_duration_s}s",
        ):
            soft.append(("DURATION_ABOVE_GRANT", "duration above the owner's grant"))
        used = used_last_hour.get(kind, 0)
        if not add(
            "hourly_budget",
            used < grant.hourly_budget,
            f"{used} of {grant.hourly_budget} automatic {kind} actions used in the last hour",
        ):
            soft.append(("BUDGET_EXHAUSTED", "the hourly budget for this control is used up"))
    if soft:
        return result("requires_human", soft[0][0], "; ".join(d for _, d in soft))
    return result("authorized", "PRE_AUTHORIZED", "owner grant, budget and blast radius allow it")
