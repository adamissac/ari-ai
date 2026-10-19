"""Live action space v2: the DefenseSimEnv layout plus one principal-scoped control.

Why: node-level containment (``isolate``/``rate_limit`` on ``payments``) blocks every
legitimate payments request while an attack runs, so the v1 candidate could not reach the
availability floor (results/live-retrain/REPORT.md). The gateway's instrumentation already
knows *who* is attempting cross-tenant reads, so v2 adds ``block_principal``: refuse
requests from the principals flagged in the previous window, on the nodes they were
flagged on, for ``LoopConfig.block_duration`` windows.

Layout (a strict extension, so a v1 index means the same thing in v2):

- actions 0..21 = DefenseSimEnv (noop, 5 nodes × 4 node actions, escalate_to_human)
- action  22    = ``block_principal`` (global; targets come from the detector, not the policy)
- obs 0..47     = DefenseSimEnv features
- obs 48        = ``principal_block_active`` (1.0 while any principal block is in force)

This is a **live-only** extension. ``shared.rl.DefenseActionName`` and DefenseSimEnv are
unchanged; the shared change is proposed in coordination/messages/
20261019T043718Z-alan-to-srihith-adam-block-principal-action.md. A v2 policy is lab-only
until that lands and must never emit a ``DefenseRecommendation``.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import torch

from rl_defense.agents.ddqn import DDQNAgent
from rl_defense.envs.defense_sim import DISRUPTIVE, N_ACTIONS, NOOP_ACTION, OBS_DIM, decode_action

ActionSpace = Literal["sim", "live_v2"]
LIVE_V2_ENV_ID = "LiveDefense-payments-lite-v2"
BLOCK_PRINCIPAL = "block_principal"
BLOCK_PRINCIPAL_ACTION = N_ACTIONS  # 22
LIVE_V2_N_ACTIONS = N_ACTIONS + 1  # 23
LIVE_V2_OBS_DIM = OBS_DIM + 1  # 49
LIVE_V2_EXTRA_FEATURES: tuple[str, ...] = ("principal_block_active",)


def dims(space: ActionSpace) -> tuple[int, int]:
    """(obs_dim, n_actions) of an action space."""
    return (OBS_DIM, N_ACTIONS) if space == "sim" else (LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS)


def live_decode_action(action: int) -> tuple[str, int | None]:
    if action == BLOCK_PRINCIPAL_ACTION:
        return BLOCK_PRINCIPAL, None
    return decode_action(action)


def disruptive_mask(n_actions: int) -> np.ndarray:
    """Disruptive actions (can block legitimate traffic) for either layout."""
    m = np.array([decode_action(a)[0] in DISRUPTIVE for a in range(N_ACTIONS)])
    if n_actions == LIVE_V2_N_ACTIONS:
        m = np.append(m, True)
    return m


def expand_agent_to_v2(agent: DDQNAgent, *, block_bias_offset: float = -1e-3) -> DDQNAgent:
    """Warm-start a v2 agent from a sim (48→22) agent without changing what it does.

    The new input column is zero (the extra feature has no effect yet) and the new output
    row copies ``noop``'s row with a slightly lower bias, so the expanded greedy policy
    picks exactly what the sim policy picked; only exploration reaches ``block_principal``
    until retraining learns its value.
    """
    if (agent.obs_dim, agent.n_actions) != (OBS_DIM, N_ACTIONS):
        raise ValueError(f"expected a sim agent ({OBS_DIM}, {N_ACTIONS}); got {agent.obs_dim}")
    new = DDQNAgent(LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS, agent.config, seed=0)
    for src_net, dst_net in ((agent.online, new.online), (agent.target, new.target)):
        src, dst = src_net.state_dict(), dst_net.state_dict()
        out = {}
        for k, w in src.items():
            d = dst[k]
            if w.shape == d.shape:
                out[k] = w.clone()
            elif w.dim() == 2 and w.shape[1] == OBS_DIM and d.shape[1] == LIVE_V2_OBS_DIM:
                out[k] = torch.cat([w, torch.zeros(w.shape[0], 1)], dim=1)  # input layer
            elif w.shape[0] == N_ACTIONS and d.shape[0] == LIVE_V2_N_ACTIONS:  # output head
                extra = w[NOOP_ACTION : NOOP_ACTION + 1].clone()
                if w.dim() == 1:
                    extra = extra + block_bias_offset
                out[k] = torch.cat([w, extra], dim=0)
            else:  # pragma: no cover - architecture we do not know how to widen
                raise ValueError(
                    f"cannot widen parameter {k}: {tuple(w.shape)} -> {tuple(d.shape)}"
                )
        dst_net.load_state_dict(out)
    new.target.requires_grad_(False)
    new.optimizer = torch.optim.Adam(new.online.parameters(), lr=agent.config.lr)
    new.disruptive = disruptive_mask(LIVE_V2_N_ACTIONS)
    new.updates = agent.updates
    new.online.eval()
    return new


def as_v2(agent: DDQNAgent) -> DDQNAgent:
    """Return a v2-shaped agent (widening a sim agent, passing a v2 agent through)."""
    if (agent.obs_dim, agent.n_actions) == (LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS):
        return agent
    return expand_agent_to_v2(agent)
