"""Map platform facts onto the DefenseSimEnv observation vector.

Limits (documented honestly): the simulator's five-node topology is a fixed
abstraction. Mapping a real project onto it is a hand-written config (MVP), and
alert/anomaly signals from a real system are not calibrated to the simulator's
noise model. Recommendations are therefore simulation-derived (docs/09, RQ-005).
"""

from __future__ import annotations

import numpy as np

from rl_defense.contracts import PlatformFacts
from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import ALERT_NORM, OBS_DIM


def from_platform_facts(
    facts: PlatformFacts, max_monitoring_level: int = 2, *, space: str = "sim"
) -> np.ndarray:
    """48-feature simulator observation, or 49 for ``space="live_v2"`` (+ principal_block_active)."""
    by_name = {n.node: n for n in facts.nodes}
    if set(by_name) != set(NODE_NAMES):
        raise ValueError(f"facts must cover exactly the nodes {NODE_NAMES}")
    rows = []
    for name in NODE_NAMES:  # order must match the environment
        n = by_name[name]
        rows.append(
            [
                min(1.0, n.alert_rate / ALERT_NORM),
                n.anomaly_score,
                n.criticality,
                float(n.exposed),
                n.finding_severity,
                min(1.0, n.monitoring_level / max_monitoring_level),
                float(n.rate_limited),
                float(n.isolated),
                float(n.reassessment_pending),
            ]
        )
    glob = [
        facts.time_fraction,
        facts.escalations_remaining_fraction,
        float(facts.escalation_pending),
    ]
    obs = np.clip(np.concatenate([np.ravel(rows), glob]), 0.0, 1.0).astype(np.float32)
    assert obs.shape == (OBS_DIM,)
    if space == "live_v2":
        obs = np.append(obs, np.float32(facts.principal_block_active)).astype(np.float32)
    return obs


def mask_from_facts(
    facts: PlatformFacts, max_monitoring_level: int = 2, *, space: str = "sim"
) -> np.ndarray:
    """Valid-action mask from observable facts (mirrors DefenseSimEnv.action_masks).
    ``space="live_v2"`` appends block_principal, valid iff ``principal_block_available``."""
    from rl_defense.envs.defense_sim import ESCALATE_ACTION, N_ACTIONS, NOOP_ACTION, encode_action

    by_name = {n.node: n for n in facts.nodes}
    mask = np.zeros(N_ACTIONS, dtype=bool)
    mask[NOOP_ACTION] = True
    for i, name in enumerate(NODE_NAMES):
        n = by_name[name]
        mask[encode_action("raise_monitoring", i)] = n.monitoring_level < max_monitoring_level
        mask[encode_action("rate_limit", i)] = not n.isolated and not n.rate_limited
        mask[encode_action("isolate", i)] = not n.isolated
        mask[encode_action("request_reassessment", i)] = (
            not n.reassessment_pending and n.finding_severity > 0.1
        )
    mask[ESCALATE_ACTION] = (
        facts.escalations_remaining_fraction > 0 and not facts.escalation_pending
    )
    if space == "live_v2":
        mask = np.append(mask, bool(facts.principal_block_available))
    return mask
