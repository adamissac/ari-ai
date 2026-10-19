"""Live v6: DQfD demonstration loss and online training in the live loop.

Everything runs real requests against the owned demo app through the defensive gateway.
No test runs an episode on configs/live/holdout_v6, which is reserved for the one final v6
run (results/live-retrain-v6/PREREGISTRATION.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import torch

from rl_defense.agents.ddqn import Batch, DDQNAgent, DDQNConfig, cat_batches
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live import online
from rl_defense.live.actions import BLOCK_PRINCIPAL_ACTION
from rl_defense.live.adversary import live_app
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.train import train

TINY = online.OnlineConfig(
    demo_episodes_per_scenario=1,
    pretrain_updates=20,
    env_steps=40,
    eps_decay_steps=20,
    batch_size=16,
    eval_every=20,
    val_episodes=1,
    noop_margins=(0.0,),
)


def _batch(n=32, action=3, demo=None, seed=0):  # noqa: ANN001, ANN202
    g = torch.Generator().manual_seed(seed)
    return Batch(
        obs=torch.rand(n, 4, generator=g),
        actions=torch.full((n,), action, dtype=torch.long),
        rewards=torch.full((n,), -0.1),
        next_obs=torch.rand(n, 4, generator=g),
        dones=torch.zeros(n),
        next_masks=torch.ones(n, 5, dtype=torch.bool),
        demo=demo,
    )


def _sc(split="train", **kw) -> LiveScenario:  # noqa: ANN001
    base = {
        "name": f"t6_{split}",
        "split": split,
        "schedule": "always",
        "attack_per_step": 4,
        "benign_per_step": 6,
        "horizon": 10,
        "benign": ("alice", "bob", "dave"),
        "delegations": ("dave:alice",),
        "seed_start": SEED_BANDS[split][0],
        "episodes": 2,
    }
    return LiveScenario(**{**base, **kw})


# ------------------------------------------------------------------ DQfD loss
def test_demo_loss_is_off_by_default_and_only_counts_demo_rows():
    cfg = DDQNConfig()
    assert cfg.demo_lambda == 0.0
    a = DDQNAgent(4, 5, DDQNConfig(hidden_sizes=(16,)), seed=0)
    info = a.update(_batch(demo=torch.ones(32, dtype=torch.bool)))
    assert info["demo_loss"] == 0.0 and info["loss"] == pytest.approx(info["td_loss"])
    b = DDQNAgent(4, 5, DDQNConfig(hidden_sizes=(16,), demo_lambda=1.0), seed=0)
    assert b.update(_batch(demo=torch.zeros(32, dtype=torch.bool)))["demo_loss"] == 0.0


def test_demo_loss_matches_the_dqfd_formula():
    """J_E = mean(max_a [Q(s,a) + 0.8 * 1(a != a_E)] - Q(s,a_E)) over the demo rows only."""
    demo = torch.tensor([True, False] * 16)
    b = _batch(demo=demo)
    a = DDQNAgent(4, 5, DDQNConfig(hidden_sizes=(16,), demo_lambda=2.0), seed=0)
    with torch.no_grad():
        q = a.online(b.obs)[demo]
        m = torch.full_like(q, 0.8)
        m[:, 3] = 0.0
        want = ((q + m).max(1).values - q[:, 3]).mean().item()
    info = a.update(b)
    assert info["demo_loss"] == pytest.approx(want, rel=1e-5)
    assert info["loss"] == pytest.approx(info["td_loss"] + 2.0 * want, rel=1e-5)


def test_demo_loss_teaches_the_demonstrated_action_by_the_margin():
    b = _batch(n=64, action=3, demo=torch.ones(64, dtype=torch.bool))
    a = DDQNAgent(4, 5, DDQNConfig(hidden_sizes=(32,), lr=1e-2, demo_lambda=1.0), seed=0)
    for _ in range(300):
        a.update(b)
    with torch.no_grad():
        q = a.online(b.obs).numpy()
    gap = q[:, 3] - np.delete(q, 3, axis=1).max(axis=1)
    assert (gap > 0.5).all()


def test_cat_batches_keeps_rows_and_flags():
    x = cat_batches(
        _batch(n=3, demo=torch.zeros(3, dtype=torch.bool)),
        _batch(n=2, demo=torch.ones(2, dtype=torch.bool)),
    )
    assert x.obs.shape[0] == 5 and x.demo.tolist() == [False] * 3 + [True] * 2
    with pytest.raises(ValueError, match="demo"):
        cat_batches(_batch(n=1), _batch(n=1, demo=torch.ones(1, dtype=torch.bool)))


# ------------------------------------------------------------------ expert + online
def test_expert_is_chosen_on_train_only():
    params = {"isolate_anomaly": 0.6, "rate_limit_alerts": 1.1, "monitor_anomaly": 1.1}
    name, scores = online.choose_expert(
        [_sc()], live_app, params, episodes=1, loop_overrides=ev.V4_LOOP_OVERRIDES
    )
    assert name == max(scores, key=scores.get) and set(scores) == set(
        online.expert_candidates(params)
    )
    with pytest.raises(ValueError, match="train"):
        online.choose_expert([_sc("val")], live_app, params, episodes=1, loop_overrides=None)


def test_online_training_uses_demos_then_live_train_episodes(tmp_path):
    """Demonstrations come from the expert, every training episode uses a train-band seed,
    the network starts fresh (no sim prior), and the manifest records the schedule."""
    m = online.train_online(
        [_sc()],
        [_sc("val")],
        live_app,
        ev.always_block_principal,
        tmp_path,
        cfg=TINY,
        loop_overrides=ev.V4_LOOP_OVERRIDES,
        expert_name="always_block_principal",
    )
    recs = [json.loads(x) for x in (tmp_path / "candidate_online_experience.jsonl").open()]
    demos = [r for r in recs if r["kind"] == "demo"]
    agent = [r for r in recs if r["kind"] == "agent"]
    lo, hi = SEED_BANDS["train"]
    assert all(lo <= r["seed"] <= hi and r["split"] == "train" for r in recs)
    assert len(demos) == 10 and len(agent) == 40
    assert all(r["action"] in (0, BLOCK_PRINCIPAL_ACTION) for r in demos)
    assert any(r["action"] == BLOCK_PRINCIPAL_ACTION for r in demos)
    lin, o = m["lineage"], m["online"]
    assert lin["base_checkpoint_sha256"] is None
    assert (lin["demo_transitions"], lin["agent_transitions"]) == (10, o["selected_env_step"])
    assert o["experiment"]["agent_transitions"] == 40
    assert o["experiment"]["updates"] == TINY.pretrain_updates + 40
    assert [h["env_step"] for h in o["selection_history"]] == [0, 20, 40]
    assert o["selection_history"][0]["phase"] == "pretrained"
    assert m["env_id"] == "LiveDefense-payments-lite-v3" and m["ddqn_config"]["demo_lambda"] == 1.0
    with pytest.raises(ValueError, match="train"):
        online.train_online([_sc("val")], [_sc("val")], live_app, ev.noop_policy, tmp_path)


def test_holdout_v6_is_new_and_disjoint_from_everything_else():
    ho6 = load_scenarios("holdout", subdir="holdout_v6")
    others = [
        *load_scenarios("holdout"),
        *(s for k in (2, 3, 4, 5) for s in load_scenarios("holdout", subdir=f"holdout_v{k}")),
        *load_scenarios("train"),
        *load_scenarios("train", subdir="train_v3"),
        *load_scenarios("val"),
        *load_scenarios("val", subdir="val_v3"),
        *load_scenarios("val", subdir="val_v4"),
    ]
    assert len(ho6) == 3
    assert {s.name for s in ho6}.isdisjoint({s.name for s in others})
    assert {x for s in ho6 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    for s in ho6:
        s.driver()


def test_online_pipeline_smoke(tmp_path, monkeypatch):
    """End to end on tiny budgets. Uses the (already exposed) v2 holdout dir: CI must never
    evaluate configs/live/holdout_v6."""
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
        online_config=online.OnlineConfig(
            demo_episodes_per_scenario=1,
            pretrain_updates=10,
            env_steps=150,
            eps_decay_steps=100,
            batch_size=16,
            eval_every=150,
            val_episodes=1,
            noop_margins=(0.0, 0.2),
        ),
    )
    r = online.run(args)
    assert r["mode"] == "online_dqfd" and r["requires_human_approval"] is True
    assert r["loop_overrides"] == ev.V4_LOOP_OVERRIDES
    assert r["expert"]["name"] in r["policies"]
    assert {"deployed", "candidate", "threshold_rules", "always_block_principal"} <= set(
        r["policies"]
    )
    # The evidence directory must be self-contained after the transient run is removed.
    shutil.rmtree(tmp_path / "run")
    from rl_defense.checkpoint import load_checkpoint

    for item in r["artifacts"].values():
        artifact = tmp_path / "ev" / item["path"]
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == item["sha256"]
    _, reloaded = load_checkpoint(tmp_path / "ev" / r["artifacts"]["checkpoint"]["path"])
    assert reloaded["checkpoint_sha256"] == r["candidate"]["checkpoint_sha256"]
    md = (tmp_path / "ev" / "REPORT.md").read_text()
    assert "Demonstrations and online schedule" in md and "candidate − expert" in md


def test_selected_snapshot_lineage_excludes_later_experience(tmp_path, monkeypatch):
    # Force selection of the pretraining snapshot, before all 40 online transitions.
    scores = iter((3.0, 2.0, 1.0))
    monkeypatch.setattr(ev, "scenario_mean_reward", lambda rows: next(scores))
    m = online.train_online(
        [_sc()],
        [_sc("val")],
        live_app,
        ev.always_block_principal,
        tmp_path,
        cfg=TINY,
        loop_overrides=ev.V4_LOOP_OVERRIDES,
    )
    from rl_defense.checkpoint import load_checkpoint

    agent, _ = load_checkpoint(tmp_path / "candidate_online.pt")
    assert m["steps"] == m["lineage"]["agent_transitions"] == 0
    assert m["lineage"]["transitions"] == 10
    selected = tmp_path / m["lineage"]["experience_file"]
    assert len(selected.read_text().splitlines()) == 10
    assert all(json.loads(row)["kind"] == "demo" for row in selected.read_text().splitlines())
    assert hashlib.sha256(selected.read_bytes()).hexdigest() == m["lineage"]["experience_sha256"]
    assert agent.updates == TINY.pretrain_updates
    assert m["online"]["experiment"]["updates"] == TINY.pretrain_updates + 40


def test_registry_refuses_unservable_checkpoint_and_missing_dqfd_evidence(tmp_path, monkeypatch):
    from rl_defense import inference
    from rl_defense.checkpoint import save_checkpoint
    from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
    from rl_defense.live.registry import Registry, RegistryError

    path = tmp_path / "candidate.pt"
    m = save_checkpoint(
        DDQNAgent(OBS_DIM, N_ACTIONS, DDQNConfig(), seed=0), path, seed=0, steps=0, train_configs={}
    )
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "mode": "online_dqfd",
                "decision": "recommend_promote",
                "candidate": {"checkpoint_sha256": m["checkpoint_sha256"]},
            }
        )
    )
    reg = Registry(tmp_path / "registry.json")
    vid = reg.register(path, report)
    with pytest.raises(RegistryError, match="missing durable checkpoint evidence"):
        reg.promote(vid, "usr_test", "test missing evidence")

    experience = tmp_path / "selected.jsonl"
    experience.write_bytes(b"retained experience\n")
    digest = hashlib.sha256(experience.read_bytes()).hexdigest()
    report.write_text(
        json.dumps(
            {
                "mode": "online_dqfd",
                "decision": "recommend_promote",
                "candidate": {
                    "checkpoint_sha256": m["checkpoint_sha256"],
                    "lineage": {"experience_sha256": digest},
                },
                "artifacts": {
                    "checkpoint": {"path": path.name, "sha256": m["checkpoint_sha256"]},
                    "experience": {"path": experience.name, "sha256": digest},
                },
            }
        )
    )
    reg.promote(vid, "usr_test", "retained evidence")
    assert reg.deployed["sha256"] == m["checkpoint_sha256"]
    experience.write_bytes(b"changed")
    with pytest.raises(RegistryError, match="experience evidence hash mismatch"):
        reg.promote(vid, "usr_test", "tampered evidence")

    def refuse(*args, **kwargs):
        raise ValueError("unsupported layout")

    monkeypatch.setattr(inference, "PolicyRunner", refuse)
    with pytest.raises(RegistryError, match="not servable"):
        reg.promote(vid, "usr_test", "test unsupported layout")
    assert reg.deployed["sha256"] == m["checkpoint_sha256"]
