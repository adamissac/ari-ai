"""Live experience → offline candidate → held-out gate → human-approved registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pytest
from payments_lite.app import create_app

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live.experience import collect, load_dataset
from rl_defense.live.gateway import RequestRecord
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.registry import Registry, RegistryError
from rl_defense.live.retrain import retrain
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario, load_scenarios
from rl_defense.live.telemetry import _anomalous
from rl_defense.train import train


@pytest.fixture(scope="module")
def base_ckpt(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("base")
    train(
        load_configs(default_config_paths("train")), seed=0, steps=3000, run_dir=d, log_every=3000
    )
    return d / "ddqn_seed0.pt"


def _tiny(split: str, name: str = "tiny", **kw) -> LiveScenario:
    lo, _ = SEED_BANDS[split]
    base = dict(
        name=name,
        split=split,
        horizon=8,
        schedule="bursty",
        p_start=0.4,
        p_stop=0.3,
        attack_per_step=4,
        benign_per_step=4,
        seed_start=lo,
        episodes=2,
    )
    base.update(kw)
    return LiveScenario(**base)


# ------------------------------------------------------------------ semantics fixes
def test_transitions_chain_and_record_the_observation_acted_on():
    """s_{t+1} recorded in step t must be exactly the s_t recorded in step t+1."""
    seen: list[np.ndarray] = []

    def spy(obs, mask):
        seen.append(obs.copy())
        return 0

    loop = LiveDefenseLoop(create_app, config=LoopConfig(horizon=6), driver=_tiny("train").driver())
    try:
        ts = loop.run_episode(seed=3, policy=spy)
    finally:
        loop.close()
    for i, t in enumerate(ts):
        assert np.allclose(t.obs, seen[i]), "stored obs differs from what the policy saw"
    for a, b in zip(ts, ts[1:], strict=False):
        assert a.next_obs == b.obs


def test_telemetry_never_reads_the_generator_label():
    lbl_only = RequestRecord(
        "payments", "GET", "/payments", "cus_bob", True, 200, None, False, False
    )
    assert not _anomalous(lbl_only)  # label alone is not evidence
    blocked_benign = RequestRecord(
        "payments", "GET", "/payments", "cus_a", False, 503, "isolated", False, False
    )
    assert not _anomalous(blocked_benign)  # our own blocking is not evidence
    blocked_cross = RequestRecord(
        "payments", "GET", "/payments/pay_a1", "cus_bob", False, 503, "isolated", False, True
    )
    assert _anomalous(blocked_cross)  # instrumentation saw a cross-tenant attempt


def test_bursty_traffic_is_paired_across_policies():
    sc = _tiny("train", episodes=1, horizon=10)
    a = ev.run_policy(ev.noop_policy, [sc], create_app)
    b = ev.run_policy(ev.always_isolate_payments, [sc], create_app)
    assert a[0].attack_requests == b[0].attack_requests
    assert a[0].benign_requests == b[0].benign_requests
    assert a[0].steps_no_attack == b[0].steps_no_attack
    assert b[0].compromised == 0  # blanket isolation really blocks every attack
    if a[0].attack_requests:
        assert a[0].compromised > 0


# ------------------------------------------------------------------ splits
def test_shipped_scenarios_use_disjoint_seed_bands():
    seeds = {
        sp: {x for s in load_scenarios(sp) for x in s.seeds()} for sp in ("train", "val", "holdout")
    }
    assert not seeds["train"] & seeds["val"]
    assert not seeds["train"] & seeds["holdout"]
    assert not seeds["val"] & seeds["holdout"]
    names = {sp: {s.name for s in load_scenarios(sp)} for sp in ("train", "val", "holdout")}
    assert not names["train"] & names["holdout"]


def test_scenario_seeds_must_be_in_their_split_band():
    with pytest.raises(ValueError):
        LiveScenario(
            name="x",
            split="holdout",
            schedule="always",
            attack_per_step=1,
            benign_per_step=1,
            seed_start=0,
            episodes=1,
        )


# ------------------------------------------------------------------ dataset
def test_experience_is_train_only_and_hash_pinned(tmp_path):
    with pytest.raises(ValueError):
        collect([_tiny("holdout")], tmp_path / "x.jsonl", create_app)
    m = collect([_tiny("train")], tmp_path / "d.jsonl", create_app, seed=1)
    recs, m2 = load_dataset(tmp_path / "d.jsonl")
    assert m2["dataset_id"] == m["dataset_id"] and len(recs) == m["transitions"] == 16
    assert {r["split"] for r in recs} == {"train"}
    p = tmp_path / "d.jsonl"
    p.write_text(p.read_text().replace('"reward": -', '"reward": -9', 1))  # tamper
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset(p)


# ------------------------------------------------------------------ retrain
def test_retrain_selects_on_val_only_and_records_lineage(base_ckpt, tmp_path):
    collect([_tiny("train")], tmp_path / "d.jsonl", create_app, seed=1)
    with pytest.raises(ValueError, match="validation"):
        retrain(
            base_ckpt,
            [tmp_path / "d.jsonl"],
            tmp_path,
            create_app,
            val_scenarios=[_tiny("holdout")],
            updates=10,
            eval_every=5,
        )
    m = retrain(
        base_ckpt,
        [tmp_path / "d.jsonl"],
        tmp_path,
        create_app,
        val_scenarios=[_tiny("val")],
        updates=60,
        eval_every=30,
        val_episodes=1,
    )
    assert (tmp_path / "candidate.pt").exists()
    assert m["lineage"]["transitions"] == 16
    assert m["retrain"]["selected_update"] in (30, 60)
    assert m["retrain"]["selection_history"][0]["role"] == "base"
    assert (
        m["checkpoint_sha256"]
        != json.loads(base_ckpt.with_suffix(".manifest.json").read_text())["checkpoint_sha256"]
    )


# ------------------------------------------------------------------ gate
def test_gate_rejects_blanket_isolation_as_reward_hacking():
    sc = [_tiny("holdout", episodes=2, horizon=12, p_start=0.2, p_stop=0.4)]
    iso = ev.run_policy(ev.always_isolate_payments, sc, create_app)
    noop = ev.run_policy(ev.noop_policy, sc, create_app)
    v = ev.promotion_decision(
        candidate=iso, deployed=noop, rules=None, criteria=ev.PromotionCriteria()
    )
    failed = {c["name"] for c in v["checks"] if not c["passed"]}
    assert v["decision"] == "reject"
    assert {"availability_floor", "reward_hacking_no_blanket_isolation"} <= failed


def test_gate_passes_a_strictly_better_candidate():
    # fields: scenario, seed, reward, steps, attack_requests, compromised, benign_requests,
    # benign_blocked, benign_requests_no_attack, benign_blocked_no_attack, steps_no_attack,
    # disruptive_steps_no_attack, nonnoop_actions
    cand = [
        ev.EpisodeMetrics("s", i, -1.0 - 0.01 * i, 10, 10, 1, 20, 1, 5, 0, 5, 0, 1)
        for i in range(10)
    ]
    dep = [ev.EpisodeMetrics("s", i, -5.0, 10, 10, 10, 20, 0, 5, 0, 5, 0, 0) for i in range(10)]
    v = ev.promotion_decision(
        candidate=cand, deployed=dep, rules=None, criteria=ev.PromotionCriteria()
    )
    assert v["decision"] == "recommend_promote", v["checks"]
    assert v["requires_human_approval"] is True


# ------------------------------------------------------------------ registry
def _report(path: Path, sha: str, decision: str, baseline: str = "") -> Path:
    path.write_text(
        json.dumps(
            {
                "decision": decision,
                "candidate": {"checkpoint_sha256": sha},
                "deployed": {"checkpoint_sha256": baseline},
                "checks": [{"name": "x", "passed": decision == "recommend_promote"}],
            }
        )
    )
    return path


def test_registry_requires_human_passing_report_and_supports_rollback(base_ckpt, tmp_path):
    from rl_defense.checkpoint import sha256_file

    reg = Registry(tmp_path / "registry.json")
    with pytest.raises(RegistryError, match="human"):
        reg.init(base_ckpt, approved_by="agent_patch")
    v0 = reg.init(base_ckpt, approved_by="usr_alan")
    assert reg.deployed_checkpoint() == base_ckpt.resolve()

    cand = tmp_path / "cand.pt"
    cand.write_bytes(base_ckpt.read_bytes() + b"\0")  # distinct bytes
    sha = sha256_file(cand)
    v_rej = reg.register(cand, _report(tmp_path / "rej.json", sha, "reject"))
    with pytest.raises(RegistryError, match="decision"):
        reg.promote(v_rej, approved_by="usr_alan", reason="try")

    other = tmp_path / "cand2.pt"
    other.write_bytes(base_ckpt.read_bytes() + b"\1")
    v_mis = reg.register(other, _report(tmp_path / "mis.json", sha, "recommend_promote"))
    with pytest.raises(RegistryError, match="different checkpoint"):
        reg.promote(v_mis, approved_by="usr_alan", reason="try")

    v_ok = reg.register(
        cand, _report(tmp_path / "ok.json", sha, "recommend_promote", sha256_file(base_ckpt))
    )
    assert v_ok == v_rej  # same bytes → same version; the re-evaluation's report is attached
    with pytest.raises(RegistryError, match="human"):
        reg.promote(v_ok, approved_by="claude", reason="auto")
    reg.promote(v_ok, approved_by="usr_alan", reason="passed gate")
    assert reg.data["deployed"] == v_ok
    cand.write_bytes(b"swapped")
    with pytest.raises(RegistryError, match="no longer matches"):
        reg.deployed_checkpoint()
    assert reg.rollback(approved_by="usr_alan", reason="regression") == v0
    with pytest.raises(RegistryError, match="nothing to roll back"):
        reg.rollback(approved_by="usr_alan", reason="again")


# ------------------------------------------------------------------ pipeline smoke
def test_pipeline_end_to_end_smoke(base_ckpt, tmp_path, monkeypatch):
    from rl_defense.live import pipeline

    monkeypatch.setattr(
        ev,
        "RULES_GRID",
        {"isolate_anomaly": (0.3,), "rate_limit_alerts": (1.1,), "monitor_anomaly": (1.1,)},
    )
    args = argparse.Namespace(
        base_checkpoint=str(base_ckpt),
        base_steps=0,
        rounds=1,
        epsilons="0.5",
        updates=40,
        eval_every=20,
        val_episodes=1,
        train_episodes=1,
        holdout_episodes=1,
        rules_episodes=1,
        criteria=str(Path(pipeline.CONFIG_DIR) / "promotion.yaml"),
        seed=0,
        out=str(tmp_path / "run"),
        evidence_dir=str(tmp_path / "evidence"),
    )
    r = pipeline.run(args)
    assert r["decision"] in ("recommend_promote", "reject")
    assert r["requires_human_approval"] is True
    assert set(r["policies"]) == {
        "deployed",
        "candidate",
        "threshold_rules",
        "noop",
        "always_isolate_payments",
    }
    assert set(r["by_scenario"]["candidate"]) == set(r["splits"]["holdout"])
    ev_dir = tmp_path / "evidence"
    for f in [
        "promotion_report.json",
        "REPORT.md",
        "candidate.manifest.json",
        "experience_round1.manifest.json",
    ]:
        assert (ev_dir / f).exists()


def test_registry_report_integrity_and_incumbent_binding(base_ckpt, tmp_path):
    from rl_defense.checkpoint import sha256_file

    reg = Registry(tmp_path / "registry.json")
    baseline = reg.init(base_ckpt, "usr_test")
    cand = tmp_path / "candidate.pt"
    cand.write_bytes(base_ckpt.read_bytes() + b"candidate")
    report = _report(
        tmp_path / "report.json", sha256_file(cand), "recommend_promote", sha256_file(base_ckpt)
    )
    vid = reg.register(cand, report)
    reg.save()
    reg = Registry(reg.path)
    before = json.loads(json.dumps(reg.data))
    payload = json.loads(report.read_text())
    payload["decision"] = "reject"
    report.write_text(json.dumps(payload))
    with pytest.raises(RegistryError, match="report changed"):
        reg.promote(vid, "usr_test", "edited report")
    assert reg.data == before
    payload["decision"] = "recommend_promote"
    payload["deployed"]["checkpoint_sha256"] = "0" * 64
    report.write_text(json.dumps(payload))
    reg.register(cand, report)
    with pytest.raises(RegistryError, match="report baseline differs"):
        reg.promote(vid, "usr_test", "stale report")
    assert reg.data["deployed"] == baseline
    assert reg.data["stack"] == [baseline]
    payload["deployed"]["checkpoint_sha256"] = sha256_file(base_ckpt)
    report.write_text(json.dumps(payload))
    reg.register(cand, report)
    reg.promote(vid, "usr_test", "matching baseline")
    other = tmp_path / "other.pt"
    other.write_bytes(base_ckpt.read_bytes() + b"other")
    old_report = _report(
        tmp_path / "old.json", sha256_file(other), "recommend_promote", sha256_file(base_ckpt)
    )
    other_id = reg.register(other, old_report)
    with pytest.raises(RegistryError, match="report baseline differs"):
        reg.promote(other_id, "usr_test", "previous incumbent")
    assert reg.data["deployed"] == vid


def test_registry_rejects_missing_or_failed_checks(base_ckpt, tmp_path):
    from rl_defense.checkpoint import sha256_file

    reg = Registry(tmp_path / "registry.json")
    reg.init(base_ckpt, "usr_test")
    cand = tmp_path / "candidate.pt"
    cand.write_bytes(base_ckpt.read_bytes() + b"candidate")
    report = _report(
        tmp_path / "report.json", sha256_file(cand), "recommend_promote", sha256_file(base_ckpt)
    )
    payload = json.loads(report.read_text())
    for checks in (None, [], [{"passed": False}], [{"passed": "true"}]):
        payload["checks"] = checks
        report.write_text(json.dumps(payload))
        vid = reg.register(cand, report)
        with pytest.raises(RegistryError, match="nonempty passing checks"):
            reg.promote(vid, "usr_test", "inconsistent decision")
