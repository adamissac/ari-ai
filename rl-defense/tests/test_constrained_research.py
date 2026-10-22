"""Phase 1 research boundary, measurement and reproducibility tests (no training)."""

from __future__ import annotations

import ast
import gzip
import json

import numpy as np
import pytest
from pydantic import ValidationError

from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import ESCALATE_ACTION, NODE_ACTIONS, encode_action
from rl_defense.live.adversary import delegation_grants, live_app
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.scenarios import load_scenarios
from rl_defense.live.topology import load_topology
from rl_defense.research.dataset import digest, load_legacy, validate_episodes
from rl_defense.research.evaluate import ROOT, collect_episode, records_from_raw
from rl_defense.research.metrics import report, summary
from rl_defense.research.policies import CostAwareRules, capability_mask
from rl_defense.research.records import Measurement, ResearchTransition


@pytest.fixture
def scenario():
    return load_scenarios("train", subdir="train_v8")[0]


def raw_episode(sc, policy=lambda obs, mask: 0, seed=None):
    ep = {"policy": "noop", **collect_episode(sc, sc.seed_start if seed is None else seed, policy)}
    return gzip.compress((json.dumps(ep) + "\n").encode(), mtime=0)


@pytest.fixture
def rows(scenario):
    return records_from_raw(raw_episode(scenario), [scenario])


def test_measured_cost_reward_and_provenance(rows):
    for r in rows:
        assert r.threat_reward.value == -r.compromised_reads
        assert r.benign_cost.value == r.benign_blocked
        assert r.threat_reward.evidence.sha256 == r.benign_cost.evidence.sha256
        assert r.legacy_reward.value is not None
        assert r.outcome_evidence.note.startswith("raw.jsonl.gz#line/")
        assert r.behavior_probability is None


def test_legitimate_delegates_and_unauthorized_reads_remain_distinct(scenario):
    grants = delegation_grants(scenario.driver().delegates)
    controls = DefenseControls()
    with DefensiveGateway(live_app(), load_topology(), controls, grants=grants) as gw:
        own = gw.request("GET", "/payments/pay_b1", token="fixture-token-bob")
        delegate = gw.request("GET", "/payments/pay_a1", token="fixture-token-dave")
        attack = gw.request("GET", "/payments/pay_a1", token="fixture-token-bob", is_attack=True)
        assert own.cross_tenant_attempt is False
        # explicitly provision this known owned-fixture grant, independent of scenario
        if "cus_alice" not in grants.get("cus_dave", ()):
            pytest.fail("fixture scenario must include dave:alice")
        assert delegate.cross_tenant_attempt is False and delegate.compromised
        # Existing compromise flag is foreign-body read, even for authorized delegates.
        # Only attack-labelled requests enter compromised_reads; do not count delegates.
        assert attack.cross_tenant_attempt and attack.compromised
        controls.blocked_principals = {"cus_bob": ["payments"], "cus_dave": ["payments"]}
        for token, path in (
            ("fixture-token-bob", "/payments/pay_b1"),
            ("fixture-token-dave", "/payments/pay_a1"),
        ):
            rec = gw.request("GET", path, token=token)
            assert rec.blocked_reason == "principal_blocked" and not rec.is_attack


@pytest.mark.parametrize("value,reason", [(None, None), (None, ""), (0.0, "missing")])
def test_unknown_requires_reason(rows, value, reason):
    d = rows[0].benign_cost.model_dump()
    d.update(value=value, unknown_reason=reason)
    with pytest.raises(ValidationError):
        Measurement.model_validate(d)


def test_unknown_cost_propagates_without_zero_imputation(rows):
    d = rows[0].model_dump()
    d["benign_blocked"] = None
    d["benign_cost"].update(value=None, unknown_reason="missing telemetry")
    d["delegated_blocked"].update(value=None, unknown_reason="missing attribution")
    rs = [ResearchTransition.model_validate(d), *rows[1:]]
    s = summary(rs, resamples=10)
    assert s["metrics"]["mean_cumulative_cost"] is None
    assert s["metrics"]["benign_availability"] is None
    assert s["metrics"]["measured_cost_coverage"] < 1
    assert s["ci95"]["mean_cumulative_cost"] is None


