"""Fixed development families, not calibrated production or final holdout traffic."""

from __future__ import annotations

from typing import Literal

import numpy as np

from rl_defense.research.resource.service import Arrival, Config

Family = Literal[
    "stable", "legitimate_burst", "low_exhaustion", "high_exhaustion", "shifting", "mixed"
]
FAMILIES = ("stable", "legitimate_burst", "low_exhaustion", "high_exhaustion", "shifting", "mixed")


def window(
    rng: np.random.Generator, config: Config, family: Family, index: int
) -> tuple[Arrival, ...]:
    """Draw offered requests independently of actions/queue, using own seeded RNG.

    Every source can issue legitimate work; abusive work can share that source.
    Legitimate bursts and attacks can overlap. Route costs overlap across labels.
    Shifts are scripted exogenous phases, not a strategic adaptive attacker model.
    """
    jobs: list[Arrival] = []
    base = index * config.window_ticks
    legitimate = 5
    if family == "legitimate_burst" and index % 6 in (2, 3):
        legitimate = 18
    if family == "mixed":
        legitimate = 12
    for _ in range(legitimate):
        route = int(rng.random() < 0.3)
        work = int(rng.integers(3, 7)) if route else int(rng.integers(1, 3))
        jobs.append(
            Arrival(
                base + int(rng.integers(config.window_ticks)),
                int(rng.integers(4)),
                route,
                work,
                False,
            )
        )
    attack = 0
    if family == "low_exhaustion":
        attack = 2
    elif family == "high_exhaustion":
        attack = 14
    elif family == "shifting":
        attack = 12 if index % 8 in (2, 3, 4) else 1
    elif family == "mixed":
        attack = 8
    for _ in range(attack):
        source = (index // 3) % 4 if family == "shifting" else int(rng.integers(2))
        route = int(rng.random() < 0.8)
        work = int(rng.integers(3, 9)) if route else int(rng.integers(1, 3))
        jobs.append(
            Arrival(base + int(rng.integers(config.window_ticks)), source, route, work, True)
        )
    # Arrival ordering is part of the fixed workload; tie order is not policy-dependent.
    return tuple(sorted(jobs, key=lambda a: a.tick))
