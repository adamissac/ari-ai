"""Guided exploration and the monitor_isolate rule."""

import numpy as np
import torch

import rl_defense.train as train_mod
from rl_defense.agents.ddqn import DDQNConfig
from rl_defense.baselines import MonitorIsolatePolicy, NoopPolicy
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.defense_sim import DISRUPTIVE, decode_action
from rl_defense.evidence_policy_study import verdict
from rl_defense.reward_v1_study import episode_metrics
from rl_defense.train import train

TRAIN = load_configs(default_config_paths("train"))
EVAL = load_configs(default_config_paths("eval"))
SMALL = DDQNConfig(learning_starts=100, buffer_size=2_000, eps_decay_steps=300)


def test_monitor_isolate_never_disrupts_without_a_signal_and_never_rate_limits():
    policy, thr = MonitorIsolatePolicy(0.2), 0.2
    for cfg in EVAL:
        env = DefenseSimEnv(cfg)
        obs, info = env.reset(seed=1000)
        done = False
        while not done:
            a = policy.act(obs, info["action_mask"])
            assert info["action_mask"][a]
            name, node = decode_action(a)
            assert name != "rate_limit"
            if name in DISRUPTIVE:
                assert obs[node * 9 + 1] > thr  # the target's anomaly_score
            obs, _, term, trunc, info = env.step(a)
            done = term or trunc


def test_monitor_isolate_beats_doing_nothing_and_is_deterministic():
    cfg = EVAL[0]
    a = episode_metrics(cfg, MonitorIsolatePolicy(0.2), 1003)
    assert a == episode_metrics(cfg, MonitorIsolatePolicy(0.2), 1003)
    assert a["return_v0"] > episode_metrics(cfg, NoopPolicy(), 1003)["return_v0"]
    assert a["invalid_actions"] == 0


def _actions(tmp_path, monkeypatch, **kwargs):
    seen: list[int] = []
    real = DefenseSimEnv.step

    def step(self, action):  # noqa: ANN001, ANN202
        seen.append(int(action))
        return real(self, action)

    monkeypatch.setattr(DefenseSimEnv, "step", step)
    manifest = train(TRAIN, 0, 600, tmp_path, SMALL, **kwargs)
    monkeypatch.undo()
    return seen, manifest


def test_guide_drives_early_behaviour_only_and_is_recorded(tmp_path, monkeypatch):
    class Always:
        name = "always_noop"

        def reset(self, seed: int) -> None:
            pass

        def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
            return 0

    seen, manifest = _actions(
        tmp_path / "g", monkeypatch, guide=Always(), guide_steps=300, guide_prob=1.0
    )
    assert seen[:300] == [0] * 300 and any(a != 0 for a in seen[300:])
    assert manifest["guide"] == {"policy": "always_noop", "steps": 300, "prob": 1.0}


def test_no_guide_is_the_unchanged_default_run(tmp_path, monkeypatch):
    _, m0 = _actions(tmp_path / "a", monkeypatch)
    _, m1 = _actions(tmp_path / "b", monkeypatch, guide=None, guide_steps=500)
    assert "guide" not in m0 and "guide" not in m1
    a, _ = load_checkpoint(tmp_path / "a" / "ddqn_seed0.pt")
    b, _ = load_checkpoint(tmp_path / "b" / "ddqn_seed0.pt")
    for p, q in zip(a.online.parameters(), b.online.parameters(), strict=True):
        assert torch.equal(p, q)
    assert train_mod.Policy is not None


def _m(comp: float, fd: float, load: float, ret: float = 0.0) -> dict:
    return {
        "compromise_rate": {"mean": comp},
        "false_disruption_rate": {"mean": fd},
        "benign_load": {"mean": load},
        "return_arm": {"mean": ret},
    }


def test_verdict_needs_all_three_checks_and_reports_the_rule_comparison():
    rule = _m(0.1, 0.2, 0.4, -50.0)
    ok = verdict({"ddqn_guided": _m(0.1, 0.3, 0.4, -40.0), "ddqn_v0": _m(0.15, 0.7, 0.9),
                  "monitor_isolate": rule})  # fmt: skip
    assert ok["improves_on_original"] and ok["beats_monitor_isolate_on_return"]
    assert not ok["beats_monitor_isolate_on_compromise"]
    worse = verdict({"ddqn_guided": _m(0.3, 0.3, 0.4), "ddqn_v0": _m(0.15, 0.7, 0.9),
                     "monitor_isolate": rule})  # fmt: skip
    assert not worse["improves_on_original"]
    assert not worse["checks"]["compromise_not_above_original"]
