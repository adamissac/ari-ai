import warnings

import gymnasium as gym
import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

import rl_defense.envs  # noqa: F401  (registers DefenseSimEnv-v0)
from rl_defense.envs import DefenseSimEnv, default_config_paths, encode_action, load_configs
from rl_defense.envs.defense_sim import (
    N_ACTIONS,
    N_NODES,
    NOOP_ACTION,
    OBS_DIM,
    STAGE_ESCALATED,
    STAGE_IMPACT,
)

TRAIN = load_configs(default_config_paths("train"))
EVAL = load_configs(default_config_paths("eval"))


def by_name(name):
    return next(c for c in TRAIN + EVAL if c.name == name)


def rollout(env, actions, seed):
    obs, info = env.reset(seed=seed)
    out = [(obs.copy(), 0.0)]
    for a in actions:
        obs, r, term, trunc, info = env.step(a)
        out.append((obs.copy(), r))
        if term or trunc:
            break
    return out


@pytest.mark.parametrize("cfg", TRAIN + EVAL, ids=lambda c: c.name)
def test_gymnasium_check_env(cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any env_checker warning fails the test
        check_env(DefenseSimEnv(cfg), skip_render_check=True)


def test_registered_with_gymnasium():
    env = gym.make("DefenseSimEnv-v0", config=TRAIN[0])
    obs, _ = env.reset(seed=0)
    assert obs.shape == (OBS_DIM,)
    assert env.action_space.n == N_ACTIONS == 22


def test_train_and_eval_configs_are_disjoint_and_split_labeled():
    assert {c.split for c in TRAIN} == {"train"} and {c.split for c in EVAL} == {"eval"}
    assert not {c.config_hash() for c in TRAIN} & {c.config_hash() for c in EVAL}
    # Reward coefficients are identical across all configs (protocol 17: no silent reward edits).
    assert len({c.reward for c in TRAIN + EVAL}) == 1


def test_seeded_determinism():
    env_a, env_b = DefenseSimEnv(TRAIN[0]), DefenseSimEnv(TRAIN[0])
    rng = np.random.default_rng(3)
    actions = rng.integers(0, N_ACTIONS, size=200).tolist()
    ta, tb = rollout(env_a, actions, seed=42), rollout(env_b, actions, seed=42)
    assert len(ta) == len(tb)
    for (oa, ra), (ob, rb) in zip(ta, tb, strict=True):
        np.testing.assert_array_equal(oa, ob)
        assert ra == rb
    tc = rollout(DefenseSimEnv(TRAIN[0]), actions, seed=43)
    assert any(not np.array_equal(a[0], c[0]) for a, c in zip(ta, tc, strict=False))


def test_observation_does_not_leak_hidden_stage():
    env = DefenseSimEnv(TRAIN[0])
    env.reset(seed=0)
    before = env._observe().copy()
    env._hidden.stage[:] = STAGE_IMPACT  # change ONLY hidden state
    after = env._observe()
    np.testing.assert_array_equal(before, after)


def test_observation_in_bounds_over_long_rollouts():
    env = DefenseSimEnv(by_name("eval_aggressive_noisy"))
    rng = np.random.default_rng(0)
    for ep in range(5):
        obs, info = env.reset(seed=ep)
        done = False
        while not done:
            assert env.observation_space.contains(obs)
            a = int(rng.choice(np.flatnonzero(info["action_mask"])))
            obs, _, term, trunc, info = env.step(a)
            done = term or trunc


def test_action_masks():
    env = DefenseSimEnv(TRAIN[0])
    _, info = env.reset(seed=0)
    assert info["action_mask"][NOOP_ACTION]
    iso = encode_action("isolate", 2)
    _, _, _, _, info = env.step(iso)
    mask = info["action_mask"]
    assert not mask[iso], "cannot isolate an already isolated node"
    assert not mask[encode_action("rate_limit", 2)], "cannot rate-limit an isolated node"
    for _ in range(TRAIN[0].defense.max_escalations):
        a = encode_action("escalate_to_human")
        while not info["action_mask"][a]:
            _, _, _, _, info = env.step(NOOP_ACTION)
        _, _, _, _, info = env.step(a)
    while env._obs_state.escalation_timer:
        _, _, _, _, info = env.step(NOOP_ACTION)
    assert not info["action_mask"][encode_action("escalate_to_human")], (
        "escalation budget exhausted"
    )


def test_invalid_action_is_penalized_noop():
    env = DefenseSimEnv(TRAIN[0])
    env.reset(seed=0)
    iso = encode_action("isolate", 0)
    env.step(iso)
    _, r, _, _, info = env.step(iso)  # invalid now
    assert info["events"]["invalid_action"] is True
    assert info["action"] == "noop"
    assert r <= -TRAIN[0].reward.c_invalid + 1e-9 or r < 0


def test_isolation_stops_progression():
    env = DefenseSimEnv(by_name("train_aggressive"))
    env.reset(seed=1)
    env._hidden.stage[:] = STAGE_ESCALATED
    for i in range(N_NODES):
        env.step(encode_action("isolate", i))
    stages_before = env._hidden.stage.copy()
    for _ in range(3):
        env.step(NOOP_ACTION)
    assert (env._hidden.stage <= stages_before).all()


def _mean_return(cfg, policy, episodes=30):
    env = DefenseSimEnv(cfg)
    totals = []
    for s in range(episodes):
        _, info = env.reset(seed=900 + s)
        total, done = 0.0, False
        while not done:
            _, r, term, trunc, info = env.step(policy(info))
            total += r
            done = term or trunc
        totals.append(total)
    return float(np.mean(totals))


def test_reward_sanity_noop_worse_under_aggressive_adversary():
    noop = lambda info: NOOP_ACTION  # noqa: E731
    assert _mean_return(by_name("train_aggressive"), noop) < _mean_return(
        by_name("train_stealthy"), noop
    )


def test_early_termination_is_not_cheaper_than_surviving():
    """Losing the db early must cost more than defending (otherwise RL learns to die fast)."""
    noop = lambda info: NOOP_ACTION  # noqa: E731

    def isolate_all(info):
        for i in range(N_NODES):
            a = encode_action("isolate", i)
            if info["action_mask"][a]:
                return a
        return NOOP_ACTION

    cfg = by_name("train_aggressive")
    assert _mean_return(cfg, noop) < _mean_return(cfg, isolate_all)


def test_reward_components_sum_exactly_to_reward():
    from rl_defense.envs.defense_sim import REWARD_COMPONENTS

    env = DefenseSimEnv(by_name("eval_aggressive_noisy"))
    rng = np.random.default_rng(0)
    seen = set()
    for ep in range(10):
        _, info = env.reset(seed=ep)
        done = False
        while not done:
            _, r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(info["action_mask"]))))
            comp = info["events"]["reward_components"]
            assert tuple(comp) == REWARD_COMPONENTS
            total = 0.0
            for k in REWARD_COMPONENTS:
                total += comp[k]
            assert total == r
            seen |= {k for k, v in comp.items() if v != 0}
            done = term or trunc
    assert {"action_cost", "disruption", "adversary_progress"} <= seen
