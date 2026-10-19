"""Offline retraining of a *candidate* policy from live experience.

Warm-starts from a base (deployed) checkpoint, runs Double-DQN updates on transitions
from hash-verified, train-split-only datasets, selects the best snapshot on the
**validation** scenarios, and writes a new candidate checkpoint whose manifest records
its lineage (base checkpoint, datasets, selection history). It never touches the
deployed policy: promotion is a separate, human-approved step (``registry.py``).
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np

from rl_defense.agents.ddqn import ReplayBuffer
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.live.evaluate import dqn_policy, run_policy, summarize
from rl_defense.live.experience import load_dataset
from rl_defense.live.scenarios import LiveScenario
from rl_defense.train import set_determinism


def _buffer(records: list[dict], seed: int) -> ReplayBuffer:
    buf = ReplayBuffer(len(records), OBS_DIM, N_ACTIONS, seed=seed)
    for r in records:
        buf.add(
            np.asarray(r["obs"], dtype=np.float32),
            int(r["action"]),
            float(r["reward"]),
            np.asarray(r["next_obs"], dtype=np.float32),
            bool(r["done"]),
            np.asarray(r["action_mask"], dtype=bool),
        )
    return buf


def retrain(
    base_checkpoint: Path,
    datasets: list[Path],
    out_dir: Path,
    app_factory,  # noqa: ANN001
    *,
    val_scenarios: list[LiveScenario],
    updates: int = 20_000,
    batch_size: int = 64,
    lr: float = 3e-4,
    eval_every: int = 2_500,
    val_episodes: int | None = None,
    seed: int = 0,
    name: str = "candidate",
) -> dict:
    if any(s.split != "val" for s in val_scenarios):
        raise ValueError("checkpoint selection must use validation scenarios only")
    if eval_every < 1 or updates < eval_every:
        raise ValueError("need updates >= eval_every >= 1")
    set_determinism(seed)
    agent, base_manifest = load_checkpoint(Path(base_checkpoint))
    for g in agent.optimizer.param_groups:
        g["lr"] = lr

    records: list[dict] = []
    ds_manifests: list[dict] = []
    for p in datasets:
        recs, m = load_dataset(Path(p))
        records.extend(recs)
        ds_manifests.append(m)
    if not records:
        raise ValueError("no transitions to train on")
    buf = _buffer(records, seed)

    def val_score() -> dict:
        return summarize(
            run_policy(dqn_policy(agent), val_scenarios, app_factory, episodes=val_episodes)
        )

    history = [{"update": 0, "role": "base", **_brief(val_score())}]
    best: tuple[float, int, dict] | None = None
    losses: list[float] = []
    for u in range(1, updates + 1):
        losses.append(agent.update(buf.sample(batch_size))["loss"])
        if u % eval_every == 0:
            s = val_score()
            history.append(
                {"update": u, "loss_mean": float(np.mean(losses[-eval_every:])), **_brief(s)}
            )
            if best is None or s["reward"] > best[0]:
                best = (s["reward"], u, copy.deepcopy(agent.state_dict()))
    assert best is not None
    agent.load_state_dict(best[2])

    train_scen: dict[str, str] = {}
    for m in ds_manifests:
        train_scen.update(m["scenarios"])
    out_dir = Path(out_dir)
    manifest = save_checkpoint(
        agent,
        out_dir / f"{name}.pt",
        seed=seed,
        steps=best[1],
        train_configs={f"live:{k}": v for k, v in train_scen.items()},
        extra={
            "trained_on": "live:examples/payments-lite (offline, from recorded experience)",
            "lineage": {
                "base_checkpoint_sha256": base_manifest["checkpoint_sha256"],
                "base_env_id": base_manifest["env_id"],
                "datasets": [m["dataset_id"] for m in ds_manifests],
                "transitions": len(records),
            },
            "retrain": {
                "updates_run": updates,
                "selected_update": best[1],
                "batch_size": batch_size,
                "lr": lr,
                "eval_every": eval_every,
                "val_scenarios": {s.name: s.config_hash() for s in val_scenarios},
                "selection_history": history,
            },
        },
    )
    return manifest


def _brief(s: dict) -> dict:
    return {
        "val_reward": s["reward"],
        "val_compromise_rate": s["compromise_rate"],
        "val_availability": s["availability"],
        "val_no_attack_defense_duty": s["no_attack_defense_duty"],
    }
