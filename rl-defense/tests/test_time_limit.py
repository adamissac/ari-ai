"""``time_limit_terminal``: what the trainer stores at the horizon, and that the default
(bootstrap through the time limit, as protocol-v0/v1 were trained) is unchanged."""

import pytest
import torch

import rl_defense.train as train_mod
from rl_defense.agents.ddqn import DDQNConfig, ReplayBuffer
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.train import train

# A short horizon so a 1,500-step run reaches the time limit many times.
SHORT = [c.model_copy(update={"horizon": 20}) for c in load_configs(default_config_paths("train"))]
SMALL = DDQNConfig(learning_starts=200, buffer_size=5_000, eps_decay_steps=1_000)
STEPS = 1_500


def _run(tmp_path, monkeypatch, n_step: int, flag: bool | None):
    dones: list[bool] = []
    ends = {"terminated": 0, "truncated": 0}

    class Recording(ReplayBuffer):
        def add(self, obs, action, reward, next_obs, done, next_mask, *rest):  # noqa: ANN001
            dones.append(bool(done))
            super().add(obs, action, reward, next_obs, done, next_mask, *rest)

    real_step = DefenseSimEnv.step

    def step(self, action):  # noqa: ANN001, ANN202
        out = real_step(self, action)
        ends["terminated"] += int(out[2])
        ends["truncated"] += int(out[3])
        return out

    monkeypatch.setattr(train_mod, "ReplayBuffer", Recording)
    monkeypatch.setattr(DefenseSimEnv, "step", step)
    kwargs = {} if flag is None else {"time_limit_terminal": flag}
    manifest = train(
        SHORT, 0, STEPS, tmp_path, SMALL.model_copy(update={"n_step": n_step}), **kwargs
    )
    return dones, ends, manifest


@pytest.mark.parametrize("n_step", [1, 3])
def test_default_bootstraps_through_the_time_limit(tmp_path, monkeypatch, n_step):
    dones, ends, manifest = _run(tmp_path, monkeypatch, n_step, None)
    assert ends["truncated"] > 20
    # only a real termination (db impact) is stored as done; n-step flushes n windows for it
    assert sum(dones) == n_step * ends["terminated"]
    assert "time_limit_terminal" not in manifest


@pytest.mark.parametrize("n_step", [1, 3])
def test_flag_stores_the_horizon_as_terminal(tmp_path, monkeypatch, n_step):
    dones, ends, manifest = _run(tmp_path, monkeypatch, n_step, True)
    assert ends["truncated"] > 20
    assert sum(dones) == n_step * (ends["terminated"] + ends["truncated"])
    assert manifest["time_limit_terminal"] is True


def test_explicit_false_is_the_default_run(tmp_path, monkeypatch):
    _run(tmp_path / "a", monkeypatch, 3, None)
    monkeypatch.undo()
    _run(tmp_path / "b", monkeypatch, 3, False)
    a, _ = load_checkpoint(tmp_path / "a" / "ddqn_seed0.pt")
    b, _ = load_checkpoint(tmp_path / "b" / "ddqn_seed0.pt")
    for p, q in zip(a.online.parameters(), b.online.parameters(), strict=True):
        assert torch.equal(p, q)


def test_a_saved_state_cannot_resume_under_the_other_setting(tmp_path):
    train(SHORT, 0, 600, tmp_path, SMALL, checkpoint_every=200)
    state = tmp_path / "train_seed0.state.pt"
    if not state.exists():
        pytest.skip("the trainer removes the state after a completed run")
    with pytest.raises(ValueError):
        train(SHORT, 0, 600, tmp_path, SMALL, resume=True, time_limit_terminal=True)
