"""Map platform records (findings, expectations, monitoring signals) to ``PlatformFacts``.

This is how the RL recommendation stays connected to the rest of the product: open
validated findings raise a node's ``finding_severity``, expectation data-sensitivity
tags set its ``criticality``, and monitoring signals feed its alert/anomaly inputs.
A verified fix removes the finding's contribution, so the recommendation changes.

Inputs mirror docs/12 (Finding, SeverityAssessment, BehavioralExpectation,
MonitoringEvent) as local typed adapters — PENDING SHARED CONTRACT (owner: Srihith).
The route→node topology is a hand-written per-project config (MVP), e.g.
``configs/topology/payments_lite.yaml``.

Principal detection (contracts 0.14): a reporter whose instrumentation sees who each bearer
token belongs to, and who owns each requested object, sends pseudonymous per-principal
counters with its route windows (``shared.monitoring.PrincipalCounts``).
:func:`principal_facts` turns the latest window's counters into the live v3
``PlatformFacts`` fields. These are the same definitions the live lab loop computes
(``rl_defense.live.loop``, tested for equality), and they make a principal block a valid
action for live_v2/v3 policies. The platform enforces nothing, so no block is ever "in
force" here: ``principal_block_active``, ``block_remaining`` and ``flagged_repeat`` stay 0.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rl_defense.contracts import NodeName, NodeSignals, PlatformFacts
from rl_defense.envs.config import NODE_NAMES

SeverityLevel = Literal["info", "low", "medium", "high", "critical"]
DataSensitivity = Literal["none", "internal", "personal", "financial"]

SEVERITY_SCORE: dict[str, float] = {
    "info": 0.1,
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}
SENSITIVITY_CRITICALITY: dict[str, float] = {
    "none": 0.2,
    "internal": 0.4,
    "personal": 0.7,
    "financial": 0.9,
}
# Finding statuses (docs/12) that still represent an open, *evidence-backed* risk.
# Hypotheses are excluded: unvalidated suspicions must not move the policy.
# ``accepted_risk`` counts: a human accepted the risk, but the weakness is still there.
OPEN_VALIDATED_STATUSES = frozenset(
    {
        "validated",
        "diagnosed",
        "patch_proposed",
        "patch_rejected",
        "unresolved",
        "needs_recheck",
        "accepted_risk",
    }
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TopologyNode(_Strict):
    node: NodeName
    route_patterns: tuple[str, ...] = Field(description="fnmatch patterns, e.g. 'GET /payments/*'")
    exposed: bool
    criticality_floor: float = Field(0.0, ge=0.0, le=1.0)


class ProjectTopology(_Strict):
    project: str
    nodes: tuple[TopologyNode, ...] = Field(min_length=5, max_length=5)
    default_node: NodeName = "api"

    def node_for_route(self, route: str) -> str:
        for n in self.nodes:
            if any(fnmatch.fnmatchcase(route, pat) for pat in n.route_patterns):
                return n.node
        return self.default_node


class FindingInput(_Strict):
    id: str
    status: str
    severity: SeverityLevel | None = None
    routes: tuple[str, ...] = Field(description="Affected entry points as 'METHOD /path/template'")


class ExpectationInput(_Strict):
    id: str
    route: str
    data_sensitivity: DataSensitivity = "none"
    status: str = "proposed"  # proposed | confirmed | rejected


class RouteSignal(_Strict):
    route: str
    alert_rate: float = Field(0.0, ge=0.0)
    anomaly_score: float = Field(0.0, ge=0.0, le=1.0)
    source: Literal["runtime_demo", "replay", "simulated"] = Field(
        description="Provenance label; there is no production telemetry source in MVP"
    )


class PrincipalCount(_Strict):
    """One principal's requests on one route in one window (pseudonymous ref)."""

    principal: str
    cross_tenant: int = Field(0, ge=0)
    delegated: int = Field(0, ge=0)
    own: int = Field(0, ge=0)


