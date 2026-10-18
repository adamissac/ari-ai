"""Response policy: learned recommendation, deterministic floor, final proposal.

Three separate records, never merged:

* ``RLInference``  what the hash-pinned Double DQN checkpoint recommended for an
  observation built from this incident (or why it could not run). The policy was
  trained offline in the DefenseSimEnv simulator; here it only runs inference.
* ``RuleEvaluation``  the deterministic minimum response for the detection category.
* ``FinalDecision``  the stronger of the two, and which one selected it.

The RL action vocabulary (noop, raise_monitoring, rate_limit, isolate,
request_reassessment, escalate_to_human) maps onto live action kinds only where a live
adapter exists; ``isolate`` has none and is never executed. When the learned policy is
unavailable or its input is rejected, ``selected_by`` is ``rules`` and the reason is
recorded, so a rule-selected block is never presented as an RL decision.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.settings import get_settings
from shared.live_defense import (
    DefenseActionKind,
    FinalDecision,
    RLActionScore,
    RLInference,
    RuleEvaluation,
)
from shared.rl import NodeSignals, PlatformFacts

log = logging.getLogger(__name__)

K = DefenseActionKind
STRENGTH: dict[DefenseActionKind | None, int] = {
    None: 0,
    K.increase_logging: 1,
    K.request_reassessment: 1,
    K.escalate: 1,
    K.rate_limit: 2,
    K.block_source: 3,
}
DEFAULT_DURATION_S = {K.block_source: 600, K.rate_limit: 600, K.increase_logging: 1800}

# Which simulator node an incident category stands for, and the static node facts.
CATEGORY_NODE = {
    "credential_attack": "auth",
    "scanning": "gateway",
    "waf_alert": "api",
    "error_spike": "api",
}
NODES: tuple[tuple[str, float, bool], ...] = (
    ("gateway", 0.5, True),
    ("api", 0.7, True),
    ("auth", 0.8, True),
    ("payments", 1.0, False),
    ("db", 1.0, False),
)
SEVERITY_SCORE = {"low": 0.25, "medium": 0.5, "high": 0.8, "critical": 1.0}

# Test seam: an object with ``policy_version``, ``checkpoint_sha256`` and ``recommend(facts)``.
# Tests that set it must label their runner as a test runner; production never sets it.
RUNNER_OVERRIDE: Any = None
_RUNNERS: dict[str, Any] = {}


@dataclass(frozen=True)
class IncidentFacts:
    project_id: str
    category: str
    source: str | None
    severity: str
    event_count: int
    routes: tuple[str, ...]
    last_event_at: datetime
    now: datetime


# ------------------------------------------------------------------ rules


def rules_floor(f: IncidentFacts) -> RuleEvaluation:
    if f.category in ("credential_attack", "scanning", "waf_alert") and f.source:
        duration = {"credential_attack": 600, "scanning": 300, "waf_alert": 900}[f.category]
        return RuleEvaluation(
            rule_id=f"floor_{f.category}_block_source",
            minimum_kind=K.block_source,
            target=f.source,
            duration_s=duration,
            rationale=(
                f"{f.category.replace('_', ' ')} from one source: block that single address "
                f"for {duration // 60} min (reversible, expires automatically)"
            ),
        )
    if f.category == "error_spike":
        return RuleEvaluation(
            rule_id="floor_error_spike_escalate",
            minimum_kind=K.escalate,
            target=None,
            duration_s=None,
            rationale="application-wide errors have no single source to block: escalate to a person",
        )
    return RuleEvaluation(
        rule_id="floor_escalate",
        minimum_kind=K.escalate,
        target=None,
        duration_s=None,
        rationale="no safe automatic control for this pattern: escalate to a person",
    )


# ------------------------------------------------------------------ RL


def platform_facts(f: IncidentFacts) -> tuple[PlatformFacts, dict[str, str]]:
    focus = CATEGORY_NODE.get(f.category, "api")
    nodes = []
    for name, criticality, exposed in NODES:
        hit = name == focus
        nodes.append(
            NodeSignals(
                node=name,  # type: ignore[arg-type]
                criticality=criticality,
                exposed=exposed,
                alert_rate=min(f.event_count / 10.0, 5.0) if hit else 0.0,
                anomaly_score=SEVERITY_SCORE.get(f.severity, 0.5) if hit else 0.0,
            )
        )
    facts = PlatformFacts(project_id=f.project_id, nodes=nodes)
    provenance = {
        "source": "live telemetry (authenticated ingest)",
        "focus_node": focus,
        "alert_rate": f"min(evidence events / 10, 5) = {min(f.event_count / 10.0, 5.0):.2f}",
        "anomaly_score": f"incident severity {f.severity} → {SEVERITY_SCORE.get(f.severity, 0.5)}",
        "criticality": "static per simulator node",
        "other_nodes": "no signals (zero)",
    }
    return facts, provenance


def _load_runner() -> tuple[Any | None, str]:
    if RUNNER_OVERRIDE is not None:
        return RUNNER_OVERRIDE, "test runner"
    settings = get_settings()
    path = settings.rl_checkpoint_path
    if path is None:
        return None, "RL_CHECKPOINT_PATH is not configured"
    if not path.exists():
        return None, f"checkpoint file {path.name} not found"
    try:
        from backend.pipeline import verify_rl_checkpoint

        blob, sha = verify_rl_checkpoint(settings)
    except Exception as exc:  # hash mismatch or missing pin: never load it
        return None, f"checkpoint rejected: {exc}"[:300]
    if sha in _RUNNERS:
        return _RUNNERS[sha], "loaded"
    try:
        from rl_defense import api as rl_api
    except Exception as exc:
        return None, f"rl_defense/torch not importable in this worker: {type(exc).__name__}"
    try:
        runner = rl_api.load_policy(path, blob=blob)
    except Exception as exc:
        return None, f"checkpoint failed to load: {type(exc).__name__}: {exc}"[:300]
    _RUNNERS.clear()
    _RUNNERS[sha] = runner
    return runner, "loaded"


def rl_status() -> tuple[bool, bool, str | None, str]:
    """(configured, loadable, policy_version, reason) without running inference."""
    configured = RUNNER_OVERRIDE is not None or get_settings().rl_checkpoint_path is not None
    runner, reason = _load_runner()
    if runner is None:
        return configured, False, None, reason
    return configured, True, str(runner.policy_version), reason


def _map(action: str, f: IncidentFacts) -> tuple[DefenseActionKind | None, str | None, str]:
    route = f.routes[0] if len(f.routes) == 1 else None
    if action == "noop":
        return None, None, "noop: the policy proposed no action"
    if action == "raise_monitoring":
        return K.increase_logging, route, "raise_monitoring → increase_logging"
    if action == "rate_limit":
        if route:
            return K.rate_limit, route, f"rate_limit → rate_limit on {route}"
        return None, None, "rate_limit needs one route; the evidence spans several, so not mapped"
    if action == "isolate":
        return None, None, "isolate has no live adapter and is never executed"
    if action == "request_reassessment":
        return K.request_reassessment, None, "request_reassessment → recorded reassessment request"
    if action == "escalate_to_human":
        return K.escalate, None, "escalate_to_human → escalate"
    return None, None, f"unknown action {action!r} not mapped"


def rl_infer(f: IncidentFacts) -> tuple[RLInference, str | None]:
    """Returns the inference record and the mapped target (if any)."""
    window = get_settings().live_defense_stale_after_s
    age = (f.now - f.last_event_at).total_seconds()
    facts, provenance = platform_facts(f)
    if age > window:
        return RLInference(
            status="rejected_input",
            reason=f"stale telemetry: newest evidence is {age:.0f}s old (limit {window}s)",
            observation_provenance=provenance,
        ), None
    runner, why = _load_runner()
    if runner is None:
        return RLInference(
            status="unavailable", reason=why, observation_provenance=provenance
        ), None
    try:
        local = facts
        try:
            from rl_defense import api as rl_api

            local = rl_api.PlatformFacts.model_validate(facts.model_dump(mode="json"))
        except Exception:
            pass  # test runners accept shared PlatformFacts
        rec = runner.recommend(local)
        scores = [
            RLActionScore(action=str(s.action), node=s.node, q_value=float(s.q_value))
            for s in rec.top_actions
        ]
        if any(not math.isfinite(s.q_value) for s in scores):
            return RLInference(
                status="rejected_input",
                reason="non-finite Q-values: output not trusted",
                policy_version=str(rec.policy_version),
                observation_provenance=provenance,
            ), None
        explanation = None
        if hasattr(runner, "explain"):
            try:
                explanation = runner.explain(local).model_dump(mode="json")
            except Exception:
                log.exception("rl explanation failed")
        kind, target, note = _map(str(rec.action), f)
        return RLInference(
            status="ok",
            reason="inference ran on the hash-verified checkpoint",
            policy_version=str(rec.policy_version),
            checkpoint_sha256=str(rec.checkpoint_sha256),
            action=str(rec.action),
            node=rec.node,
            q_margin=float(rec.q_margin),
            top_actions=scores,
            mapped_kind=kind,
            mapping_note=note,
            observation_provenance=provenance,
            explanation=explanation,
        ), target
    except Exception as exc:
        log.exception("rl inference failed")
        return RLInference(
            status="error",
            reason=f"inference error: {type(exc).__name__}: {exc}"[:500],
            observation_provenance=provenance,
        ), None


# ------------------------------------------------------------------ final


def decide(f: IncidentFacts) -> tuple[RLInference, RuleEvaluation, FinalDecision]:
    rl, rl_target = rl_infer(f)
    rule = rules_floor(f)
    rl_kind = rl.mapped_kind if rl.status == "ok" else None
    if rl.status != "ok":
        final = FinalDecision(
            kind=rule.minimum_kind,
            target=rule.target,
            duration_s=rule.duration_s,
            selected_by="rules" if rule.minimum_kind else "none",
            reason=f"deterministic fallback: learned policy {rl.status} ({rl.reason})",
        )
    elif rl_kind is not None and rl_kind == rule.minimum_kind:
        final = FinalDecision(
            kind=rule.minimum_kind,
            target=rule.target,
            duration_s=rule.duration_s,
            selected_by="rl_and_rules",
            reason="the learned policy and the rule floor chose the same control",
        )
    elif STRENGTH[rl_kind] > STRENGTH[rule.minimum_kind]:
        final = FinalDecision(
            kind=rl_kind,
            target=rl_target,
            duration_s=DEFAULT_DURATION_S.get(rl_kind) if rl_kind else None,
            selected_by="rl",
            reason=f"the learned policy proposed a stronger control than the rule floor ({rl.action})",
        )
    else:
        final = FinalDecision(
            kind=rule.minimum_kind,
            target=rule.target,
            duration_s=rule.duration_s,
            selected_by="rules" if rule.minimum_kind else "none",
            reason=(
                f"the rule floor ({rule.rule_id}) is stronger than the learned policy's "
                f"{rl.action or 'output'} ({rl.mapping_note or 'no mapping'})"
            ),
        )
    return rl, rule, final
