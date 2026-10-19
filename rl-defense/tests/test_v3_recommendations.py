"""Serving live action space v3 checkpoints as DefenseRecommendations (contracts 0.13).

PlatformFacts carries the v3 detector features and the two long-block availabilities; the
live loop is the producer that fills them, and builds its own observation through the same
mapping that serving uses.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from shared.rl import DefenseRecommendation as SharedRecommendation

from rl_defense import layouts as lay
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.contracts import PlatformFacts
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import OBS_DIM
from rl_defense.inference import LIVE_LAB_CAVEAT, PolicyRunner
from rl_defense.live import actions as la
from rl_defense.live import run as live_run
from rl_defense.live.adversary import live_app
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario
from rl_defense.observations import from_platform_facts, mask_from_facts
from rl_defense.train import train

RL_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sim_ckpt(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sim3")
    train(
        load_configs(default_config_paths("train")), seed=0, steps=2000, run_dir=d, log_every=2000
    )
    return d / "ddqn_seed0.pt"


def _v3_ckpt(sim_ckpt: Path, path: Path, *, favour: int | None) -> Path:
    agent, _ = load_checkpoint(sim_ckpt)
    wide = la.widen_agent(agent, "live_v3")
    if favour is not None:  # make one action the clear argmax wherever it is valid
        last_bias = [p for n, p in wide.online.named_parameters() if n.endswith("bias")][-1]
        with torch.no_grad():
            last_bias[favour] += 100.0
    save_checkpoint(wide, path, seed=0, steps=1, train_configs={}, env_id=lay.LIVE_V3_ENV_ID)
    return path


def _scenario() -> LiveScenario:
    return LiveScenario(
        name="serve3",
        split="train",
        schedule="always",
        attack_per_step=4,
        benign_per_step=6,
        attackers=("bob", "mallory"),
        attacker_switch="per_window",
        benign=("alice", "bob", "dave"),
        delegations=("dave:alice",),
        seed_start=SEED_BANDS["train"][0],
        episodes=1,
    )


@pytest.fixture
def facts() -> PlatformFacts:
    loop = LiveDefenseLoop(
        live_app, config=LoopConfig(action_space="live_v3"), driver=_scenario().driver()
    )
    loop.reset(1)
    f = loop.platform_facts()
    loop.close()
    return f


def test_new_fields_default_off_and_narrower_layouts_ignore_them(facts):
    base = PlatformFacts.model_validate(
        facts.model_dump(mode="json", include={"project_id", "nodes", "time_fraction"})
    )
    assert not base.principal_block_long_available and base.flagged_volume == 0.0
    for space in ("sim", "live_v2"):  # v3 fields change nothing for sim / v2 policies
        np.testing.assert_array_equal(
            from_platform_facts(facts, space=space),
            from_platform_facts(
                facts.model_copy(update=dict.fromkeys(lay.LIVE_V3_DETECTOR_FEATURES, 0.0)),
                space=space,
            ),
        )
    o3, m3 = from_platform_facts(facts, space="live_v3"), mask_from_facts(facts, space="live_v3")
    assert o3.shape == (lay.LIVE_V3_OBS_DIM,) and m3.shape == (lay.LIVE_V3_N_ACTIONS,)
    for i, f in enumerate(lay.LIVE_V3_DETECTOR_FEATURES):
        assert o3[OBS_DIM + 1 + i] == pytest.approx(getattr(facts, f))


def test_live_loop_is_the_producer_of_the_v3_fields():
    """The loop's observation and mask equal the PlatformFacts mapping at every step, and
    the principal fields really carry the detector's view (attackers are flagged)."""
    loop = LiveDefenseLoop(
        live_app, config=LoopConfig(action_space="live_v3"), driver=_scenario().driver()
    )
    obs, mask = loop.reset(1)
    pf = loop.platform_facts()
    assert pf.flagged_principals > 0 and pf.principal_block_long_available
    np.testing.assert_array_equal(obs, from_platform_facts(pf, space="live_v3"))
    for action in (la.BLOCK_PRINCIPAL_LONG_ACTION, 0, la.BLOCK_TOP_PRINCIPAL_LONG_ACTION, 0, 0):
        t = loop.step(action)
        pf = loop.platform_facts()
        np.testing.assert_array_equal(
            np.asarray(t.next_obs, dtype=np.float32), from_platform_facts(pf, space="live_v3")
        )
        np.testing.assert_array_equal(
            np.asarray(t.action_mask), mask_from_facts(pf, space="live_v3")
        )
    assert pf.principal_block_active and pf.block_remaining > 0
    loop.close()


@pytest.mark.parametrize(
    ("favour", "name", "field"),
    [
        (lay.BLOCK_PRINCIPAL_LONG_ACTION, "block_principal_long", "principal_block_long_available"),
        (
            lay.BLOCK_TOP_PRINCIPAL_LONG_ACTION,
            "block_top_principal_long",
            "principal_block_top_long_available",
        ),
    ],
)
def test_v3_runner_recommends_a_long_block_only_when_facts_allow_it(
    sim_ckpt, tmp_path, facts, favour, name, field
):
    runner = PolicyRunner(_v3_ckpt(sim_ckpt, tmp_path / "v3.pt", favour=favour))
    assert runner.space == "live_v3"
    assert runner.policy_version.startswith(f"{lay.LIVE_V3_ENV_ID}@")
    off = runner.recommend(facts.model_copy(update={field: False}))
    assert off.action != name and all(s.action != name for s in off.top_actions)
    rec = runner.recommend(facts.model_copy(update={field: True}))
    assert rec.action == name and rec.node is None
    assert rec.caveat == LIVE_LAB_CAVEAT and rec.simulation_derived is True
    assert len(rec.observation) == lay.LIVE_V3_OBS_DIM
    # the canonical shared contract accepts the new action name
    assert SharedRecommendation.model_validate(rec.model_dump(mode="json")).action == name


