"""Frozen v6 shadow inference gates. Never executes a control.

v6 was trained with fixed baseline finding severities. On quiet windows with
real (0) severities it recommends ``escalate_to_human`` instead of ``noop``
(ADR-0017). This module therefore **does not** treat v6 as a trustworthy live
decision-maker when a serving assumption fails: it returns explicit abstention
and lets deterministic rules stand.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from monitoring.detect import RuleHit, WindowView, is_quiet
from shared.base import utcnow
from shared.live_defense import AuthorizationContext, InferenceStatus
from shared.monitoring import AUTHENTICATED_RUNTIME_SOURCES, RuntimeSource
from shared.rl import ActionScore, DefenseActionName, NodeName

log = logging.getLogger("backend.live_defense.policy")

REPO_ROOT = Path(__file__).resolve().parents[3]
V6_CHECKPOINT = REPO_ROOT / "rl-defense" / "results" / "live-retrain-v6" / "candidate_online.pt"
V6_SHA256 = "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1"
V6_OBS_DIM = 55
FRESHNESS = timedelta(minutes=30)
NODE_PATTERNS: tuple[tuple[NodeName, tuple[str, ...]], ...] = (
    ("gateway", ("* /health*", "* /docs*", "* /openapi.json")),
    ("api", ("* /customers*", "* /me*")),
    ("auth", ("* /auth/*", "* /login*", "* /token*", "* /sessions*")),
    ("payments", ("* /payments*", "* /refunds*")),
    ("db", ()),
)
DEFAULT_NODE: NodeName = "api"

_RUNNER: Any = None


@dataclass(frozen=True)
class ShadowInference:
    status: InferenceStatus
    reason: str | None
    action: DefenseActionName | None = None
    node: NodeName | None = None
    top_actions: list[ActionScore] | None = None
    q_margin: float | None = None
    observation: list[float] | None = None
    policy_version: str | None = None
    checkpoint_sha256: str | None = None
    principal_targets: list[str] | None = None
    feature_schema_ok: bool = False
    action_mask_valid: bool = False
    feature_mapping_note: str | None = None


def node_for_route(route: str) -> NodeName:
    import fnmatch

    for node, patterns in NODE_PATTERNS:
        if any(fnmatch.fnmatchcase(route, pat) for pat in patterns):
            return node
    return DEFAULT_NODE


def freshness_ok(window_end) -> bool:
    now = utcnow()
    return abs((now - window_end).total_seconds()) <= FRESHNESS.total_seconds()


def flagged_principals(windows: list[WindowView]) -> list[str]:
    seen: list[str] = []
    for window in windows:
        for principal in window.principals:
            if principal.cross_tenant > 0 and principal.principal not in seen:
                seen.append(principal.principal)
    return seen


def decide_inference(
    *,
    source: RuntimeSource,
    windows: list[WindowView],
    hits: list[RuleHit],
    auth: AuthorizationContext,
    window_end,
) -> ShadowInference:
    """Run frozen v6 only when every serving assumption holds; otherwise abstain."""
    if source not in AUTHENTICATED_RUNTIME_SOURCES:
        return ShadowInference(
            status=InferenceStatus.skipped_source,
            reason=f"source {source} is not authenticated owned staging",
        )
    if not windows:
        return ShadowInference(
            status=InferenceStatus.skipped_incomplete, reason="no scored windows in this batch"
        )
    if not freshness_ok(window_end):
        return ShadowInference(
            status=InferenceStatus.skipped_stale,
            reason="window is older than 30 minutes or in the future",
        )
    if is_quiet(windows, hits):
        return ShadowInference(
            status=InferenceStatus.skipped_quiet_window,
            reason=(
                "Quiet window: v6 was trained with fixed finding severities and is not "
                "a trustworthy live decision-maker here (ADR-0017)."
            ),
            feature_schema_ok=True,
            action_mask_valid=True,
        )
    if auth is not AuthorizationContext.verified:
        return ShadowInference(
            status=InferenceStatus.skipped_authorization,
            reason="ownership context missing; HTTP 200 is not treated as IDOR",
        )
    try:
        return _run_v6(windows)
    except Exception as exc:
        log.warning("v6 shadow inference unavailable: %s", exc)
        return ShadowInference(
            status=InferenceStatus.skipped_unavailable,
            reason=f"frozen v6 runner unavailable: {type(exc).__name__}",
        )


def _load_v6() -> tuple[Any, str]:
    global _RUNNER
    if not V6_CHECKPOINT.is_file():
        raise FileNotFoundError("v6 checkpoint missing")
    blob = V6_CHECKPOINT.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != V6_SHA256:
        raise ValueError("v6 checkpoint hash mismatch; refusing to load")
    if _RUNNER is None:
        from rl_defense.inference import PolicyRunner

        _RUNNER = PolicyRunner(V6_CHECKPOINT, blob=blob)
    return _RUNNER, digest


def _run_v6(windows: list[WindowView]) -> ShadowInference:
    from rl_defense import platform_mapping as pm
    from rl_defense.observations import from_platform_facts, mask_from_facts

    runner, digest = _load_v6()
    topology = _payments_lite_topology(pm)
    signals = [
        pm.RouteSignal(
            route=w.route,
            alert_rate=float(w.auth_failures + w.status_4xx + w.status_5xx),
            anomaly_score=min(1.0, w.anomaly_score),
            source="runtime_demo",
        )
        for w in windows
    ]
    detections = [
        pm.RouteDetection(
            route=w.route,
            source="runtime_demo",
            requests=w.requests,
            status_4xx=w.status_4xx,
            status_5xx=w.status_5xx,
            principals=tuple(
                pm.PrincipalCount(
                    principal=p.principal,
                    cross_tenant=p.cross_tenant,
                    delegated=p.delegated,
                    own=p.own,
                )
                for p in w.principals
            ),
        )
        for w in windows
        if w.principals
    ]
    facts, provenance = pm.facts_from_platform(topology, [], [], signals, detections=detections)
    obs = from_platform_facts(facts, space=runner.space)
    mask = mask_from_facts(facts, space=runner.space)
    note = (
        "Numeric PlatformFacts used RouteSignal.source=runtime_demo as a mapping "
        "adapter; LivePolicyDecision.telemetry_source stays owned_staging."
    )
    if obs.shape[-1] != V6_OBS_DIM:
        return ShadowInference(
            status=InferenceStatus.skipped_schema,
            reason=f"observation dim {obs.shape[-1]} != v6 {V6_OBS_DIM}",
            feature_schema_ok=False,
            feature_mapping_note=note,
        )
    if not mask.any():
        return ShadowInference(
            status=InferenceStatus.skipped_mask,
            reason="action mask has no valid actions",
            feature_schema_ok=True,
            action_mask_valid=False,
            feature_mapping_note=note,
        )
    rec = runner.recommend(facts)
    targets = list(provenance.get("principal_targets:all") or [])
    if rec.action in {"block_principal", "block_principal_long", "block_top_principal_long"}:
        if rec.action == "block_top_principal_long":
            targets = list(provenance.get("principal_targets:top") or targets)
        if not targets:
            return ShadowInference(
                status=InferenceStatus.skipped_target,
                reason=f"{rec.action} requires principal targets from the reporter",
                feature_schema_ok=True,
                action_mask_valid=True,
                feature_mapping_note=note,
            )
    top = [ActionScore(action=a.action, node=a.node, q_value=a.q_value) for a in rec.top_actions]
    return ShadowInference(
        status=InferenceStatus.ran,
        reason=None,
        action=rec.action,
        node=rec.node,
        top_actions=top,
        q_margin=rec.q_margin,
        observation=[float(x) for x in rec.observation],
        policy_version=rec.policy_version,
        checkpoint_sha256=digest,
        principal_targets=targets,
        feature_schema_ok=True,
        action_mask_valid=True,
        feature_mapping_note=note,
    )


def _payments_lite_topology(pm: Any) -> Any:
    nodes = []
    floors = {"gateway": 0.3, "api": 0.5, "auth": 0.7, "payments": 0.9, "db": 1.0}
    exposed = {"gateway": True, "api": True, "auth": False, "payments": False, "db": False}
    for node, patterns in NODE_PATTERNS:
        nodes.append(
            pm.TopologyNode(
                node=node,
                route_patterns=patterns,
                exposed=exposed[node],
                criticality_floor=floors[node],
            )
        )
    return pm.ProjectTopology(project="payments-lite", nodes=tuple(nodes), default_node="api")


def pick_rule_action(hits: list[RuleHit]) -> tuple[DefenseActionName | None, NodeName | None]:
    """Highest-impact deterministic suggestion. Ownership-unknown HTTP 200 is noop."""
    order = {
        "block_principal": 4,
        "escalate_to_human": 3,
        "raise_monitoring": 2,
        "noop": 1,
    }
    chosen: RuleHit | None = None
    for hit in hits:
        if hit.rule_id == "http_200_ownership_unknown":
            continue
        if chosen is None or order.get(hit.suggested_action, 0) > order.get(
            chosen.suggested_action, 0
        ):
            chosen = hit
    if chosen is None:
        return "noop", None
    node = node_for_route(chosen.route) if chosen.route else None
    return chosen.suggested_action, node
