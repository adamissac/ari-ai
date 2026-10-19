"""Real traffic against the demo app: benign customers plus a cross-tenant attacker.

The attacker abuses the planted BOLA in ``GET /payments/{id}`` (the handler omits the
owner check): holding Bob's token, it requests Alice's payment ids. A real HTTP 200 with
Alice's data is a measured compromise. Benign clients only read their own resources.

``schedule="always"`` attacks every window. ``schedule="bursty"`` runs a two-state
Markov process (off→on with ``p_start``, on→off with ``p_stop``) so attacks come and go;
the defender then has to decide *when* disruptive controls are worth their cost.
``attack_active`` is the generator's ground truth for the current window — used for
metrics (e.g. false disruption) only, never for observations.

Attackers may be several identities (``attackers``) and may rotate through several valid
tokens of the same principal (``rotate_tokens``); both are deterministic in the window
index, or drawn from the driver's own RNG independently of the defender, so traffic stays
paired across policies. The default (one attacker, Bob's primary token, victim Alice) is
byte-for-byte the v1 traffic.

Fixture-bound (``seeded_store`` plus :func:`live_store`): tokens and ids are synthetic test
data, not secrets. Everything is sent through the :class:`DefensiveGateway`, so
enforcement applies.
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
    # extra valid tokens of the same principal (used when an attacker rotates tokens)
    alt_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class FixtureIdentity:
    customer_id: str
    name: str
    tokens: tuple[str, ...]  # first = primary
    payments: tuple[str, ...]  # payment ids this tenant owns


# Synthetic fixture tenants. alice and bob (primary tokens, payments) are exactly the
# payments-lite seed; the rest are added by :func:`live_store` for v2 scenarios.
IDENTITIES: dict[str, FixtureIdentity] = {
    "alice": FixtureIdentity(
        "cus_alice", "Alice Example", ("fixture-token-alice",), ("pay_a1", "pay_a2")
    ),
    "bob": FixtureIdentity(
        "cus_bob",
        "Bob Example",
        ("fixture-token-bob", "fixture-token-bob-2", "fixture-token-bob-3"),
        ("pay_b1",),
    ),
    "carol": FixtureIdentity("cus_carol", "Carol Example", ("fixture-token-carol",), ("pay_c1",)),
    "mallory": FixtureIdentity(
        "cus_mallory",
        "Mallory Example",
        ("fixture-token-mallory", "fixture-token-mallory-2", "fixture-token-mallory-3"),
        (),
    ),
}


def live_store():  # noqa: ANN201
    """payments-lite's seed plus the extra fixture tenants/tokens above (test data only)."""
    from decimal import Decimal

    from payments_lite.store import Customer, Payment, seeded_store

    s = seeded_store()
    for ident in IDENTITIES.values():
        if ident.customer_id not in s.customers:
            email = f"{ident.customer_id.removeprefix('cus_')}@example.test"
            s.customers[ident.customer_id] = Customer(ident.customer_id, ident.name, email)
        for tok in ident.tokens:
            s.tokens.setdefault(tok, ident.customer_id)
        for pid in ident.payments:
            if pid not in s.payments:
                s.payments[pid] = Payment(
                    pid, ident.customer_id, Decimal("42.00"), "USD", "Fixture plan"
                )
    return s


def live_app():  # noqa: ANN201
    """App factory for scenarios that use the extra fixture identities."""
    from payments_lite.app import create_app

    return create_app(live_store())


def benign_profile(name: str) -> ClientProfile:
    i = IDENTITIES[name]
    return ClientProfile(i.customer_id, i.tokens[0], i.payments)


def attacker_profile(name: str, victims: tuple[str, ...]) -> ClientProfile:
    """A tenant holding valid tokens that requests other tenants' payment ids."""
    i = IDENTITIES[name]
    targets = tuple(p for v in victims for p in IDENTITIES[v].payments)
    if not targets:
        raise ValueError(f"attacker {name} has no victim payments to target")
    return ClientProfile(i.customer_id, i.tokens[0], targets, i.tokens[1:])


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
    # extra attacker identities beyond ``attacker`` (v2 scenarios); empty = v1 behaviour
    extra_attackers: tuple[ClientProfile, ...] = ()
    # "per_window": attacker identity cycles with the window index; "per_request": drawn
    # per attack request from the driver RNG (independent of the defender)
    attacker_switch: Literal["per_window", "per_request"] = "per_window"
    # cycle through the attacker's valid tokens window by window
    rotate_tokens: bool = False

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self.attack_active = self._initial_state()
        self._window = 0

    def _initial_state(self) -> bool:
        return True if self.schedule == "always" else self.start_active

    def reset(self, seed: int | None = None) -> None:
        self._rng = random.Random(self.seed if seed is None else seed)
        self.attack_active = self._initial_state()
        self._window = 0

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
        w = self._window
        self._window += 1
        attackers = (self.attacker, *self.extra_attackers)
        n_attack = self.attack_per_step if self.attack_active else 0
        plan: list[bool] = [False] * self.benign_per_step + [True] * n_attack
        self._rng.shuffle(plan)
        for is_attack in plan:
            if is_attack:
                if len(attackers) == 1:
                    att = attackers[0]  # no extra RNG draw: v1 traffic is unchanged
                elif self.attacker_switch == "per_window":
                    att = attackers[w % len(attackers)]
                else:
                    att = self._rng.choice(attackers)
                tokens = (att.token, *att.alt_tokens)
                token = tokens[w % len(tokens)] if self.rotate_tokens else att.token
                victim_id = self._rng.choice(att.own_payment_ids)
                gateway.request(
                    "GET",
                    f"/payments/{victim_id}",
                    actor=att.actor,
                    token=token,
                    is_attack=True,
                )
            else:
                client = self._rng.choice(self.benign)
                # a benign customer reads their own payments list and profile
                if self._rng.random() < 0.5:
                    gateway.request("GET", "/payments", actor=client.actor, token=client.token)
                else:
                    gateway.request("GET", "/me", actor=client.actor, token=client.token)
