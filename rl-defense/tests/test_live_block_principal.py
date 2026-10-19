"""block_principal (live action space v2): real enforcement, loop semantics, gate behavior.

Everything here runs real requests against the owned demo app (examples/payments-lite)
through the defensive gateway; nothing is mocked except where a test says so.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from payments_lite.app import create_app

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, NOOP_ACTION, OBS_DIM, encode_action
from rl_defense.live import evaluate as ev
from rl_defense.live.actions import (
    BLOCK_PRINCIPAL_ACTION,
    LIVE_V2_N_ACTIONS,
    LIVE_V2_OBS_DIM,
    expand_agent_to_v2,
)
from rl_defense.live.adversary import TrafficDriver, live_app
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.live.topology import load_topology
from rl_defense.train import train


@pytest.fixture(scope="module")
def topo():
    return load_topology()


@pytest.fixture(scope="module")
def sim_ckpt(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sim")
    train(
        load_configs(default_config_paths("train")), seed=0, steps=2000, run_dir=d, log_every=2000
    )
    return d / "ddqn_seed0.pt"


def _v2_loop(**driver_kw) -> LiveDefenseLoop:
    return LiveDefenseLoop(
        live_app, config=LoopConfig(action_space="live_v2"), driver=TrafficDriver(**driver_kw)
    )


# ------------------------------------------------------------------ gateway enforcement
def test_block_principal_stops_attacker_and_spares_other_tenants(topo):
    """Blocking cus_bob on payments: every attack is a real 403 with no data; Alice's
    traffic and Bob's own /me (api node) still reach the app."""
    gw = DefensiveGateway(
        create_app(), topo, DefenseControls(blocked_principals={"cus_bob": ["payments"]})
    )
    TrafficDriver(seed=3, benign_per_step=30).run_window(gw)
    attack = [r for r in gw.records if r.is_attack]
    alice = [r for r in gw.records if not r.is_attack and r.actor == "cus_alice"]
    bob_me = [r for r in gw.records if not r.is_attack and r.actor == "cus_bob" and r.node == "api"]
    bob_pay = [
        r for r in gw.records if not r.is_attack and r.actor == "cus_bob" and r.node == "payments"
    ]
    gw.close()
    assert attack and all(
        r.status == 403 and r.blocked_reason == "principal_blocked" for r in attack
    )
    assert sum(r.compromised for r in attack) == 0
    assert alice and all(r.allowed and r.status == 200 for r in alice)
    assert bob_me and all(r.allowed for r in bob_me)
    # honest collateral: the attacker's own tenant loses its payments reads while blocked
    assert bob_pay and all(r.blocked_reason == "principal_blocked" for r in bob_pay)


def test_block_follows_the_principal_across_rotated_tokens(topo):
    """The block is keyed by principal, so rotating to another valid token does not help."""
    gw = DefensiveGateway(
        live_app(), topo, DefenseControls(blocked_principals={"cus_bob": ["payments"]})
    )
    for tok in ("fixture-token-bob", "fixture-token-bob-2", "fixture-token-bob-3"):
        r = gw.request("GET", "/payments/pay_a1", actor="cus_bob", token=tok, is_attack=True)
        assert r.status == 403 and not r.compromised
    # an unblocked tenant is unaffected and its cross-tenant read is still a real compromise
    r = gw.request("GET", "/payments/pay_a1", actor="cus_carol", token="fixture-token-carol")
    gw.close()
    assert r.status == 200 and r.compromised


def test_isolate_still_dominates_principal_block(topo):
    gw = DefensiveGateway(
        create_app(),
        topo,
        DefenseControls(isolated={"payments": True}, blocked_principals={"cus_bob": ["payments"]}),
    )
    r = gw.request("GET", "/payments/pay_a1", actor="cus_bob", token="fixture-token-bob")
    gw.close()
    assert r.status == 503 and r.blocked_reason == "isolated"


