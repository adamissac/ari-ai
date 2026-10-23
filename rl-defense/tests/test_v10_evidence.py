"""Validate the complete saved two-arm study without executing a held-out policy."""

import importlib.util
import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint, sha256_file

ROOT = Path(__file__).resolve().parents[1] / "results/live-retrain-v10"


def _module(name):
    spec = importlib.util.spec_from_file_location(f"v10_saved_{name}", ROOT / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_complete_saved_bundle_verifies_without_policy_execution():
    _module("postprocess").verify(ROOT)


def test_all_checkpoints_and_episode_budgets_match_the_frozen_run():
    run = json.loads((ROOT / "RUN.json").read_text())
    assert run["errors"] == []
    assert sha256_file(ROOT / "PREREGISTRATION.md") == run["preregistration_sha256"]
    assert sha256_file(ROOT / "registry_snapshot.json") == run["registry_sha256"]
    episodes = 0
    for arm in ("uniform", "balanced"):
        for seed in range(5):
            directory = ROOT / arm / f"seed{seed}"
            report = json.loads((directory / "promotion_report.json").read_text())
            _, manifest = load_checkpoint(directory / "candidate_online.pt")
            assert manifest["git_sha"] == report["git_sha"] == run["git_sha"]
            assert manifest["steps"] == report["online"]["selected_env_step"]
            assert manifest["lineage"]["transitions"] == 4200 + manifest["steps"]
            assert manifest["online"]["env_steps"] == 150000
            assert report["balance_demo_actions"] == (arm == "balanced")
            rows = json.loads((directory / "holdout_episodes.json").read_text())
            assert len(rows) == 11
            assert all(len(values) == 300 for values in rows.values())
            episodes += sum(map(len, rows.values()))
    assert episodes == 33000


def test_saved_summary_reproduces_and_does_not_override_failed_gates():
    reports = {
        arm: [
            json.loads((ROOT / arm / f"seed{seed}" / "promotion_report.json").read_text())
            for seed in range(5)
        ]
        for arm in ("uniform", "balanced")
    }
    summary = _module("summarize").summarize(reports)
    assert json.loads(json.dumps(summary)) == json.loads((ROOT / "study_summary.json").read_text())
    assert summary["balanced_minus_uniform"]["reward"]["ci95"][0] > 0
    assert summary["arms"]["balanced"]["candidate_minus_incumbent"]["reward"]["ci95"][0] > 0
    assert summary["primary_hypothesis_supported"] is False
    assert summary["promotion_performed"] is False
    assert all(r["decision"] == "reject" for rows in reports.values() for r in rows)
