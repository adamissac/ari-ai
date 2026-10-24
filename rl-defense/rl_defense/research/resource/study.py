"""Single owner-approved deterministic study; no learning or checkpoint imports."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import numpy as np

from rl_defense.research.resource.baselines import Policy, action
from rl_defense.research.resource.env import ResourceEnv
from rl_defense.research.resource.preparation import settle_episode
from rl_defense.research.resource.service import Config
from rl_defense.research.resource.workload import FAMILIES, Family

POLICIES = ("noop", "static", "threshold", "resource_aware", "persistent_static")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, obj: Any) -> None:
    blob = (json.dumps(obj, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(blob, compresslevel=3, mtime=0))
    else:
        path.write_bytes(blob)


def rss() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def check_budget(start: float) -> None:
    if time.monotonic() - start >= 600 or rss() > 512 * 1024**2:
        raise RuntimeError("registered resource budget exhausted")


def measures(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    n = sum(r["final"]["legitimate_offered"] for r in rows)
    completed = sum(r["final"]["legitimate_completed"] for r in rows)
    return {
        "adversarial_work": sum(r["final"]["adversarial_work"] for r in rows) / len(rows),
        "completion": completed / n if n else None,
        "denial": sum(
            r["final"]["legitimate_rate_denied"] + r["final"]["legitimate_capacity_denied"]
            for r in rows
        )
        / n
        if n
        else None,
        "timeout": sum(r["final"]["legitimate_timeouts"] for r in rows) / n if n else None,
        "latency": sum(r["final"]["legitimate_latency_sum"] for r in rows) / completed
        if completed
        else None,
        "applications": sum(r["costs"]["applications"] for r in rows) / len(rows),
        "active_ticks": sum(r["costs"]["active_ticks"] for r in rows) / len(rows),
        "overhead": sum(r["costs"]["overhead_units"] for r in rows) / len(rows),
        "exhausted_ticks": sum(r["exhausted_ticks"] for r in rows) / len(rows),
        "recovery_mean": sum(r["final"]["recovery_ticks_sum"] for r in rows)
        / sum(r["final"]["recovery_count"] for r in rows)
        if sum(r["final"]["recovery_count"] for r in rows)
        else None,
    }


def violations(rows: list[dict[str, Any]]) -> list[str]:
    m = measures(rows)
    bad = []
    for key, limit, lower in (
        ("completion", 0.9, True),
        ("denial", 0.05, False),
        ("timeout", 0.05, False),
        ("latency", 16, False),
    ):
        value = m[key]
        if value is None or (value < limit if lower else value > limit):
            bad.append(key)
    for key, cap in (("applications", 4), ("active_ticks", 64), ("overhead_units", 4)):
        if any(r["costs"][key] > cap for r in rows):
            bad.append(key)
    return bad


def run(root: Path, output: Path) -> None:
    watched = [
        "rl-defense/rl_defense/research/resource",
        "docs/research/resource-exhaustion/PREREGISTRATION.md",
    ]
    if subprocess.check_output(["git", "status", "--porcelain", "--", *watched], cwd=root).strip():
        raise ValueError("execution source/protocol must be committed")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = {
        str(p.relative_to(root)): sha(p.read_bytes()) for p in (root / watched[0]).glob("*.py")
    }
    files[watched[1]] = sha((root / watched[1]).read_bytes())
    for name, expected in files.items():
        if sha(subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=root)) != expected:
            raise ValueError("uncommitted source")
    output.mkdir(exist_ok=False, parents=True)
    start = time.monotonic()

    def timeout(signum: int, frame: Any) -> None:
        raise RuntimeError("600-second study deadline exhausted")

    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(600)
    config = Config()
    manifest = {
        "source_commit": commit,
        "files": files,
        "config": config.model_dump(),
        "config_sha256": sha(config.model_dump_json().encode()),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {n: version(n) for n in ("numpy", "gymnasium", "pydantic")},
        "seed_ids": list(range(20)),
        "families": FAMILIES,
        "policies": POLICIES,
        "training_authorized": False,
        "checkpoint": None,
        "started_at_unix": time.time(),
        "budgets": {"processes": 1, "rss_bytes": 512 * 1024**2, "wall_seconds": 600},
    }
    dump(output / "manifest.json", manifest)
    outcomes: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    env: ResourceEnv | None = None
    identity: Any = None
    try:
        for family in FAMILIES:
            for seed in range(20):
                paired = None
                for policy in POLICIES:
                    identity = [family, seed, policy]
                    env = ResourceEnv(
                        config,
                        family=cast(Family, family),
                        fixed_static=policy == "persistent_static",
                    )
                    obs, _ = env.reset(seed=seed)
                    transitions = []
                    costs: dict[str, int] = {}
                    exhausted = 0
                    for step in range(30):
                        check_budget(start)
                        mask = env.action_masks()
                        chosen = (
                            0
                            if policy == "persistent_static"
                            else action(cast(Policy, policy), obs)
                        )
                        if not mask[chosen]:
                            raise AssertionError("infeasible policy proposal")
                        new, reward, terminated, truncated, info = env.step(chosen)
                        if (
                            not info["before_cutoff_seq"]
                            < info["action_seq"]
                            < info["observation_cutoff_seq"]
                        ):
                            raise AssertionError("cutoff failure")
                        transitions.append(
                            {
                                "step": step,
                                "observation": obs.tolist(),
                                "mask": mask.tolist(),
                                "action": chosen,
                                "reward": reward,
                                "next_observation": new.tolist(),
                                "terminated": terminated,
                                "truncated": truncated,
                                "info": info,
                            }
                        )
                        for key, value in info["costs"].items():
                            costs[key] = costs.get(key, 0) + value
                        exhausted += info["window"]["exhausted_ticks"]
                        obs = new
                    decision = env.service.metrics()
                    settlement = settle_episode(env)
                    final = env.service.metrics()
                    offered = [asdict(j.arrival) for j in env.service.jobs]
                    if paired is not None and offered != paired:
                        raise AssertionError("policy changed paired workload")
                    paired = offered
                    if final["pending"] or final["legitimate_pending"]:
                        raise AssertionError("unresolved settlement")
                    if -sum(t["reward"] for t in transitions) != decision["adversarial_work"]:
                        raise AssertionError("reward accounting")
                    row = {
                        "family": family,
                        "seed": seed,
                        "policy": policy,
                        "decision": decision,
                        "final": final,
                        "costs": costs,
                        "exhausted_ticks": exhausted,
                        "settlement": [asdict(w) for w in settlement],
                    }
                    dump(
                        output / f"{family}-{seed:02}-{policy}.json.gz",
                        {
                            "summary": row,
                            "transitions": transitions,
                            "requests": [asdict(j) for j in env.service.jobs],
                            "events": env.service.events,
                            "ledger": env.ledger,
                            "attempts": env.attempts,
                        },
                    )
                    outcomes.append(row)
                    dump(
                        output / "progress.json",
                        {
                            "completed": len(outcomes),
                            "last": identity,
                            "elapsed": time.monotonic() - start,
                            "peak_rss": rss(),
                        },
                    )
        dump(output / "outcomes.json", outcomes)
        analysis = analyze(outcomes, start)
        dump(output / "analysis.json", analysis)
        for name, expected in files.items():
            if sha((root / name).read_bytes()) != expected:
                raise AssertionError("source changed")
        if (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            != commit
        ):
            raise AssertionError("HEAD changed")
        check_budget(start)
        dump(
            output / "completion.json",
            {
                "episodes": len(outcomes),
                "decisions": sum(30 for _ in outcomes),
                "elapsed_seconds": time.monotonic() - start,
                "peak_rss_bytes": rss(),
                "status": "completed",
            },
        )
        index = {p.name: sha(p.read_bytes()) for p in output.iterdir() if p.is_file()}
        check_budget(start)
        dump(output / "STUDY_EVIDENCE.json", {"files": index, "source_commit": commit})
        print(sha((output / "STUDY_EVIDENCE.json").read_bytes()), flush=True)
    except BaseException as exc:
        dump(
            output / "FAILURE.json",
            {
                "error": repr(exc),
                "identity": identity,
                "completed": len(outcomes),
                "elapsed": time.monotonic() - start,
                "peak_rss": rss(),
                "partial_transitions": transitions,
                "partial_requests": [asdict(j) for j in env.service.jobs] if env else [],
                "partial_events": env.service.events if env else [],
                "partial_ledger": env.ledger if env else [],
            },
        )
        raise
    finally:
        signal.alarm(0)


def analyze(outcomes: list[dict[str, Any]], start: float) -> dict[str, Any]:
    rng = np.random.default_rng(20261024)
    result: dict[str, Any] = {
        "families": {},
        "bootstrap_resamples": 2000,
        "confidence": 0.95,
        "aggregate": {},
    }
    grouped = {
        (f, p): [r for r in outcomes if r["family"] == f and r["policy"] == p]
        for f in FAMILIES
        for p in POLICIES
    }
    distributions: dict[Any, Any] = {}
    for family in FAMILIES:
        draws = rng.integers(0, 20, size=(2000, 20))
        for policy in POLICIES:
            rows = grouped[family, policy]
            point = measures(rows)
            samples: dict[str, list[float | None]] = {k: [] for k in point}
            for indices in draws:
                check_budget(start)
                m = measures([rows[int(i)] for i in indices])
                for k, value in m.items():
                    samples[k].append(value)
            distributions[family, policy] = samples
            ci = {
                k: np.percentile([v for v in values if v is not None], [2.5, 97.5]).tolist()
                if all(v is not None for v in values)
                else None
                for k, values in samples.items()
            }
            result["families"].setdefault(family, {})[policy] = {
                "point": point,
                "intervals": ci,
                "violations": violations(rows),
                "eligible": not violations(rows) and policy != "persistent_static",
            }
    for policy in POLICIES:
        result["aggregate"][policy] = {
            "point": {
                k: float(np.mean([result["families"][f][policy]["point"][k] for f in FAMILIES]))
                if all(result["families"][f][policy]["point"][k] is not None for f in FAMILIES)
                else None
                for k in measures(grouped[FAMILIES[0], policy])
            },
            "eligible_all_families": all(
                result["families"][f][policy]["eligible"] for f in FAMILIES
            ),
        }
    for policy in POLICIES:
        aggregate_samples = {
            k: np.mean(
                np.array([distributions[f, policy][k] for f in FAMILIES], dtype=float), axis=0
            )
            for k in measures(grouped[FAMILIES[0], policy])
            if all(all(v is not None for v in distributions[f, policy][k]) for f in FAMILIES)
        }
        result["aggregate"][policy]["intervals"] = {
            k: np.percentile(v, [2.5, 97.5]).tolist() for k, v in aggregate_samples.items()
        }
    result["paired_effects"] = {}
    for family in FAMILIES:
        result["paired_effects"][family] = {}
        for candidate in POLICIES:
            for reference in POLICIES:
                a = np.array(distributions[family, candidate]["adversarial_work"])
                b = np.array(distributions[family, reference]["adversarial_work"])
                cp = result["families"][family][candidate]["point"]["adversarial_work"]
                rp = result["families"][family][reference]["point"]["adversarial_work"]
                result["paired_effects"][family][f"{candidate}_vs_{reference}"] = {
                    "work_difference": cp - rp,
                    "difference_ci": np.percentile(a - b, [2.5, 97.5]).tolist(),
                    "relative_reduction": 1 - cp / rp if rp else None,
                    "relative_ci": np.percentile(1 - a / b, [2.5, 97.5]).tolist()
                    if np.all(b > 0)
                    else None,
                }
    return result


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[4], Path(sys.argv[1]))