def test_missing_cost_field_and_nonfinite_or_inconsistent_values_rejected(rows):
    for key, value in (
        ("benign_cost", None),
        ("compromised_reads", 999999),
        ("obs", [float("nan")] * 55),
    ):
        d = rows[0].model_dump()
        d[key] = value
        with pytest.raises(ValidationError):
            ResearchTransition.model_validate(d)


def test_capability_mask_excludes_ineffective_and_administrative_actions():
    mask = capability_mask(np.ones(25, dtype=bool))
    assert mask[0] and not mask[ESCALATE_ACTION]
    for i, node in enumerate(NODE_NAMES):
        for action in NODE_ACTIONS:
            expected = node in {"api", "payments"} and action != "request_reassessment"
            assert mask[encode_action(action, i)] == expected
    assert mask[22:].all()
    with pytest.raises(ValueError):
        capability_mask(np.ones(22, dtype=bool))


def test_cost_aware_quiet_no_findings_noop_and_budget():
    obs = np.zeros(55, dtype=np.float32)
    mask = np.ones(25, dtype=bool)
    p = CostAwareRules()
    assert p(obs, mask) == 0
    obs[3 * 9 + 4] = 0.8
    mask[22] = False
    assert p(obs, mask) == 0
    mask[22] = True
    assert [p(obs, mask) for _ in range(4)] == [22, 22, 0, 0]
    assert CostAwareRules(0)(obs, mask) == 0
    with pytest.raises(ValueError):
        CostAwareRules(-1)


def test_principal_wide_cost_is_measured_including_authorized_delegates(scenario):
    # Fixed actions have real effects even though a principal has legitimate traffic.
    data = raw_episode(scenario, lambda obs, mask: 22 if mask[22] else 0)
    rs = records_from_raw(data, [scenario])
    assert sum(r.benign_blocked for r in rs) > 0
    assert all(r.delegated_blocked.value is not None for r in rs)
    assert sum(r.compromised_reads for r in rs) < sum(r.attack_requests for r in rs)


def test_legacy_read_only_hash_split_and_first_mask(tmp_path, scenario):
    raw = json.loads(gzip.decompress(raw_episode(scenario)))
    ep = {
        "policy": "noop",
        "scenario": scenario.name,
        "seed": scenario.seed_start,
        "transitions": [s["transition"] for s in raw["steps"]],
    }
    path = tmp_path / "trajectories.jsonl.gz"
    path.write_bytes(gzip.compress(json.dumps(ep).encode()))
    sha = digest(path.read_bytes())
    rs = load_legacy(path, expected_sha256=sha, scenarios=[scenario], policy="noop")
    assert rs[0].current_mask is None and rs[1].current_mask == rs[0].next_mask
    assert all(r.delegated_blocked.value is None for r in rs)
    with pytest.raises(ValueError, match="SHA256"):
        load_legacy(path, expected_sha256="0" * 64, scenarios=[scenario], policy="noop")
    holdout = load_scenarios("holdout", subdir="holdout_v10")
    with pytest.raises(ValueError, match="holdout"):
        load_legacy(path, expected_sha256=sha, scenarios=holdout, policy="noop")
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA256"):
        load_legacy(path, expected_sha256=sha, scenarios=[scenario], policy="noop")


def test_duplicate_incomplete_and_broken_chains_rejected(rows):
    for rs in (
        rows + rows,
        rows[:-1],
        [*rows[:2], *rows[3:]],
        [rows[0].model_copy(update={"next_obs": tuple([0.0] * 55)}), *rows[1:]],
    ):
        with pytest.raises(ValueError):
            validate_episodes(rs)


def test_weighted_ratios_and_exact_discounted_cost(rows):
    s = summary(rows, gamma=0.9, resamples=10)
    m = s["metrics"]
    assert m["attack_compromise"] == sum(r.compromised_reads for r in rows) / sum(
        r.attack_requests for r in rows
    )
    assert m["expected_discounted_cost"] == sum(r.benign_blocked * 0.9**r.t for r in rows)
    assert s["ci95"]["attack_compromise"] is None  # one independent seed


