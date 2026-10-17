"""Mandatory baselines (docs/09 §Baselines): noop, random-valid, threshold_rules.

Every baseline sees exactly what the DDQN agent sees: the observation vector and
the action mask. None of them read hidden adversary state.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from rl_defense.envs.config import ScenarioConfig
from rl_defense.envs.defense_sim import (
    ESCALATE_ACTION,
    N_NODES,
    NODE_FEATURES,
    NOOP_ACTION,
    DefenseSimEnv,
    encode_action,
)

_F = {name: i for i, name in enumerate(NODE_FEATURES)}
TUNING_SEEDS = range(500, 540)  # disjoint from eval seeds 1000-1099 (protocol 17)


class Policy(Protocol):
    name: str

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int: ...

    def reset(self, seed: int) -> None: ...


def node_feature(obs: np.ndarray, node: int, feature: str) -> float:
    return float(obs[node * len(NODE_FEATURES) + _F[feature]])


class NoopPolicy:
    name = "noop"

    def reset(self, seed: int) -> None:
        pass

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        return NOOP_ACTION


class RandomValidPolicy:
    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self._policy_seed = seed
        self._rng = np.random.default_rng(seed)

    def reset(self, seed: int) -> None:
        # Combine policy seed and episode seed: reproducible per episode, but different
        # policy seeds are genuinely different random policies.
        self._rng = np.random.default_rng((self._policy_seed, seed))

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        return int(self._rng.choice(np.flatnonzero(mask)))


@dataclass(frozen=True)
class ThresholdParams:
    isolate_anomaly: float  # θ1: isolate a high-criticality node above this anomaly
    rate_limit_alerts: float  # θ2: rate-limit when normalized alert rate exceeds this
    monitor_anomaly: float  # raise monitoring when anomaly exceeds this
    criticality_min: float = 0.6  # "criticality high" for isolation


class ThresholdRulesPolicy:
    """Hand-written rules from docs/09: isolate, rate-limit, escalate on two hot nodes."""

    name = "threshold_rules"

    def __init__(self, params: ThresholdParams) -> None:
        self.params = params

    def reset(self, seed: int) -> None:
        pass

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        p = self.params
        anomaly = np.array([node_feature(obs, i, "anomaly_score") for i in range(N_NODES)])
        alerts = np.array([node_feature(obs, i, "alert_rate") for i in range(N_NODES)])
        crit = np.array([node_feature(obs, i, "criticality") for i in range(N_NODES)])
        hot = anomaly > p.isolate_anomaly
        if hot.sum() >= 2 and mask[ESCALATE_ACTION]:
            return ESCALATE_ACTION
        for i in np.argsort(-anomaly):
            if hot[i] and crit[i] >= p.criticality_min:
                a = encode_action("isolate", int(i))
                if mask[a]:
                    return a
        for i in np.argsort(-alerts):
            if alerts[i] > p.rate_limit_alerts:
                a = encode_action("rate_limit", int(i))
                if mask[a]:
                    return a
        for i in np.argsort(-anomaly):
            if anomaly[i] > p.monitor_anomaly:
                a = encode_action("raise_monitoring", int(i))
                if mask[a]:
                    return a
        return NOOP_ACTION


def rollout_return(env: DefenseSimEnv, policy: Policy, seed: int) -> float:
    obs, info = env.reset(seed=seed)
    policy.reset(seed)
    total, done = 0.0, False
    while not done:
        obs, r, term, trunc, info = env.step(policy.act(obs, info["action_mask"]))
        total += r
        done = term or trunc
    return total


def tune_threshold_rules(
    train_configs: list[ScenarioConfig], seeds: range = TUNING_SEEDS
) -> tuple[ThresholdParams, list[dict[str, float]]]:
    """Grid-search thresholds on TRAINING configs only. Returns best params and the full grid."""
    grid = []
    for iso, rl, mon in itertools.product(
        (0.15, 0.25, 0.35, 0.5), (0.2, 0.3, 0.4, 0.6), (0.05, 0.1, 0.2)
    ):
        params = ThresholdParams(iso, rl, mon)
        policy = ThresholdRulesPolicy(params)
        returns = [
            rollout_return(DefenseSimEnv(cfg), policy, s) for cfg in train_configs for s in seeds
        ]
        grid.append(
            {
                "isolate_anomaly": iso,
                "rate_limit_alerts": rl,
                "monitor_anomaly": mon,
                "mean_return": float(np.mean(returns)),
            }
        )
    best = max(grid, key=lambda g: g["mean_return"])
    return ThresholdParams(
        best["isolate_anomaly"], best["rate_limit_alerts"], best["monitor_anomaly"]
    ), grid
