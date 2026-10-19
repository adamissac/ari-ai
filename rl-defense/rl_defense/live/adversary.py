"""Real traffic against the demo app: benign customers plus a cross-tenant attacker.

The attacker abuses the planted BOLA in ``GET /payments/{id}`` (the handler omits the
owner check): holding Bob's token, it requests Alice's payment ids. A real HTTP 200 with
Alice's data is a measured compromise. Benign clients only read their own resources.

``schedule="always"`` attacks every window. ``schedule="bursty"`` runs a two-state
Markov process (off→on with ``p_start``, on→off with ``p_stop``) so attacks come and go;
the defender then has to decide *when* disruptive controls are worth their cost.
``attack_active`` is the generator's ground truth for the current window — used for
metrics (e.g. false disruption) only, never for observations.

Fixture-bound by default (``seeded_store``): tokens and ids are synthetic test data, not
secrets. Everything is sent through the :class:`DefensiveGateway`, so enforcement applies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from rl_defense.live.gateway import DefensiveGateway


@dataclass
class ClientProfile:
    actor: str
    token: str
    own_payment_ids: tuple[str, ...]


@dataclass
class TrafficDriver:
    """Drives one window of real requests per :meth:`run_window` call."""

    benign: tuple[ClientProfile, ...] = (
        ClientProfile("cus_alice", "fixture-token-alice", ("pay_a1", "pay_a2")),
        ClientProfile("cus_bob", "fixture-token-bob", ("pay_b1",)),
    )
    # attacker holds a VALID token (Bob) but targets another tenant's ids (Alice's)
    attacker: ClientProfile = field(
        default_factory=lambda: ClientProfile("cus_bob", "fixture-token-bob", ("pay_a1", "pay_a2"))
    )
    benign_per_step: int = 6
    attack_per_step: int = 6
    seed: int = 0
    schedule: Literal["always", "bursty"] = "always"
    p_start: float = 0.2
    p_stop: float = 0.2
    start_active: bool = False

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self.attack_active = self._initial_state()

    def _initial_state(self) -> bool:
        return True if self.schedule == "always" else self.start_active

    def reset(self, seed: int | None = None) -> None:
        self._rng = random.Random(self.seed if seed is None else seed)
        self.attack_active = self._initial_state()

    def _advance_schedule(self) -> None:
        if self.schedule == "always":
            self.attack_active = True
            return
        u = self._rng.random()  # consumed every window regardless of policy → paired traffic
        if self.attack_active:
            self.attack_active = u >= self.p_stop
        else:
            self.attack_active = u < self.p_start

    def run_window(self, gateway: DefensiveGateway) -> None:
        """Advance the attack schedule, then issue this window's requests, interleaved."""
        self._advance_schedule()
        n_attack = self.attack_per_step if self.attack_active else 0
        plan: list[bool] = [False] * self.benign_per_step + [True] * n_attack
        self._rng.shuffle(plan)
        for is_attack in plan:
            if is_attack:
                victim_id = self._rng.choice(self.attacker.own_payment_ids)
                gateway.request(
                    "GET",
                    f"/payments/{victim_id}",
                    actor=self.attacker.actor,
                    token=self.attacker.token,
                    is_attack=True,
                )
            else:
                client = self._rng.choice(self.benign)
                # a benign customer reads their own payments list and profile
                if self._rng.random() < 0.5:
                    gateway.request("GET", "/payments", actor=client.actor, token=client.token)
                else:
                    gateway.request("GET", "/me", actor=client.actor, token=client.token)