def test_reproducible_episodes_splits_and_bootstrap(scenario):
    a = raw_episode(scenario)
    assert a == raw_episode(scenario)
    rs = records_from_raw(a, [scenario]) + records_from_raw(
        raw_episode(scenario, seed=scenario.seed_start + 1), [scenario]
    )
    assert summary(rs, resamples=20) == summary(rs, resamples=20)
    assert summary(rs, resamples=20)["independent_seed_clusters"] == 2
    assert scenario.config_hash() == load_scenarios("train", subdir="train_v8")[0].config_hash()
    with pytest.raises(ValueError, match="train-only"):
        collect_episode(load_scenarios("val", subdir="val_v10")[0], 20000, lambda o, m: 0)


def test_comparison_requires_same_pairs(rows):
    other = [r.model_copy(update={"policy": "other", "seed": r.seed + 1}) for r in rows]
    with pytest.raises(ValueError, match="identical"):
        report(rows + other, resamples=10)


def test_request_evidence_cannot_disagree_with_aggregates(scenario):
    raw = json.loads(gzip.decompress(raw_episode(scenario)))
    raw["steps"][0]["requests"] = []
    data = gzip.compress((json.dumps(raw) + "\n").encode())
    with pytest.raises(ValueError, match="count mismatch"):
        records_from_raw(data, [scenario])


def test_no_production_import_path_or_registry_writer():
    # Structural boundary test: customer recommendation/training modules never import
    # the research namespace. Research has no registry, agent provider or backend import.
    for root in (
        ROOT / "backend",
        ROOT / "monitoring",
        ROOT / "security-agents",
        ROOT / "rl-defense/rl_defense",
    ):
        for path in root.rglob("*.py"):
            if "research" in path.parts or "tests" in path.parts:
                continue
            assert "rl_defense.research" not in path.read_text(), path
    for path in (ROOT / "rl-defense/rl_defense/research").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("rl_defense.live.registry", "backend", "security_agents")
                )


def test_evaluation_never_modifies_existing_registry_or_checkpoint(scenario, tmp_path, monkeypatch):
    import rl_defense.live.registry as registry

    # Always present controlled champion fixture, on every OS/CI checkout.
    controlled = tmp_path / "registry.json"
    controlled.write_bytes(
        (ROOT / "rl-defense/results/duration-screen/registry_snapshot.json").read_bytes()
    )
    canonical = registry.DEFAULT_REGISTRY
    monkeypatch.setattr(registry, "DEFAULT_REGISTRY", controlled)

    def denied_write(self):
        raise AssertionError("research attempted a registry write")

    monkeypatch.setattr(registry.Registry, "save", denied_write)
    checkpoint = ROOT / "rl-defense/results/live-retrain-v6/candidate_online.pt"
    paths = [checkpoint, controlled, canonical]

    def snapshot(p):
        return p.read_bytes() if p.exists() else None

    before = {p: snapshot(p) for p in paths}
    collect_episode(scenario, scenario.seed_start, CostAwareRules())
    assert all(snapshot(p) == raw for p, raw in before.items())


def test_seed_clusters_cannot_inflate_confidence_by_repeating_scenarios(rows):
    other = [r.model_copy(update={"scenario": "other"}) for r in rows]
    s = summary(rows + other, resamples=10)
    assert s["episodes"] == 2 and s["independent_seed_clusters"] == 1
    assert s["ci95"]["mean_cumulative_cost"] is None


