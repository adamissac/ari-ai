"""Read-only readiness check; no environment, training, OPE or historical writes.

Supported reader: python -m rl_defense.research.legacy.
The original result-directory reader remains frozen archival source only.
"""

from __future__ import annotations

import json
from pathlib import Path

from rl_defense.live.scenarios import load_scenarios
from rl_defense.research.dataset import digest, load_legacy


def verify_legacy(root: Path) -> dict:
    index_path = root / "EVIDENCE.json"
    index_blob = index_path.read_bytes()
    if digest(index_blob) != "ce9317baa7cad1c1a77dacf19736d0d8fb812e8c76af0b03fc3cc699c77291b6":
        raise ValueError("historical evidence index trust anchor mismatch")
    index = json.loads(index_blob)
    run_blob = (root / "RUN.json").read_bytes()
    run = json.loads(run_blob)
    if digest(run_blob) != index["files"]["RUN.json"]:
        raise ValueError("historical run pin changed")
    scenarios = load_scenarios("train", subdir="train_v8")
    if {s.name: s.config_hash() for s in scenarios} != run["splits"]["train"]:
        raise ValueError("historical scenario definitions changed")
    result = {
        "schema": "constrained-readiness/1",
        "source_commit": run["git_sha"],
        "evidence_index_sha256": digest(index_blob),
        "historical_semantics_unchanged": True,
        "new_objective": "negative compromised read count; legitimate defense-denial count",
        "not_counterfactual_evaluation": True,
        "datasets": {},
    }
    for policy in ("short", "long", "duration", "v6", "tuned_rules"):
        rel = f"train/{policy}/trajectories.jsonl.gz"
        rows = load_legacy(
            root / rel, expected_sha256=index["files"][rel], scenarios=scenarios, policy=policy
        )
        result["datasets"][policy] = {
            "source_sha256": index["files"][rel],
            "transitions": len(rows),
            "episodes": len({(r.scenario, r.seed) for r in rows}),
            "measured_cost_records": sum(r.benign_cost.value is not None for r in rows),
            "unknown_current_masks": sum(r.current_mask is None for r in rows),
            "unknown_behavior_probabilities": sum(r.behavior_probability is None for r in rows),
            "unknown_delegated_costs": sum(r.delegated_blocked.value is None for r in rows),
        }
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "results/duration-screen"
    print(json.dumps(verify_legacy(root), indent=2, sort_keys=True))
