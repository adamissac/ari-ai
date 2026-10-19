"""Collect live experience into a versioned, hash-pinned dataset (train split only).

A behavior policy (ε-greedy around a checkpoint, or uniform over valid actions) runs
against the owned demo app on **training** scenarios. Every transition is recorded with
its scenario, seed and step. The JSONL file is pinned by a SHA-256 in a manifest; the
retrainer refuses a dataset whose bytes do not match, or that contains anything other
than training-split scenarios.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from rl_defense.checkpoint import git_sha, sha256_file
from rl_defense.live.evaluate import PolicyFn, run_policy
from rl_defense.live.scenarios import LiveScenario

DATASET_SCHEMA = "live-experience/0.1"


def behavior_policy(agent, epsilon: float, seed: int) -> PolicyFn:  # noqa: ANN001
    """ε-greedy over VALID actions around ``agent`` (uniform random when agent is None)."""
    rng = np.random.default_rng(seed)

    def act(obs: np.ndarray, mask: np.ndarray) -> int:
        valid = np.flatnonzero(mask)
        if agent is None or rng.random() < epsilon:
            return int(rng.choice(valid))
        return int(agent.greedy_action(obs, mask))

    return act


def collect(
    scenarios: list[LiveScenario],
    out_path: Path,
    app_factory,  # noqa: ANN001
    *,
    agent=None,  # noqa: ANN001
    behavior_checkpoint_sha256: str | None = None,
    epsilon: float = 0.3,
    seed: int = 0,
    episodes: int | None = None,
) -> dict:
    bad = [s.name for s in scenarios if s.split != "train"]
    if bad:
        raise ValueError(f"experience may only be collected on train scenarios, got {bad}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    n_eps = 0
    with out_path.open("w") as fh:

        def write(sc: LiveScenario, ep_seed: int, ts) -> None:  # noqa: ANN001
            nonlocal n, n_eps
            n_eps += 1
            for i, t in enumerate(ts):
                rec = {
                    "scenario": sc.name,
                    "scenario_hash": sc.config_hash(),
                    "split": sc.split,
                    "seed": ep_seed,
                    "t": i,
                    **t.model_dump(mode="json"),
                }
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                n += 1

        run_policy(
            behavior_policy(agent, epsilon, seed),
            scenarios,
            app_factory,
            episodes=episodes,
            on_episode=write,
        )
    digest = sha256_file(out_path)
    manifest = {
        "schema": DATASET_SCHEMA,
        "dataset_id": f"exp_{digest[:16]}",
        "file": out_path.name,
        "sha256": digest,
        "transitions": n,
        "episodes": n_eps,
        "scenarios": {s.name: s.config_hash() for s in scenarios},
        "splits": ["train"],
        "behavior": {
            "kind": "epsilon_greedy" if agent is not None else "uniform_valid",
            "checkpoint_sha256": behavior_checkpoint_sha256,
            "epsilon": epsilon if agent is not None else 1.0,
            "seed": seed,
        },
        "target": "examples/payments-lite (in-process)",
        "git_sha": git_sha(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    out_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_dataset(path: Path) -> tuple[list[dict], dict]:
    """Load a dataset after verifying its bytes against the manifest and its split."""
    path = Path(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != manifest["sha256"]:
        raise ValueError(f"dataset hash mismatch for {path}: {actual} != {manifest['sha256']}")
    records = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    bad = {r["split"] for r in records} - {"train"}
    if bad:
        raise ValueError(f"dataset {path} contains non-train splits {sorted(bad)}")
    return records, manifest
