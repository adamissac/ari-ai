"""Execute the preregistered v9 five-seed lab study; never promote.

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
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from reference_pins import verify_files, verify_report

from rl_defense.checkpoint import git_sha, sha256_file
from rl_defense.live import evidence, study
from rl_defense.live.registry import Registry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=5, choices=range(1, 6))
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    source_sha = study.require_clean_source(root)
    source_digest = study.source_fingerprint(root)
    verify_files(root)
    result_root = Path("results/live-retrain-v9")
    run_root = Path("runs/live/retrain-v9")
    registry = Registry(args.registry)
    checkpoint = registry.deployed_checkpoint()
    baseline_sha = sha256_file(checkpoint)
    if baseline_sha != "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1":
        raise ValueError("v9 was preregistered against incumbent v6; registry changed")
    if any(
        (run_root / f"seed{s}").exists() or (result_root / f"seed{s}").exists() for s in study.SEEDS
    ):
        raise ValueError("study outputs already exist; refuse overwrite or implicit restart")
    run_root.mkdir(parents=True, exist_ok=True)
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "git_sha": source_sha,
        "source_fingerprint": source_digest,
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "workers": args.workers,
        "registry_sha256": sha256_file(args.registry),
        "incumbent_sha256": baseline_sha,
        "training_seeds": list(study.SEEDS),
        "preregistration_sha256": sha256_file(result_root / "PREREGISTRATION.md"),
    }
    (run_root / "RUN.json").write_text(json.dumps(metadata, indent=2))

    def run_seed(seed: int) -> dict:
        if git_sha() != source_sha or study.source_fingerprint(root) != source_digest:
            raise ValueError("source changed during study")
        # Read-only use of the real local registry. No fabricated approval or init.
        out, dest = run_root / f"seed{seed}", result_root / f"seed{seed}"
        out.mkdir()
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
            "val_v9",
            "--holdout-dir",
            "holdout_v9",
            "--holdout-episodes",
            "100",
            "--severity-context",
            "platform",
            "--random-baseline",
            "--record-trajectories",
            "--reference-checkpoint",
            "v7=results/live-retrain-v7/candidate_online.pt",
            "--reference-checkpoint",
            "v8=results/live-retrain-v8/candidate_online.pt",
            "--out",
            str(out),
            "--evidence-dir",
            str(dest),
        ]
        (out / "command.json").write_text(json.dumps(command, indent=2))
        with (out / "run.log").open("w") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        if completed.returncode:
            raise RuntimeError(
                f"seed {seed} failed ({completed.returncode}); inspect {out}/run.log"
            )
        if sha256_file(Registry(args.registry).deployed_checkpoint()) != baseline_sha:
            raise ValueError("incumbent changed during study; results cannot support promotion")
        if git_sha() != source_sha or study.source_fingerprint(root) != source_digest:
            raise ValueError("source changed during study")
        evidence.pack(dest, run=" ".join(command))
        evidence.verify(dest)
        report = json.loads((dest / "promotion_report.json").read_text())
        verify_report(report)
        return report

    errors, reports = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(run_seed, s): s for s in study.SEEDS}
        for job in concurrent.futures.as_completed(jobs):
            seed = jobs[job]
            try:
                report = job.result()
                reports.append(report)
                print(f"seed {seed}: {report['decision']}", flush=True)
            except Exception as exc:
                errors.append({"seed": seed, "error": str(exc)})
                print(f"seed {seed}: FAILED: {exc}", flush=True)
    metadata["finished_at"] = datetime.now(UTC).isoformat()
    metadata["errors"] = errors
    (result_root / "RUN.json").write_text(json.dumps(metadata, indent=2))
    if errors:
        return 2
    summary = study.aggregate(reports)
    (result_root / "study_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print("All five seeds complete. Evidence retained; no policy promoted.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
