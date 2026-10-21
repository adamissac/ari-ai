"""Analyze saved v9 data only; never execute a policy in the held-out environment."""

import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np

from rl_defense.checkpoint import load_checkpoint, sha256_file
from rl_defense.envs.defense_sim import NOOP_ACTION


def main() -> None:
    root = Path(__file__).resolve().parent
    old = root.parent / "live-retrain-v9"
    output = {"source": "saved v9 artifacts only; no environment replay", "seeds": []}
    for seed in range(5):
        directory = old / f"seed{seed}"
        counts = Counter()
        with gzip.open(directory / "candidate_online_experience.jsonl.gz", "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if row["kind"] != "demo":
                    break
                counts[row["outcome"]["action_label"].split(":")[0]] += 1
        output["seeds"].append(
            {"seed": seed, "demo_actions": dict(counts), "demo_rows": sum(counts.values())}
        )
    output["mixed_rotation"] = []
    for seed in range(5):
        report = json.loads((old / f"seed{seed}" / "promotion_report.json").read_text())
        values = report["by_scenario"]
        name = "mixed_delegate_rotation"
        output["mixed_rotation"].append(
            {
                "seed": seed,
                "candidate_return": values["candidate"][name]["reward"],
                "incumbent_return": values["deployed"][name]["reward"],
                "candidate_minus_incumbent": values["candidate"][name]["reward"]
                - values["deployed"][name]["reward"],
            }
        )
    failure = json.loads((old / "failure_case.json").read_text())
    directory = old / f"seed{failure['training_seed']}"
    agent, _ = load_checkpoint(directory / "candidate_online.pt")
    decisions = []
    previous_mask = None
    for t in failure["candidate_trajectory"]:
        obs = np.asarray(t["obs"], dtype=np.float32)
        q = agent.q_values(obs)
        valid_blocks = [a for a in (22, 23, 24) if previous_mask is not None and previous_mask[a]]
        previous_mask = t["action_mask"]
        decisions.append(
            {
                "step": t["outcome"]["step"],
                "saved_action": t["action"],
                "q_noop": float(q[NOOP_ACTION]),
                "valid_block_q": {str(a): float(q[a]) for a in valid_blocks},
                "flagged_principals": t["obs"][50],
                "flagged_repeat": t["obs"][53],
                "compromised_reads": t["outcome"]["compromised_reads"],
            }
        )
    output["worst_failure"] = {
        "training_seed": failure["training_seed"],
        "evaluation_seed": failure["evaluation_seed"],
        "scenario": failure["scenario"],
        "checkpoint_sha256": sha256_file(directory / "candidate_online.pt"),
        "decisions": decisions,
    }
    (root / "v9_diagnostics.json").write_text(json.dumps(output, indent=2))
    print(json.dumps(output["seeds"], indent=2))
    print(
        "Failed attack windows with a valid block:",
        sum(d["compromised_reads"] > 0 and bool(d["valid_block_q"]) for d in decisions),
    )


if __name__ == "__main__":
    main()
