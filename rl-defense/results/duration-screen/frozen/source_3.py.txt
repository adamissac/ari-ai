"""One fixed heuristic duration screen on TRAIN/VAL only; never train, promote or use holdout."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np

from rl_defense.checkpoint import git_sha, load_checkpoint, sha256_file
from rl_defense.live import evaluate as ev
from rl_defense.live.adversary import live_app
from rl_defense.live.registry import Registry
from rl_defense.live.scenarios import LiveScenario, load_scenarios
from rl_defense.live.study import require_clean_source, source_fingerprint

ROOT = Path(__file__).resolve().parent
RL = ROOT.parents[1]
RUN = RL / "runs/live/duration-screen"
POLICIES = ("short", "long", "duration", "v6", "tuned_rules")
INCUMBENT = "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1"
DURATION_PARAMS = {
    "isolate_anomaly": 1.1,
    "rate_limit_alerts": 1.1,
    "monitor_anomaly": 1.1,
    "block_anomaly": 0.0,
    "block_min_volume": 0.0,
    "long_mode": "outsider",
    "long_target": "all",
}
OVERRIDES = {**ev.V4_LOOP_OVERRIDES, "finding_severity_context": "platform"}


def duration_policy() -> ev.PolicyFn:
    return ev.rules_policy(DURATION_PARAMS)


def paired_ratios(candidate: list[dict], reference: list[dict], metric: str) -> dict:
    """Request-weighted difference, resampling paired episodes within each scenario."""

    def keyed(rows: list[dict]) -> dict:
        result = {(r["scenario"], r["seed"]): r for r in rows}
        if len(result) != len(rows) or not rows:
            raise ValueError("missing or duplicate paired episodes")
        return result

    left, right = keyed(candidate), keyed(reference)
    if left.keys() != right.keys():
        raise ValueError("candidate and reference episode sets differ")
    numerator, denominator = (
        ("benign_blocked", "benign_requests")
        if metric == "availability"
        else ("compromised", "attack_requests")
    )
    if metric not in {"availability", "compromise_rate"}:
        raise ValueError("unknown ratio metric")
    groups = {}
    for key in sorted(left):
        a, b = left[key], right[key]
        if any(a[k] != b[k] for k in ("benign_requests", "attack_requests")):
            raise ValueError("paired traffic counts differ")
        values = [a[numerator], a[denominator], b[numerator], b[denominator]]
        if any(not np.isfinite(x) or x < 0 for x in values):
            raise ValueError("invalid traffic counters")
        if a[numerator] > a[denominator] or b[numerator] > b[denominator]:
            raise ValueError("numerator exceeds traffic denominator")
        groups.setdefault(key[0], []).append(values)
    arrays = [np.asarray(v, dtype=np.float64) for v in groups.values()]
    total = np.concatenate(arrays).sum(axis=0)
    rng = np.random.default_rng(1)
    sampled = np.zeros((10000, 4))
    for array in arrays:
        choices = rng.integers(0, len(array), size=(10000, len(array)))
        sampled += array[choices].sum(axis=1)
    undefined = int(np.count_nonzero((sampled[:, 1] == 0) | (sampled[:, 3] == 0)))
    if total[1] == 0 or total[3] == 0 or undefined:
        return {
            "mean": None,
            "ci95": None,
            "undefined_resamples": undefined,
            "reason": "undefined request fraction",
            "paired_episodes": len(left),
        }
    sign = -1 if metric == "availability" else 1
    differences = sign * (sampled[:, 0] / sampled[:, 1] - sampled[:, 2] / sampled[:, 3])
    return {
        "mean": float(sign * (total[0] / total[1] - total[2] / total[3])),
        "ci95": np.quantile(differences, [0.025, 0.975]).tolist(),
        "undefined_resamples": 0,
        "paired_episodes": len(left),
    }


def decide(rows: dict[str, list[dict]]) -> dict:
    if set(rows) != set(POLICIES):
        raise ValueError("all five fixed policies are required")
    keys = None
    for values in rows.values():
        current = {(row["scenario"], row["seed"]) for row in values}
        if len(current) != len(values) or not current or (keys is not None and current != keys):
            raise ValueError("policy episode cohorts disagree or contain duplicates")
        keys = current
    summaries = {
        name: ev.summarize([ev.EpisodeMetrics(**r) for r in values])
        for name, values in rows.items()
    }
    by_scenario = {
        name: ev.summarize_by_scenario([ev.EpisodeMetrics(**r) for r in values])
        for name, values in rows.items()
    }
    contrast = {
        metric: paired_ratios(rows["duration"], rows["v6"], metric)
        for metric in ("availability", "compromise_rate")
    }
    availability, compromise = contrast["availability"], contrast["compromise_rate"]
    per_scenario = all(
        value["compromise_rate"] is not None
        and by_scenario["v6"][name]["compromise_rate"] is not None
        and value["compromise_rate"] <= by_scenario["v6"][name]["compromise_rate"]
        for name, value in by_scenario["duration"].items()
    )
    checks = {
        "availability_gain_ci_low_positive": availability["ci95"] is not None
        and availability["ci95"][0] > 0,
        "compromise_difference_ci_high_nonpositive": compromise["ci95"] is not None
        and compromise["ci95"][1] <= 0,
        "no_scenario_compromise_increase": per_scenario,
        "availability_floor": summaries["duration"]["availability"] is not None
        and summaries["duration"]["availability"] >= 0.85,
    }
    return {
        "schema": "duration-validation-screen/0.1",
        "policies": summaries,
        "by_scenario": by_scenario,
        "duration_minus_v6": contrast,
        "checks": checks,
        "prepare_v11_preregistration": all(checks.values()),
        "promotion_performed": False,
        "scope": "Fixed heuristic policies; previously used validation, not held-out evidence or RL training.",
    }


def validate_budget(
    rows: list[ev.EpisodeMetrics], scenarios: list[LiveScenario], episodes: int
) -> None:
    expected = {(sc.name, seed) for sc in scenarios for seed in sc.seeds(episodes)}
    actual = {(row.scenario, row.seed) for row in rows}
    if len(rows) != len(expected) or actual != expected:
        raise ValueError("observed episodes do not match the fixed scenario/seed budget")


def verify_bundle(root: Path) -> None:
    root = root.resolve()
    index = json.loads((root / "EVIDENCE.json").read_text())
    for name, expected in index["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256_file(path) != expected:
            raise ValueError(f"screen artifact changed: {name}")
    saved = json.loads((root / "summary.json").read_text())
    rows = {
        name: json.loads((root / "val" / name / "episodes.json").read_text()) for name in POLICIES
    }
    for key, value in json.loads(json.dumps(decide(rows))).items():
        if saved[key] != value:
            raise ValueError(f"saved screen summary does not reproduce: {key}")


def verify_source(metadata: dict) -> None:
    if git_sha() != metadata["git_sha"] or source_fingerprint(RL) != metadata["source_fingerprint"]:
        raise ValueError("screen source changed during execution")
    if sha256_file(Path(metadata["registry"])) != metadata["registry_sha256"]:
        raise ValueError("actual registry changed during screen")


def worker(split: str, policy_name: str) -> None:
    if split not in {"train", "val"}:
        raise ValueError("duration screen forbids holdout")
    metadata = json.loads((RUN / "RUN.json").read_text())
    verify_source(metadata)
    scenarios = load_scenarios(split, subdir="train_v8" if split == "train" else "val_v10")
    if any(sc.split != split for sc in scenarios):
        raise ValueError("scenario split mismatch")
    policies = {
        "short": ev.always_block_principal,
        "long": ev.always_block_principal_long,
        "duration": duration_policy(),
        "tuned_rules": ev.rules_policy(metadata["rules_params"]),
    }
    if policy_name == "v6":
        checkpoint = Path(metadata["incumbent_checkpoint"])
        if sha256_file(checkpoint) != INCUMBENT:
            raise ValueError("actual v6 bytes changed")
        agent, _ = load_checkpoint(checkpoint)
        policy = ev.dqn_policy(agent)
    else:
        policy = policies[policy_name]
    out = ROOT / split / policy_name
    out.mkdir(parents=True)
    with gzip.GzipFile(out / "trajectories.jsonl.gz", "wb", mtime=0) as stream:

        def record(sc, seed, transitions) -> None:
            stream.write(
                (
                    json.dumps(
                        {
                            "policy": policy_name,
                            "scenario": sc.name,
                            "seed": seed,
                            "transitions": [t.model_dump(mode="json") for t in transitions],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
            )

        rows = ev.run_policy(
            policy,
            scenarios,
            live_app,
            episodes=8 if split == "train" else 16,
            action_space="live_v3",
            loop_overrides=OVERRIDES,
            on_episode=record,
        )
    validate_budget(rows, scenarios, 8 if split == "train" else 16)
    (out / "episodes.json").write_text(json.dumps([asdict(row) for row in rows], indent=2))
    verify_source(metadata)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--workers", type=int, default=5, choices=range(1, 6))
    parser.add_argument("--worker", choices=POLICIES)
    parser.add_argument("--split", choices=("train", "val"))
    args = parser.parse_args()
    os.chdir(RL)
    if args.verify_only:
        verify_bundle(ROOT)
        print("Stored screen evidence and validation summary verified; no policy execution.")
        return 0
    if args.worker:
        worker(args.split, args.worker)
        return 0
    if args.registry is None:
        parser.error("--registry required")
    if RUN.exists() or any((ROOT / split).exists() for split in ("train", "val")):
        raise ValueError("screen outputs exist; no overwrite or automatic retry")
    source = require_clean_source(RL)
    fingerprint = source_fingerprint(RL)
    checkpoint = Registry(args.registry).deployed_checkpoint()
    if sha256_file(checkpoint) != INCUMBENT:
        raise ValueError("screen is fixed against actual v6")
    old = RL / "results/live-retrain-v10/uniform/seed0/promotion_report.json"
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "git_sha": source,
        "source_fingerprint": fingerprint,
        "registry": str(args.registry.resolve()),
        "registry_sha256": sha256_file(args.registry),
        "incumbent_checkpoint": str(checkpoint.resolve()),
        "incumbent_sha256": INCUMBENT,
        "plan_sha256": sha256_file(ROOT / "PLAN.md"),
        "rules_report_sha256": sha256_file(old),
        "rules_params": json.loads(old.read_text())["rules_params"],
        "duration_params": DURATION_PARAMS,
        "workers": args.workers,
        "python": sys.version,
        "packages": {
            name: version(name) for name in ("torch", "numpy", "gymnasium", "fastapi", "pydantic")
        },
        "platform": platform.platform(),
        "command": [sys.executable, *sys.argv],
        "episodes_per_scenario": {"train": 8, "val": 16},
        "splits": {
            split: {s.name: s.config_hash() for s in load_scenarios(split, subdir=directory)}
            for split, directory in (("train", "train_v8"), ("val", "val_v10"))
        },
    }
    RUN.mkdir(parents=True)
    (RUN / "RUN.json").write_text(json.dumps(metadata, indent=2))
    (ROOT / "registry_snapshot.json").write_bytes(args.registry.read_bytes())
    if sha256_file(ROOT / "registry_snapshot.json") != metadata["registry_sha256"]:
        raise ValueError("registry changed while recording snapshot")
    errors = []

    def job(split: str, policy: str) -> None:
        verify_source(metadata)
        command = [
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "--worker",
            policy,
            "--split",
            split,
        ]
        with (RUN / f"{split}-{policy}.log").open("w") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"{split}/{policy} exited {result.returncode}")
        (ROOT / split / policy / "command.json").write_text(json.dumps(command, indent=2))
        print(f"{split}/{policy} complete", flush=True)

    for split in ("train", "val"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(job, split, policy): policy for policy in POLICIES}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as error:
                    errors.append({"split": split, "policy": futures[future], "error": repr(error)})
        if errors:
            break
    verify_source(metadata)
    metadata.update(finished_at=datetime.now(UTC).isoformat(), errors=errors)
    (ROOT / "RUN.json").write_text(json.dumps(metadata, indent=2))
    if errors:
        print(json.dumps(errors, indent=2))
        return 2
    results = {
        split: {
            name: json.loads((ROOT / split / name / "episodes.json").read_text())
            for name in POLICIES
        }
        for split in ("train", "val")
    }
    summary = decide(results["val"])
    summary["training"] = {
        name: ev.summarize([ev.EpisodeMetrics(**r) for r in rows])
        for name, rows in results["train"].items()
    }
    summary["training_by_scenario"] = {
        name: ev.summarize_by_scenario([ev.EpisodeMetrics(**r) for r in values])
        for name, values in results["train"].items()
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2))
    index = {
        str(p.relative_to(ROOT)): sha256_file(p)
        for p in sorted(ROOT.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "EVIDENCE.json"
    }
    (ROOT / "EVIDENCE.json").write_text(
        json.dumps({"files": index, "promotion_performed": False}, indent=2)
    )
    verify_bundle(ROOT)
    print("Screen complete; prepare v11:", summary["prepare_v11_preregistration"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
