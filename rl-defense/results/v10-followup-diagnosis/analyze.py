"""Diagnose exposed v10 evidence only; never execute a policy or held-out scenario."""

import gzip
import json
from collections import Counter
from pathlib import Path

from rl_defense.checkpoint import sha256_file
from rl_defense.live.online import validation_availability_screen


def analyze(root: Path) -> dict:
    inputs = {}

    def read(relative: str) -> dict:
        path = root / relative
        inputs[relative] = sha256_file(path)
        return json.loads(path.read_text())

    summary = read("study_summary.json")
    output = {
        "scope": "saved v10 evidence only; no policy or environment execution",
        "screens": {},
        "rotation": {},
        "promotion_performed": False,
    }
    worst = None
    for arm in ("uniform", "balanced"):
        output["screens"][arm] = []
        for seed in range(5):
            manifest = read(f"{arm}/seed{seed}/candidate_online.manifest.json")
            screen = validation_availability_screen(manifest, 0.85)
            screen["training_seed"] = seed
            # History retains only the best-return margin at each snapshot, not every margin.
            screen["recorded_best_margin_snapshots_meeting_floor"] = sum(
                row["val_availability"] is not None and row["val_availability"] >= 0.85
                for row in manifest["online"]["selection_history"]
            )
            output["screens"][arm].append(screen)
            episodes = read(f"{arm}/seed{seed}/holdout_episodes.json")
            deployed = {(r["scenario"], r["seed"]): r for r in episodes["deployed"]}
            for row in episodes["candidate"]:
                if arm != "balanced" or row["scenario"] != "holdout10_rotation":
                    continue
                other = deployed[(row["scenario"], row["seed"])]
                delta = row["reward"] - other["reward"]
                if worst is None or delta < worst["return_difference"]:
                    worst = {
                        "arm": arm,
                        "training_seed": seed,
                        "scenario": row["scenario"],
                        "evaluation_seed": row["seed"],
                        "return_difference": delta,
                        "candidate": row,
                        "deployed": other,
                    }
        values = summary["arms"][arm]["by_scenario"]
        output["rotation"][arm] = {
            policy: {
                metric: value["mean"] for metric, value in scenarios["holdout10_rotation"].items()
            }
            for policy, scenarios in values.items()
        }
    assert worst is not None
    relative = f"balanced/seed{worst['training_seed']}/holdout_trajectories.jsonl.gz"
    path = root / relative
    inputs[relative] = sha256_file(path)
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row["policy"] in {"candidate", "deployed"}
                and row["scenario"] == worst["scenario"]
                and row["seed"] == worst["evaluation_seed"]
            ):
                transitions = row["transitions"]
                assert len(transitions) == worst[row["policy"]]["steps"]
                worst[f"{row['policy']}_action_counts"] = dict(
                    Counter(t["outcome"]["action_label"].split(":")[0] for t in transitions)
                )
                worst[f"{row['policy']}_trajectory"] = transitions
    assert "candidate_trajectory" in worst and "deployed_trajectory" in worst
    output["worst_balanced_rotation"] = worst
    output["input_sha256"] = inputs
    return output


def main() -> None:
    directory = Path(__file__).resolve().parent
    result = analyze(directory.parent / "live-retrain-v10")
    (directory / "diagnostics.json").write_text(json.dumps(result, indent=2))
    print(
        "Selected checkpoints failing the validation floor:",
        sum(not row["eligible_for_holdout"] for rows in result["screens"].values() for row in rows),
    )
    worst = result["worst_balanced_rotation"]
    print({k: v for k, v in worst.items() if "trajectory" not in k})


if __name__ == "__main__":
    main()
