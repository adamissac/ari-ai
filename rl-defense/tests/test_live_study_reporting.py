"""Scientific reporting tests use synthetic files only; no held-out policy execution."""

from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from rl_defense.live import evidence

SCRIPTS = Path(__file__).resolve().parents[1] / "results/live-retrain-v9"


def _module(name: str):
    spec = importlib.util.spec_from_file_location(f"v9_{name}_fixture", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case():
    return {
        "quiet": {
            "windows": 100,
            "agree": 100,
            "platform_actions": {"noop": 95, "escalate_to_human": 5},
        },
        "flagged": {
            "windows": 100,
            "agree": 100,
            "platform_actions": {"block_principal": 90, "noop": 10},
        },
    }


def test_secondary_thresholds_are_inclusive_and_mapping_is_a_fraction():
    module = _module("finalize_study")
    result = module.secondary_checks({"0": {"cases": {"fixture": _case()}}})
    case = result["by_training_seed"]["0"]["fixture"]
    assert case["quiet_noop_fraction"] == 0.95
    assert case["flagged_principal_block_fraction"] == 0.9
    assert case["mapping_agreement"] == 1
    assert result["all_seed_cases_pass_behavior_thresholds"]
    below = _case()
    below["flagged"]["platform_actions"] = {"block_principal": 89, "noop": 11}
    assert not module.secondary_checks({"0": {"cases": {"fixture": below}}})[
        "all_seed_cases_pass_behavior_thresholds"
    ]


def test_secondary_empty_or_inconsistent_data_does_not_pass():
    module = _module("finalize_study")
    assert not module.secondary_checks({})["all_seed_cases_pass_behavior_thresholds"]
    assert not module.secondary_checks({"0": {"cases": {}}})[
        "all_seed_cases_pass_behavior_thresholds"
    ]
    case = _case()
    case["quiet"] = {"windows": 0, "agree": 0, "platform_actions": {}}
    result = module.secondary_checks({"0": {"cases": {"fixture": case}}})
    assert result["by_training_seed"]["0"]["fixture"]["quiet_noop_fraction"] is None
    assert not result["all_seed_cases_pass_behavior_thresholds"]
    case["quiet"]["windows"] = 1
    with pytest.raises(ValueError, match="action counts"):
        module.secondary_checks({"0": {"cases": {"fixture": case}}})


def test_finalizer_refuses_unfinished_or_changed_preregistration(tmp_path, monkeypatch):
    module = _module("finalize_study")
    monkeypatch.setattr(sys, "argv", ["finalize_study", str(tmp_path)])
    (tmp_path / "RUN.json").write_text(json.dumps({"errors": [], "finished_at": None}))
    with pytest.raises(ValueError, match="not complete"):
        module.main()
    (tmp_path / "RUN.json").write_text(
        json.dumps({"errors": [], "finished_at": "fixture", "preregistration_sha256": "different"})
    )
    (tmp_path / "PREREGISTRATION.md").write_text("synthetic fixture")
    with pytest.raises(ValueError, match="preregistration changed"):
        module.main()
    assert not (tmp_path / "STUDY_EVIDENCE.json").exists()


def test_finalizer_pins_metrics_and_traces_and_preserves_primary_verdict(tmp_path, monkeypatch):
    module = _module("finalize_study")
    (tmp_path / "PREREGISTRATION.md").write_text("synthetic preregistration")
    for filename in ("registry_snapshot.json", "environment.json", "observed_progress.json"):
        (tmp_path / filename).write_text(json.dumps({"fixture_only": True}))
    metadata = {
        "errors": [],
        "finished_at": "fixture",
        "git_sha": "fixture-source",
        "preregistration_sha256": module.digest(tmp_path / "PREREGISTRATION.md"),
        "registry_sha256": module.digest(tmp_path / "registry_snapshot.json"),
    }
    (tmp_path / "RUN.json").write_text(json.dumps(metadata))
    (tmp_path / "study_verdict.json").write_text(
        json.dumps({"primary_hypothesis_supported": False, "promotion_performed": False})
    )
    platform = {
        str(seed): {
            "cases": {name: copy.deepcopy(_case()) for name in ("no_findings", "bola_high")}
        }
        for seed in range(5)
    }
    (tmp_path / "platform_agreement.json").write_text(json.dumps(platform))

    def sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    for seed in range(5):
        root = tmp_path / f"seed{seed}"
        root.mkdir()
        checkpoint = f"synthetic checkpoint {seed}".encode()
        experiment = b"synthetic first line\nsynthetic second line\n"
        (root / "candidate_online.pt").write_bytes(checkpoint)
        (root / "experience.gz").write_bytes(gzip.compress(experiment))
        (root / "holdout_trajectories.jsonl.gz").write_bytes(
            gzip.compress(b"synthetic trajectory\n")
        )
        for filename in (
            "candidate_online.manifest.json",
            "holdout_episodes.json",
            "rules_tuning.json",
        ):
            (root / filename).write_text(json.dumps({"fixture_only": True}))
        report = {
            "artifacts": {
                "holdout_trajectories": {
                    "path": "holdout_trajectories.jsonl.gz",
                    "sha256": module.digest(root / "holdout_trajectories.jsonl.gz"),
                }
            }
        }
        (root / "promotion_report.json").write_text(json.dumps(report))
        index = {
            "schema": evidence.SCHEMA,
            "artifacts": {
                "checkpoint": {
                    "stored_as": "file",
                    "path": "candidate_online.pt",
                    "sha256": sha(checkpoint),
                },
                "experiment": {
                    "stored_as": "gzip",
                    "path": "experience.jsonl",
                    "stored_path": "experience.gz",
                    "sha256": sha(experiment),
                },
                "selected_experience": {
                    "stored_as": "prefix",
                    "of": "experiment",
                    "lines": 1,
                    "sha256": sha(b"synthetic first line\n"),
                },
            },
        }
        (root / "EVIDENCE.json").write_text(json.dumps(index))
    monkeypatch.setattr(sys, "argv", ["finalize_study", str(tmp_path)])
    module.main()
    verdict = json.loads((tmp_path / "study_verdict.json").read_text())
    assert verdict["primary_hypothesis_supported"] is False
    assert verdict["promotion_performed"] is False
    assert verdict["secondary_train_window_checks"]["all_seed_cases_pass_behavior_thresholds"]
    assert {"holdout_episodes", "holdout_trajectories", "checkpoint_manifest"} <= set(
        evidence.verify(tmp_path / "seed4")
    )
    manifest = json.loads((tmp_path / "STUDY_EVIDENCE.json").read_text())
    assert manifest["files"]["seed4/EVIDENCE.json"] == module.digest(
        tmp_path / "seed4/EVIDENCE.json"
    )
    monkeypatch.setattr(sys, "argv", ["finalize_study", str(tmp_path), "--verify-only"])
    before = (tmp_path / "STUDY_EVIDENCE.json").read_bytes()
    module.main()
    assert (tmp_path / "STUDY_EVIDENCE.json").read_bytes() == before
    (tmp_path / "seed4/holdout_episodes.json").write_text("changed")
    with pytest.raises(ValueError, match="artifact digest mismatch"):
        module.main()
    with pytest.raises(ValueError, match="holdout_episodes"):
        evidence.verify(tmp_path / "seed4")


def test_read_only_verifier_rejects_paths_outside_the_evidence_directory(tmp_path, monkeypatch):
    module = _module("finalize_study")
    (tmp_path / "STUDY_EVIDENCE.json").write_text(
        json.dumps(
            {
                "schema": "live-study-evidence/0.1",
                "files": {"../outside": "0" * 64},
            }
        )
    )
    monkeypatch.setattr(sys, "argv", ["finalize_study", str(tmp_path), "--verify-only"])
    with pytest.raises(ValueError, match="path escapes"):
        module.main()


def test_seed_index_cannot_read_files_outside_its_directory(tmp_path):
    module = _module("finalize_study")
    (tmp_path / "EVIDENCE.json").write_text(
        json.dumps(
            {
                "schema": evidence.SCHEMA,
                "artifacts": {
                    "escape": {"stored_as": "file", "path": "../outside", "sha256": "0" * 64}
                },
            }
        )
    )
    with pytest.raises(ValueError, match="path escapes"):
        module.verify_seed(tmp_path)
