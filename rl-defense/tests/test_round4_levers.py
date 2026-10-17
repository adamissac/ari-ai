"""Round-4 levers: disruption margin, disruptive-exploration weight, FD-penalised selection."""

import numpy as np
import pytest

from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM, encode_action

ISO = encode_action("isolate", 3)
MON = encode_action("raise_monitoring", 3)
OBS = np.zeros(OBS_DIM, np.float32)


def _agent(**cfg):
    return DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(**cfg), seed=0)


def _fix_q(agent, iso, mon, noop=0.0):
    q = np.full(N_ACTIONS, -10.0, dtype=np.float32)
    q[0], q[ISO], q[MON] = noop, iso, mon
    agent.q_values = lambda obs: q.copy()  # type: ignore[method-assign]


def test_disruptive_mask_marks_only_rate_limit_and_isolate():
    a = _agent()
    assert a.disruptive[ISO] and a.disruptive[encode_action("rate_limit", 0)]
    assert not a.disruptive[MON] and not a.disruptive[0]
    assert a.disruptive.sum() == 10  # 5 nodes x {rate_limit, isolate}


def test_margin_zero_is_plain_masked_argmax():
    a = _agent()
    _fix_q(a, iso=1.01, mon=1.0)
    assert a.greedy_action(OBS, np.ones(N_ACTIONS, bool)) == ISO


def test_margin_abstains_when_gap_is_small_and_acts_when_large():
    a = _agent(disruption_margin=0.1)
    mask = np.ones(N_ACTIONS, bool)
    _fix_q(a, iso=1.05, mon=1.0)
    assert a.greedy_action(OBS, mask) == MON  # gap 0.05 < 0.1
    _fix_q(a, iso=1.2, mon=1.0)
    assert a.greedy_action(OBS, mask) == ISO  # gap 0.2 >= 0.1


def test_margin_respects_mask():
    a = _agent(disruption_margin=0.5)
    mask = np.zeros(N_ACTIONS, bool)
    mask[[0, ISO]] = True
    _fix_q(a, iso=1.0, mon=5.0, noop=0.9)
    assert a.greedy_action(OBS, mask) == 0  # monitoring is masked; noop is the safe alternative


def test_exploration_weight_reduces_disruptive_share():
    mask = np.ones(N_ACTIONS, bool)

    def share(ag):
        return np.mean([ag.disruptive[ag.act(OBS, mask, 1.0)] for _ in range(4000)])

    assert share(_agent()) == pytest.approx(10 / 22, abs=0.03)
    assert share(_agent(eps_disruptive_weight=0.25)) == pytest.approx(2.5 / 14.5, abs=0.03)


def test_defaults_keep_the_original_random_stream():
    """With the new fields at defaults, exploration draws match the original code path."""
    mask = np.ones(N_ACTIONS, bool)
    valid = np.flatnonzero(mask)
    ref = np.random.default_rng(0)  # DDQNAgent seeds its exploration RNG the same way
    a = _agent()
    for _ in range(100):
        ref.random()
        assert a.act(OBS, mask, 1.0) == int(ref.choice(valid))


def test_selection_score_fd_penalty_never_raises_the_score():
    from rl_defense.train import selection_score

    cfgs = load_configs(default_config_paths("train"))[:1]
    a = _agent()
    assert selection_score(a, cfgs, 0.2) <= selection_score(a, cfgs, 0.0)


def test_train_saves_margin_but_trains_without_it(tmp_path):
    from rl_defense.checkpoint import load_checkpoint
    from rl_defense.train import train

    cfgs = load_configs(default_config_paths("train"))
    small = dict(
        learning_starts=100, buffer_size=2000, eps_decay_steps=500, target_update_interval=100
    )
    m0 = train(cfgs, 3, 400, tmp_path / "a", DDQNConfig(**small))
    m1 = train(cfgs, 3, 400, tmp_path / "b", DDQNConfig(**small, disruption_margin=0.1))
    assert m0["param_abs_change"] == m1["param_abs_change"]  # identical training
    agent, _ = load_checkpoint(tmp_path / "b" / "ddqn_seed3.pt")
    assert agent.config.disruption_margin == 0.1


def test_posthoc_candidate_loader(tmp_path):
    from experiments.select import load_candidate

    p = tmp_path / "c.yaml"
    p.write_text("from_run: r3/x\ndisruption_margin: 0.1\n")
    _, _, overrides, opts = load_candidate(p)
    assert overrides == {"disruption_margin": 0.1} and opts["from_run"] == "r3/x"
    p.write_text("from_run: r3/x\nlr: 0.1\n")
    with pytest.raises(ValueError):
        load_candidate(p)
