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


def check_source(
    root: Path,
    output: Path,
    config: dict,
    files: set[str],
    *,
    commit_object: bytes | None = None,
    index_object: bytes | None = None,
) -> None:
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
        raw = (
            commit_object
            if commit_object is not None
            else (output / "source.commit.txt").read_bytes()
        )
    elif old:
        raw = (output / "frozen/source.commit.txt").read_bytes()
    else:
        raise ValueError("source commit object proof missing")
    verify_commit(raw, config["source_commit"], config["source_tree"])
    if old and config["source_tree"] != HISTORICAL_TREE:
        raise ValueError("historical source tree mismatch")
    if old:
        review_blob = read_artifact(output / "REVIEW_EVIDENCE.json")
        committed_review = subprocess.check_output(
            ["git", "show", "HEAD:rl-defense/results/constrained-phase1/REVIEW_EVIDENCE.json"],
            cwd=root,
        )
        if review_blob != committed_review:
            raise ValueError("review manifest differs from trusted checkout commit")
        review = json.loads(review_blob)
        if review.get("schema") != "constrained-phase1-review-evidence/1":
            raise ValueError("unsupported review evidence schema")
        index_blob = (
            index_object if index_object is not None else read_artifact(output / "EVIDENCE.json")
        )
        if digest(index_blob) != review["original_execution_index_sha256"]:
            raise ValueError("historical execution index differs from trusted review anchor")
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


def verify_policy_actions(
    root: Path,
    config: dict,
    rows: list[ResearchTransition],
    *,
    semantic_inputs: dict[str, bytes] | None = None,
) -> None:
    import numpy as np

    ckpt = root / "rl-defense/results/live-retrain-v6/candidate_online.pt"
    blob = read_artifact(ckpt)
    if digest(blob) != config["v6_checkpoint_sha256"]:
        raise ValueError("policy checkpoint pin mismatch")
    manifest_blob = (
        semantic_inputs["rl-defense/results/live-retrain-v6/candidate_online.manifest.json"]
        if semantic_inputs is not None
        else read_artifact(ckpt.with_suffix(".manifest.json"))
    )
    if digest(manifest_blob) != config["v6_manifest_sha256"]:
        raise ValueError("policy manifest pin mismatch")
    params_path = root / "rl-defense/results/duration-screen/RUN.json"
    params_blob = (
        semantic_inputs["rl-defense/results/duration-screen/RUN.json"]
        if semantic_inputs is not None
        else read_artifact(params_path)
    )
    if (
        digest(params_blob) != config["rules_source_sha256"]
        or json.loads(params_blob)["rules_params"] != config["rules_params"]
    ):
        raise ValueError("fixed rules provenance mismatch")
    agent, embedded = load_checkpoint(ckpt, blob=blob)
    validate_checkpoint_manifest(json.loads(manifest_blob), embedded, ckpt.name)
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


def check_semantic_inputs(root: Path, config: dict) -> dict[str, bytes]:
    paths = sorted(
        str(p.relative_to(root)) for p in (root / "rl-defense/configs/live/train_v8").glob("*.yaml")
    )
    paths += [
        "rl-defense/results/duration-screen/RUN.json",
        "rl-defense/configs/topology/payments_lite.yaml",
        "rl-defense/results/live-retrain-v6/candidate_online.manifest.json",
    ]
    captured = {p: read_artifact(root / p) for p in paths}
    pins = {p: digest(blob) for p, blob in captured.items()}
    if config["source_commit"] == HISTORICAL_SOURCE:
        if (
            digest(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode())
            != "f87fdf3c404f095c1deb5deceee75094764c1583cc0cfe33cd8aefba98682287"
        ):
            raise ValueError("historical semantic inputs changed")
    else:
        tracked = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                config["source_commit"],
                "--",
                "rl-defense/configs/live/train_v8",
            ],
            cwd=root,
            text=True,
        ).splitlines()
        if set(tracked) != set(paths[:-3]):
            raise ValueError("scenario input set differs from source commit")
        for p, sha in pins.items():
            committed = subprocess.check_output(
                ["git", "show", f"{config['source_commit']}:{p}"], cwd=root
            )
            if digest(committed) != sha:
                raise ValueError("semantic input does not belong to source commit")

    return captured


def bounded_gzip(source: Path | bytes) -> bytes:
    """Bound both compressed and expanded memory before parsing untrusted JSON."""
    import gzip
    import io

    raw = read_artifact(source) if isinstance(source, Path) else source
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("compressed evidence exceeds verification limit")
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        expanded = stream.read(64 * 1024 * 1024 + 1)
    if len(expanded) > 64 * 1024 * 1024:
        raise ValueError("expanded evidence exceeds verification limit")
    return raw


def verify_deterministic_replay(raw: bytes, scenarios: list, topology=None) -> None:
    """Reconstruct decision inputs and HTTP outcomes; never save replacement evidence."""
    import gzip

    import numpy as np

    by = {s.name: s for s in scenarios}
    for line in gzip.decompress(raw).decode().splitlines():
        ep = json.loads(line)
        sc = by[ep["scenario"]]
        if len(ep["steps"]) != sc.horizon:
            raise ValueError("replay horizon mismatch")
        index = 0

        def recorded_action(obs, mask, steps=ep["steps"]):
            nonlocal index
            step = steps[index]
            if (
                not np.array_equal(obs, np.asarray(step["transition"]["obs"], dtype=np.float32))
                or mask.tolist() != step["current_mask"]
            ):
                raise ValueError("recorded decision inputs differ from deterministic replay")
            index += 1
            return step["transition"]["action"]

        actual = reconstruct_episode(sc, ep["seed"], recorded_action, topology)
        if actual != {k: v for k, v in ep.items() if k != "policy"}:
            raise ValueError(
                "request labels/identities or outcomes differ from deterministic replay"
            )


