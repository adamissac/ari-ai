"""Versioned live scenarios with fixed train / val / holdout splits.

A scenario fixes the traffic the attacker and benign clients generate against the
owned demo app (attack schedule, burst timing, intensity, benign volume) plus the
episode seeds. Each split uses its own scenarios **and** a disjoint seed range, so a
candidate is never selected or judged on the scenarios it was trained on. Holdout
scenarios use timing/intensity combinations absent from training (low-and-slow,
rapid bursts, heavy benign load) to test generalization rather than memorization.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rl_defense.live.adversary import TrafficDriver

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

    @model_validator(mode="after")
    def _seeds_in_band(self) -> LiveScenario:
        lo, hi = SEED_BANDS[self.split]
        if not (lo <= self.seed_start and self.seed_start + self.episodes - 1 <= hi):
            raise ValueError(f"{self.name}: seeds must lie in the {self.split} band {lo}..{hi}")
        return self

    def seeds(self, episodes: int | None = None) -> list[int]:
        n = self.episodes if episodes is None else min(episodes, self.episodes)
        return list(range(self.seed_start, self.seed_start + n))

    def driver(self) -> TrafficDriver:
        return TrafficDriver(
            benign_per_step=self.benign_per_step,
            attack_per_step=self.attack_per_step,
            schedule=self.schedule,
            p_start=self.p_start,
            p_stop=self.p_stop,
            start_active=self.start_active,
        )

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_scenarios(split: Split, config_dir: Path | None = None) -> list[LiveScenario]:
    d = (config_dir or CONFIG_DIR) / split
    out = [
        LiveScenario.model_validate(yaml.safe_load(p.read_text())) for p in sorted(d.glob("*.yaml"))
    ]
    for s in out:
        if s.split != split:
            raise ValueError(f"{s.name} declares split={s.split} but lives in {split}/")
    if not out:
        raise ValueError(f"no live scenarios found in {d}")
    return out
