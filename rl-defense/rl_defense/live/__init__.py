"""Live RL defense loop against the owned, isolated demo target.

This package closes the loop that the simulator cannot: it observes **real
telemetry** from a running copy of ``examples/payments-lite``, lets a trained DQN
pick a **permitted** defensive action, **enforces** it in a gateway in front of the
app, **measures** the real outcome, and records a reward + training transition.

Boundaries (see ``README.md`` and docs/15):
- The target runs in-process over an ASGI transport (no sockets; localhost semantics).
- Only the permitted defensive actions are enforced; nothing else touches the app.
- Every number is lab evidence, not proof of real-world effectiveness (RQ-005).
"""

from __future__ import annotations

from rl_defense.live.contracts import DefenseControls, LiveTransition, StepOutcome
from rl_defense.live.gateway import DefensiveGateway, RequestRecord
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig

__all__ = [
    "DefenseControls",
    "DefensiveGateway",
    "LiveDefenseLoop",
    "LiveTransition",
    "LoopConfig",
    "RequestRecord",
    "StepOutcome",
]
