"""Failure-case and behaviour analysis of an evaluated run (docs/17: report failure cases).

    python -m rl_defense.analysis --run-dir runs/<run_id>

Reads ``eval_episodes.jsonl`` written by ``rl_defense.evaluate`` and writes
``ANALYSIS.md`` plus replayed trajectories of the worst DDQN episodes under
``failure_cases/``. Uses only recorded evaluation output and deterministic replays.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import REWARD_COMPONENTS
from rl_defense.evaluate import CAVEAT, DDQNPolicy, run_episode

POLICY_ORDER = ("ddqn", "threshold_rules", "random", "noop")


def load_episodes(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "eval_episodes.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def _by_policy(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r["policy"]].append(r)
    return {p: out[p] for p in POLICY_ORDER if p in out}


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(r) + " |" for r in rows),
    ]


def replay_episode(run_dir: Path, row: dict[str, Any], configs: dict[str, Any]) -> dict[str, Any]:
    """Deterministically replay one DDQN episode and summarize what happened."""
    policy = DDQNPolicy(run_dir / f"ddqn_seed{row['training_seed']}.pt")
    env = DefenseSimEnv(configs[row["config"]])
    replayed, traj = run_episode(env, policy, row["episode_seed"], record=True)
    assert replayed["return"] == row["return"], "replay diverged from recorded evaluation"
    first_foothold = next(
        (s for s in traj if any(st >= 1 for st in s["hidden_stages_for_replay_only"])), None
    )
    first_impact = next((s for s in traj if 3 in s["hidden_stages_for_replay_only"]), None)
    actions = [s["action"] for s in traj if s["action"] != "noop"]
    return {
        "row": row,
        "trajectory": traj,
        "first_foothold_t": None if first_foothold is None else first_foothold["t"],
        "first_impact_t": None if first_impact is None else first_impact["t"],
        "non_noop_actions": actions,
    }


def analyze(run_dir: Path, n_failures: int = 3) -> str:
    rows = load_episodes(run_dir)
    if "reward_components" not in rows[0]:
        raise ValueError(
            "eval_episodes.jsonl predates reward components; re-run rl_defense.evaluate"
        )
    configs = {c.name: c for c in load_configs(default_config_paths("eval"))}
    by_policy = _by_policy(rows)
    lines = [
        "# Evaluation analysis",
        "",
        f"Run: `{run_dir.name}` — {len(rows)} evaluation episodes, held-out configs only.",
        f"*{CAVEAT}*",
        "",
        "## Where each policy loses reward",
        "",
        "Mean per-episode total of each reward component (negative = cost).",
        "",
    ]
    comp_rows = []
    for p, eps in by_policy.items():
        means = {k: np.mean([e["reward_components"][k] for e in eps]) for k in REWARD_COMPONENTS}
        comp_rows.append(
            [p, f"{np.mean([e['return'] for e in eps]):.1f}"]
            + [f"{means[k]:.1f}" for k in REWARD_COMPONENTS]
        )
    lines += _table(["Policy", "Return", *REWARD_COMPONENTS], comp_rows)

    lines += [
        "",
        "## Which nodes fall",
        "",
        "Share of episodes in which each node reached impact.",
        "",
    ]
    node_rows = []
    for p, eps in by_policy.items():
        node_rows.append(
            [p]
            + [f"{100 * np.mean([n in e['impact_nodes'] for e in eps]):.1f}%" for n in NODE_NAMES]
        )
    lines += _table(["Policy", *NODE_NAMES], node_rows)

    lines += ["", "## Action mix", "", "Share of all steps.", ""]
    action_names = sorted(
        {a for eps in by_policy.values() for e in eps for a in e["action_counts"]}
    )
    mix_rows = []
    for p, eps in by_policy.items():
        totals: dict[str, int] = defaultdict(int)
        for e in eps:
            for a, c in e["action_counts"].items():
                totals[a] += c
        n = sum(totals.values())
        mix_rows.append([p] + [f"{100 * totals[a] / n:.1f}%" for a in action_names])
    lines += _table(["Policy", *action_names], mix_rows)

    ddqn = by_policy.get("ddqn", [])
    lines += [
        "",
        "## DDQN by training seed",
        "",
        "Seed-to-seed variation (pooled over configs).",
        "",
    ]
    seed_rows = []
    for seed in sorted({e["training_seed"] for e in ddqn}):
        eps = [e for e in ddqn if e["training_seed"] == seed]
        fd = [e["false_disruption_rate"] for e in eps if e["false_disruption_rate"] is not None]
        seed_rows.append(
            [
                str(seed),
                f"{np.mean([e['return'] for e in eps]):.1f}",
                f"{100 * np.mean([e['compromise_rate'] for e in eps]):.1f}%",
                f"{100 * np.nanmean(fd):.1f}%" if fd else "n/a",
                f"{100 * np.mean([e['service_uptime'] for e in eps]):.1f}%",
            ]
        )
    lines += _table(["Seed", "Return", "Compromise", "False disruption", "Uptime"], seed_rows)

    fail_dir = run_dir / "failure_cases"
    fail_dir.mkdir(exist_ok=True)
    worst = sorted(ddqn, key=lambda e: e["return"])[:n_failures]
    lines += ["", f"## Failure cases: the {len(worst)} worst DDQN episodes", ""]
    for i, row in enumerate(worst, 1):
        case = replay_episode(run_dir, row, configs)
        name = f"ddqn_seed{row['training_seed']}_{row['config']}_ep{row['episode_seed']}.json"
        (fail_dir / name).write_text(json.dumps(case, indent=1))
        acts = case["non_noop_actions"]
        lines += [
            f"### {i}. `{row['config']}`, training seed {row['training_seed']}, episode seed {row['episode_seed']}",
            "",
            f"- Return {row['return']:.1f}; episode length {int(row['length'])}; "
            f"nodes that reached impact: {', '.join(row['impact_nodes']) or 'none'}.",
            f"- First foothold at step {case['first_foothold_t']}; first impact at step "
            f"{case['first_impact_t']}.",
            f"- Defender took {len(acts)} non-noop actions; first ten: "
            f"{', '.join(acts[:10]) or 'none'}.",
            "- Largest costs: "
            + ", ".join(
                f"{k} {v:.1f}"
                for k, v in sorted(row["reward_components"].items(), key=lambda kv: kv[1])[:3]
            )
            + ".",
            f"- Replay: `failure_cases/{name}` (deterministic; matches the recorded return).",
            "",
        ]
    text = "\n".join(lines) + "\n"
    (run_dir / "ANALYSIS.md").write_text(text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--failures", type=int, default=3)
    args = ap.parse_args()
    print(analyze(args.run_dir, args.failures))


if __name__ == "__main__":
    main()
