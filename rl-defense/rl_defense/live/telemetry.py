"""Turn real request records into ``PlatformFacts`` (the policy's observation source).

Signals are measured, not assumed:
- ``alert_rate``  = number of anomalous requests seen on the node this window
  (cross-tenant attempts flagged by the gateway's instrumentation, or errors the app
  returned). Normalized downstream by ``observations.from_platform_facts`` (ALERT_NORM).
- ``anomaly_score`` = the fraction of the node's traffic that looked anomalous, scaled
  by how much monitoring is raised (more monitoring → the detector sees more of the
  true anomaly fraction). A higher ``monitoring_level`` therefore sharpens detection
  without disrupting traffic — exactly the intended effect of ``raise_monitoring``.
"""

from __future__ import annotations

from collections.abc import Iterable

from rl_defense.contracts import NodeSignals, PlatformFacts
from rl_defense.envs.config import NODE_NAMES
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import RequestRecord
from rl_defense.live.topology import RouteTopology

# How much of the true anomaly fraction the detector surfaces at each monitoring level.
_MONITORING_SENSITIVITY = {0: 0.5, 1: 0.75, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}


def _anomalous(r: RequestRecord) -> bool:
    """Observable anomaly: a cross-tenant attempt seen by the gateway (whether or not it
    was blocked), or an error the app itself returned. Our own blocking of a request is
    not evidence of an attack, and the generator's ``is_attack`` label is never read."""
    return r.cross_tenant_attempt or (r.allowed and r.status >= 400)


def build_facts(
    records: Iterable[RequestRecord],
    controls: DefenseControls,
    topology: RouteTopology,
    *,
    finding_severity: dict[str, float],
    step: int,
    horizon: int,
    escalations_used: int,
    max_escalations: int,
    escalation_pending: bool,
    max_monitoring_level: int = 2,
) -> PlatformFacts:
    recs = list(records)
    per_node: dict[str, list[RequestRecord]] = {n: [] for n in NODE_NAMES}
    for r in recs:
        per_node.setdefault(r.node, []).append(r)

    nodes: list[NodeSignals] = []
    for name in NODE_NAMES:
        node_recs = per_node.get(name, [])
        total = len(node_recs)
        anomalous = sum(1 for r in node_recs if _anomalous(r))
        mon = controls.monitoring_level.get(name, 0)
        sensitivity = _MONITORING_SENSITIVITY.get(mon, 1.0)
        anomaly_fraction = (anomalous / total) if total else 0.0
        nodes.append(
            NodeSignals(
                node=name,
                criticality=topology.node(name).criticality_floor,
                exposed=topology.node(name).exposed,
                finding_severity=float(finding_severity.get(name, 0.0)),
                alert_rate=float(anomalous),
                anomaly_score=min(1.0, anomaly_fraction * sensitivity),
                monitoring_level=min(mon, max_monitoring_level),
                rate_limited=controls.rate_limited.get(name, False),
                isolated=controls.isolated.get(name, False),
                reassessment_pending=controls.reassessment_pending.get(name, False),
            )
        )

    remaining = max(0, max_escalations - escalations_used)
    return PlatformFacts(
        project_id="prj_payments_lite",
        nodes=tuple(nodes),
        time_fraction=min(1.0, step / horizon) if horizon else 0.0,
        escalations_remaining_fraction=(remaining / max_escalations) if max_escalations else 0.0,
        escalation_pending=escalation_pending,
    )
