"""Training configuration (importable without numpy)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TrainConfig:
    input_dim: int = 8192
    hidden: int = 64
    epochs: int = 60
    batch_size: int = 64
    lr: float = 2e-3
    weight_decay: float = 1e-5
    dropout: float = 0.2
    patience: int = 6
    seed: int = 7

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
