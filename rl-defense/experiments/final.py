"""Final run for ONE validation-selected candidate: train seeds 0-4, evaluate once, stress-test.

    python -m experiments.final --candidate configs/ddqn/<winner>.yaml --name protocol-v1

Trains the candidate on the final training seeds 0-4, runs the official held-out
evaluation (``rl_defense.evaluate``, eval seeds 1000-1099) exactly once and the held-out
stress test (``rl_defense.stress``, seeds 3000-3049), copies the artifacts to
``results/<name>/`` and writes ``COMPARISON.md`` against ``results/protocol-v0``. Refuses
to run if the run directory already holds checkpoints, so results cannot be silently redrawn.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from experiments.select import load_candidate

FINAL_SEEDS = (0, 1, 2, 3, 4)
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
NODES = ("gateway", "api", "auth", "payments", "db")


def _train_one(
    seed: int, steps: int, overrides: dict[str, Any], opts: dict[str, Any], run_dir: str
) -> dict[str, Any]:
    from rl_defense.agents.ddqn import DDQNConfig
    from rl_defense.envs import default_config_paths, load_configs
    from rl_defense.train import train

    m = train(
        load_configs(default_config_paths("train")),
        seed,
        steps,
        Path(run_dir),
        DDQNConfig(**overrides),
        log_every=20_000,
        **opts,
    )
    sel = m.get("checkpoint_selection") or {}
    return {
        "seed": seed,
        "steps": steps,
        "gradient_updates": m["gradient_updates"],
        "wall_clock_s": m["wall_clock_s"],
        "checkpoint_sha256": m["checkpoint_sha256"],
        "selected_step": sel.get("selected_step"),
    }


def _open(path: Path):  # noqa: ANN202
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open()


def impact_stats(episodes_file: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """db-loss rate and per-node impact per policy: mean over configs, per training seed."""
    acc: dict[tuple[str, int, str], list[list[str]]] = defaultdict(list)
    with _open(episodes_file) as f:
        for line in f:
            r = json.loads(line)
            acc[(r["policy"], r["training_seed"], r["config"])].append(r["impact_nodes"])
    per: dict[str, dict[int, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(dict))
    for (policy, seed, config), rows in acc.items():
        per[policy][seed][config] = [float(np.mean([n in nodes for nodes in rows])) for n in NODES]
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for policy, seeds in per.items():
        out[policy] = {}
        for i, n in enumerate(NODES):
            vals = [float(np.mean([v[i] for v in cfgs.values()])) for cfgs in seeds.values()]
            out[policy][f"impact_{n}"] = {"mean": float(np.mean(vals)), "per_seed": vals}
    return out


def _ci(per_seed: list[float]) -> tuple[float, float]:
    from rl_defense.evaluate import bootstrap_ci

    return bootstrap_ci(np.array(per_seed, dtype=float))


def _fmt(mean: float | None, ci: tuple[float, float] | None = None, pct: bool = False) -> str:
    if mean is None or (isinstance(mean, float) and math.isnan(mean)):
        return "n/a"
    s = 100.0 if pct else 1.0
    if ci is None or any(x is None for x in ci):
        return f"{mean * s:.1f}"
    return f"{mean * s:.1f} [{ci[0] * s:.1f}, {ci[1] * s:.1f}]"


def _verdict(new: float, base: float, higher: bool) -> str:
    if new is None or base is None or math.isnan(new) or math.isnan(base) or new == base:
        return "same"
    return "yes" if (new > base) == higher else "no"


def comparison(new_dir: Path, base_dir: Path, name: str, candidate: str) -> str:
    new = json.loads((new_dir / "eval_summary.json").read_text())
    base = json.loads((base_dir / "eval_summary.json").read_text())
    new_imp = impact_stats(next(new_dir.glob("eval_episodes.jsonl*")))
    base_imp = impact_stats(next(base_dir.glob("eval_episodes.jsonl*")))
    lines = [
        f"# {name} vs protocol-v0 (held-out evaluation)",
        "",
        f"Candidate: `{candidate}`, selected on the validation protocol in "
        "[experiments/README.md](../../experiments/README.md) without using held-out configs or "
        f"seeds. Both runs: training seeds {new['training_seeds']}, "
        f"{new['episodes_per_config_per_seed']} episodes × 3 held-out configs, eval seeds "
        f"{new['eval_seed_range'][0]}–{new['eval_seed_range'][1]}. "
        "Mean [95% bootstrap CI across training seeds], pooled over held-out configs.",
        "",
        f"v0 git `{base['git_sha'][:8]}` → {name} git `{new['git_sha'][:8]}`.",
        "",
        "| Metric | v0 DDQN | " + f"{name} DDQN | threshold_rules | Better? |",
        "|---|---|---|---|---|",
    ]
    metrics = [
        ("return", "Return", False, True),
        ("compromise_rate", "Compromise %", True, False),
        ("false_disruption_rate", "False disruption %", True, False),
        ("service_uptime", "Uptime %", True, True),
        ("time_to_containment", "Time to containment", False, False),
        ("escalations", "Escalations / episode", False, False),
    ]
    for key, title, pct, higher in metrics:
        b = base["policies"]["ddqn"]["pooled"][key]
        n = new["policies"]["ddqn"]["pooled"][key]
        t = new["policies"]["threshold_rules"]["pooled"][key]
        better = _verdict(n["mean"], b["mean"], higher)
        lines.append(
            f"| {title} | {_fmt(b['mean'], tuple(b['ci95']), pct)} | "
            f"{_fmt(n['mean'], tuple(n['ci95']), pct)} | {_fmt(t['mean'], None, pct)} | "
            f"{better} |"
        )
    for node in NODES:
        key = f"impact_{node}"
        b, n = base_imp["ddqn"][key], new_imp["ddqn"][key]
        t = new_imp["threshold_rules"][key]
        label = "db lost %" if node == "db" else f"{node} impacted %"
        lines.append(
            f"| {label} | {_fmt(b['mean'], _ci(b['per_seed']), True)} | "
            f"{_fmt(n['mean'], _ci(n['per_seed']), True)} | {_fmt(t['mean'], None, True)} | "
            f"{_verdict(n['mean'], b['mean'], higher=False)} |"
        )
    lines += [
        "",
        "Per held-out config (return):",
        "",
        "| Config | v0 DDQN | " + f"{name} DDQN |",
        "|---|---|---|",
    ]
    for cfg in new["eval_configs"]:
        b = base["policies"]["ddqn"]["per_config"][cfg]["return"]
        n = new["policies"]["ddqn"]["per_config"][cfg]["return"]
        lines.append(
            f"| {cfg} | {_fmt(b['mean'], tuple(b['ci95']))} | {_fmt(n['mean'], tuple(n['ci95']))} |"
        )
    lines += ["", f"{name} vs baselines (from its own eval_summary, Holm-corrected):", ""]
    for comp, tests in new["comparisons"].items():
        verdicts = ", ".join(f"{k}: {t['verdict']}" for k, t in tests.items())
        lines.append(f"- **{comp}** — {verdicts}")
    st_new, st_base = new_dir / "stress_summary.json", base_dir / "stress_summary.json"
    if st_new.exists() and st_base.exists():
        sn, sb = json.loads(st_new.read_text()), json.loads(st_base.read_text())
        lines += [
            "",
            "Stress test (held-out configs × adversary factor, seeds 3000–3049):",
            "",
            "| Factor | v0 return | "
            + f"{name} return | rules return | v0 db lost % | "
            + f"{name} db lost % | rules db lost % |",
            "|---|---|---|---|---|---|---|",
        ]
        for f in sn["factors"]:
            k = f"{f:g}"
            pb, pn = sb["results"][k]["policies"], sn["results"][k]["policies"]
            lines.append(
                f"| ×{k} | {pb['ddqn']['return']['mean']:.1f} | {pn['ddqn']['return']['mean']:.1f} | "
                f"{pn['threshold_rules']['return']['mean']:.1f} | "
                f"{100 * pb['ddqn']['db_loss_rate']['mean']:.1f} | "
                f"{100 * pn['ddqn']['db_loss_rate']['mean']:.1f} | "
                f"{100 * pn['threshold_rules']['db_loss_rate']['mean']:.1f} |"
            )
    lines += ["", f"*{new['caveat']}*", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--workers", type=int, default=len(FINAL_SEEDS))
    ap.add_argument("--base", type=Path, default=RESULTS / "protocol-v0")
    args = ap.parse_args()
    cand, steps, overrides, opts = load_candidate(args.candidate)
    run_dir = ROOT / "runs" / args.name
    if any(run_dir.glob("ddqn_seed*.pt")):
        ap.error(f"{run_dir} already has checkpoints; refusing to retrain/re-evaluate")
    run_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        trained = list(
            ex.map(
                _train_one,
                FINAL_SEEDS,
                [steps] * 5,
                [overrides] * 5,
                [opts] * 5,
                [str(run_dir)] * 5,
            )
        )
    (run_dir / "final_training.json").write_text(json.dumps(trained, indent=2))

    from rl_defense.envs import default_config_paths, load_configs
    from rl_defense.evaluate import evaluate
    from rl_defense.stress import stress

    evaluate(
        run_dir,
        load_configs(default_config_paths("eval")),
        load_configs(default_config_paths("train")),
    )
    stress(run_dir)

    out = RESULTS / args.name
    (out / "checkpoints").mkdir(parents=True, exist_ok=True)
    (out / "training-logs").mkdir(exist_ok=True)
    for f in (
        "eval_summary.json",
        "eval_table.md",
        "stress_summary.json",
        "stress_table.md",
        "final_training.json",
    ):
        shutil.copy(run_dir / f, out / f)
    for f in run_dir.glob("ddqn_seed*.manifest.json"):
        shutil.copy(f, out / "checkpoints" / f.name)
    for f in run_dir.glob("train_seed*.jsonl"):
        shutil.copy(f, out / "training-logs" / f.name)
    with (
        (run_dir / "eval_episodes.jsonl").open("rb") as src,
        gzip.open(out / "eval_episodes.jsonl.gz", "wb") as dst,
    ):
        shutil.copyfileobj(src, dst)
    shutil.copy(args.candidate, out / "candidate.yaml")
    (out / "COMPARISON.md").write_text(comparison(out, args.base, args.name, cand))
    print((out / "COMPARISON.md").read_text())


if __name__ == "__main__":
    main()
