"""Versioned live scenarios with fixed train / val / holdout splits.

A scenario fixes the traffic the attacker and benign clients generate against the
owned demo app (attack schedule, burst timing, intensity, benign volume) plus the
episode seeds. Each split uses its own scenarios **and** a disjoint seed range, so a
candidate is never selected or judged on the scenarios it was trained on. Holdout
scenarios use timing/intensity combinations absent from training (low-and-slow,
rapid bursts, heavy benign load) to test generalization rather than memorization.

v2 fields (``attackers``, ``victims``, ``benign``, ``attacker_switch``, ``rotate_tokens``)
describe who attacks with which tokens (fixture identities in ``adversary.IDENTITIES``).
At their defaults they reproduce the v1 traffic, and they are left out of the config hash
so v1 scenario hashes are unchanged. ``configs/live/holdout_v2/`` holds holdout scenarios
created after the v1 holdout was exposed (results/live-retrain/PROVENANCE.md).

v3 fields (``delegations``, ``delegate_per_step``, ``delegate_burst_p``,
``delegate_burst_size``) add legitimate cross-tenant readers (adversary.DelegateProfile);
like the v2 fields they are omitted from the hash at their defaults. v3 scenarios live in
``train_v3/``, ``val_v3/`` and ``holdout_v3/`` (results/live-retrain-v3/PROVENANCE.md).
v4 trains on ``train_v3/``, selects on the four scenarios in ``val_v4/`` (val3_mixed plus
three new ones) and is judged once on ``holdout_v4/`` (results/live-retrain-v4/PROVENANCE.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rl_defense.live.adversary import (
    TrafficDriver,
    attacker_profile,
    benign_profile,
    delegate_profile,
)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "live"
Split = Literal["train", "val", "holdout"]
# Disjoint seed bands per split (validated below).
SEED_BANDS: dict[str, tuple[int, int]] = {
    "train": (0, 9_999),
    "val": (20_000, 29_999),
    "holdout": (40_000, 49_999),
}


class LiveScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    split: Split
    horizon: int = Field(30, ge=5)
    schedule: Literal["always", "bursty"]
    p_start: float = Field(0.2, ge=0.0, le=1.0)
    p_stop: float = Field(0.2, ge=0.0, le=1.0)
    start_active: bool = False
    attack_per_step: int = Field(ge=0)
    benign_per_step: int = Field(ge=1)
    seed_start: int = Field(ge=0)
    episodes: int = Field(ge=1)
    # --- v2: identities (defaults = v1 traffic) ---
    attackers: tuple[str, ...] = ("bob",)
    victims: tuple[str, ...] = ("alice",)
    benign: tuple[str, ...] = ("alice", "bob")
    attacker_switch: Literal["per_window", "per_request"] = "per_window"
    rotate_tokens: bool = False
    # --- v3: legitimate cross-tenant readers ("delegate:owner"; defaults = none) ---
    delegations: tuple[str, ...] = ()
    delegate_per_step: int = Field(1, ge=0)
    delegate_burst_p: float = Field(0.0, ge=0.0, le=1.0)
    delegate_burst_size: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _seeds_in_band(self) -> LiveScenario:
        lo, hi = SEED_BANDS[self.split]
        if not (lo <= self.seed_start and self.seed_start + self.episodes - 1 <= hi):
            raise ValueError(f"{self.name}: seeds must lie in the {self.split} band {lo}..{hi}")
        return self

    def seeds(self, episodes: int | None = None) -> list[int]:
        n = self.episodes if episodes is None else min(episodes, self.episodes)
        return list(range(self.seed_start, self.seed_start + n))

    @property
    def uses_extra_identities(self) -> bool:
        """True when the scenario needs tenants/tokens beyond the payments-lite seed."""
        return any(
            getattr(self, k) != f.default for k, f in type(self).model_fields.items() if k in _V2
        )

    def driver(self) -> TrafficDriver:
        atts = [attacker_profile(a, self.victims) for a in self.attackers]
        return TrafficDriver(
            benign=tuple(benign_profile(b) for b in self.benign),
            attacker=atts[0],
            extra_attackers=tuple(atts[1:]),
            attacker_switch=self.attacker_switch,
            rotate_tokens=self.rotate_tokens,
            benign_per_step=self.benign_per_step,
            attack_per_step=self.attack_per_step,
            schedule=self.schedule,
            p_start=self.p_start,
            p_stop=self.p_stop,
            start_active=self.start_active,
            delegates=tuple(delegate_profile(d) for d in self.delegations),
            delegate_per_step=self.delegate_per_step,
            delegate_burst_p=self.delegate_burst_p,
            delegate_burst_size=self.delegate_burst_size,
        )

    def config_hash(self) -> str:
        d = self.model_dump(mode="json")
        for k in _V2:  # omitted at their defaults: v1 hashes stay valid
            if getattr(self, k) == type(self).model_fields[k].default:
                d.pop(k)
        payload = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


_V2 = (
    "attackers",
    "victims",
    "benign",
    "attacker_switch",
    "rotate_tokens",
    # v3
    "delegations",
    "delegate_per_step",
    "delegate_burst_p",
    "delegate_burst_size",
)


def load_scenarios(
    split: Split, config_dir: Path | None = None, *, subdir: str | None = None
) -> list[LiveScenario]:
    """Load ``<config_dir>/<subdir or split>/*.yaml``; every file must declare ``split``."""
    d = (config_dir or CONFIG_DIR) / (subdir or split)
    out = [
        LiveScenario.model_validate(yaml.safe_load(p.read_text())) for p in sorted(d.glob("*.yaml"))
    ]
    for s in out:
        if s.split != split:
            raise ValueError(f"{s.name} declares split={s.split} but lives in {split}/")
    if not out:
        raise ValueError(f"no live scenarios found in {d}")
    return out
