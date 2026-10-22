"""Explicit lab-only baseline evaluation; no training, promotion or serving hook.

Run: python -m rl_defense.research.evaluate run --output <new-directory>
Verify: python -m rl_defense.research.evaluate verify --output <directory>
"""

from __future__ import annotations

import argparse
import gzip
import importlib.metadata
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from rl_defense.checkpoint import load_checkpoint
from rl_defense.live.adversary import delegation_grants, live_app
from rl_defense.live.evaluate import always_block_principal, dqn_policy, noop_policy, rules_policy
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import LiveScenario, load_scenarios
from rl_defense.research.dataset import adapt, digest, evidence, validate_episodes
from rl_defense.research.metrics import report
from rl_defense.research.policies import CostAwareRules, capability_mask
from rl_defense.research.proof import (
    bounded_gzip,
    check_semantic_inputs,
    check_source,
    environment_packages,
    read_artifact,
    resolve_source,
    scenarios_from_inputs,
    topology_from_inputs,
    validate_raw_requests,
    validate_seed_selection,
    verify_deterministic_replay,
    verify_policy_actions,
    verify_runtime_closure,
)
from rl_defense.research.records import ResearchTransition

ROOT = Path(__file__).resolve().parents[3]
V6_SHA = "8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1"
POLICIES = ("noop", "tuned_rules_shielded", "fixed_short_block", "v6_shielded", "cost_aware")
OVERRIDES = {
    "c_disrupt": 1.0,
    "delegation_aware_detector": True,
    "finding_severity_context": "platform",
}


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def code_files() -> list[Path]:
    # Full source identity, not just the new adapter. Configs recorded separately.
    roots = (
        ROOT / "rl-defense/rl_defense",
        ROOT / "shared/shared",
        ROOT / "examples/payments-lite/target/payments_lite",
        ROOT / "standards/standards",
    )
    return sorted(p for root in roots for p in root.rglob("*.py"))


def collect_episode(sc: LiveScenario, seed: int, choose) -> dict:  # noqa: ANN001
    if sc.split != "train" or seed not in sc.seeds():
        raise ValueError("Phase 1 fresh evaluation is train-only")
    cfg = LoopConfig(horizon=sc.horizon, action_space="live_v3", **OVERRIDES)
    loop = LiveDefenseLoop(live_app, config=cfg, driver=sc.driver())
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


def records_from_raw(raw: bytes, scenarios: list[LiveScenario]) -> list[ResearchTransition]:
    from rl_defense.live.contracts import LiveTransition

    sha = digest(raw)
    by = {s.name: s for s in scenarios}
    rows = []
    for line_idx, line in enumerate(gzip.decompress(raw).decode().splitlines()):
        ep = json.loads(line)
        sc = by[ep["scenario"]]
        if len(ep["steps"]) != sc.horizon or ep["seed"] not in sc.seeds():
            raise ValueError("raw episode horizon/seed mismatch")
        grants = delegation_grants(sc.driver().delegates)
        for i, step in enumerate(ep["steps"]):
            t = LiveTransition.model_validate(step["transition"])
            req = step["requests"]
            observed = (
                sum(r["is_attack"] for r in req),
                sum(r["is_attack"] and r["compromised"] for r in req),
                sum(not r["is_attack"] for r in req),
                sum(not r["is_attack"] and r["blocked_reason"] is not None for r in req),
            )
            o = t.outcome
            if observed != (
                o.attack_requests,
                o.compromised_reads,
                o.benign_requests,
                o.benign_blocked,
            ):
                raise ValueError("request/outcome count mismatch")
            delegated = sum(
                r["blocked_reason"] is not None
                and not r["is_attack"]
                and r["principal"] != r["owner"]
                and r["owner"] in grants.get(r["principal"], ())
                for r in req
            )
            if delegated != step["delegated_blocked"]:
                raise ValueError("delegated request accounting mismatch")
            src = evidence("raw.jsonl.gz", sha, f"line/{line_idx}/steps/{i}")
            r = adapt(
                t,
                source=src,
                dataset_id=f"lab_{sha}",
                policy=ep["policy"],
                sc=sc,
                seed=ep["seed"],
                index=i,
                current_mask=step["current_mask"],
                delegated_blocked=delegated,
            )
            # This adapter's masks explicitly mean the capability-restricted research
            # action set. The unchanged original transition retains the lab's own mask.
            next_mask = capability_mask(np.asarray(t.action_mask)).tolist()
            if (
                next_mask != step["next_research_mask"]
                or capability_mask(np.asarray(step["current_mask"])).tolist()
                != step["current_mask"]
            ):
                raise ValueError("research capability mask mismatch")
            r = r.model_copy(update={"next_mask": tuple(next_mask)})
            rows.append(r)
    validate_episodes(rows)
    return rows


