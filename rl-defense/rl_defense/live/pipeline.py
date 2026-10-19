"""Live retraining pipeline: experience → offline candidate → held-out verdict.

    python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
        --out runs/live/retrain-v1 --evidence-dir results/live-retrain

Steps (asynchronous, versioned, and never touching the deployed policy):
  1. deployed policy = ``--base-checkpoint`` (or a sim-trained one, ``--base-steps``)
  2. for each round: collect ε-greedy experience on TRAIN scenarios with the current
     behavior policy, aggregate the datasets, retrain a candidate from the deployed
     weights, select its snapshot on VAL scenarios; the next round behaves with it
  3. pick the round whose candidate scored best on VAL
  4. tune threshold rules on the same TRAIN scenarios
  5. evaluate deployed, candidate, rules, noop and always-isolate ONCE on HOLDOUT
  6. apply the pre-registered criteria (configs/live/promotion.yaml) → report

The output is a recommendation. Promotion is ``python -m rl_defense.live.registry promote``
with a human approver id.

v2 (``--action-space live_v2 --holdout-dir holdout_v2``): the candidate and the rules may
use ``block_principal``; the deployed sim policy cannot. ``always_block_principal`` and the
best rules without blocking (``threshold_rules_no_block``) are reported for context.

v3 (``--action-space live_v3 --train-dir train_v3 --val-dir val_v3 --holdout-dir
holdout_v3 --noop-margins 0,0.1,0.2,0.3,0.5``): adds ``block_principal_long`` and legitimate
delegated cross-tenant reads. The rules are tuned with :func:`evaluate.tune_rules_v3`;
the v2-style rules (short blocks only), ``always_block_principal`` and
``always_block_principal_long`` and ``always_block_top_principal_long`` are reported
for context.

v4 (v3 flags plus ``--c-disrupt 1.0 --delegation-aware-detector --val-selection
scenario_mean --val-dir val_v4 --holdout-dir holdout_v4``): the reward prices a blocked
legitimate request like a compromised read, the detector honours the delegation grants,
and snapshots/margins/rounds are selected on the mean over several val scenarios. The
defaults (0.5, off, pooled) reproduce v1-v3. Every policy, the rules tuning and the
experience run in the same loop configuration (results/live-retrain-v4/PROVENANCE.md).
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml
from payments_lite.app import create_app

from rl_defense.checkpoint import git_sha, load_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live.actions import as_space
from rl_defense.live.adversary import live_app
from rl_defense.live.experience import collect
from rl_defense.live.retrain import retrain
from rl_defense.live.scenarios import CONFIG_DIR, load_scenarios
from rl_defense.train import train

REPORT_SCHEMA = "live-promotion-report/0.1"


def run(args: argparse.Namespace) -> dict:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    criteria = ev.PromotionCriteria(**yaml.safe_load(Path(args.criteria).read_text()))
    space = getattr(args, "action_space", "sim")
    holdout_dir = getattr(args, "holdout_dir", None) or "holdout"
    train_dir = getattr(args, "train_dir", None) or "train"
    val_dir = getattr(args, "val_dir", None) or "val"
    margins = tuple(float(x) for x in str(getattr(args, "noop_margins", "0") or "0").split(","))
    loop_overrides: dict[str, object] = {}
    c_disrupt = getattr(args, "c_disrupt", None)
    if c_disrupt is not None:
        loop_overrides["c_disrupt"] = float(c_disrupt)
    if getattr(args, "delegation_aware_detector", False):
        loop_overrides["delegation_aware_detector"] = True
    selection = getattr(args, "val_selection", None) or "pooled"
    lo = loop_overrides or None
    tr, va = load_scenarios("train", subdir=train_dir), load_scenarios("val", subdir=val_dir)
    ho = load_scenarios("holdout", subdir=holdout_dir)
    # extra fixture tenants/tokens only when needed: the v1 run stays on the stock seed
    v2_world = space != "sim" or any(s.uses_extra_identities for s in [*tr, *va, *ho])
    app_factory = live_app if v2_world else create_app

    # 1. deployed policy
    if args.base_checkpoint:
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

    # 2. rounds
    epsilons = [float(e) for e in args.epsilons.split(",")]
    if len(epsilons) < args.rounds:
        epsilons += [epsilons[-1]] * (args.rounds - len(epsilons))
    behavior = as_space(deployed_agent, space) if space != "sim" else deployed_agent
    behavior_m = deployed_m
    datasets: list[Path] = []
    rounds: list[dict] = []
    for k in range(1, args.rounds + 1):
        ds = out / f"experience_round{k}.jsonl"
        dm = collect(
            tr,
            ds,
            app_factory,
            agent=behavior,
            behavior_checkpoint_sha256=behavior_m["checkpoint_sha256"],
            epsilon=epsilons[k - 1],
            seed=args.seed + k,
            episodes=args.train_episodes,
            action_space=space,
            loop_overrides=lo,
        )
        datasets.append(ds)
        cm = retrain(
            base,
            datasets,
            out,
            app_factory,
            val_scenarios=va,
            updates=args.updates,
            eval_every=args.eval_every,
            val_episodes=args.val_episodes,
            seed=args.seed,
            name=f"candidate_round{k}",
            action_space=space,
            noop_margins=margins,
            loop_overrides=lo,
            selection=selection,
        )
        sel = next(
            h
            for h in cm["retrain"]["selection_history"]
            if h["update"] == cm["retrain"]["selected_update"]
        )
        rounds.append(
            {
                "round": k,
                "dataset_id": dm["dataset_id"],
                "transitions": dm["transitions"],
                "epsilon": epsilons[k - 1],
                "behavior_checkpoint_sha256": behavior_m["checkpoint_sha256"],
                "candidate_checkpoint_sha256": cm["checkpoint_sha256"],
                "selected_update": sel["update"],
                "val_reward": sel["val_reward"],
                "val_compromise_rate": sel["val_compromise_rate"],
                "val_availability": sel["val_availability"],
                "noop_margin": cm["retrain"]["selected_noop_margin"],
                **(
                    {"val_reward_by_scenario": sel["val_reward_by_scenario"]}
                    if "val_reward_by_scenario" in sel
                    else {}
                ),
            }
        )
        behavior, behavior_m = load_checkpoint(out / f"candidate_round{k}.pt")
        print(
            f"round {k}: {dm['transitions']} new transitions, val reward {sel['val_reward']:.2f}",
            flush=True,
        )

    # 3. final candidate by validation only
    best = max(rounds, key=lambda r: r["val_reward"])
    cand_path = out / f"candidate_round{best['round']}.pt"
    cand_agent, cand_m = load_checkpoint(cand_path)

    # 4. rules on train scenarios
    if space == "live_v3":
        rules_params, rules_table = ev.tune_rules_v3(
            tr, app_factory, episodes=args.rules_episodes, loop_overrides=lo
        )
    else:
        rules_params, rules_table = ev.tune_rules(
            tr, app_factory, episodes=args.rules_episodes, action_space=space, loop_overrides=lo
        )

    # 5. holdout, once
    policies = {
        "deployed": ev.dqn_policy(deployed_agent),
        "candidate": ev.dqn_policy(cand_agent),
        "threshold_rules": ev.rules_policy(rules_params),
        "noop": ev.noop_policy,
        "always_isolate_payments": ev.always_isolate_payments,
    }
    no_block_params = None
    short_only_params = None
    if space in ("live_v2", "live_v3"):
        nb = max(
            (r for r in rules_table if r.get("block_anomaly", 1.1) > 1.0),
            key=lambda r: r["train_reward"],
        )
        no_block_params = {
            k: v for k, v in nb.items() if k not in ("train_reward", "block_anomaly", "stage")
        }
        policies["threshold_rules_no_block"] = ev.rules_policy(no_block_params)
        policies["always_block_principal"] = ev.always_block_principal
    if space == "live_v3":
        so = max(
            (r for r in rules_table if r.get("long_mode", "never") == "never"),
            key=lambda r: r["train_reward"],
        )
        short_only_params = {k: v for k, v in so.items() if k not in ("train_reward", "stage")}
        policies["threshold_rules_short_only"] = ev.rules_policy(short_only_params)
        policies["always_block_principal_long"] = ev.always_block_principal_long
        policies["always_block_top_principal_long"] = ev.always_block_top_principal_long
    rows = {
        n: ev.run_policy(
            p,
            ho,
            app_factory,
            episodes=args.holdout_episodes,
            action_space=space,
            loop_overrides=lo,
        )
        for n, p in policies.items()
    }

    # 6. verdict
    verdict = ev.promotion_decision(
        candidate=rows["candidate"],
        deployed=rows["deployed"],
        rules=rows["threshold_rules"],
        criteria=criteria,
    )
    report = {
        "schema": REPORT_SCHEMA,
        "caveat": ev.CAVEAT,
        "target": "examples/payments-lite (in-process, owned demo app)",
        "action_space": space,
        "holdout_dir": f"configs/live/{holdout_dir}",
        "train_dir": f"configs/live/{train_dir}",
        "val_dir": f"configs/live/{val_dir}",
        "noop_margins": list(margins),
        "loop_overrides": loop_overrides,
        "val_selection": selection,
        "deployed": {
            "checkpoint_sha256": deployed_m["checkpoint_sha256"],
            "env_id": deployed_m["env_id"],
            "trained_on": deployed_m.get("trained_on", "simulator (DefenseSimEnv-v0)"),
        },
        "candidate": {
            "checkpoint_sha256": cand_m["checkpoint_sha256"],
            "round": best["round"],
            "lineage": cand_m["lineage"],
            "selected_update": cand_m["retrain"]["selected_update"],
        },
        "criteria": criteria.model_dump(),
        "splits": {
            "train": {s.name: s.config_hash() for s in tr},
            "val": {s.name: s.config_hash() for s in va},
            "holdout": {s.name: s.config_hash() for s in ho},
        },
        "holdout_episodes_per_scenario": args.holdout_episodes or ho[0].episodes,
        "rounds": rounds,
        "rules_params": rules_params,
        "rules_no_block_params": no_block_params,
        "rules_short_only_params": short_only_params,
        "policies": {n: ev.summarize(r) for n, r in rows.items()},
        "by_scenario": {n: ev.summarize_by_scenario(r) for n, r in rows.items()},
        **verdict,
        "git_sha": git_sha(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    (out / "promotion_report.json").write_text(json.dumps(report, indent=2))
    (out / "holdout_episodes.json").write_text(
        json.dumps({n: [asdict(x) for x in r] for n, r in rows.items()})
    )
    (out / "rules_tuning.json").write_text(
        json.dumps({"selected": rules_params, "grid": rules_table}, indent=2)
    )
    (out / "REPORT.md").write_text(render_markdown(report))
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
        for k in range(1, args.rounds + 1):
            shutil.copy(
                out / f"experience_round{k}.manifest.json",
                ed / f"experience_round{k}.manifest.json",
            )
        shutil.copy(cand_path.with_suffix(".manifest.json"), ed / "candidate.manifest.json")
    return report


def _f(x, nd: int = 3) -> str:  # noqa: ANN001
    return "n/a" if x is None else f"{x:.{nd}f}"


def render_markdown(r: dict) -> str:
    lines = [
        "# Live retraining — held-out evaluation and promotion verdict",
        "",
        f"> {r['caveat']}",
        "",
        f"**Decision: `{r['decision']}`** (requires human approval: {r['requires_human_approval']}).",
        f"Action space: `{r.get('action_space', 'sim')}`; holdout scenarios from "
        f"`{r.get('holdout_dir', 'configs/live/holdout')}`.",
        *(
            [
                f"Loop overrides: `{r['loop_overrides']}`; val selection: "
                f"`{r.get('val_selection', 'pooled')}` over {', '.join(r['splits']['val'])}."
            ]
            if r.get("loop_overrides")
            else []
        ),
        f"Deployed `{r['deployed']['checkpoint_sha256'][:12]}` (sim-trained) vs candidate "
        f"`{r['candidate']['checkpoint_sha256'][:12]}` (round {r['candidate']['round']}, "
        f"{r['candidate']['lineage']['transitions']} live transitions). "
        f"Holdout: {', '.join(r['splits']['holdout'])} × {r['holdout_episodes_per_scenario']} episodes, paired.",
        "",
        "## Held-out results (all scenarios)",
        "",
        "| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |",
        "|---|---|---|---|---|---|---|",
    ]
    for n, s in r["policies"].items():
        lo, hi = s["reward_ci95"]
        lines.append(
            f"| {n} | {s['reward']:.2f} [{lo:.2f}, {hi:.2f}] | {_f(s['compromise_rate'])} | {_f(s['availability'])} "
            f"| {_f(s['false_disruption'])} | {_f(s['no_attack_defense_duty'])} | {_f(s['actions_per_step'], 2)} |"
        )
    d = r["paired_reward_diff"]
    lines += [
        "",
        f"Paired return gain (candidate − deployed): {d['mean']:.2f} [{d['ci95'][0]:.2f}, {d['ci95'][1]:.2f}] over {d['pairs']} episodes.",
        "",
        "## Per held-out scenario (return / compromise / availability)",
        "",
        "| Scenario | " + " | ".join(r["by_scenario"]) + " |",
        "|---|" + "---|" * len(r["by_scenario"]),
    ]
    for sc in r["splits"]["holdout"]:
        cells = []
        for n in r["by_scenario"]:
            s = r["by_scenario"][n][sc]
            cells.append(
                f"{s['reward']:.2f} / {_f(s['compromise_rate'], 2)} / {_f(s['availability'], 2)}"
            )
        lines.append(f"| {sc} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Acceptance criteria (pre-registered in configs/live/promotion.yaml)",
        "",
        "| Check | Value | Threshold | Pass |",
        "|---|---|---|---|",
    ]
    for c in r["checks"]:
        v = c["value"]
        lines.append(
            f"| {c['name']} | {_f(v) if isinstance(v, float) else v} | {c['threshold']} | {'✅' if c['passed'] else '❌'} |"
        )
    lines += [
        "",
        "## Rounds (selection on validation only)",
        "",
        "| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for x in r["rounds"]:
        lines.append(
            f"| {x['round']} | {x['epsilon']} | {x['transitions']} | {x['selected_update']} | "
            f"{x.get('noop_margin', 0.0)} | "
            f"{x['val_reward']:.2f} | {_f(x['val_compromise_rate'])} | {_f(x['val_availability'])} |"
        )
    per_val = [x for x in r["rounds"] if x.get("val_reward_by_scenario")]
    if per_val:
        names = list(per_val[0]["val_reward_by_scenario"])
        lines += [
            "",
            "Val return per scenario at each round's selected snapshot (the score above is "
            "their unweighted mean):",
            "",
            "| Round | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
        ]
        for x in per_val:
            v = x["val_reward_by_scenario"]
            lines.append(f"| {x['round']} | " + " | ".join(f"{v[n]:.2f}" for n in names) + " |")
    lines += ["", f"Threshold rules tuned on train scenarios: `{r['rules_params']}`."]
    if r.get("rules_no_block_params"):
        lines.append(f"Best rules without `block_principal`: `{r['rules_no_block_params']}`.")
    if r.get("rules_short_only_params"):
        lines.append(f"Best rules with short blocks only: `{r['rules_short_only_params']}`.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--base-checkpoint", default=None)
    ap.add_argument("--base-steps", type=int, default=30_000)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--epsilons", default="0.5,0.3,0.2")
    ap.add_argument("--updates", type=int, default=16_000)
    ap.add_argument("--eval-every", type=int, default=2_000)
    ap.add_argument("--val-episodes", type=int, default=8)
    ap.add_argument(
        "--train-episodes", type=int, default=None, help="cap episodes per train scenario"
    )
    ap.add_argument(
        "--holdout-episodes", type=int, default=None, help="cap episodes per holdout scenario"
    )
    ap.add_argument("--rules-episodes", type=int, default=2)
    ap.add_argument("--criteria", default=str(CONFIG_DIR / "promotion.yaml"))
    ap.add_argument("--action-space", choices=["sim", "live_v2", "live_v3"], default="sim")
    ap.add_argument(
        "--holdout-dir", default="holdout", help="subdirectory of configs/live with holdout yaml"
    )
    ap.add_argument("--train-dir", default="train", help="subdirectory with train yaml")
    ap.add_argument("--val-dir", default="val", help="subdirectory with val yaml")
    ap.add_argument(
        "--noop-margins",
        default="0",
        help="comma-separated greedy abstention margins chosen on val per snapshot",
    )
    ap.add_argument(
        "--c-disrupt",
        type=float,
        default=None,
        help="reward weight of blocked legitimate traffic (default: LoopConfig, 0.5; v4: 1.0)",
    )
    ap.add_argument(
        "--delegation-aware-detector",
        action="store_true",
        help="v4: the detector honours the delegation grant table",
    )
    ap.add_argument(
        "--val-selection",
        choices=["pooled", "scenario_mean"],
        default="pooled",
        help="v4: select on the unweighted mean over val scenarios",
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/live/retrain")
    ap.add_argument("--evidence-dir", default=None)
    r = run(ap.parse_args(argv))
    print(render_markdown(r))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
