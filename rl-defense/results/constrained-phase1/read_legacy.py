"""Read-only readiness check; no environment, training, OPE or historical writes.

Run from repo root with RL/shared on PYTHONPATH. Output goes to stdout.
"""

from __future__ import annotations

import json
from pathlib import Path

from rl_defense.live.scenarios import load_scenarios
from rl_defense.research.dataset import digest, load_legacy


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "duration-screen"
    index_path = root / "EVIDENCE.json"
    index = json.loads(index_path.read_bytes())
    run = json.loads((root / "RUN.json").read_bytes())
    if digest((root / "RUN.json").read_bytes()) != index["files"]["RUN.json"]:
        raise ValueError("historical run pin changed")
    scenarios = load_scenarios("train", subdir="train_v8")
    if {s.name: s.config_hash() for s in scenarios} != run["splits"]["train"]:
        raise ValueError("historical scenario definitions changed")
    result = {
        "schema": "constrained-readiness/1",
        "source_commit": run["git_sha"],
        "evidence_index_sha256": digest(index_path.read_bytes()),
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
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