class RouteDetection(_Strict):
    """The latest window of one route from a reporter that detects principals: request
    and error totals plus per-principal counters (``shared.monitoring.RouteWindow``)."""

    route: str
    source: Literal["runtime_demo", "replay", "simulated"]
    requests: int = Field(ge=0)
    status_4xx: int = Field(0, ge=0)
    status_5xx: int = Field(0, ge=0)
    principals: tuple[PrincipalCount, ...] = ()


# How much of the anomalous fraction the lab's detector reports per monitoring level
# (rl_defense/live/telemetry.py; kept in step by a test).
MONITORING_SENSITIVITY = {0: 0.5, 1: 0.75, 2: 1.0}


class PrincipalTargets(_Strict):
    """Whom each block action would cover: every flagged principal, or the heaviest."""

    all: tuple[str, ...] = ()
    top: tuple[str, ...] = ()


def principal_facts(
    topology: ProjectTopology, detections: list[RouteDetection]
) -> tuple[dict[str, float | bool], PrincipalTargets]:
    """Live v3 ``PlatformFacts`` field values and block targets from principal counters.

    A principal is *flagged* when it attempted at least one cross-tenant read that no
    delegation grant covers (the reporter applied the grants). Definitions follow the lab
    loop's detector features (rl_defense/layouts.py):

    - ``flagged_principals`` = flagged / 3 (capped at 1)
    - ``flagged_volume``     = cross-tenant attempts per flagged principal / 6 (capped)
    - ``flagged_own_share``  = share of the flagged principals' requests that were not
      cross-tenant (own data, no tenant object, or covered by a grant)
    - ``flagged_top_share``  = heaviest flagged principal's share of the cross-tenant attempts
    - the three availabilities are True iff anything is flagged (nothing is ever blocked
      here, so every flagged principal is "not yet blocked")
    """
    cross: dict[str, int] = {}
    total: dict[str, int] = {}
    for d in detections:
        for p in d.principals:
            cross[p.principal] = cross.get(p.principal, 0) + p.cross_tenant
            total[p.principal] = total.get(p.principal, 0) + p.cross_tenant + p.delegated + p.own
    flagged = sorted(k for k, v in cross.items() if v > 0)
    n = len(flagged)
    if not n:
        return {}, PrincipalTargets()
    c = sum(cross[k] for k in flagged)
    t = sum(total[k] for k in flagged)
    hi = max(cross[k] for k in flagged)
    fields: dict[str, float | bool] = {
        "principal_block_available": True,
        "principal_block_long_available": True,
        "principal_block_top_long_available": True,
        "flagged_principals": min(1.0, n / 3),
        "flagged_volume": min(1.0, c / (6 * n)),
        "flagged_own_share": (t - c) / t if t else 0.0,
        "flagged_top_share": hi / c,
    }
    return fields, PrincipalTargets(
        all=tuple(flagged), top=tuple(k for k in flagged if cross[k] == hi)
    )


class DefenseState(_Strict):
    """Defensive measures currently in effect (recorded by humans; the platform applies none)."""

    monitoring_level: dict[str, int] = Field(default_factory=dict)
    rate_limited: frozenset[str] = frozenset()
    isolated: frozenset[str] = frozenset()
    reassessment_pending: frozenset[str] = frozenset()


def load_topology(path: str | Path) -> ProjectTopology:
    return ProjectTopology.model_validate(yaml.safe_load(Path(path).read_text()))


