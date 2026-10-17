import numpy as np
import pytest
import torch
from torch import nn

from rl_defense.agents.ddqn import (
    Batch,
    DDQNAgent,
    DDQNConfig,
    ReplayBuffer,
    double_dqn_targets,
    masked_argmax,
)
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM


class FixedQ(nn.Module):
    def __init__(self, table):
        super().__init__()
        self.table = torch.tensor(table, dtype=torch.float32)

    def forward(self, obs):
        return self.table.expand(obs.shape[0], -1)


def batch(rewards, dones, masks):
    n = len(rewards)
    return Batch(
        obs=torch.zeros(n, 2),
        actions=torch.zeros(n, dtype=torch.int64),
        rewards=torch.tensor(rewards, dtype=torch.float32),
        next_obs=torch.zeros(n, 2),
        dones=torch.tensor(dones, dtype=torch.float32),
        next_masks=torch.tensor(masks),
    )


def test_double_dqn_target_uses_online_argmax_and_target_value():
    online = FixedQ([1.0, 5.0, 3.0])  # online prefers action 1
    target = FixedQ([10.0, 2.0, 7.0])  # target's own max is action 0 (value 10)
    b = batch([1.0], [0.0], [[True, True, True]])
    y = double_dqn_targets(online, target, b, gamma=0.9)
    assert y.item() == pytest.approx(1.0 + 0.9 * 2.0)  # DDQN: Q_target(s', argmax Q_online) = 2
    assert y.item() != pytest.approx(1.0 + 0.9 * 10.0)  # NOT vanilla DQN max(target)


def test_double_dqn_target_respects_next_action_mask():
    online = FixedQ([1.0, 5.0, 3.0])
    target = FixedQ([10.0, 2.0, 7.0])
    b = batch([0.5], [0.0], [[True, False, True]])  # action 1 invalid in s'
    y = double_dqn_targets(online, target, b, gamma=0.5)
    assert y.item() == pytest.approx(0.5 + 0.5 * 7.0)  # online argmax over valid = action 2


def test_terminal_transitions_do_not_bootstrap():
    online, target = FixedQ([1.0, 5.0]), FixedQ([3.0, 4.0])
    y = double_dqn_targets(online, target, batch([2.0], [1.0], [[True, True]]), gamma=0.99)
    assert y.item() == pytest.approx(2.0)


def test_masked_argmax():
    q = torch.tensor([[1.0, 9.0, 3.0]])
    assert masked_argmax(q, torch.tensor([[True, False, True]])).item() == 2


def test_act_never_selects_masked_action():
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(), seed=0)
    mask = np.zeros(N_ACTIONS, dtype=bool)
    mask[[0, 7]] = True
    obs = np.random.default_rng(0).random(OBS_DIM).astype(np.float32)
    for eps in (0.0, 1.0):
        assert {agent.act(obs, mask, eps) for _ in range(200)} <= {0, 7}


def _filled_buffer(agent_seed=0, n=256):
    buf = ReplayBuffer(1000, OBS_DIM, N_ACTIONS, seed=agent_seed)
    rng = np.random.default_rng(agent_seed)
    for _ in range(n):
        buf.add(
            rng.random(OBS_DIM),
            rng.integers(N_ACTIONS),
            rng.normal(),
            rng.random(OBS_DIM),
            rng.random() < 0.1,
            np.ones(N_ACTIONS, dtype=bool),
        )
    return buf


def test_update_changes_online_weights_with_nonzero_gradients():
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(target_update_interval=10_000), seed=0)
    before = [p.detach().clone() for p in agent.online.parameters()]
    target_before = [p.detach().clone() for p in agent.target.parameters()]
    stats = agent.update(_filled_buffer().sample(64))
    assert stats["grad_norm"] > 0
    assert any(
        not torch.equal(a, b) for a, b in zip(before, agent.online.parameters(), strict=True)
    )
    # Target net is NOT updated by the optimizer step.
    assert all(
        torch.equal(a, b) for a, b in zip(target_before, agent.target.parameters(), strict=True)
    )


def test_hard_target_sync_interval():
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(target_update_interval=3), seed=0)
    buf = _filled_buffer()
    for _ in range(3):
        agent.update(buf.sample(32))
    for t, o in zip(agent.target.parameters(), agent.online.parameters(), strict=True):
        assert torch.equal(t, o)


def test_soft_update_moves_target_partially():
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(target_update="soft", tau=0.5), seed=0)
    for p in agent.online.parameters():
        p.data.fill_(1.0)
    for p in agent.target.parameters():
        p.data.fill_(0.0)
    agent.soft_update(0.5)
    assert all(torch.allclose(p, torch.full_like(p, 0.5)) for p in agent.target.parameters())


def test_epsilon_schedule():
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(eps_decay_steps=100), seed=0)
    assert agent.epsilon(0) == 1.0
    assert agent.epsilon(50) == pytest.approx(0.525)
    assert agent.epsilon(10_000) == pytest.approx(0.05)


def test_checkpoint_roundtrip_and_hash_verification(tmp_path):
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(), seed=1)
    agent.update(_filled_buffer().sample(64))
    path = tmp_path / "ddqn_seed1.pt"
    manifest = save_checkpoint(agent, path, seed=1, steps=10, train_configs={"x": "abc"})
    assert len(manifest["checkpoint_sha256"]) == 64
    loaded, m2 = load_checkpoint(path)
    obs = torch.rand(4, OBS_DIM)
    assert torch.equal(agent.online(obs), loaded.online(obs))
    assert loaded.updates == agent.updates and m2["seed"] == 1
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_checkpoint(path)
