"""Explain a recommendation: which observed inputs drove the chosen action.

Method: occlusion. For every input feature, reset it to a neutral baseline (0, i.e.
"no signal / no risk") and measure how much the chosen action's advantage over the
runner-up changes. Deterministic, model-agnostic, and computed on the same Q-network
that produced the recommendation. It explains the *policy*, not the real world.
"""

from __future__ import annotations

import numpy as np
import torch

from rl_defense.agents.ddqn import NEG_INF
from rl_defense.contracts import FeatureContribution, RLExplanation
from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import GLOBAL_FEATURES, NODE_FEATURES, OBS_DIM, action_label

# Static context the platform supplies (not live signals); occluding these answers
# "would the policy act differently on a less critical / less exposed node?".
STATIC_FEATURES = frozenset({"criticality", "exposed"})


METHOD = "occlusion: feature set to 0, change in Q(chosen) - Q(runner-up)"
CAVEAT = "Explains the simulation-trained policy's decision, not real-world causality."


def _feature_meta(index: int) -> tuple[str | None, str, str]:
    per = len(NODE_FEATURES)
    if index < len(NODE_NAMES) * per:
        node, feat = NODE_NAMES[index // per], NODE_FEATURES[index % per]
        if feat in {"alert_rate", "anomaly_score", "finding_severity"}:
            kind = "signal"
        elif feat in STATIC_FEATURES:
            kind = "context"
        else:
            kind = "defense_state"
        return node, feat, kind
    return None, GLOBAL_FEATURES[index - len(NODE_NAMES) * per], "global"


def explain(
    q_network: torch.nn.Module,
    obs: np.ndarray,
    mask: np.ndarray,
    recommendation_id: str,
    top_k: int = 5,
) -> RLExplanation:
    if obs.shape != (OBS_DIM,):
        raise ValueError(f"observation must have shape ({OBS_DIM},)")
    if mask.sum() < 1:
        raise ValueError("action mask has no valid actions")
    with torch.no_grad():
        q = (
            q_network(torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0))[0]
            .numpy()
            .astype(np.float64)
        )
        qm = np.where(mask, q, NEG_INF)
        order = np.argsort(-qm)
        best = int(order[0])
        runner = int(order[1]) if mask.sum() > 1 else None
        margin = float(q[best] - q[runner]) if runner is not None else 0.0

        # Batch all occlusions: row i = obs with feature i set to 0.
        occluded = np.repeat(obs[None, :], OBS_DIM, axis=0).astype(np.float32)
        occluded[np.arange(OBS_DIM), np.arange(OBS_DIM)] = 0.0
        qo = q_network(torch.as_tensor(occluded)).numpy().astype(np.float64)
    occ_margin = qo[:, best] - (qo[:, runner] if runner is not None else qo[:, best])
    deltas = margin - occ_margin
    contributions = []
    for i in np.argsort(-np.abs(deltas)):
        if obs[i] == 0.0 or abs(deltas[i]) < 1e-9:
            continue  # occluding a zero feature changes nothing
        node, feat, kind = _feature_meta(int(i))
        contributions.append(
            FeatureContribution(
                node=node,
                feature=feat,
                value=round(float(obs[i]), 4),
                delta_margin=round(float(deltas[i]), 5),
                kind=kind,  # type: ignore[arg-type]
            )
        )
        if len(contributions) == top_k:
            break
    return RLExplanation(
        recommendation_id=recommendation_id,
        method=METHOD,
        caveat=CAVEAT,
        action=action_label(best),
        runner_up=None if runner is None else action_label(runner),
        margin=round(margin, 5),
        top_contributions=contributions,
    )
