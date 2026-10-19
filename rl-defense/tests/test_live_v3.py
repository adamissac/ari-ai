"""Live action space v3: delegated reads, long/targeted blocks, detector features, margin.

Everything runs real requests against the owned demo app (examples/payments-lite) through
the defensive gateway. No test runs an episode on configs/live/holdout_v3, which is
reserved for the one final v3 run (results/live-retrain-v3/PROVENANCE.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import N_ACTIONS, NOOP_ACTION, OBS_DIM, encode_action
from rl_defense.live import evaluate as ev
from rl_defense.live.actions import (
    BLOCK_PRINCIPAL_ACTION,
    BLOCK_PRINCIPAL_LONG_ACTION,
    BLOCK_TOP_PRINCIPAL_LONG_ACTION,
    FEATURE_INDEX,
    LIVE_V2_N_ACTIONS,
    LIVE_V2_OBS_DIM,
    LIVE_V3_N_ACTIONS,
    LIVE_V3_OBS_DIM,
    as_space,
    expand_agent_to_v2,
    live_decode_action,
)
from rl_defense.live.adversary import live_app
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.live.topology import load_topology
from rl_defense.train import train

TRAIN0 = SEED_BANDS["train"][0]


@pytest.fixture(scope="module")
def topo():
    return load_topology()


@pytest.fixture(scope="module")
def sim_ckpt(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("sim3")
    train(
        load_configs(default_config_paths("train")), seed=0, steps=2000, run_dir=d, log_every=2000
    )
    return d / "ddqn_seed0.pt"


def _sc(**kw) -> LiveScenario:
    base = {
        "name": "t3",
        "split": "train",
        "schedule": "always",
        "attack_per_step": 4,
        "benign_per_step": 6,
        "seed_start": TRAIN0,
        "episodes": 1,
    }
    return LiveScenario(**{**base, **kw})


def _loop(sc: LiveScenario, **cfg) -> LiveDefenseLoop:
    return LiveDefenseLoop(
        live_app, config=LoopConfig(action_space="live_v3", **cfg), driver=sc.driver()
    )


def _f(obs, name: str) -> float:  # noqa: ANN001
    return float(obs[FEATURE_INDEX[name]])


# ------------------------------------------------------------------ delegated reads
def test_delegate_reads_are_benign_but_flagged_by_the_detector(topo):
    """A bookkeeper's authorized read of a client's payment really returns 200, is labelled
    benign, and the operator's detector still flags it as cross-tenant."""
    sc = _sc(
        attack_per_step=0,
        benign=("alice", "dave"),
        delegations=("dave:alice",),
        delegate_per_step=2,
    )
    gw = DefensiveGateway(live_app(), topo, DefenseControls())
    drv = sc.driver()
    drv.reset(0)
    drv.run_window(gw)
    deleg = [r for r in gw.records if r.actor == "cus_dave" and r.cross_tenant_attempt]
    flagged = gw.flagged_principals()
    gw.close()
    assert len(deleg) == 2 and all(r.status == 200 and not r.is_attack for r in deleg)
    assert flagged == {"cus_dave": {"payments"}}
    assert drv.benign_norm == 6 + 2


def test_blanket_blocking_has_a_real_availability_cost_without_any_attack():
    """No attack at all: noop blocks nothing; 'block whoever is flagged' blocks a
    legitimate delegate (its delegated reads and its own payments reads)."""
    sc = _sc(
        schedule="bursty",
        p_start=0.0,
        attack_per_step=0,
        horizon=10,
        benign=("alice", "bob", "dave"),
        delegations=("dave:alice",),
        episodes=2,
    )
    blk = ev.summarize(
        ev.run_policy(ev.always_block_principal, [sc], live_app, action_space="live_v3")
    )
    noop = ev.summarize(ev.run_policy(ev.noop_policy, [sc], live_app, action_space="live_v3"))
    assert noop["availability"] == 1.0 and noop["false_disruption"] == 0.0
    assert blk["false_disruption"] > 0.1 and blk["availability"] < 0.9
    assert blk["compromise_rate"] is None  # nothing to compromise


