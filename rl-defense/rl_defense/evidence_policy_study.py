"""Can the DDQN learn an evidence-driven defense under the v1 reward?

    python -m rl_defense.evidence_policy_study --out results/evidence-policy

Follow-up to results/reward-v1: with ``c_false_disrupt`` the plain DDQN stopped throttling
healthy nodes but then let the adversary through. A deterministic rule (monitor the exposed
nodes, isolate only on an anomaly signal: ``MonitorIsolatePolicy``) shows the objective is
reachable. This study fixes the trade-off at ``C`` (an owner decision, 2026-11-13) and
compares, on the same held-out episodes:

- ``ddqn_guided``  : DDQN under the v1 reward whose first ``GUIDE_STEPS`` behaviour steps
                     follow the rule 70% of the time (guided exploration; ordinary targets)
- ``ddqn_unguided``: the same settings and seeds without the guide
- ``ddqn_v0``      : the same settings and seeds under the v0 reward (the original objective)
- ``monitor_isolate``, ``exposed_guard``, ``threshold_rules``: deterministic rules tuned on
  the training configs under the v1 reward; ``random``; ``noop``

Acceptance, fixed before the run: the guided DDQN is an improvement over the original only if,
held-out, its compromise rate is not above ``ddqn_v0``'s AND its false-disruption rate and
benign load are both lower. Whether it beats ``monitor_isolate`` is reported, not assumed.
Simulation output only.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from rl_defense.baselines import (
    ExposedGuardPolicy,
    MonitorIsolatePolicy,
    NoopPolicy,
    RandomValidPolicy,
    ThresholdRulesPolicy,
    tune_exposed_guard,
    tune_monitor_isolate,
    tune_threshold_rules,
)
from rl_defense.baselines.policies import Policy
from rl_defense.checkpoint import git_sha, load_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.evaluate import CAVEAT
from rl_defense.learning_check import GreedyAgentPolicy
from rl_defense.reward_v1_study import (
    ADVERSARY_SCALE,
    DDQN,
    HELD_OUT_SEEDS,
    SELECT_EVERY,
    SELECT_START,
    STEPS,
    VALIDATION_SEEDS,
    _over_seeds,
    _row,
    score,
    to_arm,
)
from rl_defense.train import train

C = 0.25
GUIDE_STEPS = 100_000
GUIDE_PROB = 0.7
ARMS: dict[str, tuple[float, bool]] = {
    "ddqn_guided": (C, True),
    "ddqn_unguided": (C, False),
    "ddqn_v0": (0.0, False),
}


def _train_one(job: tuple[str, int, int, str, float]) -> dict[str, Any]:
    arm, seed, steps, out, guide_thr = job
    c, guided = ARMS[arm]
    configs = [to_arm(cfg, c) for cfg in load_configs(default_config_paths("train"))]
    scale = steps / STEPS
    manifest = train(
        configs,
        seed,
        steps,
        Path(out) / arm,
        DDQN.model_copy(update={"eps_decay_steps": max(1, int(DDQN.eps_decay_steps * scale))}),
        adversary_scale=ADVERSARY_SCALE,
        select_every=max(1, int(SELECT_EVERY * scale)),
        select_start=int(SELECT_START * scale),
        guide=MonitorIsolatePolicy(guide_thr) if guided else None,
        guide_steps=int(GUIDE_STEPS * scale) if guided else 0,
        guide_prob=GUIDE_PROB,
    )
    return {"arm": arm, "seed": seed, "checkpoint_sha256": manifest["checkpoint_sha256"]}


def _score_policy(job: tuple[str, str, int | None, str, dict[str, Any]]) -> tuple[str, str, dict]:
    """One policy on one split, always scored under the v1 reward at ``C``."""
    name, split, seed, out, tuned = job
    base = load_configs(default_config_paths("train" if split == "validation" else "eval"))
    cfgs = [to_arm(cfg, C) for cfg in base]
    ep_seeds = VALIDATION_SEEDS if split == "validation" else HELD_OUT_SEEDS
    policy: Policy
    if name in ARMS:
        agent, _ = load_checkpoint(Path(out) / name / f"ddqn_seed{seed}.pt")
        policy = GreedyAgentPolicy(agent, name)
    elif name == "monitor_isolate":
        policy = MonitorIsolatePolicy(tuned["monitor_isolate"])
    elif name == "exposed_guard":
        policy = ExposedGuardPolicy(tuned["exposed_guard"])
    elif name == "threshold_rules":
        policy = ThresholdRulesPolicy(tune_threshold_rules(cfgs_train())[0])
    elif name == "random":
        policy = RandomValidPolicy(seed=seed or 0)
    else:
        policy = NoopPolicy()
    return name, split, score(policy, cfgs, ep_seeds)


def cfgs_train() -> list:
    return [to_arm(cfg, C) for cfg in load_configs(default_config_paths("train"))]


def verdict(held: dict[str, Any]) -> dict[str, Any]:
    g, o = held["ddqn_guided"], held["ddqn_v0"]
    checks = {
        "compromise_not_above_original": g["compromise_rate"]["mean"]
        <= o["compromise_rate"]["mean"],
        "false_disruption_lower": g["false_disruption_rate"]["mean"]
        < o["false_disruption_rate"]["mean"],
        "benign_load_lower": g["benign_load"]["mean"] < o["benign_load"]["mean"],
    }
    rule = held["monitor_isolate"]
    return {
        "checks": checks,
        "improves_on_original": all(checks.values()),
        "beats_monitor_isolate_on_return": g["return_arm"]["mean"] > rule["return_arm"]["mean"],
        "beats_monitor_isolate_on_compromise": g["compromise_rate"]["mean"]
        < rule["compromise_rate"]["mean"],
    }


def run_study(
    out: Path,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4),
    steps: int = STEPS,
    workers: int = 9,
    arms: tuple[str, ...] = tuple(ARMS),
) -> dict[str, Any]:
    """``arms`` must include ``ddqn_guided`` and ``ddqn_v0``: the verdict compares them."""
    if not {"ddqn_guided", "ddqn_v0"} <= set(arms) or not set(arms) <= set(ARMS):
        raise ValueError(f"arms must include ddqn_guided and ddqn_v0 and come from {list(ARMS)}")
    out.mkdir(parents=True, exist_ok=True)
    train_cfgs = cfgs_train()
    tuned = {
        "monitor_isolate": tune_monitor_isolate(train_cfgs)[0],
        "exposed_guard": tune_exposed_guard(train_cfgs)[0],
    }
    jobs = [(arm, s, steps, str(out), tuned["monitor_isolate"]) for arm in arms for s in seeds]
    score_jobs: list[tuple[str, str, int | None, str, dict[str, Any]]] = []
    for split in ("validation", "held_out"):
        for name in (*arms, "random"):
            score_jobs += [(name, split, s, str(out), tuned) for s in seeds]
        for name in ("monitor_isolate", "exposed_guard", "threshold_rules", "noop"):
            score_jobs.append((name, split, None, str(out), tuned))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        trained = list(pool.map(_train_one, jobs))
        scored = list(pool.map(_score_policy, score_jobs))
    results: dict[str, dict[str, Any]] = {"validation": {}, "held_out": {}}
    for split in results:
        names = dict.fromkeys(n for n, sp, _ in scored if sp == split)
        for name in names:
            results[split][name] = _over_seeds(
                [m for n, sp, m in scored if n == name and sp == split]
            )
    summary = {
        "caveat": CAVEAT,
        "kind": "evidence-policy study (v1 reward, guided exploration)",
        "git_sha": git_sha(),
        "c_false_disrupt": C,
        "guide": {"policy": "monitor_isolate", "steps": GUIDE_STEPS, "prob": GUIDE_PROB},
        "tuned_on_train": tuned,
        "training_seeds": list(seeds),
        "training_steps": steps,
        "ddqn_config": DDQN.model_dump(mode="json"),
        "held_out_episode_seeds": [HELD_OUT_SEEDS.start, HELD_OUT_SEEDS.stop - 1],
        "validation_episode_seeds": [VALIDATION_SEEDS.start, VALIDATION_SEEDS.stop - 1],
        "checkpoints": trained,
        **results,
        "verdict": verdict(results["held_out"]),
    }
    (out / "study.json").write_text(json.dumps(summary, indent=2))
    (out / "study.md").write_text(render(summary))
    return summary


def render(summary: dict[str, Any]) -> str:
    v = summary["verdict"]
    lines = [
        "# Evidence-policy study",
        "",
        f"_{summary['caveat']}_",
        "",
        f"Commit `{summary['git_sha'][:12]}`. v1 reward with c_false_disrupt = "
        f"{summary['c_false_disrupt']}. Training seeds {summary['training_seeds']}, "
        f"{summary['training_steps']:,} steps. Every policy is scored on the same episodes; "
        "'Return (arm reward)' is the v1 return. CIs are 95% bootstrap over training seeds.",
        "",
        f"Improves on the original DDQN (all three checks): **{v['improves_on_original']}** "
        f"{v['checks']}. Beats the monitor_isolate rule on return: "
        f"**{v['beats_monitor_isolate_on_return']}**; on compromise: "
        f"**{v['beats_monitor_isolate_on_compromise']}**.",
        "",
    ]
    header = (
        "| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % "
        "| False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |"
    )
    for split, title in (("validation", "Validation"), ("held_out", "Held-out")):
        lines += [f"## {title}", "", header, "|---|---|---|---|---|---|---|---|---|---|"]
        lines += [_row(name, m) for name, m in summary[split].items()]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--workers", type=int, default=9)
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    args = ap.parse_args()
    print(
        render(run_study(args.out, tuple(args.seeds), args.steps, args.workers, tuple(args.arms)))
    )


if __name__ == "__main__":
    main()
