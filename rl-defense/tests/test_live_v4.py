"""Live v4: reward aligned with the gate, delegation-aware detector, multi-scenario val.

Everything runs real requests against the owned demo app (examples/payments-lite) through
the defensive gateway. No test runs an episode on configs/live/holdout_v4, which is
reserved for the one final v4 run (results/live-retrain-v4/PROVENANCE.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.live import evaluate as ev
from rl_defense.live.actions import BLOCK_PRINCIPAL_ACTION
from rl_defense.live.adversary import delegate_profile, delegation_grants, live_app
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.live.topology import load_topology
from rl_defense.train import train

TRAIN0 = SEED_BANDS["train"][0]
GRANTS = delegation_grants((delegate_profile("dave:alice"), delegate_profile("erin:carol")))


@pytest.fixture(scope="module")
def topo():
    return load_topology()


def _sc(**kw) -> LiveScenario:
    base = {
        "name": "t4",
        "split": "train",
        "schedule": "always",
        "attack_per_step": 4,
        "benign_per_step": 6,
        "seed_start": TRAIN0,
        "episodes": 1,
    }
    return LiveScenario(**{**base, **kw})


# ------------------------------------------------------------------ detector
def test_grant_table_is_the_scenarios_delegations():
    assert GRANTS == {"cus_dave": frozenset({"cus_alice"}), "cus_erin": frozenset({"cus_carol"})}
    sc = _sc(delegations=("dave:alice", "dave:bob"))
    assert delegation_grants(sc.driver().delegates) == {
        "cus_dave": frozenset({"cus_alice", "cus_bob"})
    }


def test_granted_read_is_not_flagged_and_ungranted_read_still_is(topo):
    """With the grant table, dave's read of alice's payment is authorized; his read of
    carol's (not granted) and bob's read of alice's are still cross-tenant attempts."""
    gw = DefensiveGateway(live_app(), topo, DefenseControls(), grants=GRANTS)
    ok = gw.request("GET", "/payments/pay_a1", actor="cus_dave", token="fixture-token-dave")
    rogue = gw.request("GET", "/payments/pay_c1", actor="cus_dave", token="fixture-token-dave")
    bob = gw.request("GET", "/payments/pay_a2", actor="cus_bob", token="fixture-token-bob")
    flagged = gw.flagged_principals()
    gw.close()
    assert ok.status == 200 and not ok.cross_tenant_attempt
    assert rogue.status == 200 and rogue.cross_tenant_attempt
    assert bob.cross_tenant_attempt
    assert flagged == {"cus_dave": {"payments"}, "cus_bob": {"payments"}}


def test_without_grants_the_v3_detector_is_unchanged(topo):
    gw = DefensiveGateway(live_app(), topo, DefenseControls())
    r = gw.request("GET", "/payments/pay_a1", actor="cus_dave", token="fixture-token-dave")
    gw.close()
    assert r.cross_tenant_attempt


def test_detector_never_reads_the_generator_label(topo):
    """Flipping ``is_attack`` changes nothing the detector reports: it depends only on the
    token's principal, the object's owner and the grant table."""
    out = []
    for label in (False, True):
        gw = DefensiveGateway(live_app(), topo, DefenseControls(), grants=GRANTS)
        a = gw.request(
            "GET", "/payments/pay_a1", actor="x", token="fixture-token-dave", is_attack=label
        )
        b = gw.request(
            "GET", "/payments/pay_c1", actor="x", token="fixture-token-dave", is_attack=label
        )
        out.append((a.cross_tenant_attempt, b.cross_tenant_attempt, gw.flagged_principals()))
        gw.close()
    assert out[0] == out[1] == (False, True, {"cus_dave": {"payments"}})


def test_aware_detector_removes_the_availability_cost_of_blanket_blocking():
    """The real effect, end to end: with no attack, 'block whoever is flagged' blocked the
    delegate under the v3 detector; with the grant table nobody is flagged, so nothing is
    blocked and the delegated reads go through."""
    sc = _sc(
        schedule="bursty",
        p_start=0.0,
        attack_per_step=0,
        horizon=10,
        benign=("alice", "bob", "dave"),
        delegations=("dave:alice",),
        delegate_burst_p=0.3,
        delegate_burst_size=3,
        episodes=2,
    )

    def run(overrides):  # noqa: ANN001, ANN202
        return ev.summarize(
            ev.run_policy(
                ev.always_block_principal_long,
                [sc],
                live_app,
                action_space="live_v3",
                loop_overrides=overrides,
            )
        )

    v3, v4 = run(None), run({"delegation_aware_detector": True})
    assert v3["availability"] < 0.9 and v3["false_disruption"] > 0.1
    assert v4["availability"] == 1.0 and v4["false_disruption"] == 0.0


