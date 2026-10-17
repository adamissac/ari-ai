"""Typed DTOs this package exposes to the backend.

PENDING SHARED CONTRACT: the canonical models belong in ``shared/`` (owner:
Srihith, see coordination/OWNERSHIP.md). These local models are the proposal sent
in coordination/messages/; replace imports with ``shared`` once V0 merges.
Field names follow docs/12_DATA_MODELS_AND_CONTRACTS.md (DefenseRecommendation,
RLCheckpoint) plus ``simulation_derived`` required by MASTER_BUILD_SPEC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from rl_defense import SIMULATION_CAVEAT
from rl_defense.envs.config import NODE_NAMES

SCHEMA_VERSION = "0.1.0"
# ID formats mirror shared/ids.py (prefix + 8-64 alphanumerics) so payloads pass shared V0.
ProjectId = Annotated[str, StringConstraints(pattern=r"^prj_[0-9A-Za-z]{8,64}$")]
RecommendationId = Annotated[str, StringConstraints(pattern=r"^rec_[0-9A-Za-z]{8,64}$")]
CheckpointId = Annotated[str, StringConstraints(pattern=r"^ckp_[0-9A-Za-z]{8,64}$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NodeName = Literal["gateway", "api", "auth", "payments", "db"]
ActionName = Literal[
    "noop", "raise_monitoring", "rate_limit", "isolate", "request_reassessment", "escalate_to_human"
]
assert set(NodeName.__args__) == set(NODE_NAMES)  # type: ignore[attr-defined]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeSignals(_Strict):
    """Observable per-node facts the platform can supply (no hidden attacker state)."""

    node: NodeName
    criticality: float = Field(ge=0.0, le=1.0, description="From expectation data-sensitivity tags")
    exposed: bool
    finding_severity: float = Field(
        0.0, ge=0.0, le=1.0, description="Max open validated-finding severity"
    )
    alert_rate: float = Field(0.0, ge=0.0, description="Mean alerts/step over the recent window")
    anomaly_score: float = Field(0.0, ge=0.0, le=1.0)
    monitoring_level: int = Field(0, ge=0)
    rate_limited: bool = False
    isolated: bool = False
    reassessment_pending: bool = False


class PlatformFacts(_Strict):
    """Input to ``recommend``: the project's demo topology mapped onto the simulator."""

    project_id: ProjectId | None = None
    nodes: tuple[NodeSignals, ...] = Field(min_length=5, max_length=5)
    time_fraction: float = Field(0.0, ge=0.0, le=1.0)
    escalations_remaining_fraction: float = Field(1.0, ge=0.0, le=1.0)
    escalation_pending: bool = False


class ActionScore(_Strict):
    action: ActionName
    node: NodeName | None
    q_value: float


class DefenseRecommendation(_Strict):
    schema_version: str = SCHEMA_VERSION
    id: RecommendationId
    project_id: ProjectId | None
    policy_version: str = Field(description="RLCheckpoint id: env id + checkpoint sha256 prefix")
    checkpoint_sha256: Sha256Hex
    action: ActionName
    node: NodeName | None
    q_margin: float = Field(description="Q(best) − Q(second best valid action)")
    top_actions: tuple[ActionScore, ...]
    observation: tuple[float, ...]
    simulation_derived: Literal[True] = True
    caveat: str = SIMULATION_CAVEAT
    created_at: datetime


class RLCheckpointRef(_Strict):
    id: CheckpointId
    env_id: str
    seed: int
    steps: int
    git_sha: str
    checkpoint_file: str
    checkpoint_sha256: Sha256Hex
    train_configs: dict[str, str]