def facts_from_platform(
    topology: ProjectTopology,
    findings: list[FindingInput],
    expectations: list[ExpectationInput],
    signals: list[RouteSignal] | None = None,
    defense: DefenseState | None = None,
    *,
    detections: list[RouteDetection] | None = None,
    project_id: str | None = None,
    time_fraction: float = 0.0,
    escalations_remaining_fraction: float = 1.0,
) -> tuple[PlatformFacts, dict[str, list[str]]]:
    """Return ``PlatformFacts`` plus provenance: which record ids drove each node's inputs.

    With ``detections`` (a reporter that detects principals) two things change, both
    matching the live lab's detector so a live policy sees what it was trained on:

    - each node's ``alert_rate`` / ``anomaly_score`` is at least the lab's detection signal:
      anomalous = cross-tenant attempts + error responses (capped at the route's requests),
      ``alert_rate`` = anomalous count, ``anomaly_score`` = anomalous / requests scaled by
      the node's monitoring sensitivity (the max with the route heuristics is kept);
    - the live v3 principal fields are filled (:func:`principal_facts`), and the provenance
      gains ``principal_targets:all`` / ``principal_targets:top``."""
    defense = defense or DefenseState()
    by_node = {n.node: n for n in topology.nodes}
    if set(by_node) != set(NODE_NAMES):
        raise ValueError(f"topology must cover exactly {NODE_NAMES}")
    severity = dict.fromkeys(NODE_NAMES, 0.0)
    criticality = {n: by_node[n].criticality_floor for n in NODE_NAMES}
    alert = dict.fromkeys(NODE_NAMES, 0.0)
    anomaly = dict.fromkeys(NODE_NAMES, 0.0)
    provenance: dict[str, list[str]] = {n: [] for n in NODE_NAMES}

    for f in findings:
        if f.status not in OPEN_VALIDATED_STATUSES or f.severity is None:
            continue
        for route in f.routes:
            node = topology.node_for_route(route)
            severity[node] = max(severity[node], SEVERITY_SCORE[f.severity])
            provenance[node].append(f.id)
    for e in expectations:
        if e.status == "rejected":
            continue
        node = topology.node_for_route(e.route)
        criticality[node] = max(criticality[node], SENSITIVITY_CRITICALITY[e.data_sensitivity])
        provenance[node].append(e.id)
    for s in signals or []:
        node = topology.node_for_route(s.route)
        alert[node] += s.alert_rate
        anomaly[node] = max(anomaly[node], s.anomaly_score)
        provenance[node].append(f"signal:{s.source}:{s.route}")
    det_anom = dict.fromkeys(NODE_NAMES, 0)
    det_total = dict.fromkeys(NODE_NAMES, 0)
    for d in detections or []:
        node = topology.node_for_route(d.route)
        cross = sum(p.cross_tenant for p in d.principals)
        det_anom[node] += min(d.requests, cross + d.status_4xx + d.status_5xx)
        det_total[node] += d.requests
        provenance[node].append(f"detection:{d.source}:{d.route}")
    for n in NODE_NAMES:
        if det_total[n]:
            sens = MONITORING_SENSITIVITY.get(defense.monitoring_level.get(n, 0), 1.0)
            alert[n] = max(alert[n], float(det_anom[n]))
            anomaly[n] = max(anomaly[n], min(1.0, det_anom[n] / det_total[n] * sens))

    nodes = tuple(
        NodeSignals(
            node=n,
            criticality=criticality[n],
            exposed=by_node[n].exposed,
            finding_severity=severity[n],
            alert_rate=alert[n],
            anomaly_score=anomaly[n],
            monitoring_level=defense.monitoring_level.get(n, 0),
            rate_limited=n in defense.rate_limited,
            isolated=n in defense.isolated,
            reassessment_pending=n in defense.reassessment_pending,
        )
        for n in NODE_NAMES
    )
    pfields, targets = principal_facts(topology, detections or [])
    facts = PlatformFacts(
        project_id=project_id,
        nodes=nodes,
        time_fraction=time_fraction,
        escalations_remaining_fraction=escalations_remaining_fraction,
        **pfields,
    )
    if detections:
        provenance["principal_targets:all"] = list(targets.all)
        provenance["principal_targets:top"] = list(targets.top)
    return facts, provenance
