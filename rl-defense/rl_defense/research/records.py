"""Internal, versioned research adapter; not a canonical platform/bus contract.

Measured cost means observed defense-denied generator-labelled legitimate requests,
not a counterfactual estimate or an authorization guarantee. Unknown is never zero.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.evidence import EvidenceRef

from rl_defense.layouts import dims


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Measurement(Strict):
    value: float | None
    evidence: EvidenceRef
    definition: str = Field(min_length=1)
    unknown_reason: str | None = None

    @model_validator(mode="after")
    def known_or_reason(self) -> Measurement:
        if (self.value is None) != bool(self.unknown_reason):
            raise ValueError("unknown values need a reason; measured values cannot have one")
        return self


class ResearchTransition(Strict):
    schema_version: Literal["constrained-lab/1"] = "constrained-lab/1"
    dataset_id: str
    policy: str
    scenario: str
    scenario_hash: str
    split: Literal["train", "val"]
    seed: int = Field(ge=0)
    t: int = Field(ge=0)
    action_space: Literal["sim", "live_v2", "live_v3"]
    obs: tuple[float, ...]
    action: int = Field(ge=0)
    current_mask: tuple[bool, ...] | None  # first historical mask was not saved
    next_obs: tuple[float, ...]
    next_mask: tuple[bool, ...]
    terminated: bool
    truncated: bool
    attack_active: bool  # metrics only
    attack_requests: int = Field(ge=0)
    compromised_reads: int = Field(ge=0)
    benign_requests: int = Field(ge=0)
    benign_blocked: int | None = Field(ge=0)
    # Separated objectives, counts per window; historical scalar reward is retained.
    threat_reward: Measurement
    benign_cost: Measurement
    legacy_reward: Measurement
    # Historical aggregate outcomes cannot separate own/delegated denial counts.
    delegated_blocked: Measurement
    outcome_evidence: EvidenceRef
    behavior_probability: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def consistent(self) -> ResearchTransition:
        obs_dim, n_actions = dims(self.action_space)
        if len(self.obs) != obs_dim or len(self.next_obs) != obs_dim:
            raise ValueError("observation layout mismatch")
        if any(not 0 <= x <= 1 for x in (*self.obs, *self.next_obs)):
            raise ValueError("observations must be finite normalized features")
        if len(self.next_mask) != n_actions or not self.next_mask[0]:
            raise ValueError("next mask layout/noop mismatch")
        if self.action >= n_actions:
            raise ValueError("action outside unchanged layout")
        if self.current_mask is not None:
            if len(self.current_mask) != n_actions or not self.current_mask[0]:
                raise ValueError("current mask layout/noop mismatch")
            if not self.current_mask[self.action]:
                raise ValueError("recorded action unavailable under current mask")
        lo, hi = (0, 9999) if self.split == "train" else (20000, 29999)
        if not lo <= self.seed <= hi:
            raise ValueError("seed outside original split band")
        if self.compromised_reads > self.attack_requests:
            raise ValueError("compromise exceeds attack count")
        if self.benign_blocked is not None and self.benign_blocked > self.benign_requests:
            raise ValueError("blocked exceeds legitimate count")
        if self.threat_reward.value != -self.compromised_reads:
            raise ValueError("reward must be negative observed compromised-read count")
        if self.benign_cost.value != self.benign_blocked:
            raise ValueError("cost must equal observed legitimate defense denials, or unknown")
        if self.delegated_blocked.value is not None:
            if (
                self.benign_blocked is None
                or not 0 <= self.delegated_blocked.value <= self.benign_blocked
            ):
                raise ValueError("delegated cost must be a measured subset of total cost")
        return self
