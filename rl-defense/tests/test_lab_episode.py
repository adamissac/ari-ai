"""An on-demand lab episode is the real simulator and the real checkpoint, step for step."""

import json

import numpy as np
import pytest

from rl_defense.baselines import NoopPolicy, RandomValidPolicy, ThresholdRulesPolicy
from rl_defense.envs import DefenseSimEnv
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM, REWARD_COMPONENTS
from rl_defense.evaluate import DDQNPolicy, run_episode
from rl_defense.inference import PolicyRunner
from rl_defense.lab_episode import (
    DEFAULT_CHECKPOINT,
    POLICY_KINDS,
    LabEpisode,
    committed_threshold_params,
    run_lab_episode,
    scenarios,
)

SCENARIOS = scenarios()
SCENARIO = SCENARIOS["eval_aggressive_noisy"]
SEED = 1003


@pytest.fixture(scope="module")
def episodes() -> dict[str, LabEpisode]:
    return {kind: run_lab_episode(SCENARIO, kind, SEED) for kind in POLICY_KINDS}


def test_all_committed_scenarios_are_available():
    assert {c.split for c in SCENARIOS.values()} == {"train", "eval"}
    assert len(SCENARIOS) == 6


@pytest.mark.parametrize("kind", POLICY_KINDS)
def test_episode_matches_the_evaluation_code_exactly(episodes, kind):
    reference = {
        "ddqn_trained": lambda: DDQNPolicy(DEFAULT_CHECKPOINT),
        "random": lambda: RandomValidPolicy(seed=0),
        "noop": NoopPolicy,
        "threshold_rules": lambda: ThresholdRulesPolicy(committed_threshold_params()),
    }.get(kind)
    ep = episodes[kind]
    assert ep.summary.total_return == pytest.approx(sum(s.reward for s in ep.steps))
    if reference is None:
        return  # the untrained control has no counterpart in evaluate.py
    row, _ = run_episode(DefenseSimEnv(SCENARIO), reference(), SEED)
    assert ep.summary.total_return == pytest.approx(row["return"], abs=1e-9)
    assert ep.summary.steps == row["length"]
    assert ep.summary.impact_nodes == row["impact_nodes"]


@pytest.mark.parametrize("kind", POLICY_KINDS)
def test_every_step_is_well_formed_and_respects_the_mask(episodes, kind):
    ep = episodes[kind]
    assert len(ep.feature_names) == OBS_DIM and len(ep.action_labels) == N_ACTIONS
    for i, s in enumerate(ep.steps):
        assert s.t == i
        assert len(s.observation) == OBS_DIM and len(s.action_mask) == N_ACTIONS
        assert all(0.0 <= x <= 1.0 for x in s.observation)
        assert s.action_mask[s.action] and s.action_label == ep.action_labels[s.action]
        assert set(s.reward_components) == set(REWARD_COMPONENTS)
        assert s.reward == pytest.approx(sum(s.reward_components.values()), abs=1e-9)
        assert s.reward_components["invalid_action"] == 0.0
    assert [s.terminated or s.truncated for s in ep.steps[:-1]] == [False] * (len(ep.steps) - 1)
    assert ep.steps[-1].terminated or ep.steps[-1].truncated
    assert ep.summary.terminated == ep.steps[-1].terminated


def test_transitions_chain_and_observations_are_decision_time(episodes):
    """Step t+1's observation is what the simulator returned from step t."""
    ep = episodes["ddqn_trained"]
    env = DefenseSimEnv(SCENARIO)
    obs, info = env.reset(seed=SEED)
    for s in ep.steps:
        np.testing.assert_array_equal(np.asarray(s.observation, dtype=np.float32), obs)
        np.testing.assert_array_equal(s.action_mask, info["action_mask"])
        obs, reward, *_, info = env.step(s.action)
        assert s.reward == pytest.approx(reward)
    np.testing.assert_array_equal(np.asarray(ep.final_observation, dtype=np.float32), obs)


def test_trained_actions_are_the_served_policy_actions(episodes):
    """The lab's learned decisions come from the same Q-network the inference API serves."""
    runner = PolicyRunner(DEFAULT_CHECKPOINT)
    ep = episodes["ddqn_trained"]
    assert ep.policy.source == "learned_checkpoint"
    assert ep.policy.checkpoint_sha256 == runner.checkpoint_sha256
    assert ep.policy.policy_version == runner.policy_version
    assert ep.policy.gradient_updates > 0
    for s in ep.steps[::7]:
        obs = np.asarray(s.observation, dtype=np.float32)
        mask = np.asarray(s.action_mask)
        rec = runner.recommend_from_observation(obs, mask)
        served = rec.action if rec.node is None else f"{rec.action}:{rec.node}"
        assert served == s.action_label
        np.testing.assert_allclose(s.q_values, runner.agent.q_values(obs), rtol=0, atol=0)
        valid_q = [q for q, ok in zip(s.q_values, s.action_mask, strict=True) if ok]
        assert s.q_values[s.action] == max(valid_q)  # this checkpoint has no abstention margin


def test_untrained_control_is_labelled_and_behaves_differently(episodes):
    trained, untrained = episodes["ddqn_trained"], episodes["ddqn_untrained"]
    assert untrained.policy.source == "untrained_network"
    assert untrained.policy.gradient_updates == 0 and untrained.policy.checkpoint_sha256 is None
    assert untrained.steps[0].observation == trained.steps[0].observation  # same episode
    assert untrained.steps[0].q_values != trained.steps[0].q_values
    assert [s.action for s in untrained.steps] != [s.action for s in trained.steps]


def test_baselines_carry_no_q_values_or_checkpoint(episodes):
    for kind in ("random", "noop", "threshold_rules"):
        ep = episodes[kind]
        assert ep.policy.source == "scripted_baseline" and ep.policy.checkpoint_sha256 is None
        assert all(s.q_values is None for s in ep.steps)
    assert set(episodes["noop"].summary.action_counts) == {"noop"}


def test_episode_is_deterministic_and_seed_sensitive(episodes):
    again = run_lab_episode(SCENARIO, "ddqn_trained", SEED)
    assert again.model_dump_json() == episodes["ddqn_trained"].model_dump_json()
    other = run_lab_episode(SCENARIO, "ddqn_trained", SEED + 1)
    assert other.steps[5].observation != episodes["ddqn_trained"].steps[5].observation


def test_json_round_trip_and_max_steps(episodes):
    ep = episodes["threshold_rules"]
    assert LabEpisode.model_validate(json.loads(ep.model_dump_json())) == ep
    short = run_lab_episode(SCENARIO, "threshold_rules", SEED, max_steps=4)
    assert len(short.steps) == 4 and short.steps == ep.steps[:4]
    assert not short.summary.terminated


def test_swapped_checkpoint_and_bad_arguments_are_refused(tmp_path):
    with pytest.raises(ValueError, match="hash mismatch"):
        run_lab_episode(SCENARIO, "ddqn_trained", SEED, expected_sha256="0" * 64)
    with pytest.raises(ValueError, match="episode_seed"):
        run_lab_episode(SCENARIO, "noop", -1)
    with pytest.raises(ValueError, match="max_steps"):
        run_lab_episode(SCENARIO, "noop", SEED, max_steps=0)
    with pytest.raises(ValueError, match="unknown policy kind"):
        run_lab_episode(SCENARIO, "ppo", SEED)  # type: ignore[arg-type]