def test_no_delegations_keeps_v1_v2_scenario_hashes_and_traffic(topo):
    """v3 fields are omitted from the hash at their defaults and draw no RNG."""
    report = json.loads(
        (Path(__file__).parents[1] / "results/live-retrain-v2/promotion_report.json").read_text()
    )
    for split, sub in (("train", "train"), ("val", "val"), ("holdout", "holdout_v2")):
        got = {s.name: s.config_hash() for s in load_scenarios(split, subdir=sub)}
        assert got == report["splits"][split]
    sc = load_scenarios("holdout", subdir="holdout_v2")[0]
    a, b = sc.driver(), sc.driver()
    b.delegates, b.delegate_per_step = (), 3  # unused without delegates

    def trace(d) -> list[tuple]:  # noqa: ANN001
        gw = DefensiveGateway(live_app(), topo, DefenseControls())
        d.reset(11)
        for _ in range(5):
            d.run_window(gw)
        out = [(r.actor, r.path, r.is_attack) for r in gw.records]
        gw.close()
        return out

    assert trace(a) == trace(b)


# ------------------------------------------------------------------ long / extended blocks
def test_long_block_closes_the_identity_switch_leak():
    """Two identities alternating per window, constant attack: re-blocking with the short
    control leaks every time a block lapses; long blocks hold both identities."""

    def compromised(action: int) -> int:
        sc = _sc(attackers=("bob", "carol"), benign=("alice", "bob", "carol"), horizon=12)
        loop = _loop(sc)
        obs, mask = loop.reset(0)
        total = 0
        for _ in range(12):
            t = loop.step(action if mask[action] else NOOP_ACTION)
            total += t.outcome.compromised_reads
            mask = np.asarray(t.action_mask)
        loop.close()
        return total

    short, long_ = compromised(BLOCK_PRINCIPAL_ACTION), compromised(BLOCK_PRINCIPAL_LONG_ACTION)
    assert long_ < short
    # each identity leaks only in the one window before it was first seen and blocked
    assert long_ <= 4


def test_long_block_extends_a_short_block_and_short_never_shortens_long():
    loop = _loop(_sc(), block_duration=3, block_long_duration=10)
    _, mask = loop.reset(1)
    t = loop.step(BLOCK_PRINCIPAL_ACTION)
    assert loop._timers.block[("cus_bob", "payments")] == 2  # 3 windows, one elapsed
    # bob keeps attacking while blocked (403s) and stays flagged: short is masked, long is
    # valid as an extension
    assert not t.action_mask[BLOCK_PRINCIPAL_ACTION] and t.action_mask[BLOCK_PRINCIPAL_LONG_ACTION]
    t = loop.step(BLOCK_PRINCIPAL_LONG_ACTION)
    assert t.outcome.action_label == "block_principal_long:cus_bob"
    assert loop._timers.block[("cus_bob", "payments")] == 9
    assert _f(t.next_obs, "block_remaining") == pytest.approx(0.9)
    assert not t.action_mask[BLOCK_PRINCIPAL_LONG_ACTION]  # 9 > block_duration windows left
    loop._flagged = {"cus_bob": {"payments"}}
    loop._apply_action(BLOCK_PRINCIPAL_ACTION)
    assert loop._timers.block[("cus_bob", "payments")] == 9
    loop.close()


