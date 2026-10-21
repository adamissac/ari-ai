"""Complete preregistered diagnostics from saved results and train-only checks."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint, sha256_file
from rl_defense.live import evidence, platform_check
from rl_defense.live.scenarios import load_scenarios


def secondary(checks: dict) -> dict:
    # Reuse the exact tested threshold definitions from the v9 reporting helper.
    path = Path(__file__).parents[1] / "live-retrain-v9/finalize_study.py"
    spec = importlib.util.spec_from_file_location("v9_secondary_definitions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.secondary_checks(checks)


def verify(root: Path) -> None:
    root = root.resolve()
    manifest = json.loads((root / "STUDY_EVIDENCE.json").read_text())
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256_file(path) != expected:
            raise ValueError(f"study artifact changed: {name}")
    for arm in ("uniform", "balanced"):
        for seed in range(5):
            evidence.verify(root / arm / f"seed{seed}")


def postprocess(root: Path) -> None:
    checks = {}
    worst = None
    train = load_scenarios("train", subdir="train_v8")
    for arm in ("uniform", "balanced"):
        checks[arm] = {}
        for seed in range(5):
            directory = root / arm / f"seed{seed}"
            evidence.verify(directory)
            agent, _ = load_checkpoint(directory / "candidate_online.pt")
            checks[arm][str(seed)] = platform_check.compare(agent, train)
            rows = json.loads((directory / "holdout_episodes.json").read_text())
            incumbent = {(r["scenario"], r["seed"]): r for r in rows["deployed"]}
            for row in rows["candidate"]:
                key = row["scenario"], row["seed"]
                difference = row["reward"] - incumbent[key]["reward"]
                if worst is None or difference < worst["candidate_minus_incumbent_return"]:
                    worst = {
                        "arm": arm,
                        "training_seed": seed,
                        "scenario": key[0],
                        "evaluation_seed": key[1],
                        "candidate_minus_incumbent_return": difference,
                        "candidate_metrics": row,
                        "incumbent_metrics": incumbent[key],
                    }
    if worst is None:
        raise ValueError("missing paired failure evidence")
    path = root / worst["arm"] / f"seed{worst['training_seed']}" / "holdout_trajectories.jsonl.gz"
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row["scenario"] == worst["scenario"]
                and row["seed"] == worst["evaluation_seed"]
                and row["policy"] in {"candidate", "deployed"}
            ):
                worst[f"{row['policy']}_trajectory"] = row["transitions"]
    for policy, metric in (("candidate", "candidate_metrics"), ("deployed", "incumbent_metrics")):
        if len(worst.get(f"{policy}_trajectory", [])) != worst[metric]["steps"]:
            raise ValueError("missing complete paired failure trajectories")
    (root / "platform_agreement.json").write_text(json.dumps(checks, indent=2))
    (root / "secondary_checks.json").write_text(
        json.dumps({a: secondary(c) for a, c in checks.items()}, indent=2)
    )
    (root / "failure_case.json").write_text(json.dumps(worst, indent=2))
    files = {
        str(p.relative_to(root)): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "STUDY_EVIDENCE.json"
    }
    (root / "STUDY_EVIDENCE.json").write_text(
        json.dumps(
            {"schema": "live-two-arm-evidence/0.1", "files": files, "promotion_performed": False},
            indent=2,
        )
    )
    verify(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.root)
    else:
        postprocess(args.root)


if __name__ == "__main__":
    main()
