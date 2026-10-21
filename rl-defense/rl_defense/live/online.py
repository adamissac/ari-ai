"""Online live training from demonstrations (live v6, DQfD-style), and its held-out run.

    python -m rl_defense.live.online --out runs/live/retrain-v6 \
        --evidence-dir results/live-retrain-v6

v4 and v5 trained the candidate *offline* on ~6k transitions collected around the
sim-trained policy, in which blocks (the only controls that contain this attack without
cutting whole nodes) were 3-5% of the data. Plain DDQN degraded with more updates (v4) and
CQL anchored the candidate to that data (v5). v6 changes how the data is made:

  1. an **expert** is chosen on TRAIN only: the best, by train return, of the tuned rules
     and the fixed block baselines (the rule is a teacher, never the deployed defense);
  2. the expert's episodes on TRAIN scenarios fill a permanent **demonstration buffer**;
  3. a fresh network (no simulator prior) is **pretrained** on the demonstrations with TD
     plus the DQfD large-margin loss (``DDQNConfig.demo_lambda``);
  4. it then trains **online in the live loop** (ε-greedy over valid actions, one update
     per real step, every batch a fixed share of demonstrations), so it can find where the
     expert is wrong (e.g. attackers that are also customers);
  5. snapshots and noop margins are selected on the mean over the VAL scenarios;
  6. deployed, candidate, rules, the expert and the other baselines run ONCE on HOLDOUT and
     the pre-registered gate (configs/live/promotion.yaml) decides. Never promotes.

Everything runs in the v4 loop (``evaluate.V4_LOOP_OVERRIDES``: ``c_disrupt=1.0``, the
grant-aware detector) and action space ``live_v3``. Training episodes use seeds drawn from
the train seed band only. Results: results/live-retrain-v6/ (PREREGISTRATION.md first).

v7 (``--severity-context platform``) runs the same method in a loop whose finding
severities are drawn per episode from what ``platform_mapping`` can produce
(``LoopConfig.finding_severity_context``); every policy (expert choice, rules tuning,
training, selection, holdout) sees that loop. ``--reference-checkpoint`` adds a fixed,
already-trained policy (v7: the promoted v6) to the holdout table; it never enters the
gate. Results: results/live-retrain-v7/ (PREREGISTRATION.md first).

v8 keeps v7's loop and method and trains on ``--train-dir train_v8`` (train_v3 unchanged
plus two low-intensity, mostly quiet scenarios). ``--reference-checkpoint`` is repeatable
(``NAME=PATH``), so v6 and v7 are both reported. Results: results/live-retrain-v8/.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import gzip
import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
import yaml

from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig, ReplayBuffer, cat_batches
from rl_defense.checkpoint import git_sha, load_checkpoint, save_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live.actions import ENV_IDS, dims
from rl_defense.live.adversary import live_app
from rl_defense.live.evaluate import PolicyFn
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import CONFIG_DIR, SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.train import set_determinism, train

SPACE = "live_v3"
REPORT_SCHEMA = "live-promotion-report/0.1"


@dataclass(frozen=True)
class OnlineConfig:
    """v6 hyperparameters (fixed in results/live-retrain-v6/PREREGISTRATION.md)."""

    demo_episodes_per_scenario: int = 20
    pretrain_updates: int = 5_000
    env_steps: int = 150_000
    eps_start: float = 0.3
    eps_end: float = 0.05
    eps_decay_steps: int = 75_000
    updates_per_step: int = 1
    batch_size: int = 64
    demo_fraction: float = 0.25
    lr: float = 3e-4
    demo_lambda: float = 1.0
    demo_margin: float = 0.8
    target_update_interval: int = 1_000
    buffer_size: int = 100_000
    hidden_sizes: tuple[int, ...] = (128, 128)
    eval_every: int = 15_000
    val_episodes: int = 8
    noop_margins: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5)
    seed: int = 0

    def epsilon(self, step: int) -> float:
        frac = min(1.0, step / max(1, self.eps_decay_steps))
        return self.eps_start + frac * (self.eps_end - self.eps_start)


# ---------------------------------------------------------------------- expert
def expert_candidates(rules_params: dict) -> dict[str, PolicyFn]:
    return {
        "threshold_rules": ev.rules_policy(rules_params),
        "always_block_principal": ev.always_block_principal,
        "always_block_principal_long": ev.always_block_principal_long,
        "always_block_top_principal_long": ev.always_block_top_principal_long,
    }


def choose_expert(
    train_scenarios: list[LiveScenario],
    app_factory,  # noqa: ANN001
    rules_params: dict,
    *,
    episodes: int,
    loop_overrides: Mapping[str, object] | None,
) -> tuple[str, dict[str, float]]:
    """The demonstrator = best train return among the tuned rules and the fixed block
    baselines. TRAIN only: val and holdout never influence the teacher."""
    if any(s.split != "train" for s in train_scenarios):
        raise ValueError("the expert must be chosen on train scenarios only")
    scores = {
        n: ev.summarize(
            ev.run_policy(
                p,
                train_scenarios,
                app_factory,
                episodes=episodes,
                action_space=SPACE,
                loop_overrides=loop_overrides,
            )
        )["reward"]
        for n, p in expert_candidates(rules_params).items()
    }
    return max(scores, key=scores.get), scores


# ---------------------------------------------------------------------- training
def _seed_stream(seed: int):  # noqa: ANN202
    """Episode seeds for training, drawn from the TRAIN band only."""
    lo, hi = SEED_BANDS["train"]
    rng = np.random.default_rng(seed + 7_919)
    while True:
        yield int(rng.integers(lo, hi + 1))


def _add(buf: ReplayBuffer, ts) -> None:  # noqa: ANN001
    for t in ts:
        buf.add(
            np.asarray(t.obs, dtype=np.float32),
            int(t.action),
            float(t.reward),
            np.asarray(t.next_obs, dtype=np.float32),
            bool(t.done),
            np.asarray(t.action_mask, dtype=bool),
        )


def _demo_flag(batch, flag: bool):  # noqa: ANN001, ANN202
    return dataclasses.replace(batch, demo=torch.full((batch.actions.shape[0],), flag))


def train_online(
    train_scenarios: list[LiveScenario],
    val_scenarios: list[LiveScenario],
    app_factory,  # noqa: ANN001
    expert: PolicyFn,
    out_dir: Path,
    *,
    cfg: OnlineConfig | None = None,
    loop_overrides: Mapping[str, object] | None = None,
    expert_name: str = "expert",
    balance_demo_actions: bool = False,
    name: str = "candidate_online",
    log=print,  # noqa: ANN001
) -> dict:
    cfg = cfg or OnlineConfig()
    if any(s.split != "train" for s in train_scenarios):
        raise ValueError("online training may only run on train scenarios")
    if any(s.split != "val" for s in val_scenarios):
        raise ValueError("snapshot selection must use validation scenarios only")
    set_determinism(cfg.seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    obs_dim, n_actions = dims(SPACE)
    base_config = DDQNConfig(
        hidden_sizes=cfg.hidden_sizes,
        lr=cfg.lr,
        batch_size=cfg.batch_size,
        buffer_size=cfg.buffer_size,
        target_update_interval=cfg.target_update_interval,
        demo_lambda=cfg.demo_lambda,
        demo_margin=cfg.demo_margin,
    )
    agent = DDQNAgent(obs_dim, n_actions, base_config, seed=cfg.seed)
    demo_buf = ReplayBuffer(cfg.buffer_size, obs_dim, n_actions, seed=cfg.seed + 1)
    agent_buf = ReplayBuffer(cfg.buffer_size, obs_dim, n_actions, seed=cfg.seed + 2)
    overrides = dict(loop_overrides or {})
    loops = [
        LiveDefenseLoop(
            app_factory,
            config=LoopConfig(horizon=sc.horizon, action_space=SPACE, **overrides),
            driver=sc.driver(),
        )
        for sc in train_scenarios
    ]
    seeds = _seed_stream(cfg.seed)
    exp_path = out_dir / f"{name}_experience.jsonl"
    exp_fh = exp_path.open("w")

    def record(kind: str, sc: LiveScenario, seed: int, ts) -> None:  # noqa: ANN001
        for i, t in enumerate(ts):
            rec = {"kind": kind, "scenario": sc.name, "split": sc.split, "seed": seed, "t": i}
            exp_fh.write(json.dumps({**rec, **t.model_dump(mode="json")}, sort_keys=True) + "\n")

    def val_score() -> tuple[dict, float]:
        best_m: tuple[dict, float] | None = None
        for m in cfg.noop_margins:
            agent.config = base_config.model_copy(update={"noop_margin": float(m)})
            rows = ev.run_policy(
                ev.dqn_policy(agent),
                val_scenarios,
                app_factory,
                episodes=cfg.val_episodes,
                action_space=SPACE,
                loop_overrides=overrides,
            )
            s = ev.summarize(rows)
            s["pooled_reward"] = s["reward"]
            s["reward"] = ev.scenario_mean_reward(rows)
            s["by_scenario"] = {
                k: round(v["reward"], 4) for k, v in ev.summarize_by_scenario(rows).items()
            }
            if best_m is None or s["reward"] > best_m[0]["reward"]:
                best_m = (s, float(m))
        agent.config = base_config
        assert best_m is not None
        return best_m

    history: list[dict] = []
    best: tuple[float, int, dict, float] | None = None

    def evaluate_snapshot(step: int, phase: str) -> None:
        nonlocal best
        s, m = val_score()
        history.append(
            {
                "env_step": step,
                "phase": phase,
                "updates": agent.updates,
                "val_reward": s["reward"],
                "val_compromise_rate": s["compromise_rate"],
                "val_availability": s["availability"],
                "val_no_attack_defense_duty": s["no_attack_defense_duty"],
                "val_reward_by_scenario": s["by_scenario"],
                "noop_margin": m,
            }
        )
        log(f"[{phase}] env_step {step}: val {s['reward']:.2f} (margin {m})", flush=True)
        if best is None or s["reward"] > best[0]:
            best = (s["reward"], step, copy.deepcopy(agent.state_dict()), m)

    try:
        # 1. demonstrations (train scenarios, expert policy)
        demo_steps = 0
        for loop, sc in zip(loops, train_scenarios, strict=True):
            for _ in range(cfg.demo_episodes_per_scenario):
                seed = next(seeds)
                ts = loop.run_episode(seed=seed, policy=expert)
                _add(demo_buf, ts)
                record("demo", sc, seed, ts)
                demo_steps += len(ts)
        # 2. pretraining on demonstrations only
        for _ in range(cfg.pretrain_updates):
            agent.update(
                _demo_flag(
                    demo_buf.sample(cfg.batch_size, balance_actions=balance_demo_actions), True
                )
            )
        evaluate_snapshot(0, "pretrained")
        # 3. online interaction in the live loop
        rng = np.random.default_rng(cfg.seed + 3)
        n_demo = round(cfg.batch_size * cfg.demo_fraction)
        step = episode = 0
        losses: list[float] = []
        while step < cfg.env_steps:
            k = episode % len(loops)
            loop, sc = loops[k], train_scenarios[k]
            eps = cfg.epsilon(step)

            def act(obs: np.ndarray, mask: np.ndarray, eps: float = eps) -> int:
                if rng.random() < eps:
                    return int(rng.choice(np.flatnonzero(mask)))
                return int(agent.greedy_action(obs, mask))

            seed = next(seeds)
            ts = loop.run_episode(seed=seed, policy=act)
            _add(agent_buf, ts)
            record("agent", sc, seed, ts)
            prev = step
            step += len(ts)
            episode += 1
            if len(agent_buf) > 0:
                for _ in range(len(ts) * cfg.updates_per_step):
                    b = cat_batches(
                        _demo_flag(agent_buf.sample(cfg.batch_size - n_demo), False),
                        _demo_flag(
                            demo_buf.sample(n_demo, balance_actions=balance_demo_actions), True
                        ),
                    )
                    losses.append(agent.update(b)["loss"])
            if step // cfg.eval_every > prev // cfg.eval_every or step >= cfg.env_steps:
                evaluate_snapshot(step, "online")
    finally:
        exp_fh.close()
        for loop in loops:
            loop.close()

    assert best is not None
    agent.load_state_dict(best[2])
    agent.config = base_config.model_copy(update={"noop_margin": best[3]})
    # A selected snapshot only learned from the prefix available at that step.
    # Keep the complete experiment separately, including post-selection interaction.
    selected_exp = out_dir / f"{name}_selected_experience.jsonl"
    with exp_path.open("rb") as source, selected_exp.open("wb") as dest:
        for _ in range(demo_steps + best[1]):
            row = source.readline()
            if not row:
                raise ValueError("experience log is shorter than selected snapshot lineage")
            dest.write(row)
    digest = hashlib.sha256(selected_exp.read_bytes()).hexdigest()
    return save_checkpoint(
        agent,
        out_dir / f"{name}.pt",
        seed=cfg.seed,
        steps=best[1],
        train_configs={f"live:{s.name}": s.config_hash() for s in train_scenarios},
        env_id=ENV_IDS[SPACE],
        extra={
            "action_space": SPACE,
            "trained_on": "live:examples/payments-lite (online, from demonstrations)",
            "lineage": {
                "base_checkpoint_sha256": None,
                "base_env_id": None,
                "datasets": [f"exp_{digest[:16]}"],
                "transitions": demo_steps + best[1],
                "demo_transitions": demo_steps,
                "agent_transitions": best[1],
                "experience_sha256": digest,
                "experience_file": selected_exp.name,
            },
            "online": {
                **{k: list(v) if isinstance(v, tuple) else v for k, v in asdict(cfg).items()},
                "experiment": {
                    "agent_transitions": step,
                    "experience_file": exp_path.name,
                    "experience_sha256": hashlib.sha256(exp_path.read_bytes()).hexdigest(),
                    "updates": history[-1]["updates"],
                },
                "balance_demo_actions": balance_demo_actions,
                "expert": expert_name,
                "loop_overrides": overrides,
                "selected_env_step": best[1],
                "selected_noop_margin": best[3],
                "val_scenarios": {s.name: s.config_hash() for s in val_scenarios},
                "selection_history": history,
                "loss_mean_last_eval": float(np.mean(losses[-cfg.eval_every :]))
                if losses
                else None,
            },
        },
    )


# ---------------------------------------------------------------------- the v6 run
def run(args: argparse.Namespace) -> dict:
    from rl_defense.live.pipeline import render_markdown

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    criteria = ev.PromotionCriteria(**yaml.safe_load(Path(args.criteria).read_text()))
    cfg = getattr(args, "online_config", None) or OnlineConfig(seed=args.seed)
    lo = dict(ev.V4_LOOP_OVERRIDES)
    severity_context = getattr(args, "severity_context", "fixed")
    if severity_context != "fixed":  # v7; absent from v6's overrides, so v6 reproduces
        lo["finding_severity_context"] = severity_context
    tr = load_scenarios("train", subdir=args.train_dir)
    va = load_scenarios("val", subdir=args.val_dir)
    ho = load_scenarios("holdout", subdir=args.holdout_dir)
    app_factory = live_app

    # Registry-backed experiments gate against the hash-verified incumbent.
    registry_path = getattr(args, "registry", None)
    if registry_path and args.base_checkpoint:
        raise ValueError("registry and base_checkpoint are mutually exclusive")
    if registry_path:
        from rl_defense.live.registry import Registry

        base = Registry(Path(registry_path)).deployed_checkpoint()
    elif args.base_checkpoint:
        base = Path(args.base_checkpoint)
    else:
        train(
            load_configs(default_config_paths("train")),
            seed=args.seed,
            steps=args.base_steps,
            run_dir=out / "base",
            log_every=max(1, args.base_steps),
        )
        base = out / "base" / f"ddqn_seed{args.seed}.pt"
    deployed_agent, deployed_m = load_checkpoint(base)

    # rules tuned on train (also the static-rules bar of the gate)
    rules_params, rules_table = ev.tune_rules_v3(
        tr, app_factory, episodes=args.rules_episodes, loop_overrides=lo
    )
    expert_name, expert_scores = choose_expert(
        tr, app_factory, rules_params, episodes=args.rules_episodes, loop_overrides=lo
    )
    print(f"expert: {expert_name} {expert_scores}", flush=True)
    expert = expert_candidates(rules_params)[expert_name]

    cm = train_online(
        tr,
        va,
        app_factory,
        expert,
        out,
        cfg=cfg,
        loop_overrides=lo,
        expert_name=expert_name,
        balance_demo_actions=getattr(args, "balance_demo_actions", False),
    )
    cand_path = out / "candidate_online.pt"
    cand_agent, cand_m = load_checkpoint(cand_path)

    policies = {
        "deployed": ev.dqn_policy(deployed_agent),  # sim layout, as in v1-v5
        "candidate": ev.dqn_policy(cand_agent),
        "threshold_rules": ev.rules_policy(rules_params),
        "noop": ev.noop_policy,
        "always_isolate_payments": ev.always_isolate_payments,
        "always_block_principal": ev.always_block_principal,
        "always_block_principal_long": ev.always_block_principal_long,
        "always_block_top_principal_long": ev.always_block_top_principal_long,
    }
    if getattr(args, "random_baseline", False):
        random_rng = np.random.default_rng(cfg.seed + 91_019)
        policies["random_valid"] = lambda obs, mask: int(random_rng.choice(np.flatnonzero(mask)))
    references = []
    for ref_name, ref_path in parse_references(getattr(args, "reference_checkpoint", None)):
        ref_agent, ref_m = load_checkpoint(Path(ref_path))
        policies[ref_name] = ev.dqn_policy(ref_agent)  # reported only; not in the gate
        references.append(
            {
                "name": ref_name,
                "path": str(ref_path),
                "checkpoint_sha256": ref_m["checkpoint_sha256"],
                "env_id": ref_m["env_id"],
            }
        )
    reference = references[0] if references else None
    trajectory_path = out / "holdout_trajectories.jsonl.gz"
    trajectories = (
        gzip.open(trajectory_path, "wt") if getattr(args, "record_trajectories", False) else None
    )
    rows = {}
    try:
        for policy_name, policy in policies.items():

            def record_episode(sc, seed, transitions, policy_name=policy_name):  # noqa: ANN001, ANN202
                if trajectories is not None:
                    trajectories.write(
                        json.dumps(
                            {
                                "policy": policy_name,
                                "scenario": sc.name,
                                "seed": seed,
                                "transitions": [t.model_dump(mode="json") for t in transitions],
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )

            rows[policy_name] = ev.run_policy(
                policy,
                ho,
                app_factory,
                episodes=args.holdout_episodes,
                action_space=SPACE,
                loop_overrides=lo,
                on_episode=record_episode,
            )
    finally:
        if trajectories is not None:
            trajectories.close()
    verdict = ev.promotion_decision(
        candidate=rows["candidate"],
        deployed=rows["deployed"],
        rules=rows["threshold_rules"],
        criteria=criteria,
    )
    expert_rows = rows[expert_name]
    hist = cm["online"]["selection_history"]
    sel = next(h for h in hist if h["env_step"] == cm["online"]["selected_env_step"])
    report = {
        "schema": REPORT_SCHEMA,
        "mode": "online_dqfd",
        "caveat": ev.CAVEAT,
        "target": "examples/payments-lite (in-process, owned demo app)",
        "action_space": SPACE,
        "holdout_dir": f"configs/live/{args.holdout_dir}",
        "train_dir": f"configs/live/{args.train_dir}",
        "val_dir": f"configs/live/{args.val_dir}",
        "noop_margins": list(cfg.noop_margins),
        "loop_overrides": lo,
        "val_selection": "scenario_mean",
        "online": {k: v for k, v in cm["online"].items() if k != "selection_history"},
        "expert": {"name": expert_name, "train_scores": expert_scores},
        "candidate_vs_expert_paired": ev.paired_reward_diff(rows["candidate"], expert_rows),
        "finding_severity_context": severity_context,
        "reference": reference,
        "candidate_vs_reference_paired": ev.paired_reward_diff(
            rows["candidate"], rows[reference["name"]]
        )
        if reference
        else None,
        "references": [
            {**r, "candidate_vs_paired": ev.paired_reward_diff(rows["candidate"], rows[r["name"]])}
            for r in references
        ],
        "deployed": {
            "checkpoint_sha256": deployed_m["checkpoint_sha256"],
            "env_id": deployed_m["env_id"],
            "trained_on": deployed_m.get("trained_on", "simulator (DefenseSimEnv-v0)"),
        },
        "candidate": {
            "checkpoint_sha256": cand_m["checkpoint_sha256"],
            "round": 1,
            "lineage": cand_m["lineage"],
            "selected_update": cm["online"]["selected_env_step"],
        },
        "criteria": criteria.model_dump(),
        "splits": {
            "train": {s.name: s.config_hash() for s in tr},
            "val": {s.name: s.config_hash() for s in va},
            "holdout": {s.name: s.config_hash() for s in ho},
        },
        "holdout_episodes_per_scenario": args.holdout_episodes or ho[0].episodes,
        "rounds": [
            {
                "round": 1,
                "epsilon": f"{cfg.eps_start}->{cfg.eps_end}",
                "transitions": cm["lineage"]["agent_transitions"],
                "selected_update": sel["env_step"],
                "noop_margin": sel["noop_margin"],
                "val_reward": sel["val_reward"],
                "val_compromise_rate": sel["val_compromise_rate"],
                "val_availability": sel["val_availability"],
                "val_reward_by_scenario": sel["val_reward_by_scenario"],
                "val_curve": [[h["env_step"], round(h["val_reward"], 4)] for h in hist],
            }
        ],
        "balance_demo_actions": getattr(args, "balance_demo_actions", False),
        "rules_episodes": args.rules_episodes,
        "rules_params": rules_params,
        "rules_no_block_params": None,
        "rules_short_only_params": None,
        "policies": {n: ev.summarize(r) for n, r in rows.items()},
        "by_scenario": {n: ev.summarize_by_scenario(r) for n, r in rows.items()},
        **verdict,
        "git_sha": git_sha(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    # Durable, hash-pinned locators alongside the report. Relative paths survive copying.
    report["artifacts"] = {
        "checkpoint": {"path": cand_path.name, "sha256": cand_m["checkpoint_sha256"]},
        "experience": {
            "path": cm["lineage"]["experience_file"],
            "sha256": cm["lineage"]["experience_sha256"],
        },
        "experiment": {
            "path": cm["online"]["experiment"]["experience_file"],
            "sha256": cm["online"]["experiment"]["experience_sha256"],
        },
    }
    if trajectories is not None:
        report["artifacts"]["holdout_trajectories"] = {
            "path": trajectory_path.name,
            "sha256": hashlib.sha256(trajectory_path.read_bytes()).hexdigest(),
        }
    (out / "promotion_report.json").write_text(json.dumps(report, indent=2))
    (out / "holdout_episodes.json").write_text(
        json.dumps({n: [asdict(x) for x in r] for n, r in rows.items()})
    )
    (out / "rules_tuning.json").write_text(
        json.dumps({"selected": rules_params, "grid": rules_table}, indent=2)
    )
    (out / "REPORT.md").write_text(render_online_markdown(report, render_markdown))
    if args.evidence_dir:
        ed = Path(args.evidence_dir)
        ed.mkdir(parents=True, exist_ok=True)
        for f in [
            "promotion_report.json",
            "REPORT.md",
            "rules_tuning.json",
            "holdout_episodes.json",
        ]:
            shutil.copy(out / f, ed / f)
        for artifact in report["artifacts"].values():
            shutil.copy(out / artifact["path"], ed / artifact["path"])
        shutil.copy(
            cand_path.with_suffix(".manifest.json"),
            ed / cand_path.with_suffix(".manifest.json").name,
        )
    return report


_REF_PAIRED = "candidate_vs_reference_paired"


def parse_references(spec: str | list[str] | None) -> list[tuple[str, str]]:
    """``--reference-checkpoint`` values as (policy name, path). ``NAME=PATH`` names the
    policy; a bare path is ``reference`` (v7's single reference), then ``reference_2``..."""
    items = [spec] if isinstance(spec, str) else list(spec or [])
    out: list[tuple[str, str]] = []
    for i, item in enumerate(items):
        name, sep, path = item.partition("=")
        if not sep or not name.isidentifier():
            name, path = ("reference" if i == 0 else f"reference_{i + 1}"), item
        out.append((name, path))
    names = [n for n, _ in out]
    taken = set(names) & {"deployed", "candidate", "threshold_rules", "noop", "random_valid"}
    if (
        len(set(names)) != len(names)
        or taken
        or "reference" in names[1:]
        or any(n.startswith("always_") for n in names)
    ):
        raise ValueError(f"reference names must be unique and new: {names}")
    return out


def render_online_markdown(r: dict, render_markdown) -> str:  # noqa: ANN001
    """The shared report, with the online-training specifics (expert, schedule) added and
    the "rounds" wording adapted (one online run; "update" = environment step)."""
    md = render_markdown(r)
    md = md.replace(
        "## Rounds (selection on validation only)",
        "## Online training (selection on validation only; one run, columns in env steps)",
    )
    md = md.replace(
        "Val return by number of offline updates (selection score; update 0 = warm start):",
        "Val return by environment steps (selection score; step 0 = after demonstration "
        "pretraining):",
    )
    o, e, d = r["online"], r["expert"], r["candidate_vs_expert_paired"]
    lin = r["candidate"]["lineage"]
    extra = [
        "",
        "## Demonstrations and online schedule",
        "",
        f"Expert (chosen on train only): `{e['name']}`. Train returns: "
        + ", ".join(f"{k} {v:.2f}" for k, v in e["train_scores"].items())
        + ".",
        f"Demonstrations: {lin['demo_transitions']} transitions "
        f"({o['demo_episodes_per_scenario']} episodes per train scenario); pretraining "
        f"{o['pretrain_updates']} updates; online {lin['agent_transitions']} live transitions, "
        f"ε {o['eps_start']}→{o['eps_end']} over {o['eps_decay_steps']} steps, demo share "
        f"{o['demo_fraction']} of every batch, DQfD λ={o['demo_lambda']}, margin "
        f"{o['demo_margin']}. Fresh network (no simulator prior).",
        f"Selected: env step {o['selected_env_step']}, noop margin {o['selected_noop_margin']}.",
        "",
        f"Paired return (candidate − expert `{e['name']}`) on holdout: {d['mean']:.2f} "
        f"[{d['ci95'][0]:.2f}, {d['ci95'][1]:.2f}] over {d['pairs']} episodes.",
        "",
    ]
    if r.get("finding_severity_context", "fixed") != "fixed":
        extra += [
            f"Finding-severity context: `{r['finding_severity_context']}` (drawn per episode "
            "from the severities platform_mapping can produce; every policy, every split).",
            "",
        ]
    refs = r.get("references") or (
        [{**r["reference"], "name": "reference", "candidate_vs_paired": r[_REF_PAIRED]}]
        if r.get("reference")
        else []
    )
    for ref in refs:
        rd = ref["candidate_vs_paired"]
        extra += [
            f"Reference (reported only, not in the gate) `{ref['name']}`: `{ref['path']}` "
            f"(`{ref['checkpoint_sha256'][:12]}`). Paired return (candidate − "
            f"{ref['name']}) on holdout: {rd['mean']:.2f} [{rd['ci95'][0]:.2f}, "
            f"{rd['ci95'][1]:.2f}] over {rd['pairs']} episodes.",
            "",
        ]
    return md + "\n".join(extra)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    baseline = ap.add_mutually_exclusive_group()
    baseline.add_argument("--base-checkpoint", default=None)
    baseline.add_argument(
        "--registry",
        default=None,
        help="gate against the hash-verified deployed checkpoint in this local registry",
    )
    ap.add_argument("--base-steps", type=int, default=30_000)
    ap.add_argument("--rules-episodes", type=int, default=2)
    ap.add_argument("--holdout-episodes", type=int, default=None)
    ap.add_argument("--criteria", default=str(CONFIG_DIR / "promotion.yaml"))
    ap.add_argument("--train-dir", default="train_v3")
    ap.add_argument("--val-dir", default="val_v4")
    ap.add_argument("--holdout-dir", default="holdout_v6")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--balance-demo-actions",
        action="store_true",
        help="sample observed demonstration action classes uniformly (experimental)",
    )
    ap.add_argument("--random-baseline", action="store_true")
    ap.add_argument("--record-trajectories", action="store_true")
    ap.add_argument("--out", default="runs/live/retrain-v6")
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument(
        "--severity-context",
        choices=["fixed", "platform"],
        default="fixed",
        help="finding severities per episode: fixed baseline (v1-v6) or platform-producible (v7)",
    )
    ap.add_argument(
        "--reference-checkpoint",
        action="append",
        default=None,
        help="an already-trained policy reported on holdout next to the candidate (not gated);"
        " repeatable, as NAME=PATH or a bare PATH (v8: v6=... and v7=...)",
    )
    r = run(ap.parse_args(argv))
    print(r["decision"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
