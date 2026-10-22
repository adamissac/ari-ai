"""Verification-only extensions. Never collect data or rewrite archived measurements."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.live.evaluate import always_block_principal, dqn_policy, noop_policy, rules_policy
from rl_defense.research.dataset import digest
from rl_defense.research.policies import CostAwareRules
from rl_defense.research.records import ResearchTransition

HISTORICAL_SOURCE = "9d6460487275d25cc31194d7b603196d436c4485"
HISTORICAL_TREE = "22c2f7f50c36e5fe5b7eb1d26c41b1b314438e4a"
HISTORICAL_EVALUATOR = "8c0002a79444f367a3b34967c198d4b3b1a292d5573fc134553168d385452b2e"
EVALUATOR_PATH = "rl-defense/rl_defense/research/evaluate.py"


def resolve_source(root: Path, revision: str, expected_tree: str) -> bytes:
    """A declared SHA/tree pair is not proof; Git must resolve the actual commit."""
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("source revision must be a full Git commit SHA")
    try:
        tree = subprocess.check_output(
            ["git", "rev-parse", f"{revision}^{{tree}}"],
            cwd=root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        raw = subprocess.check_output(
            ["git", "cat-file", "commit", revision], cwd=root, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "source commit is unavailable; fetch its Git object before execution"
        ) from exc
    if tree != expected_tree:
        raise ValueError("published commit does not own the execution tree")
    verify_commit(raw, revision, tree)
    return raw


def verify_commit(raw: bytes, revision: str, tree: str) -> None:
    # Git's exact raw object proves the SHA->tree relationship offline, even on CI
    # where an earlier source revision's object has not been fetched yet.
    actual = hashlib.sha1(b"commit " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if actual != revision or raw.split(b"\n", 1)[0] != f"tree {tree}".encode():
        raise ValueError("source commit object/tree proof mismatch")


def check_source(root: Path, output: Path, config: dict, files: set[str]) -> None:
    old = config["source_commit"] == HISTORICAL_SOURCE
    if "source.commit.txt" in files:
        raw = (output / "source.commit.txt").read_bytes()
    elif old:
        raw = (output / "frozen/source.commit.txt").read_bytes()
    else:
        raise ValueError("source commit object proof missing")
    verify_commit(raw, config["source_commit"], config["source_tree"])
    if old and config["source_tree"] != HISTORICAL_TREE:
        raise ValueError("historical source tree mismatch")
    for rel, sha in config["code_sha256"].items():
        p = (root / rel).resolve()
        if not p.is_relative_to(root):
            raise ValueError("source path leaves checkout")
        if digest(p.read_bytes()) == sha:
            continue
        if not (old and rel == EVALUATOR_PATH and sha == HISTORICAL_EVALUATOR):
            raise ValueError(f"source semantics changed: {rel}; use recorded source commit")
        original = (output / "frozen/evaluate.py.txt").read_bytes()
        if digest(original) != HISTORICAL_EVALUATOR:
            raise ValueError("archived original evaluator source mismatch")

        # Only run/provenance/verification orchestration changed. Reuse identical
        # collection and adaptation functions; reward/cost/policy/environment code
        # must still match the original complete source pins above.
        def definitions(data: bytes) -> dict:
            return {
                n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse(data).body
                if isinstance(n, ast.FunctionDef)
                and n.name in {"collect_episode", "records_from_raw"}
            }

        if definitions(original) != definitions(p.read_bytes()):
            raise ValueError("historical collection/adaptation semantics changed")


def verify_policy_actions(root: Path, config: dict, rows: list[ResearchTransition]) -> None:
    import json

    import numpy as np

    ckpt = root / "rl-defense/results/live-retrain-v6/candidate_online.pt"
    if digest(ckpt.read_bytes()) != config["v6_checkpoint_sha256"]:
        raise ValueError("policy checkpoint pin mismatch")
    if digest(ckpt.with_suffix(".manifest.json").read_bytes()) != config["v6_manifest_sha256"]:
        raise ValueError("policy manifest pin mismatch")
    params_path = root / "rl-defense/results/duration-screen/RUN.json"
    if (
        digest(params_path.read_bytes()) != config["rules_source_sha256"]
        or json.loads(params_path.read_bytes())["rules_params"] != config["rules_params"]
    ):
        raise ValueError("fixed rules provenance mismatch")
    agent, _ = load_checkpoint(ckpt)
    choices = {
        "noop": lambda: noop_policy,
        "tuned_rules_shielded": lambda: rules_policy(config["rules_params"]),
        "fixed_short_block": lambda: always_block_principal,
        "v6_shielded": lambda: dqn_policy(agent),
        "cost_aware": lambda: CostAwareRules(config["cost_aware_max_interventions"]),
    }
    episodes: dict[tuple, list[ResearchTransition]] = {}
    for r in rows:
        episodes.setdefault((r.policy, r.scenario, r.seed), []).append(r)
    for (policy, scenario, seed), ts in episodes.items():
        if policy not in choices:
            raise ValueError("unknown baseline policy")
        choose = choices[policy]()
        for r in sorted(ts, key=lambda r: r.t):
            if r.current_mask is None:
                raise ValueError("on-policy certification needs the recorded decision mask")
            expected = int(
                choose(np.asarray(r.obs, dtype=np.float32), np.asarray(r.current_mask, dtype=bool))
            )
            if expected != r.action:
                raise ValueError(
                    f"action differs from claimed policy {policy}/{scenario}/{seed}/{r.t}"
                )