# ------------------------------------------------------------------ loop semantics
def test_v2_loop_shapes_and_sim_loop_unchanged():
    v1 = LiveDefenseLoop(create_app)
    o1, m1 = v1.reset(5)
    v1.close()
    v2 = _v2_loop()
    o2, m2 = v2.reset(5)
    v2.close()
    assert o1.shape == (OBS_DIM,) and m1.shape == (N_ACTIONS,)
    assert o2.shape == (LIVE_V2_OBS_DIM,) and m2.shape == (LIVE_V2_N_ACTIONS,)
    np.testing.assert_array_equal(o1, o2[:OBS_DIM])
    np.testing.assert_array_equal(m1, m2[:N_ACTIONS])


def test_block_action_targets_flagged_principal_for_fixed_duration():
    loop = _v2_loop(schedule="always")
    _, mask = loop.reset(1)
    assert mask[BLOCK_PRINCIPAL_ACTION], "warm-up window flagged cus_bob"
    t = loop.step(BLOCK_PRINCIPAL_ACTION)
    assert t.outcome.action_label == "block_principal:cus_bob"
    assert t.outcome.compromised_reads == 0 and t.outcome.attack_requests > 0
    assert t.next_obs[OBS_DIM] == 1.0 and not t.action_mask[BLOCK_PRINCIPAL_ACTION]
    comp = [loop.step(NOOP_ACTION).outcome.compromised_reads for _ in range(3)]
    loop.close()
    # blocked for block_duration=3 windows in total, then the BOLA is open again
    assert comp[:2] == [0, 0] and comp[2] > 0


def test_block_beats_isolate_on_availability_under_attack():
    """Measured, same traffic: both contain the attack; the principal block keeps more
    legitimate traffic flowing than isolating the payments node."""

    def run(action: int) -> tuple[int, int, int]:
        loop = _v2_loop(schedule="always", benign_per_step=20)
        loop.reset(2)
        o = loop.step(action).outcome
        loop.close()
        return o.compromised_reads, o.benign_blocked, o.benign_requests

    iso = run(encode_action("isolate", 3))
    blk = run(BLOCK_PRINCIPAL_ACTION)
    assert iso[0] == 0 and blk[0] == 0
    assert iso[2] == blk[2]  # paired traffic
    assert blk[1] < iso[1]


def test_block_is_masked_without_a_flagged_principal():
    loop = _v2_loop(attack_per_step=0)
    _, mask = loop.reset(0)
    assert not mask[BLOCK_PRINCIPAL_ACTION]
    t = loop.step(BLOCK_PRINCIPAL_ACTION)  # invalid -> applied as noop
    loop.close()
    assert t.action == NOOP_ACTION


def test_second_identity_needs_its_own_block():
    """Two attacker identities alternating per window: blocking the one just seen leaves
    the other open, so detection-driven re-blocking is required."""
    sc = LiveScenario(
        name="t",
        split="holdout",
        schedule="always",
        attack_per_step=4,
        benign_per_step=4,
        seed_start=SEED_BANDS["holdout"][0],
        episodes=1,
        attackers=("bob", "carol"),
        benign=("alice", "bob", "carol"),
    )
    loop = LiveDefenseLoop(live_app, config=LoopConfig(action_space="live_v2"), driver=sc.driver())
    loop.reset(0)  # warm-up window 0 -> bob
    t1 = loop.step(BLOCK_PRINCIPAL_ACTION)  # blocks bob; window 1 -> carol
    t2 = loop.step(BLOCK_PRINCIPAL_ACTION)  # blocks carol; window 2 -> bob (still blocked)
    loop.close()
    assert t1.outcome.action_label == "block_principal:cus_bob" and t1.outcome.compromised_reads > 0
    assert t2.outcome.action_label == "block_principal:cus_carol"
    assert t2.outcome.compromised_reads == 0


# ------------------------------------------------------------------ agent widening
def test_widened_sim_agent_acts_exactly_like_the_sim_agent(sim_ckpt):
    from rl_defense.checkpoint import load_checkpoint

    agent, _ = load_checkpoint(sim_ckpt)
    wide = expand_agent_to_v2(agent)
    rng = np.random.default_rng(0)
    for _ in range(200):
        obs = rng.random(OBS_DIM).astype(np.float32)
        mask = rng.random(N_ACTIONS) < 0.7
        mask[NOOP_ACTION] = True
        a = agent.greedy_action(obs, mask)
        for extra in (0.0, 1.0):
            o2 = np.append(obs, np.float32(extra)).astype(np.float32)
            assert wide.greedy_action(o2, np.append(mask, True)) == a


