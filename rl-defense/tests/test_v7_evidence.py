"""The v7 evidence (results/live-retrain-v7/): hash-pinned, restorable, and the v7
candidate's platform-vs-lab agreement on train windows.

Never runs a policy on holdout_v7 and never touches a real registry.
"""

from __future__ import annotations

import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.inference import PolicyRunner
from rl_defense.live import evidence, platform_check
from rl_defense.live.scenarios import load_scenarios

V7 = Path(__file__).resolve().parents[1] / "results" / "live-retrain-v7"
CK = "results/live-retrain-v7/candidate_online.pt"


def test_index_report_and_checkpoint_pin_the_same_bytes():
    idx = evidence.load_index(V7)["artifacts"]
    report = json.loads((V7 / "promotion_report.json").read_text())
    manifest = json.loads((V7 / "candidate.manifest.json").read_text())
    assert idx["checkpoint"]["sha256"] == manifest["checkpoint_sha256"]
    assert idx["checkpoint"]["sha256"] == report["candidate"]["checkpoint_sha256"]
    # v7 pins the selected snapshot's prefix in the lineage, the complete log separately
    assert idx["selected_experience"]["sha256"] == manifest["lineage"]["experience_sha256"]
    assert idx["experiment"]["sha256"] == manifest["online"]["experiment"]["experience_sha256"]
    assert idx["selected_experience"]["lines"] == manifest["lineage"]["transitions"] == 48_000
    assert report["artifacts"]["experience"]["sha256"] == idx["selected_experience"]["sha256"]
    assert report["artifacts"]["experiment"]["sha256"] == idx["experiment"]["sha256"]
    assert (V7 / "candidate_online.manifest.json").read_bytes() == (
        V7 / "candidate.manifest.json"
    ).read_bytes()


def test_committed_evidence_verifies_by_streaming():
    assert set(evidence.verify(V7)) == {"checkpoint", "experiment", "selected_experience"}


def test_report_records_the_platform_context_and_the_reject():
    r = json.loads((V7 / "promotion_report.json").read_text())
    assert r["decision"] == "reject"
    assert r["loop_overrides"]["finding_severity_context"] == "platform"
    assert r["reference"]["checkpoint_sha256"].startswith("8113a37f")
    failed = [c["name"] for c in r["checks"] if not c["passed"]]
    assert failed == ["no_per_scenario_regression"]


def test_v7_checkpoint_loads_and_serves():
    agent, m = load_checkpoint(V7 / "candidate_online.pt")
    assert m["env_id"] == "LiveDefense-payments-lite-v3" and m["steps"] == 45_000
    assert agent.config.noop_margin == m["online"]["selected_noop_margin"] == 0.2
    assert PolicyRunner(V7 / "candidate_online.pt").policy_version.endswith("@d1c0c9b506fd")


def test_v7_platform_recommendations_agree_with_its_lab_recommendations():
    """On platform-style facts (platform_mapping with real finding severities, plus the
    reporter's RouteDetection counters) the v7 candidate recommends exactly what it
    recommends on the lab's own facts, on quiet and on flagged train windows. The result
    reproduces the committed platform_agreement.json."""
    agent, _ = load_checkpoint(V7 / "candidate_online.pt")
    got = platform_check.compare(agent, load_scenarios("train", subdir="train_v3"))
    committed = json.loads((V7 / "platform_agreement.json").read_text())["checkpoints"][CK]
    assert {k: v for k, v in committed.items() if k != "checkpoint_sha256"} == json.loads(
        json.dumps(got)
    )
    assert got["agree"] == got["windows"] == 200  # 100% agreement, as measured
    for case in ("no_findings", "bola_high"):
        c = got["cases"][case]
        assert c["quiet"]["agreement"] == c["flagged"]["agreement"] == 1.0
        assert c["quiet"]["windows"] == 53 and c["flagged"]["windows"] == 47
        # the gap ADR-0017 recorded is closed on these windows: quiet -> noop,
        # flagged -> a principal block, with or without the BOLA finding on record
        assert c["quiet"]["platform_actions"] == {"noop": 53}
        assert c["flagged"]["platform_actions"] == {"block_principal": 47}
    assert got["cases"]["bola_high"]["finding_severity"]["payments"] == 0.75
    assert set(got["cases"]["no_findings"]["finding_severity"].values()) == {0.0}


def test_v6_reference_shows_the_gap_v7_was_trained_to_close():
    v6 = json.loads((V7 / "platform_agreement.json").read_text())["checkpoints"][
        "results/live-retrain-v6/candidate_online.pt"
    ]
    assert v6["agreement"] == 1.0  # the mapping agrees; the policy's choices drift
    assert v6["cases"]["bola_high"]["quiet"]["platform_actions"] == {"escalate_to_human": 53}
    assert "noop" not in v6["cases"]["no_findings"]["quiet"]["platform_actions"]
