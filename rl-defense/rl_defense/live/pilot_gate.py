"""The RL-gated pilot evaluation: frozen v6 against the rules on fresh, frozen scenarios.

    python -m rl_defense.live.pilot_gate --out results/pilot-gate

Pre-registered in results/pilot-gate/PREREGISTRATION.md. Nothing is trained, selected or
promoted here. Every policy runs the same (scenario, seed) episodes against the owned demo
app in the in-process lab; all numbers are measured from real HTTP outcomes there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from rl_defense.checkpoint import git_sha, load_checkpoint, sha256_file
from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.layouts import FEATURE_INDEX
from rl_defense.live import evaluate as ev
from rl_defense.live.adversary import live_app
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import CONFIG_DIR, LiveScenario, load_scenarios

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = "pilot_gate"
CANDIDATE = ROOT / "results" / "live-retrain-v6" / "candidate_online.pt"
CANDIDATE_SHA256 = "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1"
RULES_TUNING = ROOT / "results" / "live-retrain-v6" / "rules_tuning.json"
RULES_TUNING_SHA256 = "7eab230b65c54f80acec60a992e055abb600f1240172159251a99fbe0fbca01f"
CRITERIA = CONFIG_DIR / "promotion.yaml"
CRITERIA_SHA256 = "1d1faf231f4610a346c79447a9dbed8284c023018a12f46e721ddac8a9b27fcc"
MIN_DELEGATED_SUCCESS = 0.85
SPACE = "live_v3"
SCHEMA = "pilot-gate/1"
FLAGGED = FEATURE_INDEX["flagged_principals"]


def _pinned(path: Path, expected: str) -> Path:
    if sha256_file(path) != expected:
        raise ValueError(f"{path.name} does not match its pinned sha256")
    return path


def run_policy(
    policy: ev.PolicyFn,
    scenarios: list[LiveScenario],
    *,
    episodes: int | None = None,
    q_values=None,  # noqa: ANN001
) -> tuple[list[ev.EpisodeMetrics], list[dict[str, Any]], list[dict[str, Any]]]:
    """``ev.run_policy`` plus what it does not record: per-episode own-object and delegated
    request outcomes (from the gateway's records) and, with ``q_values``, per-step decisions."""
    rows: list[ev.EpisodeMetrics] = []
    access: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for sc in scenarios:
        loop = LiveDefenseLoop(
            live_app,
            config=LoopConfig(horizon=sc.horizon, action_space=SPACE, **ev.V4_LOOP_OVERRIDES),
            driver=sc.driver(),
        )
        try:
            for seed in sc.seeds(episodes):
                obs, mask = loop.reset(seed)
                ts, done = [], False
                own = own_ok = delegated = delegated_ok = 0
                while not done:
                    action = int(policy(obs, mask))
                    margin = None
                    if q_values is not None:
                        q = np.sort(q_values(obs)[: len(mask)][mask])[::-1]
                        margin = float(q[0] - q[1]) if len(q) > 1 else 0.0
                    t = loop.step(action)
                    ts.append(t)
                    for r in loop._gateway.records:  # this window's real request outcomes
                        if r.is_attack:
                            continue
                        ok = r.allowed and r.status == 200
                        # an authorized cross-tenant read: the token's principal is not the
                        # object's owner and the traffic generator did not label it an attack
                        if r.owner is not None and r.principal != r.owner:
                            delegated, delegated_ok = delegated + 1, delegated_ok + ok
                        else:
                            own, own_ok = own + 1, own_ok + ok
                    if q_values is not None:
                        o = t.outcome
                        decisions.append(
                            {
                                "flagged": bool(obs[FLAGGED] > 0),
                                "acted": o.action != NOOP_ACTION,
                                "q_margin": margin,
                                "harm": bool(
                                    o.compromised_reads > 0
                                    or (not o.attack_active and o.benign_blocked > 0)
                                ),
                            }
                        )
                    obs = np.asarray(t.next_obs, dtype=np.float32)
                    mask = np.asarray(t.action_mask, dtype=bool)
                    done = t.done
                rows.append(ev.episode_metrics(sc.name, seed, ts))
                access.append(
                    {
                        "scenario": sc.name,
                        "seed": seed,
                        "own_requests": own,
                        "own_succeeded": int(own_ok),
                        "delegated_requests": delegated,
                        "delegated_succeeded": int(delegated_ok),
                    }
                )
        finally:
            loop.close()
    return rows, access, decisions


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else float(num / den)


def access_summary(access: list[dict[str, Any]]) -> dict[str, float | None]:
    tot = {k: sum(a[k] for a in access) for k in access[0] if k not in ("scenario", "seed")}
    return {
        "own_traffic_success": _ratio(tot["own_succeeded"], tot["own_requests"]),
        "delegated_success": _ratio(tot["delegated_succeeded"], tot["delegated_requests"]),
    }


def abstention(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    quiet = [d for d in decisions if not d["flagged"]]
    flagged = [d for d in decisions if d["flagged"]]
    return {
        "windows_without_flagged_principal": len(quiet),
        "no_action_share_without_flag": _ratio(sum(not d["acted"] for d in quiet), len(quiet)),
        "windows_with_flagged_principal": len(flagged),
        "action_share_with_flag": _ratio(sum(d["acted"] for d in flagged), len(flagged)),
    }


def uncertainty(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Harm rate by tercile of the Q-margin. Q-values are scores, not probabilities; this
    shows whether a small margin goes with worse outcomes, nothing more."""
    margins = np.array([d["q_margin"] for d in decisions])
    harm = np.array([d["harm"] for d in decisions], dtype=float)
    lo, hi = np.quantile(margins, [1 / 3, 2 / 3])
    bins = {
        "low_margin": margins <= lo,
        "mid_margin": (margins > lo) & (margins <= hi),
        "high_margin": margins > hi,
    }
    return {
        "q_values_are_not_probabilities": True,
        "tercile_edges": [float(lo), float(hi)],
        "harm_rate": {k: _ratio(float(harm[m].sum()), int(m.sum())) for k, m in bins.items()},
        "steps": {k: int(m.sum()) for k, m in bins.items()},
        "overall_harm_rate": float(harm.mean()),
    }


def gate(
    candidate: list[ev.EpisodeMetrics],
    rules: list[ev.EpisodeMetrics],
    candidate_access: list[dict[str, Any]],
    criteria: ev.PromotionCriteria,
) -> dict[str, Any]:
    """The pre-registered checks: the promotion gate with the rules as the incumbent, plus
    the delegated-access floor. Undefined metrics fail."""
    verdict = ev.promotion_decision(
        candidate=candidate, deployed=rules, rules=rules, criteria=criteria
    )
    delegated = access_summary(candidate_access)["delegated_success"]
    checks = [
        *verdict["checks"],
        {
            "name": "delegated_success_floor",
            "passed": bool(delegated is not None and delegated >= MIN_DELEGATED_SUCCESS),
            "value": delegated,
            "threshold": f">= {MIN_DELEGATED_SUCCESS}; undefined fails",
        },
    ]
    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "paired_reward_diff_vs_rules": verdict["paired_reward_diff"],
    }


def run(
    out: Path,
    episodes: int | None = None,
    *,
    scenario_dir: str = SCENARIO_DIR,
    candidate: Path = CANDIDATE,
    candidate_sha256: str = CANDIDATE_SHA256,
    rules_tuning: Path = RULES_TUNING,
    rules_tuning_sha256: str = RULES_TUNING_SHA256,
    references: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    """Defaults are the first gate (frozen v6). ``references`` are other pinned checkpoints
    run on the same episodes and reported only; they are not part of the gate."""
    out.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios("holdout", subdir=scenario_dir)
    agent, manifest = load_checkpoint(_pinned(candidate, candidate_sha256))
    rules_params = json.loads(_pinned(rules_tuning, rules_tuning_sha256).read_text())["selected"]
    criteria = ev.PromotionCriteria(
        **yaml.safe_load(_pinned(CRITERIA, CRITERIA_SHA256).read_text())
    )
    policies: dict[str, ev.PolicyFn] = {
        "candidate": ev.dqn_policy(agent),
        "threshold_rules": ev.rules_policy(rules_params),
        "always_block_principal": ev.always_block_principal,
        "always_block_principal_long": ev.always_block_principal_long,
        "always_block_top_principal_long": ev.always_block_top_principal_long,
        "noop": ev.noop_policy,
    }
    for ref_name, (ref_path, ref_sha) in (references or {}).items():
        policies[ref_name] = ev.dqn_policy(load_checkpoint(_pinned(ref_path, ref_sha))[0])
    rows: dict[str, list[ev.EpisodeMetrics]] = {}
    access: dict[str, list[dict[str, Any]]] = {}
    decisions: list[dict[str, Any]] = []
    for name, policy in policies.items():
        q = agent.q_values if name == "candidate" else None
        rows[name], access[name], d = run_policy(policy, scenarios, episodes=episodes, q_values=q)
        decisions = d or decisions
        print(f"{name}: {ev.summarize(rows[name])['reward']:.3f}", flush=True)

    summary = {
        name: {
            "pooled": {**ev.summarize(r), **access_summary(access[name])},
            "by_scenario": {
                sc: {
                    **s,
                    **access_summary([a for a in access[name] if a["scenario"] == sc]),
                }
                for sc, s in ev.summarize_by_scenario(r).items()
            },
        }
        for name, r in rows.items()
    }
    result = {
        "schema": SCHEMA,
        "caveat": ev.CAVEAT,
        "git_sha": git_sha(),
        "candidate": {
            "checkpoint_sha256": manifest["checkpoint_sha256"],
            "env_id": manifest["env_id"],
            "noop_margin": manifest["ddqn_config"].get("noop_margin"),
            "trained_commit_sha": manifest.get("git_sha"),
            "lineage": manifest.get("lineage"),
        },
        "scenarios": {s.name: s.config_hash() for s in scenarios},
        "episode_seeds": {s.name: [s.seeds(episodes)[0], s.seeds(episodes)[-1]] for s in scenarios},
        "loop_overrides": dict(ev.V4_LOOP_OVERRIDES),
        "action_space": SPACE,
        "scenario_dir": scenario_dir,
        "rules": {"params": rules_params, "tuning_sha256": rules_tuning_sha256},
        "references": {n: sha for n, (_, sha) in (references or {}).items()},
        "criteria": {
            **criteria.model_dump(),
            "min_delegated_success": MIN_DELEGATED_SUCCESS,
            "promotion_yaml_sha256": CRITERIA_SHA256,
            "incumbent": "threshold_rules",
        },
        "gate": gate(rows["candidate"], rows["threshold_rules"], access["candidate"], criteria),
        "abstention": abstention(decisions),
        "uncertainty": uncertainty(decisions),
        "summary": summary,
    }
    episodes_blob = json.dumps(
        {
            name: [{**asdict(r), **a} for r, a in zip(rows[name], access[name], strict=True)]
            for name in rows
        },
        indent=1,
        sort_keys=True,
    )
    (out / "episodes.json").write_text(episodes_blob)
    (out / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    evidence = {
        "schema": SCHEMA,
        "files": {
            f: hashlib.sha256((out / f).read_bytes()).hexdigest()
            for f in ("episodes.json", "summary.json")
        },
        "candidate_checkpoint_sha256": manifest["checkpoint_sha256"],
        "passed": result["gate"]["passed"],
    }
    (out / "EVIDENCE.json").write_text(json.dumps(evidence, indent=2, sort_keys=True))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--episodes", type=int, help="per scenario (default: all 30)")
    ap.add_argument("--scenario-dir", default=SCENARIO_DIR)
    ap.add_argument("--candidate", type=Path, default=CANDIDATE)
    ap.add_argument("--candidate-sha256", default=CANDIDATE_SHA256)
    ap.add_argument("--rules-tuning", type=Path, default=RULES_TUNING)
    ap.add_argument("--rules-tuning-sha256", default=RULES_TUNING_SHA256)
    ap.add_argument("--reference-v6", action="store_true", help="also run frozen v6, reported only")
    args = ap.parse_args()
    result = run(
        args.out,
        args.episodes,
        scenario_dir=args.scenario_dir,
        candidate=args.candidate,
        candidate_sha256=args.candidate_sha256,
        rules_tuning=args.rules_tuning,
        rules_tuning_sha256=args.rules_tuning_sha256,
        references={"frozen_v6": (CANDIDATE, CANDIDATE_SHA256)} if args.reference_v6 else None,
    )
    print(json.dumps(result["gate"], indent=2))


if __name__ == "__main__":
    main()