def test_v3_explanation_names_the_new_actions_and_features(sim_ckpt, tmp_path, facts):
    runner = PolicyRunner(
        _v3_ckpt(sim_ckpt, tmp_path / "v3.pt", favour=lay.BLOCK_PRINCIPAL_LONG_ACTION)
    )
    rec, exp = runner.recommend_with_explanation(facts)
    assert exp.action == "block_principal_long" == rec.action
    from rl_defense.envs.defense_sim import GLOBAL_FEATURES

    globals_ = {c.feature for c in exp.top_contributions if c.node is None}
    assert globals_ <= {*GLOBAL_FEATURES, *lay.LIVE_V3_EXTRA_FEATURES}
    assert exp.caveat.startswith("Explains the lab")


def test_widened_v3_policy_recommends_like_the_sim_policy(sim_ckpt, tmp_path, facts):
    sim = PolicyRunner(sim_ckpt)
    wide = PolicyRunner(_v3_ckpt(sim_ckpt, tmp_path / "w.pt", favour=None))
    assert wide.recommend(facts).action == sim.recommend(facts).action
    assert wide.recommend(facts).node == sim.recommend(facts).node


def test_inference_does_not_import_the_live_lab(sim_ckpt, tmp_path):
    """Serving any layout needs no httpx/starlette (issue #335): inference and the mapping
    use rl_defense.layouts, never rl_defense.live."""
    path = _v3_ckpt(sim_ckpt, tmp_path / "core.pt", favour=None)
    code = f"""
import importlib.abc
import sys
class NoLab(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {{'httpx', 'starlette', 'fastapi'}} or fullname.startswith('rl_defense.live'):
            raise ImportError(fullname)
sys.meta_path.insert(0, NoLab())
from rl_defense.inference import PolicyRunner
PolicyRunner({str(path)!r})
assert not any(m.startswith('rl_defense.live') for m in sys.modules)
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=RL_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_layout_constants_are_the_live_ones():
    assert lay.DIMS["live_v3"] == (la.LIVE_V3_OBS_DIM, la.LIVE_V3_N_ACTIONS) == (55, 25)
    assert lay.LIVE_V3_EXTRA_FEATURES == la.LIVE_V3_EXTRA_FEATURES
    assert {lay.live_decode_action(a)[0] for a in (22, 23, 24)} == {
        "block_principal",
        "block_principal_long",
        "block_top_principal_long",
    }


def test_run_cli_drives_a_v3_checkpoint_in_its_own_layout(sim_ckpt, tmp_path, capsys):
    ckpt = _v3_ckpt(sim_ckpt, tmp_path / "v3.pt", favour=None)
    out = tmp_path / "t.jsonl"
    assert (
        live_run.main(
            ["--checkpoint", str(ckpt), "--episodes", "1", "--horizon", "5", "--out", str(out)]
        )
        == 0
    )
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert rows and len(rows[0]["obs"]) == lay.LIVE_V3_OBS_DIM
    stdout = capsys.readouterr().out
    assert "does not establish its training origin" in stdout
    assert "trained on the abstract simulator" not in stdout


def test_served_action_is_the_evaluated_greedy_action(sim_ckpt, tmp_path, facts):
    """A checkpoint selected with a noop margin abstains when serving exactly as it did in
    evaluation; with margin 0 the served action is the plain argmax."""
    facts = facts.model_copy(update={"principal_block_long_available": True})
    path = _v3_ckpt(sim_ckpt, tmp_path / "m.pt", favour=lay.BLOCK_PRINCIPAL_LONG_ACTION)
    agent, _ = load_checkpoint(path)
    obs = from_platform_facts(facts, space="live_v3")
    mask = mask_from_facts(facts, space="live_v3")
    q = np.where(mask, agent.q_values(obs), -np.inf)
    best = int(np.argmax(q))
    gap = float(q[best] - q[0])
    agent.config = agent.config.model_copy(update={"noop_margin": gap + 1.0})
    save_checkpoint(
        agent, tmp_path / "abstain.pt", seed=0, steps=1, train_configs={}, env_id=lay.LIVE_V3_ENV_ID
    )
    plain = PolicyRunner(path).recommend(facts)
    abstain_runner = PolicyRunner(tmp_path / "abstain.pt")
    abstain, explanation = abstain_runner.recommend_with_explanation(facts)
    assert best == lay.BLOCK_PRINCIPAL_LONG_ACTION and plain.action == "block_principal_long"
    assert abstain.action == "noop"
    assert abstain.top_actions[0].action == "block_principal_long"
    assert abstain.q_margin >= 0
    assert [a.q_value for a in abstain.top_actions] == sorted(
        [a.q_value for a in abstain.top_actions], reverse=True
    )
    assert explanation.action == abstain.action
    assert explanation.runner_up == "block_principal_long"
    assert explanation.recommendation_id == abstain.id
    assert explanation.margin == pytest.approx(float(q[0] - q[best]), abs=1e-5)
