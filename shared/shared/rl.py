"""RL defense contracts (producer: rl-defense / Adam).

Adopted from Adam's proposal (coordination/messages/20261017T001311Z-adam-to-srihith-
rl-recommendation-contract.md, issue #2) field-for-field so rl_defense.contracts can
re-export these. Recommendations are simulation-derived decision support only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from shared.base import Sha256Hex, ShortText, StrictModel, UtcDatetime
from shared.ids import ArtifactId, CheckpointId, ProjectId, RecommendationId, RLEvaluationId
from shared.standards import DefensiveMapping

RL_SCHEMA_VERSION = "0.1.0"
SIMULATION_CAVEAT_DEFAULT = (
    "Simulation-derived recommendation from a policy trained only in DefenseSimEnv; "
    "not a detection of a real attack and never executed automatically."
)

NodeName = Literal["gateway", "api", "auth", "payments", "db"]
# ``block_principal`` exists only in the live lab's action space v2
# (rl-defense/rl_defense/live/actions.py); DefenseSimEnv policies never emit it.
DefenseActionName = Literal[
    "noop",
    "raise_monitoring",
    "rate_limit",
    "isolate",
    "request_reassessment",
    "escalate_to_human",
    "block_principal",
]


class NodeSignals(StrictModel):
    """Observable per-node facts the platform can supply (no hidden attacker state)."""

    node: NodeName
    criticality: float = Field(ge=0.0, le=1.0)
    exposed: bool
    finding_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    alert_rate: float = Field(default=0.0, ge=0.0)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    monitoring_level: int = Field(default=0, ge=0)
    rate_limited: bool = False
    isolated: bool = False
    reassessment_pending: bool = False


class PlatformFacts(StrictModel):
    project_id: ProjectId | None = None
    nodes: list[NodeSignals] = Field(min_length=5, max_length=5)
    time_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    escalations_remaining_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    escalation_pending: bool = False
    # Live action space v2 (block_principal). Only a source with a gateway that detects
    # principals (the live lab) can set these; elsewhere they stay False, so a v2 policy
    # sees "no block in force" and block_principal is not a valid action.
    principal_block_active: bool = Field(
        default=False, description="a block_principal control is currently in force"
    )
    principal_block_available: bool = Field(
        default=False,
        description="the detector flagged a principal that is not yet blocked where it was seen",
    )


class ActionScore(StrictModel):
    action: DefenseActionName
    node: NodeName | None
    q_value: float


class DefenseRecommendation(StrictModel):
    d3fend: list[DefensiveMapping] = Field(default_factory=list)
    schema_version: str = RL_SCHEMA_VERSION
    id: RecommendationId
    project_id: ProjectId | None
    policy_version: ShortText = Field(description="env id + checkpoint sha256 prefix")
    checkpoint_sha256: Sha256Hex
    action: DefenseActionName
    node: NodeName | None
    q_margin: float = Field(description="Q(best) - Q(second best valid action)")
    top_actions: list[ActionScore]
    observation: list[float]
    simulation_derived: Literal[True] = True
    caveat: ShortText = SIMULATION_CAVEAT_DEFAULT
    created_at: UtcDatetime


class RLCheckpointRef(StrictModel):
    id: CheckpointId
    env_id: ShortText
    seed: int
    steps: int = Field(ge=0)
    git_sha: ShortText
    checkpoint_file: ShortText
    checkpoint_sha256: Sha256Hex
    train_configs: dict[str, str] = Field(default_factory=dict)


class RLEvaluation(StrictModel):
    """Pointer to a persisted protocol-17 ``eval_summary.json`` (stored verbatim as artifact)."""

    id: RLEvaluationId
    protocol_version: ShortText
    checkpoint_ids: list[CheckpointId] = Field(default_factory=list)
    summary_artifact_id: ArtifactId
    summary_sha256: Sha256Hex
    simulation_derived: Literal[True] = True
    created_at: UtcDatetime


class FeatureContribution(StrictModel):
    node: NodeName | None = Field(description="None for global features")
    feature: ShortText
    value: float
    delta_margin: float = Field(
        description="margin(original) - margin(feature occluded); > 0 supports the chosen action"
    )
    kind: Literal["signal", "context", "defense_state", "global"]


class RLExplanation(StrictModel):
    """Occlusion explanation of one recommendation (V0.1, proposed by Adam). Explains the
    simulation-trained policy's decision, not real-world causality."""

    recommendation_id: RecommendationId
    action: ShortText
    runner_up: ShortText | None
    margin: float
    method: ShortText
    top_contributions: list[FeatureContribution]
    caveat: ShortText
    simulation_derived: Literal[True] = True