def test_evidence_bundle_verifier_rejects_rehashed_summary_and_overlap(
    tmp_path, scenario, monkeypatch
):
    import rl_defense.research.evaluate as ev

    # Owned lab baseline smoke, five fixed policies, two small episodes; no training.
    sc = scenario.model_copy(update={"horizon": 5, "episodes": 2})
    monkeypatch.setattr(ev, "load_scenarios", lambda *a, **k: [sc])
    original = ev.subprocess.check_output

    def source_read(cmd, **kwargs):
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return ""
        return original(cmd, **kwargs)

    monkeypatch.setattr(ev.subprocess, "check_output", source_read)
    result = ev.run(tmp_path / "result", episodes=2)
    assert result["verified"] and result["episodes"] == 10 and result["transitions"] == 50
    root = tmp_path / "result"
    path = root / "summary.json"
    data = json.loads(path.read_text())
    data["noop"]["pooled"]["metrics"]["mean_threat_reward"] += 1
    path.write_bytes(ev.encoded(data))
    index = json.loads((root / "EVIDENCE.json").read_text())
    index["files"]["summary.json"] = digest(path.read_bytes())
    (root / "EVIDENCE.json").write_bytes(ev.encoded(index))
    with pytest.raises(ValueError, match="summary differs"):
        ev.verify(root)
    with pytest.raises(FileExistsError):
        ev.run(root, episodes=2)


def test_source_fingerprint_allowlist_is_exact_and_does_not_skip_manifest():
    import re
    import tomllib

    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    rule = next(
        a
        for a in config["allowlists"]
        if a["description"].startswith("Verified constrained-Phase1")
    )
    assert rule["condition"] == "AND" and rule["regexTarget"] == "line"
    assert rule["paths"] == [r"^rl-defense/results/constrained-phase1/config\.json$"]
    manifest = json.loads((ROOT / "rl-defense/results/constrained-phase1/config.json").read_text())
    paths = (
        "rl-defense/rl_defense/api.py",
        "shared/shared/api.py",
        "standards/standards/owasp_api.py",
    )
    assert len(rule["regexes"]) == len(paths)
    for rel in paths:
        # The allowlist belongs to the historical manifest, not future product code.
        sha = manifest["code_sha256"][rel]
        assert any(re.fullmatch(pattern, f'    "{rel}": "{sha}",') for pattern in rule["regexes"])
        assert not any(
            re.fullmatch(pattern, f'    "api_key": "{sha}",') for pattern in rule["regexes"]
        )
        assert not any(
            re.fullmatch(pattern, f'    "{rel}": "{"a" * 64}",') for pattern in rule["regexes"]
        )


def test_published_revision_must_resolve_to_its_actual_tree(tmp_path):
    import subprocess

    from rl_defense.research.proof import resolve_source

    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert resolve_source(ROOT, head, tree).startswith(f"tree {tree}\n".encode())
    with pytest.raises(ValueError, match="unavailable"):
        resolve_source(ROOT, "0" * 40, tree)
    with pytest.raises(ValueError, match="does not own"):
        resolve_source(ROOT, head, "0" * 40)
    with pytest.raises(ValueError, match="full Git commit"):
        resolve_source(ROOT, "HEAD", tree)


def test_wrong_baseline_label_is_rejected_without_new_traffic(rows):
    from rl_defense.research.proof import verify_policy_actions

    config = json.loads((ROOT / "rl-defense/results/constrained-phase1/config.json").read_text())
    # Noop trajectory falsely attributed to v6. Metrics/labels alone can look valid.
    wrong = [r.model_copy(update={"policy": "v6_shielded"}) for r in rows]
    with pytest.raises(ValueError, match="differs from claimed policy"):
        verify_policy_actions(ROOT, config, wrong)


@pytest.mark.parametrize("which", ["index", "config"])
def test_unknown_manifest_schema_is_rejected_before_semantic_loading(tmp_path, which):
    import rl_defense.research.evaluate as ev

    # Only tiny manifests needed: unknown version must stop before source/model/metrics.
    config = {"schema": "constrained-lab-evaluation/999"}
    index = {"schema": "constrained-lab-evidence/999", "files": {}}
    if which == "config":
        index["schema"] = "constrained-lab-evidence/1"
        for name in ("config.json", "raw.jsonl.gz", "transitions.jsonl.gz", "summary.json"):
            data = ev.encoded(config) if name == "config.json" else b""
            (tmp_path / name).write_bytes(data)
            index["files"][name] = digest(data)
    (tmp_path / "EVIDENCE.json").write_bytes(ev.encoded(index))
    with pytest.raises(ValueError, match="unsupported .* schema"):
        ev.verify(tmp_path)


