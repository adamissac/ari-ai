"""Inference refuses inputs the policy was never trained on (no recommendation from garbage)."""

from pathlib import Path

import numpy as np
import pytest
import torch

from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.inference import MalformedPolicyInput, PolicyRunner, validate_policy_input

CHECKPOINT = (
    Path(__file__).resolve().parents[1] / "results/protocol-v1-retrain/checkpoints/ddqn_seed0.pt"
)
OBS = np.full(OBS_DIM, 0.25, dtype=np.float32)
MASK = np.ones(N_ACTIONS, dtype=bool)


@pytest.fixture(scope="module")
def runner() -> PolicyRunner:
    return PolicyRunner(CHECKPOINT)


def test_valid_input_is_served_and_float64_is_accepted(runner):
    rec = runner.recommend_from_observation(OBS.astype(np.float64), MASK)
    assert np.isfinite(rec.q_margin) and rec.q_margin >= 0
    assert all(np.isfinite(a.q_value) for a in rec.top_actions)


@pytest.mark.parametrize(
    ("obs", "mask", "match"),
    [
        (np.full(OBS_DIM, np.nan, dtype=np.float32), MASK, "NaN or infinite"),
        (np.full(OBS_DIM, np.inf, dtype=np.float32), MASK, "NaN or infinite"),
        (np.full(OBS_DIM, 50.0, dtype=np.float32), MASK, r"\[0, 1\]"),
        (np.full(OBS_DIM, -0.01, dtype=np.float32), MASK, r"\[0, 1\]"),
        (np.zeros(OBS_DIM - 1, dtype=np.float32), MASK, "observation shape"),
        (np.zeros((1, OBS_DIM), dtype=np.float32), MASK, "observation shape"),
        (np.zeros(OBS_DIM, dtype=np.int64), MASK, "not floating point"),
        (OBS, np.ones(5, dtype=bool), "action mask shape"),
        (OBS, np.ones(N_ACTIONS, dtype=np.int64), "not bool"),
        (OBS, np.full(N_ACTIONS, 0.5), "not bool"),
        (OBS, np.zeros(N_ACTIONS, dtype=bool), "no valid actions"),
    ],
)
def test_malformed_input_is_refused(runner, obs, mask, match):
    with pytest.raises(MalformedPolicyInput, match=match):
        runner.recommend_from_observation(obs, mask)


def test_one_nan_feature_is_enough_to_refuse():
    obs = OBS.copy()
    obs[7] = np.nan
    with pytest.raises(MalformedPolicyInput):
        validate_policy_input(obs, MASK, OBS_DIM, N_ACTIONS)


def test_non_finite_q_values_are_not_served(runner, monkeypatch):
    monkeypatch.setattr(runner.agent, "q_values", lambda obs: np.full(N_ACTIONS, np.nan))
    with pytest.raises(MalformedPolicyInput, match="non-finite Q-values"):
        runner.recommend_from_observation(OBS, MASK)


def test_checkpoint_with_wrong_action_count_is_refused(tmp_path):
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(), seed=0)
    path = tmp_path / "ddqn.pt"
    save_checkpoint(agent, path, seed=0, steps=1, train_configs={})
    loaded = torch.load(path, weights_only=True)
    loaded["manifest"]["n_actions"] = N_ACTIONS + 1
    torch.save(loaded, path)
    with pytest.raises(ValueError, match="n_actions"):
        load_checkpoint(path, verify=False)
