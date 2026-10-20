"""The v8 evidence (results/live-retrain-v8/): hash-pinned, restorable, the gate's verdict
as recorded, and the v8 candidate's platform-vs-lab agreement on train windows.

Never runs a policy on holdout_v8 and never touches a real registry.
"""

from __future__ import annotations

import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.inference import PolicyRunner
from rl_defense.live import evidence, platform_check
from rl_defense.live.scenarios import load_scenarios

V8 = Path(__file__).resolve().parents[1] / "results" / "live-retrain-v8"
CK = "results/live-retrain-v8/candidate_online.pt"


def _report() -> dict:
    return json.loads((V8 / "promotion_report.json").read_text())


def test_index_report_and_checkpoint_pin_the_same_bytes():
    idx = evidence.load_index(V8)["artifacts"]
    report = _report()
    manifest = json.loads((V8 / "candidate.manifest.json").read_text())
    assert idx["checkpoint"]["sha256"] == manifest["checkpoint_sha256"]
    assert idx["checkpoint"]["sha256"] == report["candidate"]["checkpoint_sha256"]
    assert idx["selected_experience"]["sha256"] == manifest["lineage"]["experience_sha256"]
    assert idx["experiment"]["sha256"] == manifest["online"]["experiment"]["experience_sha256"]
    # 4,200 demonstrations (20 x 7 train_v8 scenarios x 30 steps) + 105,000 online
    assert idx["selected_experience"]["lines"] == manifest["lineage"]["transitions"] == 109_200
    assert manifest["lineage"]["demo_transitions"] == 4_200
    assert report["artifacts"]["experience"]["sha256"] == idx["selected_experience"]["sha256"]
    assert report["artifacts"]["experiment"]["sha256"] == idx["experiment"]["sha256"]
    assert (V8 / "candidate_online.manifest.json").read_bytes() == (
        V8 / "candidate.manifest.json"
    ).read_bytes()


def test_committed_evidence_verifies_by_streaming():
    assert set(evidence.verify(V8)) == {"checkpoint", "experiment", "selected_experience"}


def test_report_records_the_pre_registered_run_and_the_gate_verdict():
    r = _report()
    assert r["git_sha"].startswith("15e25f9")  # the pushed pre-registration commit
    assert r["decision"] == "recommend_promote" and r["requires_human_approval"] is True
    assert all(c["passed"] for c in r["checks"]) and len(r["checks"]) == 7
    assert r["loop_overrides"]["finding_severity_context"] == "platform"
    assert r["train_dir"] == "configs/live/train_v8"
    assert r["holdout_dir"] == "configs/live/holdout_v8"
    assert set(r["splits"]["train"]) == {s.name for s in load_scenarios("train", subdir="train_v8")}
    refs = {x["name"]: x for x in r["references"]}
    assert refs["v6"]["checkpoint_sha256"].startswith("8113a37f")
    assert refs["v7"]["checkpoint_sha256"].startswith("d1c0c9b5")


def test_references_are_reported_honestly():
    """v8 ties v6 and is worse than v7 on holdout_v8 (paired 95% CIs), as PROVENANCE.md says."""
    refs = {x["name"]: x["candidate_vs_paired"] for x in _report()["references"]}
    lo, hi = refs["v6"]["ci95"]
    assert lo < 0 < hi
    assert refs["v7"]["ci95"][1] < 0
    by = _report()["by_scenario"]
    for sc in ("rare_bookkeeper_raids", "faint_outsider_campaigns"):  # the hypothesis' half
        assert by["candidate"][sc]["reward"] >= by["deployed"][sc]["reward"]
        assert by["candidate"][sc]["reward"] < by["v7"][sc]["reward"]  # ... that fails


def test_v8_checkpoint_loads_and_serves():
    agent, m = load_checkpoint(V8 / "candidate_online.pt")
    assert m["env_id"] == "LiveDefense-payments-lite-v3" and m["steps"] == 105_000
    assert agent.config.noop_margin == m["online"]["selected_noop_margin"] == 0.0
    assert PolicyRunner(V8 / "candidate_online.pt").policy_version.endswith("@ec8b5042fd56")


def test_v8_platform_recommendations_agree_with_its_lab_recommendations():
    """On platform-style facts (platform_mapping with real finding severities, plus the
    reporter's RouteDetection counters) the v8 candidate recommends exactly what it
    recommends on the lab's own facts, on quiet and on flagged train_v8 windows. It keeps
    v7's behaviour: noop when nothing is flagged, a principal block when someone is. The
    result reproduces the committed platform_agreement.json."""
    agent, _ = load_checkpoint(V8 / "candidate_online.pt")
    got = platform_check.compare(agent, load_scenarios("train", subdir="train_v8"))
    committed = json.loads((V8 / "platform_agreement.json").read_text())["checkpoints"][CK]
    assert {k: v for k, v in committed.items() if k != "checkpoint_sha256"} == json.loads(
        json.dumps(got)
    )
    assert got["agree"] == got["windows"] == 280  # 100% agreement, as measured
    for case in ("no_findings", "bola_high"):
        c = got["cases"][case]
        assert c["quiet"]["agreement"] == c["flagged"]["agreement"] == 1.0
        assert c["quiet"]["windows"] == 89 and c["flagged"]["windows"] == 51
        assert c["quiet"]["platform_actions"] == {"noop": 89}
        assert c["flagged"]["platform_actions"] == {"block_principal": 51}


def test_v7_and_v6_on_the_same_train_v8_windows():
    ck = json.loads((V8 / "platform_agreement.json").read_text())["checkpoints"]
    v7 = ck["results/live-retrain-v7/candidate_online.pt"]
    v6 = ck["results/live-retrain-v6/candidate_online.pt"]
    assert v7["agreement"] == v6["agreement"] == 1.0
    assert v7["cases"]["no_findings"]["quiet"]["platform_actions"] == {"noop": 89}
    assert v6["cases"]["bola_high"]["quiet"]["platform_actions"] == {"escalate_to_human": 89}
    assert "noop" not in v6["cases"]["no_findings"]["quiet"]["platform_actions"]


def test_post_run_train_check_shows_v8_still_trails_noop_on_rare_delegate_runs():
    post = json.loads((V8 / "post_run_train_check.json").read_text())
    pre = json.loads((V8 / "pre_run_evidence.json").read_text())["train_v8"]
    assert post["checkpoint_sha256"] == _report()["candidate"]["checkpoint_sha256"]
    sc = "rare_delegate_runs"
    assert post["train_v8"][sc]["reward"] < pre["noop"][sc]["reward"]
    assert post["train_v8"][sc]["reward"] < pre["v7"][sc]["reward"]
