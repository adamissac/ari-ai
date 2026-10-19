"""Live v5: conservative Q-learning (CQL) for the offline candidate, and holdout_v5 hygiene.

No test runs an episode on configs/live/holdout_v5, which is reserved for the one final
v5 run (results/live-retrain-v5/PROVENANCE.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from rl_defense.agents.ddqn import Batch, DDQNAgent, DDQNConfig
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live.scenarios import load_scenarios
from rl_defense.train import train

RESULTS = Path(__file__).resolve().parents[1] / "results"


def _batch(n: int = 32, obs_dim: int = 4, n_actions: int = 5, action: int = 1, seed: int = 0):
    g = torch.Generator().manual_seed(seed)
    return Batch(
        obs=torch.rand(n, obs_dim, generator=g),
        actions=torch.full((n,), action, dtype=torch.long),
        rewards=torch.full((n,), -0.2),
        next_obs=torch.rand(n, obs_dim, generator=g),
        dones=torch.zeros(n),
        next_masks=torch.ones(n, n_actions, dtype=torch.bool),
    )


def _agent(alpha: float, seed: int = 0) -> DDQNAgent:
    return DDQNAgent(4, 5, DDQNConfig(hidden_sizes=(32,), lr=1e-2, cql_alpha=alpha), seed=seed)


def test_cql_is_off_by_default_and_old_configs_still_load():
    assert DDQNConfig().cql_alpha == 0.0
    a = _agent(0.0)
    info = a.update(_batch())
    assert info["cql_gap"] == 0.0 and info["loss"] == pytest.approx(info["td_loss"])
    # a committed v4 manifest (written before the field existed) still parses
    cfg = json.loads((RESULTS / "live-retrain-v4" / "candidate.manifest.json").read_text())
    assert DDQNConfig(**cfg["ddqn_config"]).cql_alpha == 0.0


def test_cql_loss_is_td_plus_alpha_times_the_logsumexp_gap():
    """Same weights, same batch: the reported loss is exactly TD + alpha * gap, with
    gap = mean(logsumexp_a Q(s,a) - Q(s,a_data)) computed by hand."""
    b = _batch()
    a = _agent(2.0)
    with torch.no_grad():
        q_all = a.online(b.obs)
        gap = (torch.logsumexp(q_all, 1) - q_all[:, 1]).mean().item()
    info = a.update(b)
    assert info["cql_gap"] == pytest.approx(gap, rel=1e-5)
    assert info["loss"] == pytest.approx(info["td_loss"] + 2.0 * gap, rel=1e-5)
    assert gap > 0  # logsumexp always exceeds any single Q


def test_cql_pushes_down_actions_the_data_never_took():
    """Offline on data that only ever contains action 1: after the same updates, CQL leaves
    the unseen actions' Q well below the seen one; plain DQN does not separate them."""
    b = _batch(n=64)

    def margin(alpha: float) -> float:
        a = _agent(alpha)
        for _ in range(300):
            a.update(b)
        with torch.no_grad():
            q = a.online(b.obs).numpy()
        unseen = np.delete(q, 1, axis=1).max(axis=1)
        return float(np.mean(q[:, 1] - unseen))

    plain, cql = margin(0.0), margin(1.0)
    assert cql > plain + 1.0
    assert cql > 0


def test_holdout_v5_is_new_and_disjoint_from_everything_else():
    ho5 = load_scenarios("holdout", subdir="holdout_v5")
    others = [
        *load_scenarios("holdout"),
        *(s for k in (2, 3, 4) for s in load_scenarios("holdout", subdir=f"holdout_v{k}")),
        *load_scenarios("train"),
        *load_scenarios("train", subdir="train_v3"),
        *load_scenarios("val"),
        *load_scenarios("val", subdir="val_v3"),
        *load_scenarios("val", subdir="val_v4"),
    ]
    assert len(ho5) == 3
    assert {s.name for s in ho5}.isdisjoint({s.name for s in others})
    assert {x for s in ho5 for x in s.seeds()}.isdisjoint({x for s in others for x in s.seeds()})
    assert all(s.delegations for s in ho5)
    for s in ho5:
        s.driver()


def test_pipeline_v5_smoke(tmp_path, monkeypatch):
    """End to end with the v5 flags on tiny budgets. Uses the (already exposed) v2 holdout
    dir: CI must never evaluate configs/live/holdout_v5."""
    from rl_defense.live import pipeline

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
            "long_mode": ("never",),
            "long_target": ("all",),
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
        cql_alpha=1.0,
    )
    r = pipeline.run(args)
    assert r["cql_alpha"] == 1.0
    assert [u for u, _ in r["rounds"][0]["val_curve"]] == [0, 10, 20]
    cand = json.loads((tmp_path / "run" / "candidate_round1.manifest.json").read_text())
    assert cand["retrain"]["cql_alpha"] == 1.0 and cand["ddqn_config"]["cql_alpha"] == 1.0
    assert all("cql_gap_mean" in h for h in cand["retrain"]["selection_history"][1:])
    md = pipeline.render_markdown(r)
    assert "cql_alpha=1.0" in md and "Val return by number of offline updates" in md