def read_artifact(path: Path) -> bytes:
    """One bounded read supplies all subsequent hash/parse/replay operations."""
    with path.open("rb") as stream:
        blob = stream.read(8 * 1024 * 1024 + 1)
    if len(blob) > 8 * 1024 * 1024:
        raise ValueError("evidence file exceeds verification limit")
    return blob


def environment_packages() -> dict[str, str]:
    """Full installed distribution closure, including HTTP replay dependencies."""
    import importlib.metadata

    return dict(
        sorted(
            (d.metadata["Name"].lower().replace("_", "-"), d.version)
            for d in importlib.metadata.distributions()
        )
    )


def verify_runtime_closure(root: Path, output: Path, config: dict) -> None:
    expected = config.get("environment_packages")
    if expected is None:
        if config["source_commit"] != HISTORICAL_SOURCE:
            raise ValueError("recorded full dependency closure missing")
        # The original study did not capture its transitive closure. Do not invent
        # it retrospectively: validate the separately recorded reproduction runtime.
        path = "rl-defense/results/constrained-phase1/REVIEW_RUNTIME.json"
        blob = read_artifact(output / "REVIEW_RUNTIME.json")
        committed = subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=root)
        if blob != committed:
            raise ValueError("review runtime differs from trusted checkout commit")
        profile = json.loads(blob)
        if profile["original_dependency_closure_known"] is not False:
            raise ValueError("historical dependency closure must remain unknown")
        expected = profile["environment_packages"]
    if expected != environment_packages():
        raise ValueError("full dependency closure differs from recorded verification runtime")


def validate_checkpoint_manifest(sidecar: dict, embedded: dict, name: str) -> None:
    expected = {**embedded, "checkpoint_file": name}
    if sidecar != expected:
        raise ValueError("checkpoint sidecar lineage differs from pinned embedded manifest")


def reconstruct_episode(sc, seed: int, choose, topology) -> dict:  # noqa: ANN001
    from dataclasses import asdict

    import numpy as np

    from rl_defense.live.adversary import delegation_grants, live_app
    from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
    from rl_defense.research.evaluate import OVERRIDES
    from rl_defense.research.policies import capability_mask

    if sc.split != "train" or seed not in sc.seeds():
        raise ValueError("Phase 1 fresh evaluation is train-only")
    cfg = LoopConfig(horizon=sc.horizon, action_space="live_v3", **OVERRIDES)
    loop = LiveDefenseLoop(live_app, config=cfg, driver=sc.driver(), topology=topology)
    steps = []
    grants = delegation_grants(loop.driver.delegates)
    try:
        obs, base_mask = loop.reset(seed)
        for _ in range(sc.horizon):
            mask = capability_mask(base_mask)
            action = int(choose(obs.copy(), mask.copy()))
            if not 0 <= action < len(mask) or not mask[action]:
                raise ValueError("baseline proposed unavailable action")
            t = loop.step(action)
            # Isolated read-only observation of existing lab instrumentation; never exposed
            # to policy. Preserve records to independently verify cost and delegation.
            requests = [asdict(r) for r in loop._gateway.records]
            delegated_blocked = sum(
                r["blocked_reason"] is not None
                and not r["is_attack"]
                and r["principal"] != r["owner"]
                and r["owner"] in grants.get(r["principal"], ())
                for r in requests
            )
            steps.append(
                {
                    "transition": t.model_dump(mode="json"),
                    "current_mask": mask.tolist(),
                    "next_research_mask": capability_mask(np.asarray(t.action_mask)).tolist(),
                    "requests": requests,
                    "delegated_blocked": delegated_blocked,
                }
            )
            obs, base_mask = np.asarray(t.next_obs, dtype=np.float32), np.asarray(t.action_mask)
            if t.done:
                break
    finally:
        loop.close()
    return {"scenario": sc.name, "seed": seed, "steps": steps}


def scenarios_from_inputs(inputs: dict[str, bytes]) -> list:
    import yaml

    from rl_defense.live.scenarios import LiveScenario

    return [
        LiveScenario.model_validate(yaml.safe_load(blob))
        for path, blob in sorted(inputs.items())
        if path.startswith("rl-defense/configs/live/train_v8/")
    ]


def topology_from_inputs(inputs: dict[str, bytes]):
    import yaml

    from rl_defense.live.topology import NodeRoutes, RouteTopology

    data = yaml.safe_load(inputs["rl-defense/configs/topology/payments_lite.yaml"])
    nodes = [
        NodeRoutes(
            node=n["node"],
            patterns=tuple(n.get("route_patterns", [])),
            exposed=bool(n.get("exposed", False)),
            criticality_floor=float(n.get("criticality_floor", 0.5)),
        )
        for n in data["nodes"]
    ]
    return RouteTopology(nodes, data.get("default_node", "api"))
