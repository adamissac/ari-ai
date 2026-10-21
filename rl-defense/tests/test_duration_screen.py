"""Synthetic decision/counter tests; never execute validation or holdout scenarios."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.live.actions import (
    BLOCK_PRINCIPAL_ACTION,
    BLOCK_PRINCIPAL_LONG_ACTION,
    FEATURE_INDEX,
)

PATH = Path(__file__).parents[1] / "results/duration-screen/run_screen.py"
spec = importlib.util.spec_from_file_location("duration_screen_test", PATH)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


def episode(scenario, seed, blocked, compromised, attacks=100):
    return {
        "scenario": scenario,
        "seed": seed,
        "reward": -1.0,
        "steps": 30,
        "attack_requests": attacks,
        "compromised": compromised,
        "benign_requests": 100,
        "benign_blocked": blocked,
        "benign_requests_no_attack": 100,
        "benign_blocked_no_attack": blocked,
        "steps_no_attack": 10,
        "disruptive_steps_no_attack": int(blocked > 0),
        "nonnoop_actions": 2,
    }


def cohort(blocked, compromised):
    return [episode(name, seed, blocked, compromised) for name in ("a", "b") for seed in (1, 2)]


def test_existing_duration_rule_uses_observed_cost_and_no_broad_fallback():
    policy = screen.duration_policy()
    obs = np.full(55, 0.2, dtype=np.float32)
    mask = np.ones(25, dtype=bool)
    obs[FEATURE_INDEX["flagged_own_share"]] = 0
    assert policy(obs, mask) == BLOCK_PRINCIPAL_LONG_ACTION
    obs[FEATURE_INDEX["flagged_own_share"]] = 0.2
    assert policy(obs, mask) == BLOCK_PRINCIPAL_ACTION
    mask[BLOCK_PRINCIPAL_ACTION] = False
    assert policy(obs, mask) == NOOP_ACTION
    obs[:] = 1.0  # Even highest node alerts cannot enable the disabled broad fallback.
    assert policy(obs, mask) == NOOP_ACTION


@pytest.mark.parametrize("compromised,passed", [(0, True), (20, True), (30, False)])
def test_screen_requires_availability_improvement_without_compromise_increase(compromised, passed):
    rows = {name: cohort(10, 20) for name in screen.POLICIES}
    rows["duration"] = cohort(0, compromised)
    result = screen.decide(rows)
    assert result["prepare_v11_preregistration"] is passed
    assert result["promotion_performed"] is False
    assert result["duration_minus_v6"]["availability"]["mean"] == pytest.approx(0.1)


def test_compromise_rate_is_not_episode_count_average():
    left = [episode("a", 1, 0, 1, 1), episode("a", 2, 0, 0, 99)]
    right = [episode("a", 1, 0, 0, 1), episode("a", 2, 0, 0, 99)]
    result = screen.paired_ratios(left, right, "compromise_rate")
    assert result["mean"] == pytest.approx(0.01)
    assert result["paired_episodes"] == 2


def test_undefined_compromise_fails_instead_of_passing():
    rows = {name: [episode("a", 1, 0, 0, 0)] for name in screen.POLICIES}
    result = screen.decide(rows)
    assert result["prepare_v11_preregistration"] is False
    assert result["duration_minus_v6"]["compromise_rate"]["ci95"] is None


@pytest.mark.parametrize("fault", ["duplicate", "missing", "traffic"])
def test_paired_screen_refuses_broken_comparisons(fault):
    left, right = cohort(0, 0), cohort(0, 0)
    if fault == "duplicate":
        left.append(left[0])
    elif fault == "missing":
        left.pop()
    else:
        left[0]["attack_requests"] += 1
    with pytest.raises(ValueError):
        screen.paired_ratios(left, right, "availability")


def test_worker_forbids_holdout_before_loading_any_data():
    with pytest.raises(ValueError, match="forbids holdout"):
        screen.worker("holdout", "duration")


def test_fixed_screen_requires_all_policies_and_identical_episode_cohorts():
    rows = {name: cohort(0, 0) for name in screen.POLICIES}
    del rows["long"]
    with pytest.raises(ValueError, match="all five"):
        screen.decide(rows)
    rows["long"] = cohort(0, 0)[:-1]
    with pytest.raises(ValueError, match="cohorts"):
        screen.decide(rows)


def test_observed_budget_cannot_be_silently_truncated():
    from rl_defense.live import evaluate as ev
    from rl_defense.live.scenarios import LiveScenario

    scenario = LiveScenario(
        name="fixture",
        split="train",
        seed_start=0,
        episodes=2,
        horizon=5,
        schedule="always",
        attack_per_step=1,
        benign_per_step=1,
    )
    rows = [ev.EpisodeMetrics(**episode("fixture", seed, 0, 0)) for seed in (0, 1)]
    screen.validate_budget(rows, [scenario], 2)
    with pytest.raises(ValueError, match="budget"):
        screen.validate_budget(rows[:-1], [scenario], 2)


def test_completed_duration_screen_raw_evidence_and_failed_decision_are_preserved():
    import json

    path = PATH.with_name("finalize.py")
    spec = importlib.util.spec_from_file_location("duration_raw_verifier_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.verify(PATH.parent) == {
        "episodes": 520,
        "windows": 15600,
        "promotion_performed": False,
    }
    summary = json.loads(PATH.with_name("summary.json").read_text())
    assert summary["prepare_v11_preregistration"] is False
    assert summary["checks"]["availability_gain_ci_low_positive"] is False
    assert all(
        value
        for key, value in summary["checks"].items()
        if key != "availability_gain_ci_low_positive"
    )
