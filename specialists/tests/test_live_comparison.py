"""The live-comparison harness, exercised offline on scripted (replay) trajectories.

Replay runs say nothing about Claude; they only pin down that the harness wires each
configuration correctly and scores runs against the answer key.
"""

from __future__ import annotations

import json

import pytest

from specialists import live_comparison as lc


def test_wilson_interval_is_wide_for_few_runs():
    r = lc._rate([True, True, False])
    assert r["k"] == 2 and r["n"] == 3
    lo, hi = r["wilson95"]
    assert lo < 0.3 and hi > 0.9


def test_answer_key_paths_are_relative_to_the_snapshot():
    key = lc.load_key()
    assert {p["id"] for p in key["planted"]} == {"fnd_planted_authz", "fnd_planted_refund_bound"}
    assert all(not p["path"].startswith("target/") for p in key["planted"])


@pytest.mark.parametrize("config, specialists_used", [("claude_only", False), ("hybrid", True)])
def test_replay_run_scores_the_planted_authz_and_wires_the_configuration(config, specialists_used):
    score, _, _ = lc.run_one(config, mode="replay", max_usd=5.0, max_hypotheses=3, validate=2)
    authz = score["planted"]["fnd_planted_authz"]
    assert authz["hypothesised"] and authz["validated"] and authz["fixed_verify_accepted"]
    assert score["false_positives_confirmed"] == 0
    sources = set(score["specialist_sources"].values())
    assert (sources != {"unavailable"}) is specialists_used


def test_replay_results_refuse_the_committed_results_path():
    assert lc.main(["--mode", "replay", "--reps", "1"]) == 2


def test_main_writes_runs_and_summary(tmp_path):
    out = tmp_path / "cmp.json"
    assert lc.main(["--mode", "replay", "--reps", "1", "--configs", "claude_only", "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["mode"] == "replay" and len(doc["runs"]) == 1
    assert doc["summary"]["claude_only"]["planted"]["fnd_planted_authz"]["validated"]["k"] == 1
    assert doc["specialists_only"]["planted"]["fnd_planted_authz"]["scout_rank"]


def test_provider_failures_are_excluded_but_refusals_are_not():
    def score(code, detail):
        return {"state": "completed", "per_agent": {"patch": {"error_codes": [code], "error_details": [detail]}}}

    assert lc.provider_failure(score("LLM_UNAVAILABLE", "Error code: 400 credit balance is too low"))
    assert lc.provider_failure(score("LLM_UNAVAILABLE", "refusal: policy")) is None
    assert lc.provider_failure(score("BUDGET_EXCEEDED", "cap")) is None
    assert lc.provider_failure({"state": "crashed", "error_code": "RuntimeError"})
