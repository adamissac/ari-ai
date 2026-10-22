"""Verification-only extensions. Never collect data or rewrite archived measurements."""

from __future__ import annotations

import ast
import hashlib
import json
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
HISTORICAL_SOURCE_MAP = "2d00615c272bc2e16447b9069fd230ed43e21c96767f6996c2ea3a7e26b9d24d"
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
    pins = config["code_sha256"]
    old = config["source_commit"] == HISTORICAL_SOURCE
    if old:
        if (
            digest(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode())
            != HISTORICAL_SOURCE_MAP
        ):
            raise ValueError("historical source manifest is incomplete or altered")
    else:
        roots = (
            "rl-defense/rl_defense",
            "shared/shared",
            "examples/payments-lite/target/payments_lite",
            "standards/standards",
        )
        expected = {
            str(p.relative_to(root)) for folder in roots for p in (root / folder).rglob("*.py")
        }
        if set(pins) != expected:
            raise ValueError("source manifest is incomplete or altered")
    if "source.commit.txt" in files:
        raw = (output / "source.commit.txt").read_bytes()
    elif old:
        raw = (output / "frozen/source.commit.txt").read_bytes()
    else:
        raise ValueError("source commit object proof missing")
    verify_commit(raw, config["source_commit"], config["source_tree"])
    if old and config["source_tree"] != HISTORICAL_TREE:
        raise ValueError("historical source tree mismatch")
    if old:
        review = json.loads((output / "REVIEW_EVIDENCE.json").read_bytes())
        if review.get("schema") != "constrained-phase1-review-evidence/1":
            raise ValueError("unsupported review evidence schema")
        # The historical exception allows exactly the separately recorded verifier,
        # not arbitrary future edits outside the two frozen collection functions.
        for rel in (EVALUATOR_PATH, "rl-defense/rl_defense/research/proof.py"):
            if digest((root / rel).read_bytes()) != review["files"][rel]:
                raise ValueError("post-review source changed; use recorded verification source")
    for rel, sha in config["code_sha256"].items():
        if not old:
            try:
                committed = subprocess.check_output(
                    ["git", "show", f"{config['source_commit']}:{rel}"],
                    cwd=root,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as exc:
                raise ValueError("source Git object unavailable; fetch recorded source") from exc
            if digest(committed) != sha:
                raise ValueError(f"source fingerprint does not belong to recorded commit: {rel}")
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
    import numpy as np

    ckpt = root / "rl-defense/results/live-retrain-v6/candidate_online.pt"
    blob = ckpt.read_bytes()
    if digest(blob) != config["v6_checkpoint_sha256"]:
        raise ValueError("policy checkpoint pin mismatch")
    if digest(ckpt.with_suffix(".manifest.json").read_bytes()) != config["v6_manifest_sha256"]:
        raise ValueError("policy manifest pin mismatch")
    params_path = root / "rl-defense/results/duration-screen/RUN.json"
    if (
        digest(params_path.read_bytes()) != config["rules_source_sha256"]
        or json.loads(params_path.read_bytes())["rules_params"] != config["rules_params"]
    ):
        raise ValueError("fixed rules provenance mismatch")
    agent, _ = load_checkpoint(ckpt, blob=blob)
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


def validate_seed_selection(config: dict, scenarios: list) -> None:
    n = config["episodes_per_scenario"]
    if type(n) is not int or not 2 <= n <= 8:
        raise ValueError("invalid declared episode count")
    if any(s.episodes < n or len(s.seeds(n)) != n for s in scenarios):
        raise ValueError("declared episode count exceeds registered seeds")
    if config["episode_seeds"] != {s.name: s.seeds(n) for s in scenarios}:
        raise ValueError("scenario seed selection mismatch")


def validate_raw_requests(raw: bytes, scenarios: list) -> None:
    """Validate recorded HTTP facts before deriving any outcome counts."""
    import gzip
    from dataclasses import fields

    from rl_defense.live.adversary import delegation_grants
    from rl_defense.live.gateway import RequestRecord

    by = {s.name: s for s in scenarios}
    names = {f.name for f in fields(RequestRecord)}
    strings = {"node", "method", "path", "actor"}
    nullable = {"blocked_reason", "principal", "owner"}
    flags = {"is_attack", "compromised", "cross_tenant_attempt"}
    statuses = {"isolated": 503, "principal_blocked": 403, "rate_limited": 429}
    for line in gzip.decompress(raw).decode().splitlines():
        ep = json.loads(line)
        grants = delegation_grants(by[ep["scenario"]].driver().delegates)
        for step in ep["steps"]:
            for q in step["requests"]:
                if (
                    set(q) != names
                    or any(type(q[k]) is not str for k in strings)
                    or any(q[k] is not None and type(q[k]) is not str for k in nullable)
                    or any(type(q[k]) is not bool for k in flags)
                    or type(q["status"]) is not int
                    or not 100 <= q["status"] <= 599
                ):
                    raise ValueError("invalid raw request shape")
                principal, owner, reason = q["principal"], q["owner"], q["blocked_reason"]
                foreign = principal is not None and owner is not None and principal != owner
                cross = foreign and owner not in grants.get(principal, ())
                if (
                    q["cross_tenant_attempt"] != cross
                    or (
                        reason is not None
                        and (reason not in statuses or q["status"] != statuses[reason])
                    )
                    or (reason == "principal_blocked" and principal is None)
                    or (q["compromised"] != (reason is None and q["status"] == 200 and foreign))
                ):
                    raise ValueError("contradictory raw request outcome")
