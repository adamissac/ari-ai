"""Read-only feature/lineage inventory of fixed TRAIN archives; never policy replay.

Not a replacement for the historical execution-source verifier. No holdout reader,
training launcher, registry writer or data collector is reachable from this module.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from rl_defense.live.contracts import LiveTransition
from rl_defense.research.adaptive import ACTION_MASK, FEATURES, OBSERVATION_VERSION
from rl_defense.research.dataset import evidence, validate_episodes
from rl_defense.research.proof import bounded_gzip, read_artifact
from rl_defense.research.records import ResearchTransition

ANCHORS = {
    "constrained-phase1": "54e3af1c96b073c595f219cee025eaeb486bdcfc476e84ad91ea6665a7647506",
    "duration-screen": "ce9317baa7cad1c1a77dacf19736d0d8fb812e8c76af0b03fc3cc699c77291b6",
}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON value {value}")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def _index(results: Path, name: str) -> dict[str, Any]:
    raw = read_artifact(results / name / "EVIDENCE.json")
    if _digest(raw) != ANCHORS[name]:
        raise ValueError("evidence trust anchor changed")
    parsed = _json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("evidence index must be an object")
    return parsed


def _pinned(results: Path, name: str, rel: str, index: dict[str, Any]) -> bytes:
    raw = read_artifact(results / name / rel)
    if _digest(raw) != index["files"][rel]:
        raise ValueError("archived artifact hash mismatch")
    return raw


def audit(results: Path) -> dict[str, Any]:
    """Bounded, deterministic inventory; hashes are fixed externally in this code."""
    index = _index(results, "constrained-phase1")
    rel = "transitions.jsonl.gz"
    raw = _pinned(results, "constrained-phase1", rel, index)
    rows = [
        ResearchTransition.model_validate(_json(line))
        for line in gzip.decompress(bounded_gzip(raw)).splitlines()
    ]
    validate_episodes(rows)
    if any(r.split != "train" for r in rows):
        raise ValueError("inventory accepts training records only")
    # Scope is deliberately fixed, not a user-selected glob that can read holdout.
    legacy = _index(results, "duration-screen")
    legacy_count = legacy_episodes = missing_first_masks = 0
    refs = [evidence(f"constrained-phase1/{rel}", _digest(raw), "all training rows")]
    for policy in ("short", "long", "duration", "v6", "tuned_rules"):
        rel = f"train/{policy}/trajectories.jsonl.gz"
        raw = _pinned(results, "duration-screen", rel, legacy)
        refs.append(evidence(f"duration-screen/{rel}", _digest(raw), "all training episodes"))
        seen: set[tuple[str, int]] = set()
        for line in gzip.decompress(bounded_gzip(raw)).splitlines():
            record = _json(line)
            key = (record["scenario"], record["seed"])
            if key in seen or record["policy"] != policy or not 0 <= record["seed"] < 10000:
                raise ValueError("duplicate episode, policy or seed-band mismatch")
            seen.add(key)
            ts = [LiveTransition.model_validate(t) for t in record["transitions"]]
            if not ts or not ts[-1].done:
                raise ValueError("incomplete archived episode")
            for i, t in enumerate(ts):
                if t.done != (t.outcome.terminated or t.outcome.truncated):
                    raise ValueError("termination mismatch")
                if i and (ts[i - 1].done or ts[i - 1].next_obs != t.obs):
                    raise ValueError("broken archived chain")
            legacy_episodes += 1
            missing_first_masks += 1
            legacy_count += len(ts)
    return {
        "schema": "adaptive-readiness/0.1",
        "candidate_observation": OBSERVATION_VERSION,
        "fresh_evaluation": False,
        "historical_execution_reverified": False,
        "scope": "fixed Phase1 training adapter and duration-screen training archives only",
        "phase1": {
            "transitions": len(rows),
            "episodes": len({(r.policy, r.scenario, r.seed) for r in rows}),
            "current_masks_known": sum(r.current_mask is not None for r in rows),
            "behavior_probabilities_known": sum(r.behavior_probability is not None for r in rows),
            "aggregate_cost_known": sum(r.benign_cost.value is not None for r in rows),
            "delegated_cost_known": sum(r.delegated_blocked.value is not None for r in rows),
            "action_indices_observed": sorted({r.action for r in rows}),
            "candidate_provider_snapshots": 0,
        },
        "duration_train": {
            "transitions": legacy_count,
            "episodes": legacy_episodes,
            "first_current_masks_missing": missing_first_masks,
            "behavior_probabilities_known": 0,
            "delegated_cost_known": 0,
        },
        "feature_coverage": {
            feature: {
                "candidate_decision_time_coverage": "unavailable",
                "reason": "no versioned provider snapshot/knowledge-arrival contract in these archives",
            }
            for feature in FEATURES
        },
        "overlap": "shared familiar train_v8 scenario/seed identities; never pool as independent units",
        "supervised": "descriptive legacy on-policy outcomes only; no candidate-state causal model",
        "off_policy_evaluation": False,
        "offline_rl_ready": False,
        "online_rl_ready": False,
        "supported_action_mask": ACTION_MASK,
        "verdict": "NO-GO",
        "failed_conditions": [
            "no demonstrated adaptive residual benefit beyond deterministic authorization",
            "no measured narrow control effect or action-dependent traffic dynamics",
            "candidate decision-time telemetry and complete cost coverage missing",
            "no candidate baseline gap on eligible comparable scenarios",
            "constraints/sample size/compute/seed registry and owner approvals unset",
        ],
        "training_authorized": False,
        "collection_authorized": False,
        "evidence": [ref.model_dump(mode="json") for ref in refs],
    }


if __name__ == "__main__":
    print(
        json.dumps(audit(Path(__file__).resolve().parents[2] / "results"), indent=2, sort_keys=True)
    )