def test_saved_original_source_and_commit_proof_are_immutable():
    from rl_defense.research.proof import HISTORICAL_EVALUATOR, verify_commit

    root = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((root / "config.json").read_text())
    raw = (root / "frozen/source.commit.txt").read_bytes()
    verify_commit(raw, config["source_commit"], config["source_tree"])
    with pytest.raises(ValueError, match="proof mismatch"):
        verify_commit(raw + b"tamper", config["source_commit"], config["source_tree"])
    assert digest((root / "frozen/evaluate.py.txt").read_bytes()) == HISTORICAL_EVALUATOR


def test_historical_exception_refuses_unrecorded_future_verifier_changes(monkeypatch):
    from pathlib import Path

    from rl_defense.research.proof import check_source

    root = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((root / "config.json").read_text())
    index = json.loads((root / "EVIDENCE.json").read_text())
    changed = ROOT / "rl-defense/rl_defense/research/proof.py"
    original = Path.read_bytes
    monkeypatch.setattr(
        Path, "read_bytes", lambda p: b"future changed verifier" if p == changed else original(p)
    )
    with pytest.raises(ValueError, match="post-review source changed"):
        check_source(ROOT, root, config, set(index["files"]))


@pytest.mark.parametrize("n", [True, 1, 9, 2.0, 8])
def test_declared_seed_count_cannot_be_truncated(n):
    from rl_defense.research.proof import validate_seed_selection

    scenarios = load_scenarios("train", subdir="train_v8")
    scenarios = [scenarios[0].model_copy(update={"episodes": 4})]
    with pytest.raises(ValueError, match="episode count"):
        validate_seed_selection({"episodes_per_scenario": n, "episode_seeds": {}}, scenarios)


def test_historical_source_map_cannot_drop_pins():
    from rl_defense.research.proof import check_source

    output = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((output / "config.json").read_text())
    config["code_sha256"] = {}
    with pytest.raises(ValueError, match="source manifest"):
        check_source(ROOT, output, config, set())


def test_raw_request_cannot_claim_blocked_compromise():
    from rl_defense.research.proof import validate_raw_requests

    output = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((output / "config.json").read_text())
    from rl_defense.live.scenarios import LiveScenario

    scenarios = [LiveScenario.model_validate(d) for d in config["scenario_configs"]]
    ep = json.loads(gzip.decompress((output / "raw.jsonl.gz").read_bytes()).splitlines()[0])
    q = ep["steps"][0]["requests"][0]
    q.update(blocked_reason="principal_blocked", status=403, compromised=True)
    with pytest.raises(ValueError, match="contradictory"):
        validate_raw_requests(gzip.compress(json.dumps(ep).encode()), scenarios)


def test_policy_loader_uses_the_hashed_checkpoint_bytes(monkeypatch):
    import rl_defense.research.proof as proof

    output = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((output / "config.json").read_text())
    captured = []

    def loader(path, *, blob):
        captured.append(blob)
        return object(), {}

    monkeypatch.setattr(proof, "load_checkpoint", loader)
    proof.verify_policy_actions(ROOT, config, [])
    assert digest(captured[0]) == config["v6_checkpoint_sha256"]


@pytest.mark.parametrize(
    "field,value", [("resamples", 10**12), ("gamma", 0.5), ("bootstrap_seed", 99)]
)
def test_verifier_rejects_altered_statistical_profile(tmp_path, field, value):
    import rl_defense.research.evaluate as ev

    output = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((output / "config.json").read_text())
    config[field] = value
    raw = ev.encoded(config)
    (tmp_path / "config.json").write_bytes(raw)
    files = {"config.json": digest(raw)}
    for name in ("raw.jsonl.gz", "transitions.jsonl.gz", "summary.json"):
        (tmp_path / name).write_bytes(b"")
        files[name] = digest(b"")
    (tmp_path / "EVIDENCE.json").write_bytes(
        ev.encoded(
            {
                "schema": "constrained-lab-evidence/1",
                "files": files,
                "not_a_promotion_decision": True,
                "phase2_started": False,
            }
        )
    )
    with pytest.raises(ValueError, match="profile semantics"):
        ev.verify(tmp_path)


