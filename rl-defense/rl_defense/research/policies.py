"""Research-only capability shield and fixed, observable budgeted rules.

No permission, finding truth, request label, future traffic or cost estimate is inferred
by this policy. The intervention budget bounds *new actions*, not residual disruption.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import ESCALATE_ACTION, NODE_ACTIONS, encode_action
from rl_defense.layouts import BLOCK_PRINCIPAL_ACTION, LIVE_V3_N_ACTIONS

# Existing owned traffic driver issues /payments*, /me only. Auth is inside the app,
# not a separate gateway hop; database has no route. This profile is NOT general-purpose.
LAB_TRAFFIC_NODES = frozenset({"api", "payments"})


def capability_mask(
    mask: np.ndarray, *, traffic_nodes: frozenset[str] = LAB_TRAFFIC_NODES
) -> np.ndarray:
    if mask.shape != (LIVE_V3_N_ACTIONS,) or not mask[0]:
        raise ValueError("research shield requires live_v3 with noop")
    if not traffic_nodes <= set(NODE_NAMES):
        raise ValueError("unknown traffic node")
    out = mask.copy()
    out[ESCALATE_ACTION] = False  # timer only, no live containment/human completion
    for i, node in enumerate(NODE_NAMES):
        for name in NODE_ACTIONS:
            if node not in traffic_nodes or name == "request_reassessment":
                # Reassessment changes scripted severity, never patches this target.
                out[encode_action(name, i)] = False
    return out


@dataclass
class CostAwareRules:
    """Fixed demonstration baseline, not tuned: at most two short interventions.

    Require an observed validated finding on payments plus a flagged-principal mask.
    Avoid broad isolation/rate limiting and long extensions. No guaranteed cost cap:
    one short block can still deny legitimate or authorized delegated requests.
    """

    max_interventions: int = 2
    used: int = 0

    def __post_init__(self) -> None:
        if self.max_interventions < 0:
            raise ValueError("negative intervention budget")

    def __call__(self, obs: np.ndarray, mask: np.ndarray) -> int:
        mask = capability_mask(mask)
        if obs.shape != (55,):
            raise ValueError("live_v3 observation required")
        severity = obs[NODE_NAMES.index("payments") * 9 + 4]
        if self.used >= self.max_interventions or severity <= 0 or not mask[BLOCK_PRINCIPAL_ACTION]:
            return 0
        self.used += 1
        return BLOCK_PRINCIPAL_ACTION
