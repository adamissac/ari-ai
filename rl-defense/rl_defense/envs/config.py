"""Scenario configuration for DefenseSimEnv. Configs are versioned and hashed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

NODE_NAMES: tuple[str, ...] = ("gateway", "api", "auth", "payments", "db")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeSpec(_Strict):
    name: str
    criticality: float = Field(ge=0.0, le=1.0)
    exposed: bool
    finding_severity: float = Field(
        ge=0.0, le=1.0, description="Max open validated-finding severity"
    )


class AdversaryParams(_Strict):
    """Per-step stage-transition probabilities before modifiers."""

    entry_prob: float = Field(ge=0.0, le=1.0)
    lateral_prob: float = Field(ge=0.0, le=1.0)
    escalate_prob: float = Field(ge=0.0, le=1.0)
    impact_prob: float = Field(ge=0.0, le=1.0)
    severity_weight: float = Field(
        ge=0.0, le=2.0, description="How much open findings speed progression"
    )


class SignalParams(_Strict):
    benign_alert_rate: float = Field(ge=0.0, description="Mean benign alerts per node per step")
    stage_alert_rate: float = Field(ge=0.0, description="Extra mean alerts per adversary stage")
    monitoring_gain: float = Field(ge=0.0, description="Detection multiplier per monitoring level")
    anomaly_noise: float = Field(ge=0.0)
    benign_burst_prob: float = Field(ge=0.0, le=1.0, description="Chance of a benign alert burst")


class DefenseParams(_Strict):
    rate_limit_factor: float = Field(
        ge=0.0, le=1.0, description="Progression multiplier while rate-limited"
    )
    isolate_clean_prob: float = Field(
        ge=0.0, le=1.0, description="Per-step chance isolation evicts adversary"
    )
    effect_duration: int = Field(ge=1, description="Steps a rate-limit/isolation lasts")
    monitoring_duration: int = Field(ge=1)
    max_monitoring_level: int = Field(ge=1, le=5)
    reassessment_delay: int = Field(
        ge=1, description="Steps until a requested reassessment patches findings"
    )
    reassessment_severity_after: float = Field(ge=0.0, le=1.0)
    escalation_delay: int = Field(ge=1)
    escalation_success_prob: float = Field(ge=0.0, le=1.0)
    max_escalations: int = Field(ge=0)


class RewardParams(_Strict):
    c_impact: float = Field(ge=0.0)
    c_progress: float = Field(ge=0.0)
    c_disrupt: float = Field(ge=0.0)
    c_action: float = Field(ge=0.0)
    c_escalate: float = Field(ge=0.0)
    c_contain: float = Field(ge=0.0)
    c_terminal: float = Field(ge=0.0, description="Penalty when the db node reaches impact")
    c_invalid: float = Field(ge=0.0)


class ScenarioConfig(_Strict):
    name: str
    env_version: str = "DefenseSimEnv-v0"
    split: str = Field(pattern="^(train|eval)$")
    horizon: int = Field(default=200, ge=10)
    nodes: tuple[NodeSpec, ...]
    edges: tuple[tuple[str, str], ...] = Field(description="Directed lateral-movement edges")
    adversary: AdversaryParams
    signals: SignalParams
    defense: DefenseParams
    reward: RewardParams

    @model_validator(mode="after")
    def _check_topology(self) -> ScenarioConfig:
        names = tuple(n.name for n in self.nodes)
        if names != NODE_NAMES:
            raise ValueError(f"nodes must be exactly {NODE_NAMES} in order, got {names}")
        for src, dst in self.edges:
            if src not in names or dst not in names:
                raise ValueError(f"edge references unknown node: {src}->{dst}")
        return self

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_config(path: str | Path) -> ScenarioConfig:
    data = yaml.safe_load(Path(path).read_text())
    return ScenarioConfig.model_validate(data)


def load_configs(paths: list[str | Path]) -> list[ScenarioConfig]:
    return [load_config(p) for p in paths]


CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def default_config_paths(split: str) -> list[Path]:
    return sorted((CONFIG_DIR / split).glob("*.yaml"))
