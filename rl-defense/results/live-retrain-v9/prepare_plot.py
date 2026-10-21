"""Derive curve intervals from completed seed manifests in the training environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from rl_defense.live.evaluate import bootstrap_ci


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    root = ap.parse_args().root
    run = json.loads((root / "RUN.json").read_text())
    if run.get("errors") or not run.get("finished_at"):
        raise ValueError("study is not complete")
    manifests = [
        json.loads((root / f"seed{s}/candidate_online.manifest.json").read_text()) for s in range(5)
    ]
    steps = [r["env_step"] for r in manifests[0]["online"]["selection_history"]]
    if any([r["env_step"] for r in m["online"]["selection_history"]] != steps for m in manifests):
        raise ValueError("validation grids differ")
    scores = np.array(
        [[r["val_reward"] for r in m["online"]["selection_history"]] for m in manifests]
    )
    selected = []
    for m in manifests:
        step = m["online"]["selected_env_step"]
        selected.append(
            {
                "seed": m["seed"],
                "step": step,
                "score": next(
                    r["val_reward"]
                    for r in m["online"]["selection_history"]
                    if r["env_step"] == step
                ),
                "checkpoint_sha256": m["checkpoint_sha256"],
            }
        )
    summary = json.loads((root / "study_summary.json").read_text())
    result = {
        "steps": steps,
        "by_training_seed": scores.tolist(),
        "mean": scores.mean(axis=0).tolist(),
        "ci95": [bootstrap_ci(scores[:, i], n=10000, seed=0) for i in range(len(steps))],
        "selected": selected,
        "heldout_paired_return": summary["candidate_minus_incumbent"]["reward"],
        "training_source_commit": run["git_sha"],
        "note": "Validation scores are used for checkpoint/margin selection; not held-out evidence. CIs use five training seeds.",
    }
    (root / "figure_data.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    print("Curve data derived without executing any policy.")


if __name__ == "__main__":
    main()
