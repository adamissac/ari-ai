"""Live action spaces v2 and v3: the DefenseSimEnv layout plus principal-scoped controls.

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

**v3** (results/live-retrain-v3/) is a strict extension of v2 (every v2 index keeps its
meaning) that addresses the identity-switch leak (results/live-retrain-v2/PROVENANCE.md):

- action  23    = ``block_principal_long``: block (or *extend* an existing block of) every
                  flagged principal for ``LoopConfig.block_long_duration`` windows. Valid
                  while some flagged principal is not already under a block that long, so
                  it also extends a block while the same principal keeps being flagged.
- action  24    = ``block_top_principal_long``: the same long block/extension, but only for
                  the flagged principal(s) with the most cross-tenant attempts in the window
                  (a heavy hitter rather than every reader the detector flagged, e.g. a
                  legitimate delegate seen in the same window).
- obs 49        = ``block_remaining``: longest remaining block / ``block_long_duration``
- obs 50        = ``flagged_principals``: distinct flagged principals / 3
- obs 51        = ``flagged_volume``: cross-tenant attempts per flagged principal / 6
- obs 52        = ``flagged_own_share``: share of the flagged principals' requests that
                  read their own tenant's data (an outsider has none)
- obs 53        = ``flagged_repeat``: share of flagged principals blocked earlier this episode
- obs 54        = ``flagged_top_share``: the heaviest flagged principal's share of all
                  flagged cross-tenant attempts (1.0 = one principal did all of them)

All five features come from the gateway's instrumentation and the loop's own block history.
``block_principal_long`` and ``block_top_principal_long`` are **not** in
``shared.rl.DefenseActionName``; it is proposed in
coordination/messages/ (owner: Srihith) and stays live-only (lab evidence, no
``DefenseRecommendation``).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import torch

from rl_defense.agents.ddqn import DDQNAgent
from rl_defense.envs.defense_sim import DISRUPTIVE, N_ACTIONS, NOOP_ACTION, OBS_DIM, decode_action

ActionSpace = Literal["sim", "live_v2", "live_v3"]
LIVE_V2_ENV_ID = "LiveDefense-payments-lite-v2"
LIVE_V3_ENV_ID = "LiveDefense-payments-lite-v3"
BLOCK_PRINCIPAL = "block_principal"
BLOCK_PRINCIPAL_ACTION = N_ACTIONS  # 22
LIVE_V2_N_ACTIONS = N_ACTIONS + 1  # 23
LIVE_V2_OBS_DIM = OBS_DIM + 1  # 49
LIVE_V2_EXTRA_FEATURES: tuple[str, ...] = ("principal_block_active",)
BLOCK_PRINCIPAL_LONG = "block_principal_long"
BLOCK_PRINCIPAL_LONG_ACTION = LIVE_V2_N_ACTIONS  # 23
BLOCK_TOP_PRINCIPAL_LONG = "block_top_principal_long"
BLOCK_TOP_PRINCIPAL_LONG_ACTION = LIVE_V2_N_ACTIONS + 1  # 24
LIVE_V3_EXTRA_FEATURES: tuple[str, ...] = (
    *LIVE_V2_EXTRA_FEATURES,
    "block_remaining",
    "flagged_principals",
    "flagged_volume",
    "flagged_own_share",
    "flagged_repeat",
    "flagged_top_share",
)
LIVE_V3_N_ACTIONS = LIVE_V2_N_ACTIONS + 2  # 25
LIVE_V3_OBS_DIM = OBS_DIM + len(LIVE_V3_EXTRA_FEATURES)  # 55
# obs index of each live extra feature (same index in every layout that has it)
FEATURE_INDEX = {f: OBS_DIM + i for i, f in enumerate(LIVE_V3_EXTRA_FEATURES)}
ENV_IDS = {"live_v2": LIVE_V2_ENV_ID, "live_v3": LIVE_V3_ENV_ID}

_DIMS: dict[str, tuple[int, int]] = {
    "sim": (OBS_DIM, N_ACTIONS),
    "live_v2": (LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS),
    "live_v3": (LIVE_V3_OBS_DIM, LIVE_V3_N_ACTIONS),
}


def dims(space: ActionSpace) -> tuple[int, int]:
    """(obs_dim, n_actions) of an action space."""
    return _DIMS[space]


def space_of(agent: DDQNAgent) -> ActionSpace:
    shape = (agent.obs_dim, agent.n_actions)
    for name, d in _DIMS.items():
        if d == shape:
            return name  # type: ignore[return-value]
    raise ValueError(f"unknown action-space shape {shape}")


def live_decode_action(action: int) -> tuple[str, int | None]:
    if action == BLOCK_PRINCIPAL_ACTION:
        return BLOCK_PRINCIPAL, None
    if action == BLOCK_PRINCIPAL_LONG_ACTION:
        return BLOCK_PRINCIPAL_LONG, None
    if action == BLOCK_TOP_PRINCIPAL_LONG_ACTION:
        return BLOCK_TOP_PRINCIPAL_LONG, None
    return decode_action(action)


def disruptive_mask(n_actions: int) -> np.ndarray:
    """Disruptive actions (can block legitimate traffic) for any layout."""
    m = np.array([decode_action(a)[0] in DISRUPTIVE for a in range(N_ACTIONS)])
    return np.append(m, np.ones(n_actions - N_ACTIONS, dtype=bool))


def widen_agent(
    agent: DDQNAgent, space: ActionSpace, *, block_bias_offset: float = -1e-3
) -> DDQNAgent:
    """Warm-start a wider live agent from a narrower one without changing what it does.

    New input columns are zero (the extra features have no effect yet) and every new output
    row copies ``noop``'s row with a slightly lower bias, so the widened greedy policy picks
    exactly what the narrower policy picked; only exploration reaches the new actions until
    retraining learns their value.
    """
    obs_dim, n_actions = dims(space)
    if agent.obs_dim > obs_dim or agent.n_actions > n_actions:
        raise ValueError(f"cannot narrow a {space_of(agent)} agent to {space}")
    d_obs, d_act = obs_dim - agent.obs_dim, n_actions - agent.n_actions
    new = DDQNAgent(obs_dim, n_actions, agent.config, seed=0)
    for src_net, dst_net in ((agent.online, new.online), (agent.target, new.target)):
        src, dst = src_net.state_dict(), dst_net.state_dict()
        out = {}
        for k, w in src.items():
            d = dst[k]
            if w.shape == d.shape:
                out[k] = w.clone()
            elif w.dim() == 2 and w.shape[1] == agent.obs_dim and d.shape[1] == obs_dim:
                out[k] = torch.cat([w, torch.zeros(w.shape[0], d_obs)], dim=1)  # input layer
            elif w.shape[0] == agent.n_actions and d.shape[0] == n_actions:  # output head
                extra = (
                    w[NOOP_ACTION : NOOP_ACTION + 1].clone().repeat(d_act, *([1] * (w.dim() - 1)))
                )
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
    new.disruptive = disruptive_mask(n_actions)
    new.updates = agent.updates
    new.online.eval()
    return new


def expand_agent_to_v2(agent: DDQNAgent, *, block_bias_offset: float = -1e-3) -> DDQNAgent:
    """Widen a sim (48→22) agent to the v2 layout (see :func:`widen_agent`)."""
    if (agent.obs_dim, agent.n_actions) != (OBS_DIM, N_ACTIONS):
        raise ValueError(f"expected a sim agent ({OBS_DIM}, {N_ACTIONS}); got {agent.obs_dim}")
    return widen_agent(agent, "live_v2", block_bias_offset=block_bias_offset)


def as_space(agent: DDQNAgent, space: ActionSpace) -> DDQNAgent:
    """Return an agent shaped for ``space`` (widening a narrower one, passing a match through)."""
    if (agent.obs_dim, agent.n_actions) == dims(space):
        return agent
    return widen_agent(agent, space)


def as_v2(agent: DDQNAgent) -> DDQNAgent:
    """Return a v2-shaped agent (widening a sim agent, passing a v2 agent through)."""
    return as_space(agent, "live_v2")
