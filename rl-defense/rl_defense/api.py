"""Public interface of rl-defense for other subsystems (backend, frontend via backend).

Import only from here; everything else is internal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rl_defense import ENV_ID, SIMULATION_CAVEAT
from rl_defense.contracts import DefenseRecommendation, PlatformFacts, RLCheckpointRef
from rl_defense.explain import Explanation
from rl_defense.inference import PolicyRunner

__all__ = [
    "ENV_ID",
    "SIMULATION_CAVEAT",
    "DefenseRecommendation",
    "Explanation",
    "PlatformFacts",
    "PolicyRunner",
    "RLCheckpointRef",
    "checkpoint_ref",
    "load_eval_summary",
    "load_policy",
    "recommend",
]


def load_policy(checkpoint: str | Path) -> PolicyRunner:
    """Load and hash-verify a checkpoint for inference."""
    return PolicyRunner(Path(checkpoint))


def recommend(checkpoint: str | Path, facts: PlatformFacts) -> DefenseRecommendation:
    return load_policy(checkpoint).recommend(facts)


def checkpoint_ref(checkpoint: str | Path) -> RLCheckpointRef:
    m = json.loads(Path(checkpoint).with_suffix(".manifest.json").read_text())
    return RLCheckpointRef(
        id=f"ckp_{m['checkpoint_sha256'][:24]}",
        env_id=m["env_id"],
        seed=m["seed"],
        steps=m["steps"],
        git_sha=m["git_sha"],
        checkpoint_file=m["checkpoint_file"],
        checkpoint_sha256=m["checkpoint_sha256"],
        train_configs=m["train_configs"],
    )


def load_eval_summary(run_dir: str | Path) -> dict[str, Any]:
    """The persisted protocol-17 evaluation artifact the UI should plot (never invented numbers)."""
    return json.loads((Path(run_dir) / "eval_summary.json").read_text())
