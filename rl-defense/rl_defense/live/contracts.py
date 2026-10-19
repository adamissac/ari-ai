"""Typed records for the live loop.

``LiveTransition`` is the concrete realization of the PROPOSED experience schema in
docs/architecture/seven-agent-rl-adversarial-integration.md. It is defined locally
here (not in ``shared/``) on purpose: the loop is a vertical-slice proof, and the
shared contract must go through contract-first review (owner: Srihith) before it is
canonical. The field shape matches ``DefenseSimEnv``/``ReplayBuffer`` so transitions
can later feed offline retraining unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from rl_defense.envs.defense_sim import NODE_ACTIONS


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DefenseControls(_Strict):
    """Per-node enforced defensive state. The gateway reads this before every request.

    ``rate_limit_allow_every`` = N means 1 of every N requests to the node is allowed
    through; the rest get 429. ``monitoring_level`` raises detection fidelity only.
    """

    isolated: dict[str, bool] = Field(default_factory=dict)
    rate_limited: dict[str, bool] = Field(default_factory=dict)
    monitoring_level: dict[str, int] = Field(default_factory=dict)
    reassessment_pending: dict[str, bool] = Field(default_factory=dict)
    rate_limit_allow_every: int = 3

    def clone(self) -> DefenseControls:
        return self.model_copy(deep=True)


class StepOutcome(_Strict):
    """What the loop actually measured in one step window (all from real HTTP outcomes)."""

    step: int
    action: int
    action_label: str
    node: str | None
    # measured counts over the window
    attack_requests: int
    compromised_reads: int  # attack requests that really returned cross-tenant data (HTTP 200)
    benign_requests: int
    benign_blocked: int  # benign requests the defense really blocked/throttled (503/429)
    reward: float
    reward_components: dict[str, float]
    terminated: bool
    truncated: bool


class LiveTransition(_Strict):
    """One (s, a, r, s', done) transition recorded from the live loop.

    Shapes mirror the simulator so the record is replay-buffer compatible.
    """

    obs: list[float]
    action: int
    reward: float
    next_obs: list[float]
    done: bool
    action_mask: list[bool]
    reward_components: dict[str, float]
    outcome: StepOutcome


ACTION_NAMES_HELP = ("noop", *NODE_ACTIONS, "escalate_to_human")
