"""DefenseSimEnv-v1: the benign-disruption term, and that v0 is untouched by it."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from rl_defense.baselines import ExposedGuardPolicy, RandomValidPolicy
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ENV_V1
from rl_defense.envs.defense_sim import REWARD_COMPONENTS, encode_action
from rl_defense.reward_v1_study import episode_metrics, select_arm, to_arm

TRAIN = load_configs(default_config_paths("train"))
EVAL = load_configs(default_config_paths("eval"))
# Hashes recorded in committed manifests (results/protocol-v1, results/learning-check).
V0_HASHES = {
    "train_aggressive": "127321eafd88be15",
    "train_balanced": "535d99ff8777c11e",
    "train_stealthy": "c9e32096ebd76da4",
    "eval_aggressive_noisy": "0f088b0baba76eef",
    "eval_shifted_severity": "8408d6aa4d5bdf4d",
    "eval_stealthy_lowsignal": "b712960bd39563c8",
}


def test_v0_config_hashes_are_unchanged_by_the_new_field() -> None:
    assert {c.name: c.config_hash() for c in TRAIN + EVAL} == V0_HASHES


def test_reward_version_and_term_must_agree() -> None:
    base = TRAIN[0]
    with pytest.raises(ValidationError):  # v0 config carrying the v1 term
        type(base).model_validate(
            {**base.model_dump(), "reward": {**base.reward.model_dump(), "c_false_disrupt": 0.2}}
        )
    with pytest.raises(ValidationError):  # v1 label without the term
        type(base).model_validate({**base.model_dump(), "env_version": ENV_V1})
    with pytest.raises(ValidationError):
        type(base).model_validate({**base.model_dump(), "env_version": "DefenseSimEnv-v9"})
    v1 = to_arm(base, 0.2)
    assert v1.env_version == ENV_V1 and v1.config_hash() != base.config_hash()
    assert to_arm(base, 0.0) is base


def _rollout(cfg, seed: int, actions: list[int]):
    env = DefenseSimEnv(cfg)
    env.reset(seed=seed)
    out = []
    for a in actions:
        obs, r, term, trunc, info = env.step(a)
        out.append((obs, r, term, trunc, info))
        if term or trunc:
            break
    return out


def test_v1_changes_only_the_disruption_component_and_not_the_dynamics() -> None:
    base, c = TRAIN[1], 0.25
    rng = np.random.default_rng(0)
    env = DefenseSimEnv(base)
    _, info = env.reset(seed=7)
    actions = []
    for _ in range(base.horizon):
        a = int(rng.choice(np.flatnonzero(info["action_mask"])))
        actions.append(a)
        _, _, term, trunc, info = env.step(a)
        if term or trunc:
            break
    v0, v1 = _rollout(base, 7, actions), _rollout(to_arm(base, c), 7, actions)
    assert len(v0) == len(v1)
    charged = 0
    for (o0, r0, t0, tr0, i0), (o1, r1, t1, tr1, i1) in zip(v0, v1, strict=True):
        assert np.array_equal(o0, o1) and (t0, tr0) == (t1, tr1)
        assert i0["metrics"]["stages"] == i1["metrics"]["stages"]
        c0, c1 = i0["events"]["reward_components"], i1["events"]["reward_components"]
        load = i1["events"]["benign_disruption_load"]
        assert load == i0["events"]["benign_disruption_load"]
        for key in REWARD_COMPONENTS:
            if key != "disruption":
                assert c0[key] == c1[key]
        assert c1["disruption"] == pytest.approx(c0["disruption"] - c * load)
        assert r1 == pytest.approx(sum(c1[k] for k in REWARD_COMPONENTS))
        assert r1 == pytest.approx(r0 - c * load)
        charged += load > 0
    assert charged > 0  # the random walk did disrupt healthy nodes


def test_benign_load_counts_healthy_nodes_and_ignores_criticality() -> None:
    # No adversary: every node stays healthy, so each control is a benign disruption.
    quiet = TRAIN[1].model_copy(
        update={
            "adversary": TRAIN[1].adversary.model_copy(
                update={"entry_prob": 0.0, "lateral_prob": 0.0}
            )
        }
    )
    cfg = to_arm(quiet, 0.5)
    steps = _rollout(cfg, 0, [encode_action("rate_limit", 0), encode_action("isolate", 4)])
    assert steps[0][4]["events"]["benign_disruption_load"] == pytest.approx(0.3)
    assert steps[1][4]["events"]["benign_disruption_load"] == pytest.approx(1.3)
    # gateway (criticality 0.3) and db (1.0) cost the same v1 amount per unit of load
    gw = _rollout(cfg, 0, [encode_action("isolate", 0)])[0][4]["events"]
    db = _rollout(cfg, 0, [encode_action("isolate", 4)])[0][4]["events"]
    v0_gw = _rollout(quiet, 0, [encode_action("isolate", 0)])[0][4]["events"]
    v0_db = _rollout(quiet, 0, [encode_action("isolate", 4)])[0][4]["events"]
    extra_gw = v0_gw["reward_components"]["disruption"] - gw["reward_components"]["disruption"]
    extra_db = v0_db["reward_components"]["disruption"] - db["reward_components"]["disruption"]
    assert extra_gw == pytest.approx(0.5) and extra_db == pytest.approx(0.5)


def test_episode_metrics_returns_agree_across_reward_versions() -> None:
    cfg = EVAL[0]
    m0 = episode_metrics(cfg, RandomValidPolicy(seed=3), 1000)
    m1 = episode_metrics(to_arm(cfg, 0.25), RandomValidPolicy(seed=3), 1000)
    assert m0["return_arm"] == m0["return_v0"]
    assert m1["return_v0"] == pytest.approx(m0["return_v0"])
    assert m1["return_arm"] < m0["return_arm"]
    for key in ("compromise_rate", "false_disruption_rate", "benign_load", "service_uptime"):
        assert m1[key] == m0[key]


def test_exposed_guard_is_deterministic_and_keeps_exposed_nodes_limited() -> None:
    cfg = EVAL[0]
    a = episode_metrics(cfg, ExposedGuardPolicy(0.15), 1001)
    b = episode_metrics(cfg, ExposedGuardPolicy(0.15), 1001)
    assert a == b and a["invalid_actions"] == 0 and a["benign_load"] > 0.1


def _arm(c: float, fd: float, load: float, comp: float) -> dict:
    m = lambda v: {"mean": v}  # noqa: E731
    return {
        "c_false_disrupt": c,
        "validation": {
            "ddqn": {
                "false_disruption_rate": m(fd),
                "benign_load": m(load),
                "compromise_rate": m(comp),
            }
        },
    }


def test_selection_rule_uses_validation_and_can_select_nothing() -> None:
    ref = _arm(0.0, 0.7, 0.4, 0.05)
    assert select_arm([ref, _arm(0.1, 0.6, 0.1, 0.01)])["selected_c_false_disrupt"] is None
    assert select_arm([ref, _arm(0.1, 0.3, 0.3, 0.01)])["selected_c_false_disrupt"] is None
    picked = select_arm([ref, _arm(0.1, 0.3, 0.1, 0.2), _arm(0.5, 0.2, 0.05, 0.1)])
    assert picked["selected_c_false_disrupt"] == 0.5
    assert not picked["validation"][0]["qualifies"]  # the reference arm never qualifies


def test_a_v1_trained_checkpoint_records_its_reward_version(tmp_path) -> None:
    from rl_defense.agents.ddqn import DDQNConfig
    from rl_defense.train import train

    small = DDQNConfig(learning_starts=100, buffer_size=1_000, eps_decay_steps=200)
    v0 = train(TRAIN, 0, 300, tmp_path / "v0", small)
    v1 = train([to_arm(c, 0.25) for c in TRAIN], 0, 300, tmp_path / "v1", small)
    assert "reward_env_version" not in v0
    assert v1["reward_env_version"] == [ENV_V1]
