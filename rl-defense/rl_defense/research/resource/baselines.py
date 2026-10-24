"""Frozen conventional rules; no labels, future workload or evaluation info input."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from rl_defense.research.resource.env import FEATURES, INDEX

Policy = Literal["noop", "static", "threshold", "resource_aware"]
POLICIES = ("noop", "static", "threshold", "resource_aware")


def action(policy: Policy, observation: NDArray[np.float32]) -> int:
    if policy not in POLICIES:
        raise ValueError("unknown fixed research policy")
    mask = observation[-3:].astype(bool)
    known = observation[len(FEATURES) : len(FEATURES) * 2].astype(bool)

    def value(name: str) -> float | None:
        return float(observation[INDEX[name]]) if known[INDEX[name]] else None

    if policy == "noop" or not mask[1]:
        return 0
    if policy == "static":
        # Fixed expensive-route quota whenever the common actuator permits it.
        return 1
    queue, utilization, latency = value("queue_depth"), value("utilization"), value("latency_mean")
    if queue is None or utilization is None:
        return 0
    if policy == "threshold":
        return 1 if queue >= 0.5 or (latency is not None and latency >= 0.6) else 0
    # Early pressure response, bounded by the same actuator/cooldown/budget mask.
    denials, arrivals = value("limit_denials"), value("arrivals")
    if denials is not None and arrivals and denials / arrivals >= 0.3:
        return 0
    if queue < 0.2 and utilization < 0.85:
        return 0
    work = [value(f"source_work_{i}") for i in range(4)]
    if all(x is not None for x in work):
        total = sum(x for x in work if x is not None)
        top = max(x for x in work if x is not None)
        if total > 0 and top / total >= 0.5 and mask[2]:
            return 2
    return 1
