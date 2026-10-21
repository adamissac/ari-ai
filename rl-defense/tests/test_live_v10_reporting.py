"""Synthetic postprocessing and source-edit guards, never execute a v10 holdout."""

import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1] / "results/live-retrain-v10"


def module(name):
    spec = importlib.util.spec_from_file_location(f"v10_{name}_test", ROOT / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_source_pin_detects_uncommitted_edits_without_head_change(tmp_path, monkeypatch):
    source = module("source_pin")
    (tmp_path / "trainer.py").write_text("version = 1\n")
    (tmp_path / "config.yaml").write_text("budget: 150000\n")

    def git(command, **kwargs):
        return SimpleNamespace(
            stdout=str(tmp_path) if command[1] == "rev-parse" else b"trainer.py\0config.yaml\0"
        )

    monkeypatch.setattr(source.subprocess, "run", git)
    initial = source.source_fingerprint(tmp_path)
    (tmp_path / "trainer.py").write_text("version = 2\n")
    assert source.source_fingerprint(tmp_path) != initial
    (tmp_path / "trainer.py").write_text("version = 1\n")
    assert source.source_fingerprint(tmp_path) == initial
    (tmp_path / "config.yaml").write_text("budget: 1\n")
    assert source.source_fingerprint(tmp_path) != initial


def test_postprocess_covers_both_arms_and_keeps_worst_paired_traces(tmp_path, monkeypatch):
    report = module("postprocess")
    monkeypatch.setattr(report.evidence, "verify", lambda directory: {})
    monkeypatch.setattr(report, "load_checkpoint", lambda path: (object(), {}))

    def counts(agent, scenarios):
        group = {
            "quiet": {"windows": 89, "agree": 89, "platform_actions": {"noop": 89}},
            "flagged": {"windows": 51, "agree": 51, "platform_actions": {"block_principal": 51}},
        }
        return {"cases": {"no_findings": group, "bola_high": group}}

    monkeypatch.setattr(report.platform_check, "compare", counts)
    for arm in ("uniform", "balanced"):
        for seed in range(5):
            directory = tmp_path / arm / f"seed{seed}"
            directory.mkdir(parents=True)
            row = {"scenario": "fixture", "seed": 1, "steps": 1, "reward": 0.0}
            candidate = {**row, "reward": -float(seed + (10 if arm == "balanced" else 0))}
            (directory / "holdout_episodes.json").write_text(
                json.dumps({"candidate": [candidate], "deployed": [row]})
            )
            with gzip.open(directory / "holdout_trajectories.jsonl.gz", "wt") as stream:
                for policy in ("candidate", "deployed"):
                    stream.write(
                        json.dumps(
                            {
                                "scenario": "fixture",
                                "seed": 1,
                                "policy": policy,
                                "transitions": [{"saved": policy}],
                            }
                        )
                        + "\n"
                    )
    report.postprocess(tmp_path)
    failure = json.loads((tmp_path / "failure_case.json").read_text())
    assert (failure["arm"], failure["training_seed"]) == ("balanced", 4)
    assert failure["candidate_trajectory"] == [{"saved": "candidate"}]
    assert failure["deployed_trajectory"] == [{"saved": "deployed"}]
    checks = json.loads((tmp_path / "secondary_checks.json").read_text())
    assert set(checks) == {"uniform", "balanced"}
    assert all(c["all_seed_cases_pass_behavior_thresholds"] for c in checks.values())
    assert all(len(c["by_training_seed"]) == 5 for c in checks.values())
    (tmp_path / "failure_case.json").write_text("tampered")
    with pytest.raises(ValueError, match="study artifact changed"):
        report.verify(tmp_path)
