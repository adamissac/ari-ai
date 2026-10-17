"""Optional agent variants: vanilla-DQN ablation, dueling head, n-step returns."""

import numpy as np
import pytest
import torch

from rl_defense.agents.ddqn import (
    DDQNAgent,
    DDQNConfig,
    DuelingQNetwork,
    NStepAccumulator,
    ReplayBuffer,
    double_dqn_targets,
    dqn_targets,
)
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.train import train
from tests.test_ddqn import FixedQ, batch


def test_vanilla_dqn_target_uses_target_max():
    online = FixedQ([1.0, 5.0, 3.0])
    target = FixedQ([10.0, 2.0, 7.0])
    b = batch([1.0], [0.0], [[True, True, True]])
    assert dqn_targets(target, b, 0.9).item() == pytest.approx(1.0 + 0.9 * 10.0)
    assert double_dqn_targets(online, target, b, 0.9).item() == pytest.approx(1.0 + 0.9 * 2.0)


def test_vanilla_dqn_target_respects_mask():
    target = FixedQ([10.0, 2.0, 7.0])
    b = batch([0.0], [0.0], [[False, True, True]])
    assert dqn_targets(target, b, 1.0).item() == pytest.approx(7.0)


def test_per_transition_discount_overrides_gamma():
    online, target = FixedQ([1.0, 5.0]), FixedQ([3.0, 4.0])
    b = batch([1.0, 1.0], [0.0, 0.0], [[True, True], [True, True]])
    b.discounts = torch.tensor([0.5, 0.25])
    y = double_dqn_targets(online, target, b, gamma=0.99)
    assert y.tolist() == pytest.approx([1.0 + 0.5 * 4.0, 1.0 + 0.25 * 4.0])


def test_dueling_network_combines_value_and_centered_advantage():
    net = DuelingQNetwork(4, 3, (8,))
    obs = torch.rand(5, 4)
    q = net(obs)
    z = net.trunk(obs)
    adv = net.advantage(z)
    expected = net.value(z) + adv - adv.mean(-1, keepdim=True)
    assert torch.allclose(q, expected)
    assert torch.allclose(q.mean(-1, keepdim=True), net.value(z), atol=1e-6)


def test_nstep_accumulator_returns_and_discounts():
    acc = NStepAccumulator(n=3, gamma=0.5)
    mask = np.ones(2, dtype=bool)
    out = []
    for t in range(4):
        out += acc.push(f"s{t}", t, 1.0, f"s{t + 1}", False, False, mask)
    assert [o[0] for o in out] == ["s0", "s1"]
    assert out[0][2] == pytest.approx(1 + 0.5 + 0.25) and out[0][3] == "s3" and out[0][6] == 0.125
    flushed = acc.push("s4", 4, 2.0, "s5", True, False, mask)  # termination flushes window
    assert [f[0] for f in flushed] == ["s2", "s3", "s4"]
    assert all(f[4] is True for f in flushed)
    assert flushed[-1][2] == pytest.approx(2.0) and flushed[-1][6] == 0.5


def test_nstep_truncation_bootstraps():
    acc = NStepAccumulator(n=5, gamma=0.9)
    acc.push("a", 0, 1.0, "b", False, False, np.ones(1, dtype=bool))
    out = acc.push("b", 0, 1.0, "c", False, True, np.ones(1, dtype=bool))
    assert len(out) == 2 and not out[0][4]
    assert out[0][6] == pytest.approx(0.81) and out[1][6] == pytest.approx(0.9)


@pytest.mark.parametrize(
    "cfg",
    [DDQNConfig(double=False), DDQNConfig(dueling=True), DDQNConfig(n_step=3)],
    ids=["dqn", "dueling", "nstep3"],
)
def test_variants_update_and_checkpoint(cfg, tmp_path):
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, cfg, seed=0)
    buf = ReplayBuffer(500, OBS_DIM, N_ACTIONS, seed=0)
    rng = np.random.default_rng(0)
    for _ in range(100):
        buf.add(
            rng.random(OBS_DIM),
            rng.integers(N_ACTIONS),
            rng.normal(),
            rng.random(OBS_DIM),
            False,
            np.ones(N_ACTIONS, dtype=bool),
            0.9,
        )
    assert agent.update(buf.sample(32))["grad_norm"] > 0
    save_checkpoint(agent, tmp_path / "ddqn_seed0.pt", seed=0, steps=1, train_configs={})
    loaded, _ = load_checkpoint(tmp_path / "ddqn_seed0.pt")
    obs = torch.rand(3, OBS_DIM)
    assert torch.equal(loaded.online(obs), agent.online(obs))


def test_domain_randomization_records_sampled_factors(tmp_path):
    cfgs = load_configs(default_config_paths("train"))
    small = DDQNConfig(learning_starts=100, buffer_size=2000, eps_decay_steps=500)
    m = train(
        cfgs,
        seed=3,
        steps=1500,
        run_dir=tmp_path / "dr",
        ddqn_config=small,
        adversary_scale=(0.5, 2.5),
    )
    assert m["adversary_scale"] == [0.5, 2.5]
    s = m["adversary_scale_sampled"]
    assert 0.5 <= s["min"] <= s["mean"] <= s["max"] <= 2.5
    plain = train(cfgs, seed=3, steps=1500, run_dir=tmp_path / "plain", ddqn_config=small)
    assert plain["adversary_scale"] is None and plain["adversary_scale_sampled"] is None
    assert plain["param_abs_change"] != m["param_abs_change"]


def test_domain_randomization_rejects_bad_range(tmp_path):
    with pytest.raises(ValueError, match="adversary_scale"):
        train(
            load_configs(default_config_paths("train")),
            seed=0,
            steps=10,
            run_dir=tmp_path,
            adversary_scale=(2.0, 1.0),
        )


def test_nstep_training_runs(tmp_path):
    cfg = DDQNConfig(n_step=3, learning_starts=100, buffer_size=2000, eps_decay_steps=500)
    m = train(
        load_configs(default_config_paths("train")),
        seed=0,
        steps=600,
        run_dir=tmp_path,
        ddqn_config=cfg,
    )
    assert m["gradient_updates"] == 500 and m["param_abs_change"] > 0