def test_aware_detector_still_blocks_attackers_and_rogue_delegates():
    """Attacks are still caught: an outsider and a delegate reading outside its grant are
    flagged, and long-blocking them cuts compromise against noop on identical traffic."""
    sc = _sc(
        attack_per_step=4,
        benign=("alice", "carol", "dave"),
        attackers=("dave", "mallory"),
        attacker_switch="per_request",
        victims=("carol",),
        delegations=("dave:alice",),
        horizon=12,
        episodes=2,
    )
    kw = {"action_space": "live_v3", "loop_overrides": ev.V4_LOOP_OVERRIDES}
    noop = ev.summarize(ev.run_policy(ev.noop_policy, [sc], live_app, **kw))
    blk = ev.summarize(ev.run_policy(ev.always_block_principal_long, [sc], live_app, **kw))
    assert noop["compromise_rate"] == 1.0
    assert blk["compromise_rate"] < 0.3


def test_loop_passes_the_grants_only_when_enabled():
    sc = _sc(attack_per_step=0, benign=("alice", "dave"), delegations=("dave:alice",))
    for aware, flagged in ((False, {"cus_dave"}), (True, set())):
        loop = LiveDefenseLoop(
            live_app,
            config=LoopConfig(action_space="live_v3", delegation_aware_detector=aware),
            driver=sc.driver(),
        )
        loop.reset(0)
        loop.step(NOOP_ACTION)
        assert set(loop._gateway.flagged_principals()) == flagged
        loop.close()


# ------------------------------------------------------------------ reward
def test_reward_defaults_are_the_v3_values_and_v4_is_explicit():
    cfg = LoopConfig()
    assert (cfg.c_disrupt, cfg.c_impact, cfg.delegation_aware_detector) == (0.5, 1.0, False)
    assert ev.V4_LOOP_OVERRIDES == {"c_disrupt": 1.0, "delegation_aware_detector": True}


def test_c_disrupt_prices_a_blocked_legit_request_like_a_compromised_read():
    """Same traffic, same action: the disruption term doubles from 0.5 to 1.0, and at 1.0
    blocking the whole normalized legitimate volume costs exactly one full compromise."""
    sc = _sc(attack_per_step=0, benign=("alice", "dave"), delegations=("dave:alice",))
    comps = {}
    for c in (0.5, 1.0):
        loop = LiveDefenseLoop(
            live_app, config=LoopConfig(action_space="live_v3", c_disrupt=c), driver=sc.driver()
        )
        loop.reset(0)
        loop.step(BLOCK_PRINCIPAL_ACTION)  # blocks dave (flagged under the v3 detector)
        t = loop.step(NOOP_ACTION)
        comps[c] = t.reward_components
        blocked = t.outcome.benign_blocked
        loop.close()
    assert blocked > 0
    assert comps[1.0]["disruption"] == pytest.approx(2 * comps[0.5]["disruption"])
    assert comps[1.0]["disruption"] == pytest.approx(-blocked / sc.driver().benign_norm)


# ------------------------------------------------------------------ selection
def test_scenario_mean_weights_every_val_scenario_equally():
    a = _sc(name="a", split="val", seed_start=SEED_BANDS["val"][0], episodes=3, horizon=5)
    b = _sc(
        name="b", split="val", seed_start=SEED_BANDS["val"][0] + 100, episodes=1, horizon=5,
        attack_per_step=0,
    )  # fmt: skip
    rows = ev.run_policy(ev.noop_policy, [a, b], live_app, action_space="live_v3")
    by = ev.summarize_by_scenario(rows)
    assert ev.scenario_mean_reward(rows) == pytest.approx(
        (by["a"]["reward"] + by["b"]["reward"]) / 2
    )
    assert ev.scenario_mean_reward(rows) != pytest.approx(ev.summarize(rows)["reward"])