def test_top_target_spares_the_delegate_seen_in_the_same_window():
    """Attacker and delegate are flagged in the same window. The 'all flagged' long block
    also blocks the delegate; the heavy-hitter block only blocks the attacker."""

    def run(action: int) -> tuple[str, int, int]:
        sc = _sc(
            attackers=("mallory",),
            attack_per_step=6,
            benign=("alice", "dave"),
            delegations=("dave:alice",),
        )
        loop = _loop(sc)
        _, mask = loop.reset(3)
        assert mask[action]
        t = loop.step(action)
        o = t.outcome
        loop.close()
        return o.action_label, o.compromised_reads, o.benign_blocked

    all_lbl, all_comp, all_blocked = run(BLOCK_PRINCIPAL_LONG_ACTION)
    top_lbl, top_comp, top_blocked = run(BLOCK_TOP_PRINCIPAL_LONG_ACTION)
    assert all_lbl == "block_principal_long:cus_dave,cus_mallory"
    assert top_lbl == "block_top_principal_long:cus_mallory"
    assert all_comp == 0 and top_comp == 0
    assert top_blocked == 0 < all_blocked


# ------------------------------------------------------------------ detector features
def test_v3_features_describe_the_flagged_principals():
    out = _loop(_sc(attackers=("mallory",), benign=("alice",), attack_per_step=6))
    obs, _ = out.reset(0)
    out.close()
    assert _f(obs, "flagged_principals") == pytest.approx(1 / 3)
    assert _f(obs, "flagged_volume") == pytest.approx(1.0)
    assert _f(obs, "flagged_own_share") == 0.0  # an outsider reads none of its own data
    assert _f(obs, "flagged_top_share") == 1.0
    assert _f(obs, "flagged_repeat") == 0.0

    ins = _loop(_sc(benign=("alice", "bob"), benign_per_step=20))
    obs, _ = ins.reset(0)
    assert 0.0 < _f(obs, "flagged_own_share") < 1.0  # bob is also a customer
    ins.step(BLOCK_PRINCIPAL_ACTION)
    for _ in range(3):
        t = ins.step(NOOP_ACTION)
    ins.close()
    assert _f(t.next_obs, "flagged_repeat") == 1.0  # flagged again after its block lapsed


def test_v3_loop_is_a_strict_extension_of_v2():
    sc = _sc(delegations=("dave:alice",), benign=("alice", "bob", "dave"))
    v2 = LiveDefenseLoop(live_app, config=LoopConfig(action_space="live_v2"), driver=sc.driver())
    v3 = _loop(sc)
    o2, m2 = v2.reset(4)
    o3, m3 = v3.reset(4)
    t2, t3 = v2.step(BLOCK_PRINCIPAL_ACTION), v3.step(BLOCK_PRINCIPAL_ACTION)
    v2.close()
    v3.close()
    assert o3.shape == (LIVE_V3_OBS_DIM,) and m3.shape == (LIVE_V3_N_ACTIONS,)
    np.testing.assert_array_equal(o2, o3[:LIVE_V2_OBS_DIM])
    np.testing.assert_array_equal(m2, m3[:LIVE_V2_N_ACTIONS])
    assert t2.outcome.model_dump() == t3.outcome.model_dump()
    assert t2.next_obs == t3.next_obs[:LIVE_V2_OBS_DIM]
    assert live_decode_action(BLOCK_TOP_PRINCIPAL_LONG_ACTION) == ("block_top_principal_long", None)


# ------------------------------------------------------------------ agents
def test_widened_agents_act_exactly_like_the_narrower_ones(sim_ckpt):
    from rl_defense.checkpoint import load_checkpoint

    sim, _ = load_checkpoint(sim_ckpt)
    v2 = expand_agent_to_v2(sim)
    v3_from_sim, v3_from_v2 = as_space(sim, "live_v3"), as_space(v2, "live_v3")
    rng = np.random.default_rng(0)
    for _ in range(200):
        obs = rng.random(LIVE_V3_OBS_DIM).astype(np.float32)
        mask = rng.random(LIVE_V3_N_ACTIONS) < 0.7
        mask[NOOP_ACTION] = True
        a = sim.greedy_action(obs[:OBS_DIM], mask[:N_ACTIONS])
        assert v3_from_sim.greedy_action(obs, mask) == a
        assert v3_from_v2.greedy_action(obs, mask) == a
    with pytest.raises(ValueError, match="cannot narrow"):
        as_space(v3_from_sim, "live_v2")


