"""Interrupted training resumes to exactly the weights of an uninterrupted run."""

import json

import pytest
import torch

import rl_defense.train as train_mod
from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.train import train

TRAIN = load_configs(default_config_paths("train"))
SMALL = DDQNConfig(
    learning_starts=200, buffer_size=5_000, eps_decay_steps=2_000, target_update_interval=200
)
VARIANTS = {
    "plain": (SMALL, {}),
    "nstep_randomized_selected": (
        SMALL.model_copy(update={"n_step": 3, "lr_end": 1e-4, "buffer_size": 1_500}),
        {"adversary_scale": (0.5, 2.5), "select_every": 1_000, "select_start": 1_000},
    ),
}
STEPS = 3_000


class Crash(Exception):
    pass


def _weights(run_dir, seed=0):
    agent, manifest = load_checkpoint(run_dir / f"ddqn_seed{seed}.pt")
    return agent, manifest


def _log_rows(run_dir, seed=0):
    rows = [json.loads(x) for x in (run_dir / f"train_seed{seed}.jsonl").read_text().splitlines()]
    for r in rows:
        r.pop("elapsed_s")
    return rows


def _crash_after(monkeypatch, n_saves):
    real, calls = train_mod._save_state, []

    def save_then_crash(path, state):
        real(path, state)
        calls.append(state["step"])
        if len(calls) == n_saves:
            raise Crash

    monkeypatch.setattr(train_mod, "_save_state", save_then_crash)
    return calls


@pytest.mark.parametrize("variant", VARIANTS)
def test_resumed_run_matches_uninterrupted_run(tmp_path, monkeypatch, variant):
    cfg, kwargs = VARIANTS[variant]
    common = dict(seed=0, steps=STEPS, ddqn_config=cfg, log_every=500, **kwargs)
    train(TRAIN, run_dir=tmp_path / "straight", **common)

    saves = _crash_after(monkeypatch, 2)
    with pytest.raises(Crash):
        train(TRAIN, run_dir=tmp_path / "resumed", checkpoint_every=400, **common)
    assert not (tmp_path / "resumed" / "ddqn_seed0.pt").exists()
    monkeypatch.undo()
    manifest = train(
        TRAIN, run_dir=tmp_path / "resumed", checkpoint_every=400, resume=True, **common
    )

    assert manifest["resumed_from_steps"] == [saves[1]] and 0 < saves[1] < STEPS
    a, ma = _weights(tmp_path / "straight")
    b, mb = _weights(tmp_path / "resumed")
    for name in ("online", "target"):
        for p, q in zip(getattr(a, name).parameters(), getattr(b, name).parameters(), strict=True):
            assert torch.equal(p, q)
    assert a.updates == b.updates
    for key in ("episodes", "gradient_updates", "param_abs_change", "adversary_scale_sampled"):
        assert ma[key] == mb[key]
    if kwargs:
        assert ma["checkpoint_selection"] == mb["checkpoint_selection"]
    assert _log_rows(tmp_path / "straight") == _log_rows(tmp_path / "resumed")


def test_periodic_state_does_not_change_an_uninterrupted_run(tmp_path):
    common = dict(seed=1, steps=1_500, ddqn_config=SMALL)
    train(TRAIN, run_dir=tmp_path / "a", **common)
    m = train(TRAIN, run_dir=tmp_path / "b", checkpoint_every=300, **common)
    assert (tmp_path / "b" / "train_seed1.state.pt").exists()
    assert m["resumed_from_steps"] == []
    a, _ = _weights(tmp_path / "a", 1)
    b, _ = _weights(tmp_path / "b", 1)
    for p, q in zip(a.online.parameters(), b.online.parameters(), strict=True):
        assert torch.equal(p, q)


def test_resume_without_a_saved_state_starts_from_scratch(tmp_path):
    m = train(TRAIN, seed=0, steps=600, run_dir=tmp_path, ddqn_config=SMALL, resume=True)
    assert m["resumed_from_steps"] == []


def test_resume_refuses_a_state_from_a_different_run_definition(tmp_path, monkeypatch):
    _crash_after(monkeypatch, 1)
    with pytest.raises(Crash):
        train(TRAIN, seed=0, steps=STEPS, run_dir=tmp_path, ddqn_config=SMALL, checkpoint_every=400)
    monkeypatch.undo()
    other = SMALL.model_copy(update={"lr": 5e-4})
    with pytest.raises(ValueError, match="different run definition"):
        train(TRAIN, seed=0, steps=STEPS, run_dir=tmp_path, ddqn_config=other, resume=True)


def test_non_finite_loss_stops_training_without_a_checkpoint(tmp_path, monkeypatch):
    def nan_update(self, batch):
        self.updates += 1
        return {"loss": float("nan")}

    monkeypatch.setattr(DDQNAgent, "update", nan_update)
    with pytest.raises(FloatingPointError, match="non-finite loss"):
        train(TRAIN, seed=0, steps=1_000, run_dir=tmp_path, ddqn_config=SMALL)
    assert not (tmp_path / "ddqn_seed0.pt").exists()