def run(
    output: Path,
    episodes: int = 4,
    *,
    published_commit: str | None = None,
    published_tree: str | None = None,
) -> dict:
    if not 2 <= episodes <= 8:
        raise ValueError("bounded Phase 1 evaluation requires 2..8 episodes/scenario")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True
    ).strip()
    if dirty:
        raise ValueError("commit research source/config before evaluation")
    local_revision = revision
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    if published_commit is not None:
        if (
            len(published_commit) != 40
            or any(c not in "0123456789abcdef" for c in published_commit)
            or published_tree != tree
        ):
            raise ValueError("published commit needs the exact matching execution source tree")
        revision = published_commit
    elif published_tree is not None:
        raise ValueError("published tree needs a commit")
    source_object = resolve_source(ROOT, revision, tree)
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "source.commit.txt").write_bytes(source_object)
        ckpt = ROOT / "rl-defense/results/live-retrain-v6/candidate_online.pt"
        before = ckpt.read_bytes()
        if digest(before) != V6_SHA:
            raise ValueError("frozen v6 checkpoint mismatch")
        agent, manifest = load_checkpoint(ckpt, blob=before)
        if agent.n_actions != 25 or manifest["checkpoint_sha256"] != V6_SHA:
            raise ValueError("v6 layout/manifest mismatch")
        params_path = ROOT / "rl-defense/results/duration-screen/RUN.json"
        params = json.loads(params_path.read_text())["rules_params"]
        scenarios = load_scenarios("train", subdir="train_v8")
        config = {
            "schema": "constrained-lab-evaluation/1",
            "source_commit": revision,
            "execution_local_commit": local_revision,
            "source_tree": tree,
            "publication": "Git-resolved commit with verified matching tree"
            if published_commit
            else "local Git commit",
            "environment": "owned payments-lite in-process lab; not production",
            "semantics": "all baselines share research capability mask; v6_shielded is NOT original v6 performance",
            "reward": "negative compromised attack read count",
            "cost": "blocked legitimate request count",
            "gamma": 1.0,
            "bootstrap_seed": 17,
            "resamples": 2000,
            "episodes_per_scenario": episodes,
            "policies": list(POLICIES),
            "scenario_configs": [s.model_dump(mode="json") for s in scenarios],
            "scenario_hashes": {s.name: s.config_hash() for s in scenarios},
            "episode_seeds": {s.name: s.seeds(episodes) for s in scenarios},
            "loop_overrides": OVERRIDES,
            "cost_aware_max_interventions": 2,
            "v6_checkpoint_sha256": V6_SHA,
            "v6_manifest_sha256": digest(ckpt.with_suffix(".manifest.json").read_bytes()),
            "rules_params": params,
            "rules_source_sha256": digest(params_path.read_bytes()),
            "python": sys.version,
            "dependencies": {
                p: importlib.metadata.version(p)
                for p in ("numpy", "pydantic", "torch", "gymnasium", "fastapi", "httpx", "PyYAML")
            },
            "environment_packages": environment_packages(),
            "code_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in code_files()},
        }
        (output / "config.json").write_bytes(encoded(config))
        with gzip.GzipFile(filename=str(output / "raw.jsonl.gz"), mode="wb", mtime=0) as fh:
            for sc in scenarios:
                for seed in sc.seeds(episodes):
                    for p in POLICIES:
                        policy = {
                            "noop": noop_policy,
                            "tuned_rules_shielded": rules_policy(params),
                            "fixed_short_block": always_block_principal,
                            "v6_shielded": dqn_policy(agent),
                            "cost_aware": CostAwareRules(),
                        }[p]
                        ep = {"policy": p, **collect_episode(sc, seed, policy)}
                        fh.write(json.dumps(ep, sort_keys=True, allow_nan=False).encode() + b"\n")
        if ckpt.read_bytes() != before:
            raise ValueError("checkpoint changed during evaluation")
        rows = records_from_raw((output / "raw.jsonl.gz").read_bytes(), scenarios)
        (output / "transitions.jsonl.gz").write_bytes(
            gzip.compress("".join(r.model_dump_json() + "\n" for r in rows).encode(), mtime=0)
        )
        result = report(
            rows,
            gamma=config["gamma"],
            bootstrap_seed=config["bootstrap_seed"],
            resamples=config["resamples"],
        )
        (output / "summary.json").write_bytes(encoded(result))
        files = (
            "config.json",
            "raw.jsonl.gz",
            "transitions.jsonl.gz",
            "summary.json",
            "source.commit.txt",
        )
        index = {
            "schema": "constrained-lab-evidence/1",
            "source_commit": revision,
            "files": {f: digest((output / f).read_bytes()) for f in files},
            "dataset_id": rows[0].dataset_id,
            "not_a_promotion_decision": True,
            "phase2_started": False,
        }
        (output / "EVIDENCE.json").write_bytes(encoded(index))
        return verify(output)
    except Exception as exc:
        (output / "FAILURE.json").write_bytes(
            encoded({"error": str(exc), "automatic_retry": False})
        )
        raise