def test_noop_margin_abstains_only_on_near_ties(sim_ckpt):
    from rl_defense.checkpoint import load_checkpoint, save_checkpoint

    agent, _ = load_checkpoint(sim_ckpt)
    rng = np.random.default_rng(1)
    obs = rng.random(OBS_DIM).astype(np.float32)
    mask = np.ones(N_ACTIONS, dtype=bool)
    q = agent.q_values(obs)
    best = int(np.argmax(q))
    gap = float(q[best] - q[NOOP_ACTION])
    assert agent.config.noop_margin == 0.0 and agent.greedy_action(obs, mask) == best
    if best != NOOP_ACTION:
        agent.config = agent.config.model_copy(update={"noop_margin": gap + 1e-3})
        assert agent.greedy_action(obs, mask) == NOOP_ACTION
        agent.config = agent.config.model_copy(update={"noop_margin": max(gap - 1e-3, 1e-6)})
        assert agent.greedy_action(obs, mask) == best
    # persisted through the hash-verified checkpoint
    agent.config = agent.config.model_copy(update={"noop_margin": 0.3})
    p = Path(str(sim_ckpt).replace(".pt", "_m.pt"))
    save_checkpoint(agent, p, seed=0, steps=1, train_configs={})
    back, _ = load_checkpoint(p)
    assert back.config.noop_margin == 0.3


# ------------------------------------------------------------------ rules
def test_v3_rules_use_every_new_control():
    sc = _sc(attackers=("mallory",), benign=("alice", "dave"), delegations=("dave:alice",))
    loop = _loop(sc)
    obs, mask = loop.reset(3)
    loop.close()
    base = {"isolate_anomaly": 0.6, "rate_limit_alerts": 1.1, "monitor_anomaly": 1.1}

    def pick(**kw) -> int:
        return ev.rules_policy({**base, "block_anomaly": 0.1, **kw})(obs, mask)

    assert pick(long_mode="never") == BLOCK_PRINCIPAL_ACTION
    assert pick(long_mode="always") == BLOCK_PRINCIPAL_LONG_ACTION
    assert pick(long_mode="always", long_target="top") == BLOCK_TOP_PRINCIPAL_LONG_ACTION
    assert pick(long_mode="repeat") == BLOCK_PRINCIPAL_ACTION  # nobody blocked before
    assert pick(long_mode="outsider") == BLOCK_PRINCIPAL_ACTION  # dave reads his own data
    assert pick(long_mode="always", block_min_volume=0.99) != BLOCK_PRINCIPAL_LONG_ACTION
    # the same rules inside the v2 loop never see the v3 controls
    v2_obs, v2_mask = obs[:LIVE_V2_OBS_DIM], mask[:LIVE_V2_N_ACTIONS]
    assert (
        ev.rules_policy({**base, "block_anomaly": 0.1, "long_mode": "always"})(v2_obs, v2_mask)
        == BLOCK_PRINCIPAL_ACTION
    )
    assert ev.always_block_top_principal_long(obs, mask) == BLOCK_TOP_PRINCIPAL_LONG_ACTION
    assert ev.always_block_top_principal_long(v2_obs, v2_mask) == NOOP_ACTION


