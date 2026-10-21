"""Read-only analysis of completed v9 runs; never executes a held-out policy."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

BLOCKS = {"block_principal", "block_principal_long", "block_top_principal_long"}


def secondary_checks(checks: dict) -> dict:
    output = {}
    for seed, record in checks.items():
        output[seed] = {}
        for case, stats in record["cases"].items():
            quiet, flagged = stats["quiet"], stats["flagged"]
            for group in (quiet, flagged):
                if sum(group["platform_actions"].values()) != group["windows"]:
                    raise ValueError("action counts do not match checked windows")
            q = (
                quiet["platform_actions"].get("noop", 0) / quiet["windows"]
                if quiet["windows"]
                else None
            )
            b = (
                sum(flagged["platform_actions"].get(a, 0) for a in BLOCKS) / flagged["windows"]
                if flagged["windows"]
                else None
            )
            output[seed][case] = {
                "quiet_noop_fraction": q,
                "flagged_principal_block_fraction": b,
                "quiet_noop_passed": q is not None and q >= 0.95,
                "flagged_principal_block_passed": b is not None and b >= 0.90,
                "mapping_agreement": (quiet["agree"] + flagged["agree"])
                / (quiet["windows"] + flagged["windows"])
                if quiet["windows"] + flagged["windows"]
                else None,
                "mapping_agree_windows": quiet["agree"] + flagged["agree"],
                "checked_windows": quiet["windows"] + flagged["windows"],
            }
    return {
        "scope": "secondary train-window diagnostics, not a held-out promotion gate",
        "by_training_seed": output,
        "all_seed_cases_pass_behavior_thresholds": bool(output)
        and all(bool(cases) for cases in output.values())
        and all(
            c["quiet_noop_passed"] and c["flagged_principal_block_passed"]
            for cases in output.values()
            for c in cases.values()
        ),
    }


def digest(path: Path, *, gzip_contents: bool = False) -> str:
    h = hashlib.sha256()
    with gzip.open(path, "rb") if gzip_contents else path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def verify_seed(directory: Path) -> None:
    from rl_defense.live import evidence

    base = directory.resolve()
    index = evidence.load_index(base)
    for artifact in index["artifacts"].values():
        for field in ("path", "stored_path"):
            if field in artifact and not (base / artifact[field]).resolve().is_relative_to(base):
                raise ValueError("artifact path escapes the seed evidence directory")
    evidence.verify(base)


def main() -> None:
    from rl_defense.live import evidence

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--registry-snapshot", type=Path)
    ap.add_argument("--environment", type=Path)
    ap.add_argument("--observed-progress", type=Path)
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    if args.verify_only:
        manifest = json.loads((root / "STUDY_EVIDENCE.json").read_text())
        if manifest.get("schema") != "live-study-evidence/0.1":
            raise ValueError("unknown study evidence schema")
        for relative, expected in manifest["files"].items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError("artifact path escapes the study directory")
            if digest(path) != expected:
                raise ValueError(f"artifact digest mismatch: {relative}")
        for seed in range(5):
            directory = root / f"seed{seed}"
            if not directory.resolve().is_relative_to(root):
                raise ValueError("seed directory escapes the study directory")
            verify_seed(directory)
        print(f"Verified {len(manifest['files'])} saved artifacts and all five evidence indices.")
        return
    metadata = json.loads((root / "RUN.json").read_text())
    if metadata.get("errors") or not metadata.get("finished_at"):
        raise ValueError("study is not complete")
    if digest(root / "PREREGISTRATION.md") != metadata["preregistration_sha256"]:
        raise ValueError("preregistration changed")
    platform = json.loads((root / "platform_agreement.json").read_text())
    if set(platform) != {str(s) for s in range(5)} or any(
        set(c["cases"]) != {"no_findings", "bola_high"} for c in platform.values()
    ):
        raise ValueError("incomplete platform diagnostic cohort")
    checks = secondary_checks(platform)
    verdict = json.loads((root / "study_verdict.json").read_text())
    verdict["secondary_train_window_checks"] = checks
    (root / "study_verdict.json").write_text(json.dumps(verdict, indent=2))
    restored_files: set[Path] = set()
    for seed in range(5):
        directory = root / f"seed{seed}"
        report = json.loads((directory / "promotion_report.json").read_text())
        trajectory = report["artifacts"]["holdout_trajectories"]
        if digest(directory / trajectory["path"]) != trajectory["sha256"]:
            raise ValueError(f"seed{seed}: trajectory digest mismatch")
        index = evidence.load_index(directory)
        for name, filename in {
            "holdout_episodes": "holdout_episodes.json",
            "promotion_report": "promotion_report.json",
            "checkpoint_manifest": "candidate_online.manifest.json",
            "rules_tuning": "rules_tuning.json",
        }.items():
            index["artifacts"][name] = {
                "path": filename,
                "stored_as": "file",
                "sha256": digest(directory / filename),
            }
        index["artifacts"]["holdout_trajectories"] = {
            "path": str(Path(trajectory["path"]).with_suffix("")),
            "stored_as": "gzip",
            "stored_path": trajectory["path"],
            "sha256": digest(directory / trajectory["path"], gzip_contents=True),
            "note": "Logical JSONL digest; the promotion report separately pins the gzip container bytes.",
        }
        for artifact in index["artifacts"].values():
            if artifact["stored_as"] in {"gzip", "prefix"} and "path" in artifact:
                restored_files.add((directory / artifact["path"]).resolve())
        (directory / "EVIDENCE.json").write_text(json.dumps(index, indent=2) + "\n")
        verify_seed(directory)
    snapshots = {
        "registry_snapshot.json": args.registry_snapshot or root / "registry_snapshot.json",
        "environment.json": args.environment or root / "environment.json",
        "observed_progress.json": args.observed_progress or root / "observed_progress.json",
    }
    if digest(snapshots["registry_snapshot.json"]) != metadata["registry_sha256"]:
        raise ValueError("registry snapshot does not match the launch digest")
    for filename, source in snapshots.items():
        if source.resolve() != (root / filename).resolve():
            shutil.copyfile(source, root / filename)
    files = {}
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.name != "STUDY_EVIDENCE.json"
            and path.resolve() not in restored_files
        ):
            if not path.resolve().is_relative_to(root):
                raise ValueError("artifact path escapes the study directory")
            files[str(path.relative_to(root))] = digest(path)
    (root / "STUDY_EVIDENCE.json").write_text(
        json.dumps(
            {
                "schema": "live-study-evidence/0.1",
                "training_source_commit": metadata["git_sha"],
                "files": files,
                "promotion_performed": False,
            },
            indent=2,
        )
    )
    print("Final evidence and preregistered secondary checks verified; no held-out execution.")


if __name__ == "__main__":
    main()