def verify(output: Path) -> dict:
    index_blob = read_artifact(output / "EVIDENCE.json")
    index = json.loads(index_blob)
    if index.get("schema") != "constrained-lab-evidence/1":
        raise ValueError("unsupported evidence schema")
    expected_files = {"config.json", "raw.jsonl.gz", "transitions.jsonl.gz", "summary.json"}
    if set(index["files"]) not in (expected_files, expected_files | {"source.commit.txt"}):
        raise ValueError("unexpected evidence files")
    artifacts = {name: read_artifact(output / name) for name in index["files"]}
    for name, sha in index["files"].items():
        if digest(artifacts[name]) != sha:
            raise ValueError(f"evidence hash mismatch: {name}")
    config = json.loads(artifacts["config.json"])
    if config.get("schema") != "constrained-lab-evaluation/1":
        raise ValueError("unsupported configuration schema")
    if (
        index.get("not_a_promotion_decision") is not True
        or index.get("phase2_started") is not False
    ):
        raise ValueError("evidence violates Phase 1 boundary")
    if (
        config["loop_overrides"] != OVERRIDES
        or config["policies"] != list(POLICIES)
        or config["v6_checkpoint_sha256"] != V6_SHA
        or config["cost_aware_max_interventions"] != 2
        or type(config["resamples"]) is not int
        or config["resamples"] != 2000
        or config["bootstrap_seed"] != 17
        or config["gamma"] != 1.0
    ):
        raise ValueError("unsupported baseline profile semantics")
    check_source(
        ROOT,
        output,
        config,
        set(index["files"]),
        commit_object=artifacts.get("source.commit.txt"),
        index_object=index_blob,
    )
    semantic_inputs = check_semantic_inputs(ROOT, config)
    scenarios = [LiveScenario.model_validate(d) for d in config["scenario_configs"]]
    if scenarios != scenarios_from_inputs(semantic_inputs):
        raise ValueError("scenario definitions differ from the pinned train_v8 benchmark")
    if any(s.split != "train" for s in scenarios):
        raise ValueError("Phase 1 fresh evaluation cannot contain holdout/validation")
    if index["source_commit"] != config["source_commit"]:
        raise ValueError("source commit identity mismatch")
    if {s.name: s.config_hash() for s in scenarios} != config["scenario_hashes"]:
        raise ValueError("scenario hash mismatch")
    validate_seed_selection(config, scenarios)
    runtime = {
        p: importlib.metadata.version(p)
        for p in ("numpy", "pydantic", "torch", "gymnasium", "fastapi", "httpx", "PyYAML")
    }
    if config["python"] != sys.version or config["dependencies"] != runtime:
        raise ValueError("recorded runtime differs; use the exact execution environment")
    scope = {
        "environment": "owned payments-lite in-process lab; not production",
        "semantics": "all baselines share research capability mask; v6_shielded is NOT original v6 performance",
        "reward": "negative compromised attack read count",
        "cost": "blocked legitimate request count",
    }
    if any(config[k] != v for k, v in scope.items()) or config["publication"] not in (
        "local Git commit",
        "Git-resolved commit with verified matching tree",
        "caller-supplied GitHub commit with matching tree",
    ):
        raise ValueError("evidence scope metadata mismatch")
    verify_runtime_closure(ROOT, output, config)
    raw = bounded_gzip(artifacts["raw.jsonl.gz"])
    bounded_gzip(artifacts["transitions.jsonl.gz"])
    validate_raw_requests(raw, scenarios)
    rows = records_from_raw(raw, scenarios)
    saved = [
        ResearchTransition.model_validate_json(line)
        for line in gzip.decompress(artifacts["transitions.jsonl.gz"]).decode().splitlines()
    ]
    if rows != saved or index["dataset_id"] != rows[0].dataset_id:
        raise ValueError("raw-derived transitions differ from saved records")
    expected = {
        (p, s.name, seed, i)
        for p in config["policies"]
        for s in scenarios
        for seed in config["episode_seeds"][s.name]
        for i in range(s.horizon)
    }
    if {(r.policy, r.scenario, r.seed, r.t) for r in rows} != expected or len(rows) != len(
        expected
    ):
        raise ValueError("missing, repeated or additional evaluation units")
    verify_deterministic_replay(raw, scenarios, topology_from_inputs(semantic_inputs))
    verify_policy_actions(ROOT, config, rows, semantic_inputs=semantic_inputs)
    actual = report(
        rows,
        gamma=config["gamma"],
        bootstrap_seed=config["bootstrap_seed"],
        resamples=config["resamples"],
    )
    if actual != json.loads(artifacts["summary.json"]):
        raise ValueError("summary differs from raw evidence")
    return {
        "verified": True,
        "transitions": len(rows),
        "episodes": len({(r.policy, r.scenario, r.seed) for r in rows}),
        "source_commit": config["source_commit"],
        "original_dependency_closure_known": "environment_packages" in config,
        "verification_source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--published-commit")
    parser.add_argument("--published-tree")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output,
                args.episodes,
                published_commit=args.published_commit,
                published_tree=args.published_tree,
            )
            if args.operation == "run"
            else verify(args.output)
        )
    )


if __name__ == "__main__":
    main()
