"""Deterministic policy inference -> DefenseRecommendation. No training code imported.

There is intentionally no function here (or anywhere in this package) that
applies a recommendation to a real system.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from rl_defense import ENV_ID
from rl_defense.checkpoint import load_checkpoint
from rl_defense.contracts import ActionScore, DefenseRecommendation, PlatformFacts, RLExplanation
from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import NEG_INF_MASK, decode_action
from rl_defense.explain import explain
from rl_defense.observations import from_platform_facts, mask_from_facts
from rl_defense.standards import defensive_refs


class PolicyRunner:
    def __init__(self, checkpoint: Path, *, blob: bytes | None = None) -> None:
        self.agent, self.manifest = load_checkpoint(checkpoint, blob=blob)
        if self.manifest["env_id"] != ENV_ID:
            # e.g. live action space v2 (block_principal): PlatformFacts has no
            # principal-block state, so the 49-feature observation cannot be built from it.
            raise ValueError(
                f"{self.manifest['env_id']} checkpoints are lab-only; recommendations need {ENV_ID}"
            )
        self.checkpoint_sha256 = self.manifest["checkpoint_sha256"]
        self.policy_version = f"{ENV_ID}@{self.checkpoint_sha256[:12]}"

    def recommend_from_observation(
        self, obs: np.ndarray, mask: np.ndarray, project_id: str | None = None, top_k: int = 3
    ) -> DefenseRecommendation:
        if not mask.any():
            raise ValueError("action mask has no valid actions")
        q = self.agent.q_values(obs).astype(np.float64)
        q_masked = np.where(mask, q, NEG_INF_MASK)
        order = [int(a) for a in np.argsort(-q_masked) if mask[a]]
        best = order[0]
        margin = float(q[best] - q[order[1]]) if len(order) > 1 else 0.0
        name, node = decode_action(best)

        def score(a: int) -> ActionScore:
            n, nd = decode_action(a)
            return ActionScore(
                action=n, node=None if nd is None else NODE_NAMES[nd], q_value=float(q[a])
            )

        return DefenseRecommendation(
            id=f"rec_{uuid.uuid4().hex}",
            project_id=project_id,
            policy_version=self.policy_version,
            checkpoint_sha256=self.checkpoint_sha256,
            action=name,
            d3fend=defensive_refs(name),
            node=None if node is None else NODE_NAMES[node],
            q_margin=margin,
            top_actions=tuple(score(a) for a in order[:top_k]),
            observation=tuple(float(x) for x in obs),
            created_at=datetime.now(UTC),
        )

    def explain(
        self,
        facts: PlatformFacts,
        recommendation: DefenseRecommendation | None = None,
        top_k: int = 5,
    ) -> RLExplanation:
        """Which observed inputs drove the decision for ``facts`` (occlusion on the same Q-network).

        ``recommendation`` is optional for backward compatibility with ``explain(facts)``
        (used by the backend, which then sets ``recommendation_id`` itself). Without it, the
        explanation carries the id of an equivalent fresh recommendation; inference is
        deterministic, so the explained decision is the same.
        """
        rec_id = (recommendation or self.recommend(facts)).id
        return explain(
            self.agent.online,
            from_platform_facts(facts),
            mask_from_facts(facts),
            rec_id,
            top_k,
        )

    def recommend_with_explanation(
        self, facts: PlatformFacts, top_k: int = 5
    ) -> tuple[DefenseRecommendation, RLExplanation]:
        rec = self.recommend(facts)
        return rec, self.explain(facts, rec, top_k)

    def recommend(self, facts: PlatformFacts) -> DefenseRecommendation:
        return self.recommend_from_observation(
            from_platform_facts(facts), mask_from_facts(facts), project_id=facts.project_id
        )
