"""The learning check compares against a real untrained control and reports what it measured."""

import json

import torch

from rl_defense.agents.ddqn import DDQNConfig
from rl_defense.baselines import ThresholdParams
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.learning_check import (
    POLICIES,
    action_agreement,
    param_distance,
    run_check,
    untrained_agent,
)
from rl_defense.train import train

TRAIN = load_configs(default_config_paths("train"))
EVAL = load_configs(default_config_paths("eval"))
SMALL = DDQNConfig(
    learning_starts=200, buffer_size=5_000, eps_decay_steps=2_000, target_update_interval=200
)
RULES = ThresholdParams(0.25, 0.3, 0.1)


def test_untrained_control_is_exactly_the_network_training_starts_from(tmp_path):
    # learning_starts beyond the run: train() performs no gradient update at all
    cfg = SMALL.model_copy(update={"learning_starts": 10_000})
    manifest = train(TRAIN, seed=3, steps=300, run_dir=tmp_path, ddqn_config=cfg)
    assert manifest["gradient_updates"] == 0
    never_updated, _ = load_checkpoint(tmp_path / "ddqn_seed3.pt")
    control = untrained_agent(cfg, seed=3)
    for a, b in zip(never_updated.online.parameters(), control.online.parameters(), strict=True):
        assert torch.equal(a, b)
    assert param_distance(never_updated, control) == 0.0
    assert action_agreement(never_updated, control, EVAL[:1], range(1000, 1001)) == 1.0


def test_check_reports_measured_change_and_all_policies(tmp_path):
    summary = run_check(
        TRAIN,
        EVAL,
        seeds=[0],
        steps=3_000,
        episodes=2,
        out_dir=tmp_path,
        config=SMALL,
        adversary_scale=None,
        threshold_params=RULES,
    )
    assert set(summary["policies"]) == set(POLICIES)
    seed0 = summary["per_training_seed"]["0"]
    assert seed0["gradient_updates"] == 2_800
    assert seed0["param_abs_change_from_init"] > 0.0
    assert seed0["greedy_action_agreement_with_untrained"] < 1.0
    # every comparison is paired on the same held-out episodes
    assert {p["episodes"] for p in summary["paired_return"].values()} == {2 * len(EVAL)}
    for p in summary["paired_return"].values():
        assert not (p["trained_better"] and p["trained_worse"])
    assert summary["threshold_rules"]["tuned_on"] == "not tuned (supplied)"
    on_disk = json.loads((tmp_path / "learning_check.json").read_text())
    assert on_disk["policies"] == json.loads(json.dumps(summary["policies"]))
    assert "trained" in (tmp_path / "learning_check.md").read_text()


def test_check_is_reproducible(tmp_path):
    kwargs = dict(seeds=[1], steps=1_500, episodes=1, config=SMALL, threshold_params=RULES)
    a = run_check(TRAIN, EVAL, out_dir=tmp_path / "a", **kwargs)
    b = run_check(TRAIN, EVAL, out_dir=tmp_path / "b", **kwargs)
    # compared as JSON text: a policy with no disruptive action reports NaN, and NaN != NaN
    assert json.dumps(a["policies"]) == json.dumps(b["policies"])
    assert json.dumps(a["paired_return"]) == json.dumps(b["paired_return"])
