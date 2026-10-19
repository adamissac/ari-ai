"""Offline retraining of a *candidate* policy from live experience.

Warm-starts from a base (deployed) checkpoint, runs Double-DQN updates on transitions
from hash-verified, train-split-only datasets, selects the best snapshot on the
**validation** scenarios, and writes a new candidate checkpoint whose manifest records
its lineage (base checkpoint, datasets, selection history). It never touches the
deployed policy: promotion is a separate, human-approved step (``registry.py``).

``noop_margins`` (live v3): each snapshot is also scored on val with greedy abstention
margins (``DDQNConfig.noop_margin``: take a non-noop action only if its Q beats Q(noop) by
the margin), and the best (snapshot, margin) pair on val is kept. Why: the v2 candidate
spent ~45% of val steps on ``raise_monitoring`` although monitoring cannot contain anything
live. At the selected snapshot its Q-values were still near the simulator's scale (mean
Q ≈ +1.5 against measured returns ≈ −3.7), so the many effect-free actions (raise_monitoring
on five nodes, reassessment, escalation) tie with noop up to estimation noise far larger
than their 0.02 action cost, and argmax over ~10 near-ties rarely lands on noop. See
results/live-retrain-v3/PROVENANCE.md. ``(0.0,)`` = the v1/v2 behaviour.

``selection="scenario_mean"`` (live v4): a (snapshot, margin) pair is scored by the
unweighted mean over the val scenarios of each scenario's mean return
(:func:`evaluate.scenario_mean_reward`), and the per-scenario val returns are recorded.
v3 selected on a single val scenario and overfit it (results/live-retrain-v3/REPORT.md).
``"pooled"`` (default) is the v1-v3 score, the mean over all pooled val episodes.

``cql_alpha`` (live v5): train with the conservative Q-learning penalty
(``DDQNConfig.cql_alpha``, rl_defense/agents/ddqn.py). 0 (default) = the v1-v4 updates.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import numpy as np

from rl_defense import ENV_ID
from rl_defense.agents.ddqn import ReplayBuffer
from rl_defense.checkpoint import load_checkpoint, save_checkpoint
from rl_defense.live.actions import ENV_IDS, ActionSpace, as_space, dims
from rl_defense.live.evaluate import (
    dqn_policy,
    run_policy,
    scenario_mean_reward,
    summarize,
    summarize_by_scenario,
)
from rl_defense.live.experience import load_dataset
from rl_defense.live.scenarios import LiveScenario
from rl_defense.train import set_determinism


def _buffer(records: list[dict], seed: int, space: ActionSpace = "sim") -> ReplayBuffer:
    obs_dim, n_actions = dims(space)
    buf = ReplayBuffer(len(records), obs_dim, n_actions, seed=seed)
    for r in records:
        if len(r["obs"]) != obs_dim or len(r["action_mask"]) != n_actions:
            raise ValueError(f"transition shape does not match action space {space}")
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
    action_space: ActionSpace = "sim",
    noop_margins: tuple[float, ...] = (0.0,),
    loop_overrides: Mapping[str, object] | None = None,
    selection: Literal["pooled", "scenario_mean"] = "pooled",
    cql_alpha: float = 0.0,
) -> dict:
    if any(s.split != "val" for s in val_scenarios):
        raise ValueError("checkpoint selection must use validation scenarios only")
    if eval_every < 1 or updates < eval_every:
        raise ValueError("need updates >= eval_every >= 1")
    set_determinism(seed)
    agent, base_manifest = load_checkpoint(Path(base_checkpoint))
    if action_space != "sim":
        agent = as_space(agent, action_space)  # widen without changing its greedy choices
    for g in agent.optimizer.param_groups:
        g["lr"] = lr
    if cql_alpha:
        agent.config = agent.config.model_copy(update={"cql_alpha": float(cql_alpha)})

    records: list[dict] = []
    ds_manifests: list[dict] = []
    for p in datasets:
        recs, m = load_dataset(Path(p))
        records.extend(recs)
        ds_manifests.append(m)
    if not records:
        raise ValueError("no transitions to train on")
    buf = _buffer(records, seed, action_space)

    base_config = agent.config

    def val_score() -> tuple[dict, float]:
        """Best val summary over the abstention margins (and that margin)."""
        best_m: tuple[dict, float] | None = None
        for m in noop_margins:
            agent.config = base_config.model_copy(update={"noop_margin": float(m)})
            rows = run_policy(
                dqn_policy(agent),
                val_scenarios,
                app_factory,
                episodes=val_episodes,
                action_space=action_space,
                loop_overrides=loop_overrides,
            )
            s = summarize(rows)
            if selection == "scenario_mean":
                s["pooled_reward"] = s["reward"]
                s["reward"] = scenario_mean_reward(rows)
                s["by_scenario"] = {
                    k: round(v["reward"], 4) for k, v in summarize_by_scenario(rows).items()
                }
            if best_m is None or s["reward"] > best_m[0]["reward"]:
                best_m = (s, float(m))
        agent.config = base_config
        assert best_m is not None
        return best_m

    s0, m0 = val_score()
    history = [{"update": 0, "role": "base", **_brief(s0), **_margin(m0, noop_margins)}]
    best: tuple[float, int, dict, float] | None = None
    losses: list[float] = []
    gaps: list[float] = []
    for u in range(1, updates + 1):
        info = agent.update(buf.sample(batch_size))
        losses.append(info["loss"])
        gaps.append(info["cql_gap"])
        if u % eval_every == 0:
            s, m = val_score()
            history.append(
                {
                    "update": u,
                    "loss_mean": float(np.mean(losses[-eval_every:])),
                    **({"cql_gap_mean": float(np.mean(gaps[-eval_every:]))} if cql_alpha else {}),
                    **_brief(s),
                    **_margin(m, noop_margins),
                }
            )
            if best is None or s["reward"] > best[0]:
                best = (s["reward"], u, copy.deepcopy(agent.state_dict()), m)
    assert best is not None
    agent.load_state_dict(best[2])
    agent.config = base_config.model_copy(update={"noop_margin": best[3]})

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
        env_id=ENV_ID if action_space == "sim" else ENV_IDS[action_space],
        extra={
            "action_space": action_space,
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
                "noop_margins": list(noop_margins),
                "selected_noop_margin": best[3],
                "selection": selection,
                "cql_alpha": float(cql_alpha),
                **({"loop_overrides": dict(loop_overrides)} if loop_overrides else {}),
                "val_scenarios": {s.name: s.config_hash() for s in val_scenarios},
                "selection_history": history,
            },
        },
    )
    return manifest


def _margin(m: float, margins: tuple[float, ...]) -> dict:
    return {} if tuple(margins) == (0.0,) else {"noop_margin": m}


def _brief(s: dict) -> dict:
    out = {
        "val_reward": s["reward"],
        "val_compromise_rate": s["compromise_rate"],
        "val_availability": s["availability"],
        "val_no_attack_defense_duty": s["no_attack_defense_duty"],
    }
    if "by_scenario" in s:
        out["val_reward_by_scenario"] = s["by_scenario"]
    return out
