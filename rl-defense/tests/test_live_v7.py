"""Live v7: platform-producible finding-severity context, and the v6 method trained in it.

No test runs an episode on configs/live/holdout_v7 (results/live-retrain-v7/PREREGISTRATION.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from rl_defense import platform_mapping as pm
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.live import evaluate as ev
from rl_defense.live import online
from rl_defense.live.adversary import live_app
from rl_defense.live.loop import (
    DEFAULT_FINDING_SEVERITY,
    LiveDefenseLoop,
    LoopConfig,
    platform_severity_context,
)
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.train import train

LEVELS = {0.0, *pm.SEVERITY_SCORE.values()}


def _sc(split="train", **kw) -> LiveScenario:  # noqa: ANN001
    base = {
        "name": f"t7_{split}",
        "split": split,
        "schedule": "always",
        "attack_per_step": 4,
        "benign_per_step": 6,
        "horizon": 6,
        "benign": ("alice", "bob", "dave"),
        "delegations": ("dave:alice",),
        "seed_start": SEED_BANDS[split][0],
        "episodes": 2,
    }
    return LiveScenario(**{**base, **kw})


def _loop(**cfg) -> LiveDefenseLoop:  # noqa: ANN003
    return LiveDefenseLoop(
        live_app,
        config=LoopConfig(horizon=6, action_space="live_v3", **ev.V4_LOOP_OVERRIDES, **cfg),
        driver=_sc().driver(),
    )


def test_default_context_is_the_fixed_v1_to_v6_baseline():
    assert LoopConfig().finding_severity_context == "fixed"
    loop = _loop()
    loop.reset(3)
    assert loop.finding_severity == DEFAULT_FINDING_SEVERITY
    loop.close()


def test_platform_context_only_uses_values_platform_mapping_can_produce():
    draws = [platform_severity_context(s, 0.5, 0.25) for s in range(3000)]
    assert all(set(d.values()) <= LEVELS for d in draws)
    assert all(d["db"] == 0.0 for d in draws)  # no payments-lite route maps to db
    pay = [d["payments"] > 0 for d in draws]
    assert 0.45 < sum(pay) / len(pay) < 0.55
    other = [d["api"] > 0 for d in draws]
    assert 0.2 < sum(other) / len(other) < 0.3
    assert {d["payments"] for d in draws} == LEVELS
    # a clean project and a project holding only the validated high BOLA both occur
    assert any(all(v == 0 for v in d.values()) for d in draws)
    assert any(d["payments"] == 0.75 and sum(d.values()) == 0.75 for d in draws)
    # every value is what platform_mapping derives from some finding set
    topo = pm.load_topology(Path(online.CONFIG_DIR).parent / "topology/payments_lite.yaml")
    route = {"gateway": "GET /health", "api": "GET /customers/x", "auth": "POST /auth/token"}
    route["payments"] = "GET /payments/{payment_id}"
    level = {v: k for k, v in pm.SEVERITY_SCORE.items()}
    for d in draws[:50]:
        findings = [
            pm.FindingInput(id=f"f_{n}", status="validated", severity=level[v], routes=(route[n],))
            for n, v in d.items()
            if v > 0
        ]
        facts, _ = pm.facts_from_platform(topo, findings, [])
        assert {n.node: n.finding_severity for n in facts.nodes} == d


def test_platform_context_is_seeded_by_the_episode_and_reaches_the_observation():
    a, b = _loop(finding_severity_context="platform"), _loop(finding_severity_context="platform")
    seen = set()
    for seed in range(20):
        a.reset(seed)
        b.reset(seed)
        assert (
            a.finding_severity == b.finding_severity == platform_severity_context(seed, 0.5, 0.25)
        )
        a.step(NOOP_ACTION)
        got = {n.node: n.finding_severity for n in a.platform_facts().nodes}
        assert got == a.finding_severity
        seen.add(tuple(sorted(got.items())))
    assert len(seen) > 5  # the context varies across episodes
    a.close()
    b.close()


def test_traffic_is_unchanged_by_the_context():
    """The context draw has its own RNG: paired episodes keep identical traffic."""
    out = []
    for ctx in ("fixed", "platform"):
        loop = _loop(finding_severity_context=ctx)
        ts = loop.run_episode(seed=11, policy=ev.noop_policy)
        out.append([(t.outcome.attack_requests, t.outcome.benign_requests, t.reward) for t in ts])
        loop.close()
    assert out[0] == out[1]


def test_unknown_context_is_refused():
    loop = _loop(finding_severity_context="made_up")
    with pytest.raises(ValueError, match="finding_severity_context"):
        loop.reset(0)
    loop.close()


def test_holdout_v7_is_new_and_disjoint_from_everything_else():
    ho7 = load_scenarios("holdout", subdir="holdout_v7")
    others = [
        *load_scenarios("holdout"),
        *(s for k in (2, 3, 4, 5, 6) for s in load_scenarios("holdout", subdir=f"holdout_v{k}")),
        *load_scenarios("train"),
        *load_scenarios("train", subdir="train_v3"),
        *load_scenarios("val"),
        *load_scenarios("val", subdir="val_v3"),
        *load_scenarios("val", subdir="val_v4"),
    ]
    assert len(ho7) == 3
    assert {s.name for s in ho7}.isdisjoint({s.name for s in others})
    assert {x for s in ho7 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    for s in ho7:
        s.driver()


def test_online_pipeline_smoke_with_platform_context(tmp_path, monkeypatch):
    """End to end on tiny budgets in the v7 loop, with a reference policy. Uses the exposed
    v2 holdout: CI must never evaluate configs/live/holdout_v7."""
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
    monkeypatch.setattr(ev, "RULES_BLOCK_GRID", (0.2,))
    monkeypatch.setattr(
        ev,
        "RULES_V3_GRID",
        {
            "block_anomaly": (0.2,),
            "block_min_volume": (0.0,),
            "long_mode": ("never",),
            "long_target": ("all",),
        },
    )
    v6 = Path(online.CONFIG_DIR).parents[1] / "results/live-retrain-v6/candidate_online.pt"
    args = argparse.Namespace(
        base_checkpoint=str(tmp_path / "sim" / "ddqn_seed0.pt"),
        base_steps=0,
        rules_episodes=1,
        holdout_episodes=1,
        criteria=str(Path(online.CONFIG_DIR) / "promotion.yaml"),
        train_dir="train_v3",
        val_dir="val_v4",
        holdout_dir="holdout_v2",
        seed=0,
        out=str(tmp_path / "run"),
        evidence_dir=str(tmp_path / "ev"),
        severity_context="platform",
        reference_checkpoint=str(v6),
        online_config=online.OnlineConfig(
            demo_episodes_per_scenario=1,
            pretrain_updates=10,
            env_steps=100,
            eps_decay_steps=50,
            batch_size=16,
            eval_every=100,
            val_episodes=1,
            noop_margins=(0.0,),
        ),
    )
    r = online.run(args)
    assert r["loop_overrides"] == {**ev.V4_LOOP_OVERRIDES, "finding_severity_context": "platform"}
    assert r["finding_severity_context"] == "platform"
    assert r["online"]["loop_overrides"]["finding_severity_context"] == "platform"
    assert "reference" in r["policies"] and r["reference"]["checkpoint_sha256"].startswith(
        "8113a37f"
    )
    assert r["candidate_vs_reference_paired"]["pairs"] == r["candidate_vs_expert_paired"]["pairs"]
    md = (tmp_path / "ev" / "REPORT.md").read_text()
    assert "Finding-severity context: `platform`" in md and "Reference (reported only" in md
    # pack: the run's evidence becomes a hash-pinned, compressed, restorable index
    from rl_defense.live import evidence

    ev_dir = tmp_path / "ev"
    idx = evidence.pack(ev_dir, "smoke")["artifacts"]
    assert idx["checkpoint"]["sha256"] == r["candidate"]["checkpoint_sha256"]
    assert idx["selected_experience"]["sha256"] == r["candidate"]["lineage"]["experience_sha256"]
    assert idx["selected_experience"]["lines"] == r["candidate"]["lineage"]["transitions"]
    assert not (ev_dir / idx["experiment"]["path"]).exists()
    assert set(evidence.verify(ev_dir)) == {"checkpoint", "experiment", "selected_experience"}
    restored = {p.name for p in evidence.restore(ev_dir)}
    assert restored == {idx["experiment"]["path"], idx["selected_experience"]["path"]}
