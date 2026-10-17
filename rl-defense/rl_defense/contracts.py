"""RL contracts: re-exported from the canonical ``shared.rl`` (shared/ V0, owner: Srihith).

rl-defense produces these; ``shared`` owns their definition. Do not redefine them here.
History: proposed in coordination/messages/20261017T001311Z-adam-to-srihith-rl-recommendation-contract.md,
adopted field-for-field into shared V0 (issue #2, PR #8).
"""

from __future__ import annotations

from shared.ids import CheckpointId, ProjectId, RecommendationId
from shared.rl import (
    RL_SCHEMA_VERSION,
    SIMULATION_CAVEAT_DEFAULT,
    ActionScore,
    DefenseActionName,
    DefenseRecommendation,
    FeatureContribution,
    NodeName,
    NodeSignals,
    PlatformFacts,
    RLCheckpointRef,
    RLEvaluation,
    RLExplanation,
)

from rl_defense.envs.config import NODE_NAMES

SCHEMA_VERSION = RL_SCHEMA_VERSION
ActionName = DefenseActionName
assert set(NodeName.__args__) == set(NODE_NAMES)  # type: ignore[attr-defined]

__all__ = [
    "SCHEMA_VERSION",
    "SIMULATION_CAVEAT_DEFAULT",
    "ActionName",
    "ActionScore",
    "CheckpointId",
    "DefenseRecommendation",
    "FeatureContribution",
    "NodeName",
    "NodeSignals",
    "PlatformFacts",
    "ProjectId",
    "RLCheckpointRef",
    "RLEvaluation",
    "RLExplanation",
    "RecommendationId",
]