# ------------------------------------------------------------------ split hygiene
def test_val_v4_has_several_scenarios_in_the_val_band():
    va = load_scenarios("val", subdir="val_v4")
    assert len(va) >= 4 and all(s.split == "val" for s in va)
    v3 = {s.name: s.config_hash() for s in load_scenarios("val", subdir="val_v3")}
    assert all(v4.config_hash() == v3[v4.name] for v4 in va if v4.name in v3)
    for s in va:
        s.driver()


def test_holdout_v4_is_new_and_disjoint_from_everything_else():
    ho4 = load_scenarios("holdout", subdir="holdout_v4")
    others = [
        *load_scenarios("holdout"),
        *load_scenarios("holdout", subdir="holdout_v2"),
        *load_scenarios("holdout", subdir="holdout_v3"),
        *load_scenarios("train"),
        *load_scenarios("train", subdir="train_v3"),
        *load_scenarios("val"),
        *load_scenarios("val", subdir="val_v3"),
        *load_scenarios("val", subdir="val_v4"),
    ]
    assert len(ho4) == 3
    assert {s.name for s in ho4}.isdisjoint({s.name for s in others})
    assert {x for s in ho4 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    assert all(s.delegations for s in ho4)
    for s in ho4:
        s.driver()


# ------------------------------------------------------------------ pipeline
def test_pipeline_v4_smoke(tmp_path, monkeypatch):
    """End to end with the v4 flags on tiny budgets. Uses the (already exposed) v2 holdout
    dir: CI must never evaluate configs/live/holdout_v4."""
    from rl_defense.live import pipeline
    from rl_defense.live.experience import load_dataset

    train(
        load_configs(default_config_paths("train")),
        seed=0,
        steps=1000,
        run_dir=tmp_path / "sim",
        log_every=1000,
    )
    monkeypatch.setattr(
        ev,
        "RULES_GRID",
        {"isolate_anomaly": (0.6,), "rate_limit_alerts": (1.1,), "monitor_anomaly": (1.1,)},
    )
    monkeypatch.setattr(ev, "RULES_BLOCK_GRID", (0.2, 1.1))
    monkeypatch.setattr(
        ev,
        "RULES_V3_GRID",
        {
            "block_anomaly": (0.2,),
            "block_min_volume": (0.2,),
            "long_mode": ("never", "always"),
            "long_target": ("top",),
        },
    )
    args = argparse.Namespace(
        base_checkpoint=str(tmp_path / "sim" / "ddqn_seed0.pt"),
        base_steps=0,
        rounds=1,
        epsilons="0.5",
        updates=20,
        eval_every=10,
        val_episodes=1,
        train_episodes=1,
        holdout_episodes=1,
        rules_episodes=1,
        criteria=str(Path(pipeline.CONFIG_DIR) / "promotion.yaml"),
        seed=0,
        out=str(tmp_path / "run"),
        evidence_dir=None,
        action_space="live_v3",
        holdout_dir="holdout_v2",
        train_dir="train_v3",
        val_dir="val_v4",
        noop_margins="0,0.2",
        c_disrupt=1.0,
        delegation_aware_detector=True,
        val_selection="scenario_mean",
    )
    r = pipeline.run(args)
    assert r["loop_overrides"] == ev.V4_LOOP_OVERRIDES and r["val_selection"] == "scenario_mean"
    names = {s.name for s in load_scenarios("val", subdir="val_v4")}
    assert set(r["rounds"][0]["val_reward_by_scenario"]) == names
    by = r["rounds"][0]["val_reward_by_scenario"]
    assert r["rounds"][0]["val_reward"] == pytest.approx(sum(by.values()) / len(by), abs=1e-3)
    _, m = load_dataset(tmp_path / "run" / "experience_round1.jsonl")
    assert m["loop_overrides"] == ev.V4_LOOP_OVERRIDES
    cand = json.loads((tmp_path / "run" / "candidate_round1.manifest.json").read_text())
    assert cand["retrain"]["selection"] == "scenario_mean"
    assert cand["retrain"]["loop_overrides"] == ev.V4_LOOP_OVERRIDES
    assert "Loop overrides" in pipeline.render_markdown(r)
