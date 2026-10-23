"""Audit retained bytes without invoking the collector or application."""

import copy
import json
import shutil
import subprocess

import pytest

from rl_defense.research import readiness


def saved():
    result = json.loads((readiness.ROOT / readiness.BUNDLE / "RESULT.json").read_text())
    blob = subprocess.check_output(
        ["git", "show", f"{result['source_commit']}:{readiness.PROTOCOL}"], cwd=readiness.ROOT
    )
    return json.loads(blob), result


def test_original_audit_preserves_unknowns_and_never_approves_training():
    receipt = readiness.audit(readiness.ROOT / readiness.BUNDLE)
    assert receipt["artifact_integrity_verified"] is True
    assert receipt["request_units"] == 54
    assert receipt["readiness"] == "inconclusive"
    assert receipt["rl_training_ready"] is False and receipt["promotion_ready"] is False
    assert receipt["timing_budget_verified"] is None
    assert receipt["original_python_runtime_verified"] is None
    assert receipt["canonical_payment_authority_verified"] is None
    assert receipt["database_consistency_verified"] is None
    assert receipt["numeric_summaries"]["exact_resource_guard"]["passes_owner_limits"] is True
    assert receipt["numeric_summaries"]["unguarded"]["successful_unauthorized_reads"] == 7
    assert receipt["numeric_summaries"]["blanket_deny"]["owner_denials"] == 2
    assert receipt["numeric_summaries"]["blanket_deny"]["delegated_denials"] == 3


@pytest.mark.parametrize("target", ["index", "result", "rehashed"])
def test_copied_bundle_cannot_replace_its_trust_anchor(tmp_path, target):
    shutil.copytree(readiness.ROOT / readiness.BUNDLE, tmp_path / "bundle")
    bundle = tmp_path / "bundle"
    result = bundle / "RESULT.json"
    if target != "index":
        result.write_bytes(result.read_bytes() + b"\n")
    if target in ("index", "rehashed"):
        path = bundle / "EVIDENCE.json"
        index = json.loads(path.read_text())
        index["result_sha256"] = readiness._digest(result.read_bytes())
        path.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="trust anchor|result hash"):
        readiness.audit(bundle)


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "duplicate",
        "reorder",
        "label",
        "status",
        "forwarded",
        "summary",
        "summary_bool",
        "schema",
        "training",
    ],
)
def test_rehashed_semantic_forgery_is_rejected_by_independent_checks(kind):
    protocol, result = saved()
    result = copy.deepcopy(result)
    if kind == "missing":
        result["requests"].pop()
    elif kind == "duplicate":
        result["requests"][-1] = result["requests"][0]
    elif kind == "reorder":
        result["requests"].reverse()
    elif kind == "label":
        result["requests"][0]["label"] = "owner"
    elif kind == "status":
        result["requests"][0]["status"] = True
    elif kind == "forwarded":
        result["requests"][0]["forwarded"] = False
    elif kind == "summary":
        result["summary"]["unguarded"]["successful_unauthorized_reads"] = 0
    elif kind == "summary_bool":
        result["summary"]["exact_resource_guard"]["passes_owner_limits"] = 1
    elif kind == "schema":
        result["schema"] = "future/2"
    elif kind == "training":
        result["model_training"] = True
    with pytest.raises(ValueError):
        readiness._validate(protocol, result)


@pytest.mark.parametrize("blob", [b'{"a":1,"a":2}', b'{"a":NaN}', b"[]"])
def test_ambiguous_json_is_rejected(blob):
    with pytest.raises(ValueError):
        readiness._json(blob)


def test_oversized_artifact_read_is_bounded(tmp_path):
    path = tmp_path / "large"
    path.write_bytes(b"x" * 101)
    with pytest.raises(ValueError, match="size limit"):
        readiness._read(path, limit=100)
