"""Simulated defense environments."""

from gymnasium.envs.registration import register, registry

from rl_defense.envs.config import ScenarioConfig, default_config_paths, load_config, load_configs
from rl_defense.envs.defense_sim import (
    N_ACTIONS,
    OBS_DIM,
    DefenseSimEnv,
    action_label,
    decode_action,
    encode_action,
)

if "DefenseSimEnv-v0" not in registry:
    register(id="DefenseSimEnv-v0", entry_point="rl_defense.envs.defense_sim:DefenseSimEnv")

__all__ = [
    "N_ACTIONS",
    "OBS_DIM",
    "DefenseSimEnv",
    "ScenarioConfig",
    "action_label",
    "decode_action",
    "default_config_paths",
    "encode_action",
    "load_config",
    "load_configs",
]
