"""Map platform records (findings, expectations, monitoring signals) to ``PlatformFacts``.

This is how the RL recommendation stays connected to the rest of the product: open
validated findings raise a node's ``finding_severity``, expectation data-sensitivity
tags set its ``criticality``, and monitoring signals feed its alert/anomaly inputs.
A verified fix removes the finding's contribution, so the recommendation changes.

Inputs mirror docs/12 (Finding, SeverityAssessment, BehavioralExpectation,
MonitoringEvent) as local typed adapters — PENDING SHARED CONTRACT (owner: Srihith).
The route→node topology is a hand-written per-project config (MVP), e.g.
``configs/topology/payments_lite.yaml``.
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
OPEN_VALIDATED_STATUSES = frozenset(
    {"validated", "diagnosed", "patch_proposed", "patch_rejected", "unresolved", "needs_recheck"}
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
    project_id: str | None = None,
    time_fraction: float = 0.0,
    escalations_remaining_fraction: float = 1.0,
) -> tuple[PlatformFacts, dict[str, list[str]]]:
    """Return ``PlatformFacts`` plus provenance: which record ids drove each node's inputs."""
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
    facts = PlatformFacts(
        project_id=project_id,
        nodes=nodes,
        time_fraction=time_fraction,
        escalations_remaining_fraction=escalations_remaining_fraction,
    )
    return facts, provenance