def test_v2_checkpoint_roundtrip_and_lab_only(sim_ckpt, tmp_path):
    from rl_defense.checkpoint import load_checkpoint, save_checkpoint
    from rl_defense.inference import PolicyRunner

    agent, _ = load_checkpoint(sim_ckpt)
    wide = expand_agent_to_v2(agent)
    m = save_checkpoint(
        wide,
        tmp_path / "v2.pt",
        seed=0,
        steps=1,
        train_configs={},
        env_id="LiveDefense-payments-lite-v2",
    )
    back, bm = load_checkpoint(tmp_path / "v2.pt")
    assert (back.obs_dim, back.n_actions) == (LIVE_V2_OBS_DIM, LIVE_V2_N_ACTIONS)
    assert bm["checkpoint_sha256"] == m["checkpoint_sha256"]
    assert back.disruptive[BLOCK_PRINCIPAL_ACTION]
    with pytest.raises(ValueError, match="lab-only"):
        PolicyRunner(tmp_path / "v2.pt")
    with pytest.raises(ValueError, match="does not match env"):
        save_checkpoint(wide, tmp_path / "bad.pt", seed=0, steps=1, train_configs={})


# ------------------------------------------------------------------ policies and gate
def test_sim_policies_cannot_block_in_v2():
    obs = np.zeros(LIVE_V2_OBS_DIM, dtype=np.float32)
    mask = np.zeros(LIVE_V2_N_ACTIONS, dtype=bool)
    mask[BLOCK_PRINCIPAL_ACTION] = True
    mask[NOOP_ACTION] = True
    seen = {}

    def spy(o, m):
        seen["shape"] = (o.shape, m.shape)
        return NOOP_ACTION

    assert ev.sim_view(spy)(obs, mask) == NOOP_ACTION
    assert seen["shape"] == ((OBS_DIM,), (N_ACTIONS,))
    assert ev.always_block_principal(obs, mask) == BLOCK_PRINCIPAL_ACTION


def test_rules_with_block_threshold_use_the_new_control():
    loop = _v2_loop(schedule="always")
    obs, mask = loop.reset(1)
    loop.close()
    pol = ev.rules_policy(
        {
            "isolate_anomaly": 0.3,
            "rate_limit_alerts": 1.1,
            "monitor_anomaly": 1.1,
            "block_anomaly": 0.1,
        }
    )
    assert pol(obs, mask) == BLOCK_PRINCIPAL_ACTION
    never = ev.rules_policy(
        {
            "isolate_anomaly": 0.3,
            "rate_limit_alerts": 1.1,
            "monitor_anomaly": 1.1,
            "block_anomaly": 1.1,
        }
    )
    assert never(obs, mask) != BLOCK_PRINCIPAL_ACTION


def test_gate_on_measured_v2_episodes():
    """Measured episodes under constant attack. Blocking principals contains the attack at
    a fraction of isolation's availability cost; when the attacker is an outsider tenant
    with no legitimate traffic, it costs nothing and clears the gate's availability floor.
    The gate still rejects a candidate that is not better than the deployed policy."""

    def sc(**kw) -> LiveScenario:
        return LiveScenario(
            name="gate",
            split="holdout",
            horizon=10,
            schedule="always",
            attack_per_step=4,
            benign_per_step=8,
            seed_start=SEED_BANDS["holdout"][0],
            episodes=3,
            **kw,
        )

    def run(pol, scen):  # noqa: ANN001
        return ev.run_policy(pol, [scen], live_app, action_space="live_v2")

    insider = sc()  # attacker = bob, who is also a legitimate customer
    blk, iso = run(ev.always_block_principal, insider), run(ev.always_isolate_payments, insider)
    sb, si = ev.summarize(blk), ev.summarize(iso)
    assert sb["availability"] > si["availability"] + 0.15
    assert sb["compromise_rate"] < 0.5

    outsider = sc(attackers=("mallory",), rotate_tokens=True)
    block, noop = run(ev.always_block_principal, outsider), run(ev.noop_policy, outsider)
    so = ev.summarize(block)
    assert so["availability"] == 1.0 and so["compromise_rate"] < 0.5
    crit = ev.PromotionCriteria()
    ok = ev.promotion_decision(candidate=block, deployed=noop, rules=None, criteria=crit)
    by = {c["name"]: c["passed"] for c in ok["checks"]}
    assert by["availability_floor"] and by["paired_reward_gain_ci_low"]
    bad = ev.promotion_decision(candidate=noop, deployed=block, rules=None, criteria=crit)
    assert bad["decision"] == "reject"
    assert not {c["name"]: c["passed"] for c in bad["checks"]}["paired_reward_gain_ci_low"]


