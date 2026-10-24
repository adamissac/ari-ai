"""Read-only verification of retained study bytes; never simulates or trains."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def verify(output: Path, expected: str) -> dict[str, int]:
    blob = (output / "STUDY_EVIDENCE.json").read_bytes()
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError("external index anchor mismatch")
    index = json.loads(blob)
    files = index["files"]
    if {p.name for p in output.iterdir()} != set(files) | {"STUDY_EVIDENCE.json"}:
        raise ValueError("unexpected or missing artifact")
    for name, sha in files.items():
        if (
            Path(name).name != name
            or hashlib.sha256((output / name).read_bytes()).hexdigest() != sha
        ):
            raise ValueError("artifact digest mismatch")
    outcomes = json.loads((output / "outcomes.json").read_text())
    identities = set()
    total_steps = 0
    paired: dict[Any, Any] = {}
    for row in outcomes:
        f, seed, policy = row["family"], row["seed"], row["policy"]
        identity = (f, seed, policy)
        if identity in identities:
            raise ValueError("duplicate episode")
        identities.add(identity)
        data = json.loads(
            gzip.decompress((output / f"{f}-{seed:02}-{policy}.json.gz").read_bytes())
        )
        if data["summary"] != row:
            raise ValueError("summary mismatch")
        jobs, events, steps = data["requests"], data["events"], data["transitions"]
        if len(steps) != 30 or not steps[-1]["truncated"]:
            raise ValueError("incomplete decisions")
        total_steps += len(steps)
        offered = [j["arrival"] for j in jobs]
        if (f, seed) in paired and paired[f, seed] != offered:
            raise ValueError("unpaired workloads")
        paired[f, seed] = offered
        work = Counter(e["job"] for e in events if e["kind"] == "work")
        last_cutoff = 0
        costs: Counter[str] = Counter()
        for i, t in enumerate(steps):
            info = t["info"]
            if t["step"] != i or not t["mask"][t["action"]]:
                raise ValueError("invalid action/step")
            if (
                not last_cutoff
                == info["before_cutoff_seq"]
                < info["action_seq"]
                < info["observation_cutoff_seq"]
            ):
                raise ValueError("invalid cutoff")
            last_cutoff = info["observation_cutoff_seq"]
            if i and steps[i - 1]["next_observation"] != t["observation"]:
                raise ValueError("observation chain mismatch")
            costs.update(info["costs"])
        if dict(costs) != row["costs"]:
            raise ValueError("cost aggregation mismatch")
        legitimate = [j for j in jobs if not j["arrival"]["adversarial"]]
        checks = {
            "offered": len(jobs),
            "pending": 0,
            "adversarial_work": sum(j["consumed"] for j in jobs if j["arrival"]["adversarial"]),
            "legitimate_offered": len(legitimate),
            "legitimate_completed": sum(j["outcome"] == "completed" for j in legitimate),
            "legitimate_rate_denied": sum(j["outcome"] == "rate_limited" for j in legitimate),
            "legitimate_capacity_denied": sum(
                j["outcome"] == "capacity_rejected" for j in legitimate
            ),
            "legitimate_timeouts": sum(j["outcome"] == "timeout" for j in legitimate),
            "legitimate_latency_sum": sum(
                j["finished"] - j["arrival"]["tick"]
                for j in legitimate
                if j["outcome"] == "completed"
            ),
        }
        if any(row["final"][k] != v for k, v in checks.items()):
            raise ValueError("raw outcome mismatch")
        for j in jobs:
            if (
                j["consumed"] + j["remaining"] != j["arrival"]["work"]
                or work[j["identifier"]] != j["consumed"]
                or j["outcome"] == "pending"
            ):
                raise ValueError("raw work or settlement mismatch")
        if -sum(t["reward"] for t in steps) != row["decision"]["adversarial_work"]:
            raise ValueError("reward aggregation mismatch")
        active = sum(e["event"] == "active" for e in data["ledger"]) * 8
        apps = sum(e["event"] in ("scheduled", "static_reference") for e in data["ledger"])
        if (
            active != costs["active_ticks"]
            or apps != costs["applications"]
            or apps != costs["overhead_units"]
        ):
            raise ValueError("control ledger mismatch")
    manifest = json.loads((output / "manifest.json").read_text())
    expected_ids = {
        (f, s, p) for f in manifest["families"] for s in range(20) for p in manifest["policies"]
    }
    if identities != expected_ids or len(identities) != 600 or total_steps != 18000:
        raise ValueError("study coverage mismatch")
    return {"episodes": 600, "decisions": 18000, "paired_workloads": len(paired)}
