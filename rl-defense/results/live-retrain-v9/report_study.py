"""Post-run diagnostics only: no training or held-out policy execution."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.live import platform_check, study
from rl_defense.live.scenarios import load_scenarios


def main() -> None:
    root = Path(__file__).resolve().parent
    summary = json.loads((root / "study_summary.json").read_text())
    quiet_scenarios = ("quiet_rogue_reconciler", "faint_outsider_reconciliation")
    quiet_checks = {
        s: summary["by_scenario"]["candidate"][s]["reward"]["mean"]
        >= summary["by_scenario"]["v8"][s]["reward"]["mean"]
        for s in quiet_scenarios
    }
    support = summary["candidate_minus_incumbent"]["reward"]["ci95"][0] > 0 and all(
        quiet_checks.values()
    )
    checks = {}
    worst = None
    scenarios = load_scenarios("train", subdir="train_v8")
    for seed in study.SEEDS:
        directory = root / f"seed{seed}"
        agent, _ = load_checkpoint(directory / "candidate_online.pt")
        checks[str(seed)] = platform_check.compare(agent, scenarios)
        rows = json.loads((directory / "holdout_episodes.json").read_text())
        incumbent = {(r["scenario"], r["seed"]): r for r in rows["deployed"]}
        for row in rows["candidate"]:
            key = row["scenario"], row["seed"]
            difference = row["reward"] - incumbent[key]["reward"]
            if worst is None or difference < worst["candidate_minus_incumbent_return"]:
                worst = {
                    "training_seed": seed,
                    "scenario": key[0],
                    "evaluation_seed": key[1],
                    "candidate_minus_incumbent_return": difference,
                    "candidate_metrics": row,
                    "incumbent_metrics": incumbent[key],
                }
    assert worst is not None
    directory = root / f"seed{worst['training_seed']}"
    with gzip.open(directory / "holdout_trajectories.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row["scenario"] == worst["scenario"]
                and row["seed"] == worst["evaluation_seed"]
                and row["policy"] in {"candidate", "deployed"}
            ):
                worst[f"{row['policy']}_trajectory"] = row["transitions"]
    (root / "platform_agreement.json").write_text(json.dumps(checks, indent=2))
    (root / "failure_case.json").write_text(json.dumps(worst, indent=2))
    verdict = {
        "primary_hypothesis_supported": bool(support),
        "low_intensity_vs_v8": quiet_checks,
        "candidate_minus_incumbent_return": summary["candidate_minus_incumbent"]["reward"],
        "per_seed_gate": summary["per_seed_gate"],
        "promotion_performed": False,
    }
    (root / "study_verdict.json").write_text(json.dumps(verdict, indent=2))
    label = "supported" if support else "not supported"
    r = summary["candidate_minus_incumbent"]["reward"]
    (root / "PROVENANCE.md").write_text(
        "# V9 five-seed lab study\n\n"
        f"The preregistered hypothesis is **{label}**. No policy was promoted.\n\n"
        f"Candidate-minus-incumbent return: {r['mean']:.4f}, 95% training-seed bootstrap "
        f"CI [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]. Five seeds, 100 paired episodes per scenario.\n\n"
        "See study_summary.json for every policy, metric and per-scenario seed value; "
        "study_verdict.json for every gate; platform_agreement.json for train-only mapping "
        "checks; failure_case.json for the worst episode and raw trajectories.\n\n"
        "RUN.json records source, preregistration, registry hashes and hardware. Each seed "
        "contains exact checkpoint/experience/evaluation evidence. Small-n paired t tests "
        "assume independent training seeds; bootstrap intervals with n=5 have limited precision. "
        "The fixed incumbent/reference policies do not have fresh training-seed uncertainty.\n\n"
        "Measured in the owned, in-process payments-lite lab. These results do not establish "
        "real-world effectiveness and are not the DefenseSimEnv-v0 benchmark.\n"
    )
    print(f"Primary hypothesis {label}; no promotion.")


if __name__ == "__main__":
    main()
