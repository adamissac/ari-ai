"""Live v8: the v7 method on a train mix with low-intensity, mostly quiet traffic.

No test runs an episode on configs/live/holdout_v8 (results/live-retrain-v8/PREREGISTRATION.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live import online
from rl_defense.live.scenarios import SEED_BANDS, load_scenarios
from rl_defense.train import train

NEW_TRAIN = {"rare_delegate_runs", "trickle_outsider_quiet"}
RESULTS = Path(online.CONFIG_DIR).parents[1] / "results"


def _everything_but(*skip: str) -> list:
    dirs = {
        ("holdout", None),
        *(("holdout", f"holdout_v{k}") for k in range(2, 9)),
        ("train", None),
        ("train", "train_v3"),
        ("train", "train_v8"),
        ("val", None),
        ("val", "val_v3"),
        ("val", "val_v4"),
    }
    return [s for split, sub in dirs if sub not in skip for s in load_scenarios(split, subdir=sub)]


def test_train_v8_is_train_v3_unchanged_plus_two_low_intensity_scenarios():
    v3 = {s.name: s.config_hash() for s in load_scenarios("train", subdir="train_v3")}
    v8 = {s.name: s for s in load_scenarios("train", subdir="train_v8")}
    assert set(v8) == set(v3) | NEW_TRAIN
    assert all(v8[n].config_hash() == h for n, h in v3.items())
    lo, hi = SEED_BANDS["train"]
    others = _everything_but("train_v8")
    new = [v8[n] for n in NEW_TRAIN]
    assert {s.name for s in new}.isdisjoint({s.name for s in others})
    assert {x for s in new for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    for s in new:
        assert lo <= min(s.seeds()) and max(s.seeds()) <= hi
        # low intensity, mostly quiet: rarer and smaller campaigns than any train_v3 scenario
        assert s.schedule == "bursty" and s.attack_per_step <= 3
        assert s.p_start <= 0.06 and s.p_stop >= 0.45
        s.driver()


def test_holdout_v8_is_new_and_disjoint_from_everything_else():
    ho8 = load_scenarios("holdout", subdir="holdout_v8")
    others = _everything_but("holdout_v8")
    assert len(ho8) == 3
    assert {s.name for s in ho8}.isdisjoint({s.name for s in others})
    assert {x for s in ho8 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    # at least one low-intensity, mostly quiet scenario (v7's failure regime)
    assert any(s.schedule == "bursty" and s.attack_per_step <= 3 and s.p_start <= 0.05 for s in ho8)
    for s in ho8:
        s.driver()


def test_reference_names():
    assert online.parse_references(None) == []
    assert online.parse_references("a/v6.pt") == [("reference", "a/v6.pt")]
    assert online.parse_references(["v6=a/v6.pt", "v7=b/v7.pt"]) == [
        ("v6", "a/v6.pt"),
        ("v7", "b/v7.pt"),
    ]
    assert online.parse_references(["a.pt", "b.pt"]) == [
        ("reference", "a.pt"),
        ("reference_2", "b.pt"),
    ]
    for bad in (["v6=a", "v6=b"], ["candidate=a"], ["always_block=a"], ["v6=a", "reference=b"]):
        with pytest.raises(ValueError, match="reference names"):
            online.parse_references(bad)


def test_online_pipeline_smoke_with_train_v8_and_two_references(tmp_path, monkeypatch):
    """End to end on tiny budgets with the v8 train mix and v6 + v7 as references. Uses the
    exposed v2 holdout: CI must never evaluate configs/live/holdout_v8."""
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
    from rl_defense.live.registry import Registry

    registry = Registry(tmp_path / "registry.json")
    registry.init(tmp_path / "sim" / "ddqn_seed0.pt", "usr_test")
    registry.save()
    args = argparse.Namespace(
        registry=str(registry.path),
        base_checkpoint=None,
        base_steps=0,
        rules_episodes=1,
        holdout_episodes=1,
        criteria=str(Path(online.CONFIG_DIR) / "promotion.yaml"),
        train_dir="train_v8",
        val_dir="val_v4",
        holdout_dir="holdout_v2",
        seed=0,
        out=str(tmp_path / "run"),
        evidence_dir=str(tmp_path / "ev"),
        severity_context="platform",
        reference_checkpoint=[
            f"v6={RESULTS / 'live-retrain-v6/candidate_online.pt'}",
            f"v7={RESULTS / 'live-retrain-v7/candidate_online.pt'}",
        ],
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
    assert r["deployed"]["checkpoint_sha256"] == registry.deployed["sha256"]
    assert set(r["splits"]["train"]) == set(
        s.name for s in load_scenarios("train", subdir="train_v8")
    )
    assert {"v6", "v7"} <= set(r["policies"]) and "reference" not in r["policies"]
    assert [x["name"] for x in r["references"]] == ["v6", "v7"]
    assert r["references"][0]["checkpoint_sha256"].startswith("8113a37f")
    assert r["references"][1]["checkpoint_sha256"].startswith("d1c0c9b5")
    assert r["reference"]["name"] == "v6"  # the v7 field keeps the first reference
    assert r["candidate_vs_reference_paired"] == r["references"][0]["candidate_vs_paired"]
    assert r["checks"] and {c["name"] for c in r["checks"]} >= {"no_per_scenario_regression"}
    md = (tmp_path / "ev" / "REPORT.md").read_text()
    assert "Reference (reported only, not in the gate) `v6`" in md
    assert "Reference (reported only, not in the gate) `v7`" in md
