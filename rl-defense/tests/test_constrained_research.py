"""Phase 1 research boundary, measurement and reproducibility tests (no training)."""

from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

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


def test_evaluation_never_modifies_existing_registry_or_checkpoint(scenario):
    checkpoint = ROOT / "rl-defense/results/live-retrain-v6/candidate_online.pt"
    registry = Path(
        "/Users/alanmozhoor/Documents/hackatl-agentic-security/.claude/worktrees/mystifying-hofstadter-c5aaf7/rl-defense/runs/live/registry.json"
    )
    paths = [checkpoint, *([registry] if registry.exists() else [])]
    before = {p: p.read_bytes() for p in paths}
    collect_episode(scenario, scenario.seed_start, CostAwareRules())
    assert all(p.read_bytes() == raw for p, raw in before.items())


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
