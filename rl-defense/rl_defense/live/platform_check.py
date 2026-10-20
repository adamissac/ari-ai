"""Does a live policy recommend the same thing in the product as in the lab?

For each window of real requests through the lab gateway, a checkpoint chooses an action
twice:

- **lab**: on the loop's own ``PlatformFacts``, with the loop's finding severities set to
  what the platform derives from the case's findings;
- **platform**: on ``platform_mapping.facts_from_platform`` built from those findings plus
  the lab gateway acting as a runtime reporter (``report.runtime_batch`` ->
  ``RouteDetection``), i.e. what the backend worker computes.

Windows are split into *quiet* (the detector flagged nobody) and *flagged*. The result
also counts which actions each side recommends, so the quiet-window behaviour (``noop``
versus ``escalate_to_human``, ADR-0017's training-distribution gap) is visible.

Runs on TRAIN scenarios with ``noop`` driving the loop (no block in force, as on the
platform, which enforces none). The time and escalation-budget fields are passed through
from the lab: they are not finding-derived and the backend supplies its own.

    python -m rl_defense.live.platform_check results/live-retrain-v7/candidate_online.pt \
        --out results/live-retrain-v7/platform_agreement.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rl_defense import platform_mapping as pm
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.live import evaluate as ev
from rl_defense.live import report
from rl_defense.live.actions import live_decode_action
from rl_defense.live.adversary import live_app
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import LiveScenario, load_scenarios
from rl_defense.observations import from_platform_facts, mask_from_facts

SPACE = "live_v3"
TOPOLOGY = pm.load_topology(
    Path(__file__).resolve().parents[2] / "configs/topology/payments_lite.yaml"
)
_KEY = b"platform-check-reporter-key"
_T0 = datetime(2026, 10, 19, tzinfo=UTC)
_BOLA_ROUTE = "GET /payments/{payment_id}"

# Finding sets the product can hold for payments-lite.
CASES: dict[str, list[pm.FindingInput]] = {
    "no_findings": [],
    "bola_high": [
        pm.FindingInput(id="fnd_bola", status="validated", severity="high", routes=(_BOLA_ROUTE,))
    ],
}


def _label(action: int) -> str:
    name, node = live_decode_action(action)
    return name if node is None else f"{name}:{NODE_NAMES[node]}"


def _detections(records) -> list[pm.RouteDetection]:  # noqa: ANN001
    batch = report.runtime_batch(
        records,
        source="simulated",
        window_start=_T0,
        window_end=_T0 + timedelta(minutes=1),
        key=_KEY,
    )
    keep = {"route", "requests", "status_4xx", "status_5xx", "principals"}
    return [
        pm.RouteDetection(source="simulated", **w.model_dump(include=keep)) for w in batch.routes
    ]


def compare(
    agent,  # noqa: ANN001
    scenarios: list[LiveScenario],
    *,
    episodes: int = 2,
    windows: int = 10,
    cases: dict[str, list[pm.FindingInput]] | None = None,
) -> dict:
    if any(s.split != "train" for s in scenarios):
        raise ValueError("the platform check runs on train scenarios only")
    policy = ev.dqn_policy(agent)
    lvl = LoopConfig().max_monitoring_level
    out: dict = {"cases": {}}
    for case, findings in (cases or CASES).items():
        severity = {
            n.node: n.finding_severity
            for n in pm.facts_from_platform(TOPOLOGY, findings, [])[0].nodes
        }
        stats = {
            k: {"windows": 0, "agree": 0, "lab": Counter(), "platform": Counter()}
            for k in ("quiet", "flagged")
        }
        for sc in scenarios:
            loop = LiveDefenseLoop(
                live_app,
                config=LoopConfig(horizon=sc.horizon, action_space=SPACE, **ev.V4_LOOP_OVERRIDES),
                driver=sc.driver(),
            )
            try:
                for seed in sc.seeds(episodes):
                    loop.reset(seed)
                    loop.finding_severity = dict(severity)  # the platform's values
                    for _ in range(windows):
                        loop.step(NOOP_ACTION)
                        lab = loop.platform_facts()
                        plat, _ = pm.facts_from_platform(
                            TOPOLOGY,
                            findings,
                            [],
                            detections=_detections(loop._gateway.records),
                            time_fraction=lab.time_fraction,
                            escalations_remaining_fraction=lab.escalations_remaining_fraction,
                        )
                        a_lab = policy(
                            from_platform_facts(lab, lvl, space=SPACE),
                            mask_from_facts(lab, lvl, space=SPACE),
                        )
                        a_plat = policy(
                            from_platform_facts(plat, lvl, space=SPACE),
                            mask_from_facts(plat, lvl, space=SPACE),
                        )
                        s = stats["flagged" if loop._flagged else "quiet"]
                        s["windows"] += 1
                        s["agree"] += a_lab == a_plat
                        s["lab"][_label(a_lab)] += 1
                        s["platform"][_label(a_plat)] += 1
            finally:
                loop.close()
        out["cases"][case] = {
            "finding_severity": severity,
            **{
                k: {
                    "windows": v["windows"],
                    "agree": v["agree"],
                    "agreement": v["agree"] / v["windows"] if v["windows"] else None,
                    "lab_actions": dict(sorted(v["lab"].items())),
                    "platform_actions": dict(sorted(v["platform"].items())),
                }
                for k, v in stats.items()
            },
        }
    total = sum(c[k]["windows"] for c in out["cases"].values() for k in ("quiet", "flagged"))
    agree = sum(c[k]["agree"] for c in out["cases"].values() for k in ("quiet", "flagged"))
    out["windows"], out["agree"] = total, agree
    out["agreement"] = agree / total if total else None
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", nargs="+")
    ap.add_argument("--subdir", default="train_v3")
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--windows", type=int, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    scenarios = load_scenarios("train", subdir=a.subdir)
    result: dict = {
        "_generated_by": "python -m rl_defense.live.platform_check "
        + " ".join(a.checkpoint)
        + f" --subdir {a.subdir} --episodes {a.episodes} --windows {a.windows} --out <path>",
        "train_dir": f"configs/live/{a.subdir}",
        "checkpoints": {},
    }
    for path in a.checkpoint:
        agent, m = load_checkpoint(Path(path))
        result["checkpoints"][path] = {
            "checkpoint_sha256": m["checkpoint_sha256"],
            **compare(agent, scenarios, episodes=a.episodes, windows=a.windows),
        }
    Path(a.out).write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