def test_setup_failure_is_recorded_without_retry(tmp_path, monkeypatch):
    import rl_defense.research.evaluate as ev

    original = ev.subprocess.check_output

    def command(args, **kw):
        if args[:3] == ["git", "status", "--porcelain"]:
            return ""
        return original(args, **kw)

    monkeypatch.setattr(ev.subprocess, "check_output", command)
    monkeypatch.setattr(
        ev, "load_checkpoint", lambda *a, **kw: (_ for _ in ()).throw(ValueError("setup failure"))
    )
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="setup failure"):
        ev.run(output, 2)
    assert json.loads((output / "FAILURE.json").read_text()) == {
        "error": "setup failure",
        "automatic_retry": False,
    }


def test_verifier_rejects_self_declared_scenario_changes(tmp_path):
    import shutil

    import rl_defense.research.evaluate as ev

    output = ROOT / "rl-defense/results/constrained-phase1"
    shutil.copytree(output, tmp_path / "bundle")
    bundle = tmp_path / "bundle"
    config = json.loads((bundle / "config.json").read_text())
    config["scenario_configs"][0]["attack_per_step"] += 1
    data = ev.encoded(config)
    (bundle / "config.json").write_bytes(data)
    index = json.loads((bundle / "EVIDENCE.json").read_text())
    index["files"]["config.json"] = digest(data)
    (bundle / "EVIDENCE.json").write_bytes(ev.encoded(index))
    with pytest.raises(ValueError, match="pinned train_v8"):
        ev.verify(bundle)


@pytest.mark.parametrize(
    "key,value", [("not_a_promotion_decision", False), ("phase2_started", True)]
)
def test_phase_boundary_cannot_be_relabelled(tmp_path, key, value):
    import shutil

    import rl_defense.research.evaluate as ev

    output = ROOT / "rl-defense/results/constrained-phase1"
    shutil.copytree(output, tmp_path / "bundle")
    bundle = tmp_path / "bundle"
    index = json.loads((bundle / "EVIDENCE.json").read_text())
    index[key] = value
    (bundle / "EVIDENCE.json").write_bytes(ev.encoded(index))
    with pytest.raises(ValueError, match="Phase 1 boundary"):
        ev.verify(bundle)


def test_successful_foreign_read_cannot_omit_compromise():
    from rl_defense.live.scenarios import LiveScenario
    from rl_defense.research.proof import validate_raw_requests

    output = ROOT / "rl-defense/results/constrained-phase1"
    config = json.loads((output / "config.json").read_text())
    scenarios = [LiveScenario.model_validate(d) for d in config["scenario_configs"]]
    episodes = [
        json.loads(line)
        for line in gzip.decompress((output / "raw.jsonl.gz").read_bytes()).splitlines()
    ]
    ep = next(
        ep
        for ep in episodes
        if any(q["compromised"] for step in ep["steps"] for q in step["requests"])
    )
    q = next(q for step in ep["steps"] for q in step["requests"] if q["compromised"])
    q["compromised"] = False
    with pytest.raises(ValueError, match="contradictory"):
        validate_raw_requests(gzip.compress(json.dumps(ep).encode()), scenarios)


def test_rehashed_source_cannot_claim_an_unrelated_commit(tmp_path):
    import subprocess

    from rl_defense.research.proof import check_source

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    p = root / "rl-defense/rl_defense/metric.py"
    p.parent.mkdir(parents=True)
    p.write_text("original = True\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    (tmp_path / "source.commit.txt").write_bytes(
        subprocess.check_output(["git", "cat-file", "commit", revision], cwd=root)
    )
    p.write_text("original = False\n")
    config = {
        "source_commit": revision,
        "source_tree": tree,
        "code_sha256": {str(p.relative_to(root)): digest(p.read_bytes())},
    }
    with pytest.raises(ValueError, match="does not belong"):
        check_source(root, tmp_path, config, {"source.commit.txt"})