# ------------------------------------------------------------------ holdout v2 hygiene
def test_holdout_v2_is_new_and_disjoint_from_v1():
    v1 = load_scenarios("holdout")
    v2 = load_scenarios("holdout", subdir="holdout_v2")
    assert {s.name for s in v1}.isdisjoint({s.name for s in v2})
    seeds1 = {x for s in v1 for x in s.seeds()}
    seeds2 = {x for s in v2 for x in s.seeds()}
    assert seeds1.isdisjoint(seeds2)
    assert all(s.uses_extra_identities for s in v2)
    # v1 scenario hashes (recorded in results/live-retrain) are unchanged by the v2 fields
    assert {s.name: s.config_hash() for s in v1} == {
        "heavy_benign": "0b8def9bab338285",
        "low_and_slow": "efd5df0755d25d85",
        "rapid_bursts": "2dfd285c76f3ac63",
    }


def test_default_scenario_driver_reproduces_v1_traffic(topo):
    sc = load_scenarios("train")[0]
    legacy = TrafficDriver(
        benign_per_step=sc.benign_per_step,
        attack_per_step=sc.attack_per_step,
        schedule=sc.schedule,
        p_start=sc.p_start,
        p_stop=sc.p_stop,
        start_active=sc.start_active,
    )

    def trace(driver) -> list[tuple]:
        gw = DefensiveGateway(create_app(), topo, DefenseControls())
        driver.reset(7)
        for _ in range(6):
            driver.run_window(gw)
        out = [(r.actor, r.path, r.is_attack, r.status) for r in gw.records]
        gw.close()
        return out

    assert trace(sc.driver()) == trace(legacy)


def test_pipeline_v2_smoke(sim_ckpt, tmp_path, monkeypatch):
    """End to end in live_v2. Uses the (already exposed) v1 holdout dir on purpose: CI must
    never evaluate configs/live/holdout_v2, which is reserved for the one final v2 run."""
    import argparse

    from rl_defense.live import pipeline

    monkeypatch.setattr(
        ev,
        "RULES_GRID",
        {"isolate_anomaly": (0.3,), "rate_limit_alerts": (1.1,), "monitor_anomaly": (1.1,)},
    )
    monkeypatch.setattr(ev, "RULES_BLOCK_GRID", (0.2, 1.1))
    args = argparse.Namespace(
        base_checkpoint=str(sim_ckpt),
        base_steps=0,
        rounds=1,
        epsilons="0.5",
        updates=40,
        eval_every=20,
        val_episodes=1,
        train_episodes=1,
        holdout_episodes=1,
        rules_episodes=1,
        criteria=str(Path(pipeline.CONFIG_DIR) / "promotion.yaml"),
        seed=0,
        out=str(tmp_path / "run"),
        evidence_dir=None,
        action_space="live_v2",
        holdout_dir="holdout",
    )
    r = pipeline.run(args)
    assert r["action_space"] == "live_v2" and r["requires_human_approval"] is True
    assert {"always_block_principal", "threshold_rules_no_block"} <= set(r["policies"])
    assert "block_anomaly" in r["rules_params"]
    import json

    from rl_defense.live.experience import load_dataset

    recs, m = load_dataset(tmp_path / "run" / "experience_round1.jsonl")
    assert m["action_space"] == "live_v2"
    assert len(recs[0]["obs"]) == LIVE_V2_OBS_DIM
    assert any(x["action"] == BLOCK_PRINCIPAL_ACTION for x in recs), "ε explores the new action"
    cand = json.loads((tmp_path / "run" / "candidate_round1.manifest.json").read_text())
    assert cand["env_id"] == "LiveDefense-payments-lite-v2" and cand["n_actions"] == 23
