"""Train the v11 live candidate and apply its pre-registered validation screen.

    python -m rl_defense.live.v11 --out runs/live/v11 --evidence-dir results/live-retrain-v11

Pre-registered in results/pilot-gate-v2/PREREGISTRATION.md. Same method as v6 (DQfD online
in the live lab, ``rl_defense/live/online.py``) with two changes: the training set adds the
two scenario families v6 lost or over-blocked on in the first pilot gate, and snapshot
selection prefers snapshots that meet the availability floor on validation. Train and
validation scenarios only; no holdout or gate scenario is touched here.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from rl_defense.checkpoint import sha256_file
from rl_defense.live import evaluate as ev
from rl_defense.live.adversary import live_app
from rl_defense.live.online import (
    SPACE,
    OnlineConfig,
    choose_expert,
    expert_candidates,
    train_online,
)
from rl_defense.live.scenarios import load_scenarios

TRAIN_DIR, VAL_DIR = "train_v11", "val_v11"
MIN_AVAILABILITY = 0.85
NAME = "candidate_v11"


def validation_screen(manifest: dict, rules_by_scenario: dict[str, float]) -> dict[str, Any]:
    """The pre-registered prediction, checked on validation only. Ineligible = the gate
    scenarios are not run and stay unexposed."""
    online = manifest["online"]
    selected = [
        h
        for h in online["selection_history"]
        if h["env_step"] == online["selected_env_step"]
        and h["noop_margin"] == online["selected_noop_margin"]
    ]
    if len(selected) != 1:
        raise ValueError("selected snapshot does not match exactly one history entry")
    sel = selected[0]
    by = sel["val_reward_by_scenario"]
    trailing = {n: [by[n], r] for n, r in rules_by_scenario.items() if by[n] < r}
    availability = sel["val_availability"]
    checks = {
        "availability_floor": availability is not None and availability >= MIN_AVAILABILITY,
        "no_val_scenario_trails_rules": not trailing,
    }
    return {
        "selected_env_step": sel["env_step"],
        "selected_noop_margin": sel["noop_margin"],
        "val_availability": availability,
        "val_reward_by_scenario": by,
        "rules_val_reward_by_scenario": rules_by_scenario,
        "trailing_scenarios": trailing,
        "checks": checks,
        "eligible_for_gate": all(checks.values()),
    }


def run(out: Path, evidence_dir: Path, cfg: OnlineConfig, rules_episodes: int = 2) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    lo = dict(ev.V4_LOOP_OVERRIDES)
    tr = load_scenarios("train", subdir=TRAIN_DIR)
    va = load_scenarios("val", subdir=VAL_DIR)
    rules_params, table = ev.tune_rules_v3(tr, live_app, episodes=rules_episodes, loop_overrides=lo)
    (evidence_dir / "rules_tuning.json").write_text(
        json.dumps({"selected": rules_params, "grid": table}, indent=1, sort_keys=True)
    )
    expert_name, scores = choose_expert(
        tr, live_app, rules_params, episodes=rules_episodes, loop_overrides=lo
    )
    print(f"expert: {expert_name} {scores}", flush=True)
    manifest = train_online(
        tr,
        va,
        live_app,
        expert_candidates(rules_params)[expert_name],
        out,
        cfg=cfg,
        loop_overrides=lo,
        expert_name=expert_name,
        name=NAME,
    )
    rules_rows = ev.run_policy(
        ev.rules_policy(rules_params),
        va,
        live_app,
        episodes=cfg.val_episodes,
        action_space=SPACE,
        loop_overrides=lo,
    )
    rules_by = {k: round(v["reward"], 4) for k, v in ev.summarize_by_scenario(rules_rows).items()}
    screen = validation_screen(manifest, rules_by)
    screen["expert"] = {"name": expert_name, "train_scores": scores}
    (evidence_dir / "validation_screen.json").write_text(
        json.dumps(screen, indent=2, sort_keys=True)
    )
    for name in (f"{NAME}.pt", f"{NAME}.manifest.json"):
        shutil.copy2(out / name, evidence_dir / name)
    screen["checkpoint_sha256"] = sha256_file(evidence_dir / f"{NAME}.pt")
    print(json.dumps(screen, indent=2), flush=True)
    return screen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run(
        args.out,
        args.evidence_dir,
        OnlineConfig(seed=args.seed, min_val_availability=MIN_AVAILABILITY),
    )


if __name__ == "__main__":
    main()