def test_tune_rules_v3_on_train_only_covers_the_new_grid():
    tr = [_sc(horizon=5, delegations=("dave:alice",), benign=("alice", "bob", "dave"))]
    base_grid = {"isolate_anomaly": (0.6,), "rate_limit_alerts": (1.1,), "monitor_anomaly": (1.1,)}
    grid = {
        "block_anomaly": (0.1,),
        "block_min_volume": (0.0,),
        "long_mode": ("never", "always"),
        "long_target": ("all", "top"),
    }
    import unittest.mock as um

    with um.patch.object(ev, "RULES_BLOCK_GRID", (0.1, 1.1)):
        params, table = ev.tune_rules_v3(tr, live_app, episodes=1, grid=grid, base_grid=base_grid)
    assert {r["stage"] for r in table} == {1, 2}
    assert {r.get("long_target") for r in table if r["stage"] == 2} == {"all", "top"}
    assert len([r for r in table if r["stage"] == 2]) == 3  # never × top is skipped
    assert params in [
        {k: v for k, v in r.items() if k not in ("train_reward", "stage")} for r in table
    ]
    with pytest.raises(ValueError, match="train"):
        ev.tune_rules_v3([_sc(split="val", seed_start=SEED_BANDS["val"][0])], live_app)


# ------------------------------------------------------------------ holdout v3 hygiene
def test_holdout_v3_is_new_and_disjoint_from_everything_else():
    ho3 = load_scenarios("holdout", subdir="holdout_v3")
    others = [
        *load_scenarios("holdout"),
        *load_scenarios("holdout", subdir="holdout_v2"),
        *load_scenarios("train"),
        *load_scenarios("train", subdir="train_v3"),
        *load_scenarios("val"),
        *load_scenarios("val", subdir="val_v3"),
    ]
    assert {s.name for s in ho3}.isdisjoint({s.name for s in others})
    assert {x for s in ho3 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    assert all(s.delegations for s in ho3)
    for s in ho3:
        s.driver()  # identities and delegations resolve


def test_pipeline_v3_smoke(sim_ckpt, tmp_path, monkeypatch):
    """End to end in live_v3 on tiny budgets. Uses the (already exposed) v2 holdout dir:
    CI must never evaluate configs/live/holdout_v3."""
    import argparse

    from rl_defense.live import pipeline
    from rl_defense.live.experience import load_dataset

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
        action_space="live_v3",
        holdout_dir="holdout_v2",
        train_dir="train_v3",
        val_dir="val_v3",
        noop_margins="0,0.2",
    )
    r = pipeline.run(args)
    assert r["action_space"] == "live_v3" and r["requires_human_approval"] is True
    assert {
        "threshold_rules_short_only",
        "always_block_principal_long",
        "always_block_top_principal_long",
    } <= set(r["policies"])
    assert r["noop_margins"] == [0.0, 0.2] and r["rounds"][0]["noop_margin"] in (0.0, 0.2)
    recs, m = load_dataset(tmp_path / "run" / "experience_round1.jsonl")
    assert m["action_space"] == "live_v3" and len(recs[0]["obs"]) == LIVE_V3_OBS_DIM
    cand = json.loads((tmp_path / "run" / "candidate_round1.manifest.json").read_text())
    assert cand["env_id"] == "LiveDefense-payments-lite-v3" and cand["n_actions"] == 25
    assert cand["ddqn_config"]["noop_margin"] == cand["retrain"]["selected_noop_margin"]


def test_raise_monitoring_has_no_containment_effect_live():
    """The diagnosis behind the noop margin: raising monitoring changes only the anomaly
    score the detector reports; compromise and blocked traffic are identical to noop."""

    def run(action: int):  # noqa: ANN202
        loop = _loop(_sc(benign=("alice", "bob")))
        loop.reset(5)
        t = loop.step(action)
        loop.close()
        return t

    mon, noop = run(encode_action("raise_monitoring", 3)), run(NOOP_ACTION)
    assert mon.outcome.compromised_reads == noop.outcome.compromised_reads > 0
    assert mon.outcome.benign_blocked == noop.outcome.benign_blocked == 0
    assert mon.reward == pytest.approx(noop.reward - 0.02)  # only the action cost differs
    pay = 9 * 3 + 1  # payments anomaly_score
    assert mon.next_obs[pay] > noop.next_obs[pay]
