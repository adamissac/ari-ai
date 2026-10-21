"""Execute the preregistered v10 five-seed lab study; never promote.

Run from rl-defense after committing/pushing PREREGISTRATION.md. All five seeds are
required. A failed seed fails the study; rerunning a seed is not automatic. Existing
seed directories are refused so exposed holdout evidence cannot be overwritten.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from source_pin import source_fingerprint

from rl_defense.checkpoint import git_sha, load_checkpoint, sha256_file
from rl_defense.live import evidence, study
from rl_defense.live.registry import Registry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=5, choices=range(1, 6))
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    result_root = Path("results/live-retrain-v10")
    run_root = Path("runs/live/retrain-v10")
    registry = Registry(args.registry)
    checkpoint = registry.deployed_checkpoint()
    baseline_sha = sha256_file(checkpoint)
    if baseline_sha != "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1":
        raise ValueError("v10 was preregistered against incumbent v6; registry changed")
    if any(
        (run_root / arm / f"seed{s}").exists() or (result_root / arm / f"seed{s}").exists()
        for arm in ("uniform", "balanced")
        for s in study.SEEDS
    ):
        raise ValueError("study outputs already exist; refuse overwrite or implicit restart")
    source_sha = study.require_clean_source(root)
    source_digest = source_fingerprint(root)
    refs = {"v8": Path("results/live-retrain-v8/candidate_online.pt")}
    refs.update(
        {
            f"v9_seed{s}": Path(f"results/live-retrain-v9/seed{s}/candidate_online.pt")
            for s in study.SEEDS
        }
    )
    pins = {}
    for name, path in refs.items():
        _, manifest = load_checkpoint(path)
        pins[name] = manifest["checkpoint_sha256"]
    if pins["v8"] != "ec8b5042fd56d2f75c6791b89152b57f4a6870c3656321b9f554056b4c0fc528":
        raise ValueError("fixed v8 reference changed")
    # V9 identity is pinned by its committed study bundle, not a replaceable sidecar.
    bundle = json.loads(Path("results/live-retrain-v9/STUDY_EVIDENCE.json").read_text())
    for seed in study.SEEDS:
        if pins[f"v9_seed{seed}"] != bundle["files"][f"seed{seed}/candidate_online.pt"]:
            raise ValueError("fixed v9 reference changed")
    run_root.mkdir(parents=True, exist_ok=True)
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "git_sha": source_sha,
        "source_fingerprint": source_digest,
        "python": sys.version,
        "packages": {
            name: version(name)
            for name in (
                "torch",
                "numpy",
                "scipy",
                "gymnasium",
                "pydantic",
                "fastapi",
                "httpx",
                "PyYAML",
            )
        },
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "workers": args.workers,
        "reference_sha256": pins,
        "registry_sha256": sha256_file(args.registry),
        "incumbent_sha256": baseline_sha,
        "training_seeds": list(study.SEEDS),
        "preregistration_sha256": sha256_file(result_root / "PREREGISTRATION.md"),
    }
    shutil.copyfile(args.registry, result_root / "registry_snapshot.json")
    if sha256_file(result_root / "registry_snapshot.json") != metadata["registry_sha256"]:
        raise ValueError("registry changed while capturing launch metadata")
    (run_root / "RUN.json").write_text(json.dumps(metadata, indent=2))

    def run_seed(arm: str, seed: int) -> dict:
        if git_sha() != metadata["git_sha"] or source_fingerprint(root) != source_digest:
            raise ValueError("training source changed during study")
        # Read-only use of the real local registry. No fabricated approval or init.
        out, dest = run_root / arm / f"seed{seed}", result_root / arm / f"seed{seed}"
        out.mkdir(parents=True)
        command = [
            sys.executable,
            "-m",
            "rl_defense.live.online",
            "--registry",
            str(args.registry.resolve()),
            "--rules-episodes",
            "2",
            "--seed",
            str(seed),
            "--train-dir",
            "train_v8",
            "--val-dir",
            "val_v10",
            "--holdout-dir",
            "holdout_v10",
            "--holdout-episodes",
            "100",
            "--severity-context",
            "platform",
            "--random-baseline",
            "--record-trajectories",
            "--reference-checkpoint",
            "v8=results/live-retrain-v8/candidate_online.pt",
            "--reference-checkpoint",
            f"v9=results/live-retrain-v9/seed{seed}/candidate_online.pt",
            "--out",
            str(out),
            "--evidence-dir",
            str(dest),
        ]
        if arm == "balanced":
            command.append("--balance-demo-actions")
        (out / "command.json").write_text(json.dumps(command, indent=2))
        with (out / "run.log").open("w") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        if completed.returncode:
            raise RuntimeError(
                f"seed {seed} failed ({completed.returncode}); inspect {out}/run.log"
            )
        if sha256_file(Registry(args.registry).deployed_checkpoint()) != baseline_sha:
            raise ValueError("incumbent changed during study; results cannot support promotion")
        if git_sha() != metadata["git_sha"] or source_fingerprint(root) != source_digest:
            raise ValueError("training source changed during study")
        evidence.pack(dest, run=" ".join(command))
        evidence.verify(dest)
        report = json.loads((dest / "promotion_report.json").read_text())
        expected = {"v8": pins["v8"], "v9": pins[f"v9_seed{seed}"]}
        if {r["name"]: r["checkpoint_sha256"] for r in report["references"]} != expected:
            raise ValueError("reference identity changed during run")
        for filename in ("run.log", "command.json"):
            shutil.copyfile(out / filename, dest / filename)
        return report

    errors, reports = [], {"uniform": [], "balanced": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(run_seed, arm, s): (arm, s) for arm in reports for s in study.SEEDS}
        for job in concurrent.futures.as_completed(jobs):
            arm, seed = jobs[job]
            try:
                report = job.result()
                reports[arm].append(report)
                print(f"{arm} seed {seed}: {report['decision']}", flush=True)
            except Exception as exc:
                errors.append({"arm": arm, "seed": seed, "error": str(exc)})
                print(f"{arm} seed {seed}: FAILED: {exc}", flush=True)
    metadata["finished_at"] = datetime.now(UTC).isoformat()
    metadata["errors"] = errors
    (result_root / "RUN.json").write_text(json.dumps(metadata, indent=2))
    if errors:
        return 2
    from summarize import summarize

    summary = summarize(reports)
    (result_root / "study_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    from postprocess import postprocess

    postprocess(result_root)
    print("Both arms / all ten runs complete. Evidence retained; no policy promoted.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
