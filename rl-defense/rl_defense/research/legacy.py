"""Read-only readiness check; no environment, training, OPE or historical writes.

Supported reader: python -m rl_defense.research.legacy.
The original result-directory reader remains frozen archival source only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from rl_defense.research.dataset import digest, load_legacy
from rl_defense.research.proof import (
    bounded_gzip,
    check_semantic_inputs,
    check_source,
    read_artifact,
    scenarios_from_inputs,
    verify_runtime_closure,
)
from rl_defense.research.snapshot import certify_legacy_snapshot

ROOT = Path(__file__).resolve().parents[3]
POLICIES = ("short", "long", "duration", "v6", "tuned_rules")


def verify_legacy(root: Path) -> dict:
    blob = read_artifact(root / "EVIDENCE.json")
    if digest(blob) != "ce9317baa7cad1c1a77dacf19736d0d8fb812e8c76af0b03fc3cc699c77291b6":
        raise ValueError("historical evidence index trust anchor mismatch")
    index = json.loads(blob)
    captured = {"EVIDENCE.json": blob, "RUN.json": read_artifact(root / "RUN.json")}
    if digest(captured["RUN.json"]) != index["files"]["RUN.json"]:
        raise ValueError("historical run pin changed")
    for policy in POLICIES:
        rel = f"train/{policy}/trajectories.jsonl.gz"
        raw = bounded_gzip(read_artifact(root / rel))
        if digest(raw) != index["files"][rel]:
            raise ValueError("historical trajectory pin changed")
        captured[rel] = raw
    return certify_legacy_snapshot(ROOT, captured)


def _verify_legacy(root: Path) -> dict:
    evidence = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads(read_artifact(evidence / "config.json"))
    index = json.loads(read_artifact(evidence / "EVIDENCE.json"))
    check_source(ROOT, evidence, config, set(index["files"]))
    semantic_inputs = check_semantic_inputs(ROOT, config)
    _require_legacy_runtime(config, evidence)
    return _adapt_legacy_data(root, scenarios_from_inputs(semantic_inputs))


def _require_legacy_runtime(config: dict, evidence: Path) -> None:
    if config["python"] != sys.version:
        raise ValueError("legacy verification requires the recorded Python runtime")
    verify_runtime_closure(ROOT, evidence, config)


def _adapt_legacy_data(root: Path, scenarios: list) -> dict:
    index_path = root / "EVIDENCE.json"
    index_blob = read_artifact(index_path)
    if digest(index_blob) != "ce9317baa7cad1c1a77dacf19736d0d8fb812e8c76af0b03fc3cc699c77291b6":
        raise ValueError("historical evidence index trust anchor mismatch")
    index = json.loads(index_blob)
    run_blob = read_artifact(root / "RUN.json")
    if digest(run_blob) != index["files"]["RUN.json"]:
        raise ValueError("historical run pin changed")
    run = json.loads(run_blob)
    if {s.name: s.config_hash() for s in scenarios} != run["splits"]["train"]:
        raise ValueError("historical scenario definitions changed")
    result = {
        "schema": "constrained-readiness/1",
        "source_commit": run["git_sha"],
        "evidence_index_sha256": digest(index_blob),
        "historical_semantics_unchanged": True,
        "new_objective": "negative compromised read count; legitimate defense-denial count",
        "not_counterfactual_evaluation": True,
        "datasets": {},
    }
    with TemporaryDirectory(prefix="rl-legacy-snapshot-") as private_snapshot:
        for policy in POLICIES:
            rel = f"train/{policy}/trajectories.jsonl.gz"
            raw = bounded_gzip(read_artifact(root / rel))
            if digest(raw) != index["files"][rel]:
                raise ValueError("historical trajectory pin changed")
            snapshot = Path(private_snapshot) / "trajectories.jsonl.gz"
            snapshot.write_bytes(raw)
            rows = load_legacy(
                snapshot, expected_sha256=index["files"][rel], scenarios=scenarios, policy=policy
            )
            result["datasets"][policy] = {
                "source_sha256": index["files"][rel],
                "transitions": len(rows),
                "episodes": len({(r.scenario, r.seed) for r in rows}),
                "measured_cost_records": sum(r.benign_cost.value is not None for r in rows),
                "unknown_current_masks": sum(r.current_mask is None for r in rows),
                "unknown_behavior_probabilities": sum(r.behavior_probability is None for r in rows),
                "unknown_delegated_costs": sum(r.delegated_blocked.value is None for r in rows),
            }
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "results/duration-screen"
    print(json.dumps(verify_legacy(root), indent=2, sort_keys=True))
