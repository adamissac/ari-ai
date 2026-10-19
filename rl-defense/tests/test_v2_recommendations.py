"""Serving live action space v2 checkpoints as DefenseRecommendations.

PlatformFacts carries ``principal_block_active`` / ``principal_block_available``; a v2
policy reads them as observation feature 48 and the block_principal mask entry.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
from payments_lite.app import create_app

from rl_defense import explain as ex
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.contracts import PlatformFacts
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.inference import LIVE_LAB_CAVEAT, PolicyRunner
from rl_defense.live import actions as la
from rl_defense.live.adversary import TrafficDriver, live_app
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.observations import from_platform_facts, mask_from_facts
from rl_defense.train import train


@pytest.fixture(scope="module")
def sim_ckpt(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sim")
    train(
        load_configs(default_config_paths("train")), seed=0, steps=2000, run_dir=d, log_every=2000
    )
    return d / "ddqn_seed0.pt"


def _v2_ckpt(sim_ckpt: Path, path: Path, *, favour_block: bool) -> Path:
    agent, _ = load_checkpoint(sim_ckpt)
    wide = la.expand_agent_to_v2(agent)
    if favour_block:  # make block_principal the clear argmax wherever it is valid
        last_bias = [p for n, p in wide.online.named_parameters() if n.endswith("bias")][-1]
        with torch.no_grad():
            last_bias[la.BLOCK_PRINCIPAL_ACTION] += 100.0
    save_checkpoint(wide, path, seed=0, steps=1, train_configs={}, env_id=la.LIVE_V2_ENV_ID)
    return path


def _facts(loop: LiveDefenseLoop, **kw) -> PlatformFacts:
    return loop._facts().model_copy(update=kw)


@pytest.fixture
def facts() -> PlatformFacts:
    loop = LiveDefenseLoop(create_app, driver=TrafficDriver(schedule="always"))
    loop.reset(1)
    f = loop._facts()
    loop.close()
    return f


def test_new_fields_default_off_and_sim_obs_unchanged(facts):
    assert not facts.principal_block_active and not facts.principal_block_available
    on = facts.model_copy(
        update={"principal_block_active": True, "principal_block_available": True}
    )
    np.testing.assert_array_equal(from_platform_facts(facts), from_platform_facts(on))
    np.testing.assert_array_equal(mask_from_facts(facts), mask_from_facts(on))
    o2, m2 = from_platform_facts(on, space="live_v2"), mask_from_facts(on, space="live_v2")
    assert o2.shape == (la.LIVE_V2_OBS_DIM,) and o2[OBS_DIM] == 1.0
    assert m2.shape == (la.LIVE_V2_N_ACTIONS,) and m2[la.BLOCK_PRINCIPAL_ACTION]


def test_v2_runner_recommends_block_only_when_facts_allow_it(sim_ckpt, tmp_path, facts):
    runner = PolicyRunner(_v2_ckpt(sim_ckpt, tmp_path / "v2.pt", favour_block=True))
    assert runner.space == "live_v2"
    assert runner.policy_version.startswith(f"{la.LIVE_V2_ENV_ID}@")

    blocked = runner.recommend(facts)  # principal_block_available=False -> masked
    assert blocked.action != "block_principal"
    assert all(s.action != "block_principal" for s in blocked.top_actions)

    rec = runner.recommend(facts.model_copy(update={"principal_block_available": True}))
    assert rec.action == "block_principal" and rec.node is None
    assert rec.d3fend == []  # unmapped pending human review (standards rule tables)
    assert rec.caveat == LIVE_LAB_CAVEAT and rec.simulation_derived is True
    assert len(rec.observation) == la.LIVE_V2_OBS_DIM


def test_v2_explanation_labels_the_new_action(sim_ckpt, tmp_path, facts):
    runner = PolicyRunner(_v2_ckpt(sim_ckpt, tmp_path / "v2.pt", favour_block=True))
    f = facts.model_copy(update={"principal_block_available": True, "principal_block_active": True})
    rec, exp = runner.recommend_with_explanation(f)
    assert exp.action == "block_principal" == rec.action
    assert exp.caveat == ex.LIVE_CAVEAT and exp.recommendation_id == rec.id


def test_widened_policy_recommends_like_the_sim_policy(sim_ckpt, tmp_path, facts):
    """Serving a v2 checkpoint that has learned nothing about blocking changes nothing."""
    sim = PolicyRunner(sim_ckpt)
    wide = PolicyRunner(_v2_ckpt(sim_ckpt, tmp_path / "w.pt", favour_block=False))
    for f in (facts, facts.model_copy(update={"principal_block_available": True})):
        assert wide.recommend(f).action == sim.recommend(f).action
        assert wide.recommend(f).node == sim.recommend(f).node


def test_live_loop_v2_obs_matches_platform_facts_mapping():
    """The loop's v2 observation equals PlatformFacts -> from_platform_facts(space=live_v2)
    when the two fields are filled from the loop's own block state."""
    loop = LiveDefenseLoop(
        live_app, config=LoopConfig(action_space="live_v2"), driver=TrafficDriver(schedule="always")
    )
    loop.reset(1)
    # after each step the gateway still holds that window's records -> facts for next_obs
    for action in (la.BLOCK_PRINCIPAL_ACTION, 0, 0, 0, la.BLOCK_PRINCIPAL_ACTION):
        t = loop.step(action)
        f = _facts(
            loop,
            principal_block_active=bool(loop._timers.block),
            principal_block_available=any(
                (p, n) not in loop._timers.block for p, ns in loop._flagged.items() for n in ns
            ),
        )
        np.testing.assert_array_equal(
            np.asarray(t.next_obs, dtype=np.float32), from_platform_facts(f, space="live_v2")
        )
        np.testing.assert_array_equal(
            np.asarray(t.action_mask), mask_from_facts(f, space="live_v2")
        )
    loop.close()


def test_explain_layout_constants_match_live_actions():
    assert ex._V2_OBS_DIM == la.LIVE_V2_OBS_DIM
    assert ex._V2_EXTRA == la.LIVE_V2_EXTRA_FEATURES
    assert (ex._BLOCK_ACTION, ex._BLOCK_NAME) == (la.BLOCK_PRINCIPAL_ACTION, la.BLOCK_PRINCIPAL)
    assert la.BLOCK_PRINCIPAL_ACTION == N_ACTIONS
