"""Scenario configuration for DefenseSimEnv. Configs are versioned and hashed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

NODE_NAMES: tuple[str, ...] = ("gateway", "api", "auth", "payments", "db")
ENV_V0 = "DefenseSimEnv-v0"
# Same dynamics, observation and action space as v0. Only the reward differs: a benign node
# under a disruptive control costs ``c_false_disrupt`` per step whatever its criticality.
ENV_V1 = "DefenseSimEnv-v1"
ENV_VERSIONS: tuple[str, ...] = (ENV_V0, ENV_V1)


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
    c_false_disrupt: float = Field(
        default=0.0,
        ge=0.0,
        description="DefenseSimEnv-v1 only. Per-step cost of each uncompromised node under "
        "isolation (x1.0) or rate-limit (x0.3), NOT scaled by criticality. 0 = the v0 reward.",
    )


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
        if self.env_version not in ENV_VERSIONS:
            raise ValueError(f"env_version must be one of {ENV_VERSIONS}, got {self.env_version}")
        # The reward version is part of the scenario identity: a v0 config cannot carry the
        # v1 term, and a v1 config must (otherwise it would be v0 under another name).
        if (self.reward.c_false_disrupt > 0.0) != (self.env_version == ENV_V1):
            raise ValueError(
                f"c_false_disrupt > 0 is required by and only allowed in {ENV_V1} configs"
            )
        return self

    def config_hash(self) -> str:
        data = self.model_dump(mode="json")
        if self.env_version == ENV_V0:
            # v0 hashes predate c_false_disrupt; committed manifests must keep matching.
            del data["reward"]["c_false_disrupt"]
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_config(path: str | Path) -> ScenarioConfig:
    data = yaml.safe_load(Path(path).read_text())
    return ScenarioConfig.model_validate(data)


def load_configs(paths: list[str | Path]) -> list[ScenarioConfig]:
    return [load_config(p) for p in paths]


CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def default_config_paths(split: str) -> list[Path]:
    return sorted((CONFIG_DIR / split).glob("*.yaml"))
