"""Real traffic against the demo app: benign customers plus a cross-tenant attacker.

The attacker abuses the planted BOLA in ``GET /payments/{id}`` (the handler omits the
owner check): holding Bob's token, it requests Alice's payment ids. A real HTTP 200 with
Alice's data is a measured compromise. Benign clients only read their own resources.

Fixture-bound by default (``seeded_store``): tokens and ids are synthetic test data, not
secrets. Everything is sent through the :class:`DefensiveGateway`, so enforcement applies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

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

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def reset(self, seed: int | None = None) -> None:
        self._rng = random.Random(self.seed if seed is None else seed)

    def run_window(self, gateway: DefensiveGateway) -> None:
        """Issue this step's benign and attack requests through the gateway, interleaved."""
        plan: list[bool] = [False] * self.benign_per_step + [True] * self.attack_per_step
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
