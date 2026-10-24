"""Read-only necessary bounds on sealed records. No environment or policy imports."""

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
from pathlib import Path
from typing import Any

ANCHOR = "931fbd6737f963a1fe661ab029d08b7f4a26fe09e42805c291c9d1a1a2a0246c"
STUDY = "docs/research/resource-exhaustion/feasibility-001/evidence"


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def completion_upper(jobs: list[tuple[int, int, int]], workers: int = 2) -> dict[str, Any]:
    """Necessary interval-work bound, relaxing queue/FIFO/nonpreemption/collateral.

    For I=[a,b], jobs wholly confined to I need all their work in I. If only k
    cheapest confined jobs fit its supply, at least |J_I|-k cannot complete.
    This is an upper bound on completion, never a feasible scheduling witness.
    """
    if workers < 1 or any(r < 0 or d <= r or p < 1 for r, d, p in jobs):
        raise ValueError("positive work, workers and time windows required")
    n = len(jobs)
    upper, binding = n, None
    for a in sorted({0, *(r for r, _, _ in jobs)}):
        confined = sorted((d, p) for r, d, p in jobs if r >= a)
        histogram: dict[int, int] = {}
        count = 0
        for i, (b, p) in enumerate(confined):
            histogram[p] = histogram.get(p, 0) + 1
            count += 1
            if i + 1 < len(confined) and confined[i + 1][0] == b:
                continue
            capacity, fit = workers * (b - a), 0
            for cost, amount in sorted(histogram.items()):
                take = min(amount, capacity // cost)
                fit += take
                capacity -= take * cost
            candidate = n - count + fit
            if candidate < upper:
                upper, binding = candidate, [a, b, count, fit]
    return {
        "completed_upper": upper,
        "binding_interval": binding,
        "optimality": "necessary_bound_only",
    }


def coverage(jobs: list[dict[str, Any]]) -> dict[str, int]:
    """Optimistic offered-work rejection bound, NOT consumed-work/safety bound."""
    potential = []
    for window in range(30):
        attack = [j for j in jobs if j["adversarial"] and j["tick"] // 8 == window]
        scopes = [sum(j["work"] for j in attack if j["route"] == 1)]
        scopes += [sum(j["work"] for j in attack if j["source"] == s) for s in range(4)]
        potential.append(max(scopes))
    total = sum(j["work"] for j in jobs if j["adversarial"])
    removed_upper = sum(sorted(potential, reverse=True)[:8])
    return {
        "adversarial_offered_work": total,
        "offered_work_removable_upper": removed_upper,
        "unfiltered_offered_work_lower": total - removed_upper,
    }


def run(root: Path, output: Path) -> None:
    source = Path(__file__).resolve()
    rel = str(source.relative_to(root))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", rel], cwd=root).strip():
        raise ValueError("commit analysis source first")
    blob = source.read_bytes()
    if subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=root) != blob:
        raise ValueError("source mismatch")
    evidence = root / STUDY
    index = (evidence / "STUDY_EVIDENCE.json").read_bytes()
    if digest(index) != ANCHOR:
        raise ValueError("original study anchor changed")
    for name, sha in json.loads(index)["files"].items():
        if Path(name).name != name or digest((evidence / name).read_bytes()) != sha:
            raise ValueError("original evidence changed")
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()

    def timeout(signum: int, frame: Any) -> None:
        raise RuntimeError("read-only analysis 60-second limit")

    prior = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    records = []
    try:
        outcomes = json.loads((evidence / "outcomes.json").read_text())
        for summary in outcomes:
            if summary["policy"] != "noop":
                continue
            family, seed = summary["family"], summary["seed"]
            data = json.loads(
                gzip.decompress((evidence / f"{family}-{seed:02}-noop.json.gz").read_bytes())
            )
            jobs = [j["arrival"] for j in data["requests"]]
            legitimate = [j for j in jobs if not j["adversarial"]]
            adversarial = [j for j in jobs if j["adversarial"]]
            bounds = completion_upper([(j["tick"], j["tick"] + 24, j["work"]) for j in legitimate])
            arms = [r for r in outcomes if r["family"] == family and r["seed"] == seed]
            shared = sum(
                any(
                    legit["source"] == a["source"] and legit["tick"] // 8 == a["tick"] // 8
                    for legit in legitimate
                )
                for a in adversarial
            )
            row = {
                "family": family,
                "seed": seed,
                "legitimate_jobs": len(legitimate),
                "legitimate_offered_work": sum(j["work"] for j in legitimate),
                "total_offered_work": sum(j["work"] for j in jobs),
                "decision_capacity": 480,
                "settlement_capacity_upper": 48,
                "work_for_cheapest_90pct": sum(
                    sorted(j["work"] for j in legitimate)[: (9 * len(legitimate) + 9) // 10]
                ),
                **bounds,
                **coverage(jobs),
                "observed_completion_lower_A": max(
                    r["final"]["legitimate_completed"] for r in arms
                ),
                "observed_completion_lower_B": max(
                    r["final"]["legitimate_completed"]
                    for r in arms
                    if r["policy"] != "persistent_static"
                ),
                "adversarial_jobs": len(adversarial),
                "shared_source_window_adversarial_jobs": shared,
                "legitimate_route1_jobs": sum(j["route"] == 1 for j in legitimate),
                "adversarial_route1_jobs": sum(j["route"] == 1 for j in adversarial),
            }
            records.append(row)
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak_bytes = peak if sys.platform == "darwin" else peak * 1024
            if peak_bytes > 256 * 1024**2 or time.monotonic() - start >= 60:
                raise RuntimeError("analysis budget exhausted")
        if len(records) != 120:
            raise ValueError("expected120 archived workload records")
        result = {
            "source_commit": commit,
            "source_sha256": digest(blob),
            "input_index_sha256": ANCHOR,
            "python": sys.version,
            "platform": platform.platform(),
            "purpose": "read_only_bounds_not_simulation",
            "elapsed_seconds": time.monotonic() - start,
            "peak_rss_bytes": peak_bytes,
            "records": records,
        }
        encoded = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
        (output / "BOUNDS.json").write_bytes(encoded)
        (output / "EVIDENCE.json").write_text(
            json.dumps(
                {"BOUNDS.json": digest(encoded), "original_study_index": ANCHOR}, sort_keys=True
            )
            + "\n"
        )
        print(
            {
                "records": len(records),
                "elapsed_seconds": result["elapsed_seconds"],
                "bounds_sha256": digest(encoded),
            }
        )
    except BaseException as exc:
        (output / "FAILURE.json").write_text(
            json.dumps(
                {"error": repr(exc), "records_completed": len(records), "source_commit": commit}
            )
            + "\n"
        )
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prior)


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[2], Path(sys.argv[1]))
