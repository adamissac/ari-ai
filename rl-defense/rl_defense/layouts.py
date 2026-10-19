"""Observation/action layouts of the live action spaces (constants only, no live deps).

``rl_defense.live.actions`` documents and uses these. They live here so that inference,
explanation and the PlatformFacts mapping can serve live checkpoints without importing
``rl_defense.live`` (httpx/starlette, the lab's dev dependencies; issue #335).

- ``sim``     : DefenseSimEnv, 48 features / 22 actions
- ``live_v2`` : + obs 48 ``principal_block_active``, + action 22 ``block_principal``
- ``live_v3`` : + obs 49..54 (detector features below), + actions 23
  ``block_principal_long`` and 24 ``block_top_principal_long``

Each layout is a strict extension of the previous one: an index keeps its meaning.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from rl_defense.envs.defense_sim import DISRUPTIVE, N_ACTIONS, OBS_DIM, decode_action

ActionSpace = Literal["sim", "live_v2", "live_v3"]
LIVE_V2_ENV_ID = "LiveDefense-payments-lite-v2"
LIVE_V3_ENV_ID = "LiveDefense-payments-lite-v3"
ENV_IDS: dict[str, str] = {"live_v2": LIVE_V2_ENV_ID, "live_v3": LIVE_V3_ENV_ID}

BLOCK_PRINCIPAL = "block_principal"
BLOCK_PRINCIPAL_ACTION = N_ACTIONS  # 22
LIVE_V2_N_ACTIONS = N_ACTIONS + 1  # 23
LIVE_V2_OBS_DIM = OBS_DIM + 1  # 49
LIVE_V2_EXTRA_FEATURES: tuple[str, ...] = ("principal_block_active",)

BLOCK_PRINCIPAL_LONG = "block_principal_long"
BLOCK_PRINCIPAL_LONG_ACTION = LIVE_V2_N_ACTIONS  # 23
BLOCK_TOP_PRINCIPAL_LONG = "block_top_principal_long"
BLOCK_TOP_PRINCIPAL_LONG_ACTION = LIVE_V2_N_ACTIONS + 1  # 24
# obs 49..54, in order; also the PlatformFacts field names that carry them
LIVE_V3_DETECTOR_FEATURES: tuple[str, ...] = (
    "block_remaining",
    "flagged_principals",
    "flagged_volume",
    "flagged_own_share",
    "flagged_repeat",
    "flagged_top_share",
)
LIVE_V3_EXTRA_FEATURES: tuple[str, ...] = (*LIVE_V2_EXTRA_FEATURES, *LIVE_V3_DETECTOR_FEATURES)
LIVE_V3_N_ACTIONS = LIVE_V2_N_ACTIONS + 2  # 25
LIVE_V3_OBS_DIM = OBS_DIM + len(LIVE_V3_EXTRA_FEATURES)  # 55
# obs index of each live extra feature (same index in every layout that has it)
FEATURE_INDEX = {f: OBS_DIM + i for i, f in enumerate(LIVE_V3_EXTRA_FEATURES)}

DIMS: dict[str, tuple[int, int]] = {
    "sim": (OBS_DIM, N_ACTIONS),
    "live_v2": (LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS),
    "live_v3": (LIVE_V3_OBS_DIM, LIVE_V3_N_ACTIONS),
}
SPACE_OF_ENV_ID: dict[str, str] = {LIVE_V2_ENV_ID: "live_v2", LIVE_V3_ENV_ID: "live_v3"}
# global (non-node) observation features beyond DefenseSimEnv's, per layout
EXTRA_FEATURES: dict[str, tuple[str, ...]] = {
    "sim": (),
    "live_v2": LIVE_V2_EXTRA_FEATURES,
    "live_v3": LIVE_V3_EXTRA_FEATURES,
}
_LIVE_ACTIONS = {
    BLOCK_PRINCIPAL_ACTION: BLOCK_PRINCIPAL,
    BLOCK_PRINCIPAL_LONG_ACTION: BLOCK_PRINCIPAL_LONG,
    BLOCK_TOP_PRINCIPAL_LONG_ACTION: BLOCK_TOP_PRINCIPAL_LONG,
}


def dims(space: ActionSpace) -> tuple[int, int]:
    """(obs_dim, n_actions) of an action space."""
    return DIMS[space]


def space_of_obs_dim(obs_dim: int) -> str:
    for name, (d, _) in DIMS.items():
        if d == obs_dim:
            return name
    raise ValueError(f"no layout has {obs_dim} observation features")


def live_decode_action(action: int) -> tuple[str, int | None]:
    """(action name, node index or None) for any layout."""
    if action in _LIVE_ACTIONS:
        return _LIVE_ACTIONS[action], None
    return decode_action(action)


def disruptive_mask(n_actions: int) -> np.ndarray:
    """Disruptive actions (can block legitimate traffic) for any layout."""
    m = np.array([decode_action(a)[0] in DISRUPTIVE for a in range(N_ACTIONS)])
    return np.append(m, np.ones(n_actions - N_ACTIONS, dtype=bool))
