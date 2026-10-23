"""Fixed development families, not calibrated production or final holdout traffic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from rl_defense.research.resource.service import Arrival, Config

Family = Literal[
    "stable", "legitimate_burst", "low_exhaustion", "high_exhaustion", "shifting", "mixed"
]
FAMILIES = ("stable", "legitimate_burst", "low_exhaustion", "high_exhaustion", "shifting", "mixed")


@dataclass
class TrafficState:
    burst: bool = False
    attack: bool = False
    source: int = 0


def window(
    rng: np.random.Generator,
    config: Config,
    family: Family,
    index: int,
    state: TrafficState,
) -> tuple[Arrival, ...]:
    """Offered traffic is action-independent; private stochastic phase is not observed.

    Exogenous on/off phases and source shifts have no deterministic episode-clock
    schedule. Legitimate high-volume clients and abusive jobs share source/route
    identities. No modeled strategic response to control is claimed.
    """
    jobs: list[Arrival] = []
    base = index * config.window_ticks
    legitimate = 5
    if family == "legitimate_burst":
        if rng.random() < (0.4 if state.burst else 0.2):
            state.burst = not state.burst
        legitimate = 9 if state.burst else 5
    if family == "mixed":
        legitimate = 6
    for _ in range(legitimate):
        route = int(rng.random() < 0.3)
        work = int(rng.integers(3, 7)) if route else int(rng.integers(1, 3))
        source = (
            3
            if family in ("mixed", "legitimate_burst") and rng.random() < 0.6
            else int(rng.integers(4))
        )
        jobs.append(
            Arrival(base + int(rng.integers(config.window_ticks)), source, route, work, False)
        )
    attack = 0
    if family == "low_exhaustion":
        attack = 2
    elif family == "high_exhaustion":
        attack = 14
    elif family == "shifting":
        if index == 0 or rng.random() < 1 / 3:
            state.source = int(rng.integers(4))
        if rng.random() < (0.5 if state.attack else 0.25):
            state.attack = not state.attack
        attack = 12 if state.attack else 1
    elif family == "mixed":
        attack = 8
    for _ in range(attack):
        source = (
            state.source
            if family == "shifting"
            else int(rng.integers(4 if family == "mixed" else 2))
        )
        route = int(rng.random() < 0.8)
        work = int(rng.integers(3, 9)) if route else int(rng.integers(1, 3))
        jobs.append(
            Arrival(base + int(rng.integers(config.window_ticks)), source, route, work, True)
        )
    # Random tie order prevents generation order from giving either label FIFO priority.
    mixed = [jobs[int(i)] for i in rng.permutation(len(jobs))]
    return tuple(sorted(mixed, key=lambda a: a.tick))
