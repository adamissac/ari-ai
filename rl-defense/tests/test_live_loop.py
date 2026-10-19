"""End-to-end live-loop tests: a genuinely trained DQN drives the real app.

The checkpoint is trained once (module scope) on the simulator configs — the policy
that exists today — then run against the live loop. These tests prove the closed
cycle (real telemetry → DQN → enforced action → measured outcome → reward →
transition) and that rewards/outcomes are *measured*, not scripted.
"""

from __future__ import annotations

import pathlib
import tempfile

import numpy as np
import pytest
from payments_lite.app import create_app

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM, encode_action
from rl_defense.inference import PolicyRunner
from rl_defense.live import LiveDefenseLoop, LoopConfig
from rl_defense.train import train


@pytest.fixture(scope="module")
def runner() -> PolicyRunner:
    cfgs = load_configs(default_config_paths("train"))
    d = pathlib.Path(tempfile.mkdtemp())
    train(cfgs, seed=0, steps=8000, run_dir=d, log_every=8000)
    return PolicyRunner(d / "ddqn_seed0.pt")


def test_loop_produces_wellformed_transitions(runner):
    loop = LiveDefenseLoop(create_app, runner, config=LoopConfig(horizon=12))
    try:
        ts = loop.run_episode(seed=1)
    finally:
        loop.close()
    assert len(ts) == 12
    for t in ts:
        assert len(t.obs) == OBS_DIM and len(t.next_obs) == OBS_DIM
        assert len(t.action_mask) == N_ACTIONS  # mask for next_obs (replay-buffer convention)
        assert 0 <= t.action < N_ACTIONS
        assert np.isfinite(t.reward)
        assert all(np.isfinite(v) for v in t.obs)
        # measured outcome accounting is self-consistent
        assert t.outcome.compromised_reads <= t.outcome.attack_requests
        assert t.outcome.benign_blocked <= t.outcome.benign_requests
    assert ts[-1].done is True


def test_policy_only_picks_valid_actions(runner):
    """The trained policy, as driven by the loop, never emits a masked action."""
    loop = LiveDefenseLoop(create_app, runner, config=LoopConfig(horizon=12))
    try:
        obs, mask = loop.reset(seed=3)
        for _ in range(12):
            a = loop.act(obs, mask)
            assert mask[a], "policy selected a masked action"
            t = loop.step(a)
            obs = np.asarray(t.next_obs, dtype=np.float32)
            mask = np.asarray(t.action_mask, dtype=bool)
    finally:
        loop.close()


def test_isolating_payments_really_contains_and_moves_reward(runner):
    """Causality check: forcing isolate:payments drives measured compromise to zero and
    yields a strictly higher reward than doing nothing while under attack."""
    iso = encode_action("isolate", _payments_index())
    loop = LiveDefenseLoop(create_app, runner, config=LoopConfig(horizon=6))
    try:
        loop.reset(seed=5)
        noop_t = loop.step(0)  # do nothing: attack succeeds
        isolate_t = loop.step(iso)  # isolate payments: attack blocked
    finally:
        loop.close()
    assert noop_t.outcome.compromised_reads > 0
    assert isolate_t.outcome.compromised_reads == 0
    assert isolate_t.reward > noop_t.reward


def test_reassessment_eventually_lowers_finding_severity(runner):
    """request_reassessment is a real control: after its delay the finding is remediated
    and the payments finding_severity drops in the observation."""
    rea = encode_action("request_reassessment", _payments_index())
    cfg = LoopConfig(horizon=12, reassessment_delay=2, reassessment_severity_after=0.2)
    loop = LiveDefenseLoop(create_app, runner, config=cfg)
    pay_feat = _payments_finding_feature_index()
    try:
        loop.reset(seed=7)
        before = loop.step(rea).obs[pay_feat]
        loop.step(0)
        after = loop.step(0).obs[pay_feat]  # a couple of steps later the reassessment lands
    finally:
        loop.close()
    assert after < before


# ------------------------------------------------------------------ helpers
def _payments_index() -> int:
    from rl_defense.envs.config import NODE_NAMES

    return NODE_NAMES.index("payments")


def _payments_finding_feature_index() -> int:
    """Index of the payments node's finding_severity feature in the obs vector."""
    from rl_defense.envs.config import NODE_NAMES
    from rl_defense.envs.defense_sim import NODE_FEATURES

    return NODE_NAMES.index("payments") * len(NODE_FEATURES) + NODE_FEATURES.index(
        "finding_severity"
    )
