"""Validation-only rejection must preserve the holdout and model evidence."""

import argparse
import copy
import json
from pathlib import Path

import pytest

from rl_defense.live import online
from rl_defense.live.adversary import live_app
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.scenarios import CONFIG_DIR
from rl_defense.live.topology import load_topology


def manifest(availability=0.84):
    return {
        "checkpoint_sha256": "a" * 64,
        "git_sha": "b" * 40,
        "seed": 0,
        "online": {
            "val_scenarios": {"validation_fixture": "pinned-config"},
            "selected_env_step": 15000,
            "selected_noop_margin": 0.3,
            "selection_history": [
                {"env_step": 0, "noop_margin": 0.0, "val_availability": 0.99},
                {"env_step": 15000, "noop_margin": 0.3, "val_availability": availability},
            ],
        },
    }


@pytest.mark.parametrize(
    "value", [None, float("nan"), float("inf"), -0.1, 1.1, True, "0.99", 0.8499]
)
def test_invalid_or_below_floor_selected_validation_is_ineligible(value):
    result = online.validation_availability_screen(manifest(value), 0.85)
    assert result["eligible_for_holdout"] is False
    assert result["promotion_performed"] is False
    # Earlier safe snapshots cannot make the selected unsafe one eligible.
    assert result["selected_env_step"] == 15000


def test_exact_floor_is_eligible_without_claiming_promotion():
    result = online.validation_availability_screen(manifest(0.85), 0.85)
    assert result["eligible_for_holdout"] is True
    assert result["promotion_performed"] is False


@pytest.mark.parametrize("fault", ["missing", "duplicate", "margin"])
def test_screen_refuses_ambiguous_selected_snapshot(fault):
    m = manifest()
    history = m["online"]["selection_history"]
    if fault == "missing":
        history.pop()
    elif fault == "duplicate":
        history.append(copy.deepcopy(history[-1]))
    else:
        history[-1]["noop_margin"] = 0.5
    with pytest.raises(ValueError, match="validation"):
        online.validation_availability_screen(m, 0.85)


def test_rejected_validation_stops_before_any_holdout_policy(tmp_path, monkeypatch):
    args = argparse.Namespace(
        out=tmp_path,
        criteria=CONFIG_DIR / "promotion.yaml",
        seed=0,
        train_dir="train_v8",
        val_dir="val_v10",
        holdout_dir="holdout_v10",
        holdout_episodes=1,
        base_checkpoint="synthetic-base.pt",
        rules_episodes=2,
        require_validation_availability=True,
    )
    monkeypatch.setattr(online, "load_checkpoint", lambda path: (object(), manifest()))
    monkeypatch.setattr(online.ev, "tune_rules_v3", lambda *a, **kw: ({}, []))
    monkeypatch.setattr(online, "choose_expert", lambda *a, **kw: ("threshold_rules", {}))
    monkeypatch.setattr(online, "expert_candidates", lambda params: {"threshold_rules": object()})
    monkeypatch.setattr(online, "train_online", lambda *a, **kw: manifest())

    def forbidden(*args, **kwargs):
        pytest.fail("holdout policy execution must not occur after rejected validation")

    monkeypatch.setattr(online.ev, "run_policy", forbidden)
    with pytest.raises(ValueError, match="holdout not executed"):
        online.run(args)
    screen = json.loads((tmp_path / "validation_screen.json").read_text())
    assert screen["eligible_for_holdout"] is False
    assert not (tmp_path / "holdout_trajectories.jsonl.gz").exists()
    assert not (tmp_path / "promotion_report.json").exists()


def test_saved_v10_selected_models_already_miss_validation_floor():
    root = Path(__file__).parents[1] / "results/live-retrain-v10"
    for arm in ("uniform", "balanced"):
        for seed in range(5):
            m = json.loads(
                (root / arm / f"seed{seed}" / "candidate_online.manifest.json").read_text()
            )
            assert online.validation_availability_screen(m, 0.85)["eligible_for_holdout"] is False


@pytest.mark.parametrize("token", ["fixture-token-bob", "fixture-token-bob-2"])
def test_principal_control_contains_rotated_tokens_but_also_blocks_authorized_reads(token):
    controls = DefenseControls(blocked_principals={"cus_bob": ["payments"]})
    gateway = DefensiveGateway(
        live_app(), load_topology(), controls, grants={"cus_bob": {"cus_dave"}}
    )
    try:
        unauthorized = gateway.request("GET", "/payments/pay_a1", token=token)
        own = gateway.request("GET", "/payments/pay_b1", token=token)
        delegated = gateway.request("GET", "/payments/pay_d1", token=token)
        assert unauthorized.cross_tenant_attempt
        assert not own.cross_tenant_attempt and not delegated.cross_tenant_attempt
        assert all(
            r.status == 403 and r.blocked_reason == "principal_blocked"
            for r in (unauthorized, own, delegated)
        )
        # Clearing the same control restores ordinary reads; token rotation is not a bypass.
        controls.blocked_principals.clear()
        restored = gateway.request("GET", "/payments/pay_b1", token=token)
        assert restored.status == 200 and restored.allowed
    finally:
        gateway.close()


@pytest.mark.parametrize("enabled", [False, True])
def test_cli_screen_is_explicit_opt_in(monkeypatch, enabled):
    captured = []

    def run(args):
        captured.append(args.require_validation_availability)
        return {"decision": "reject"}

    monkeypatch.setattr(online, "run", run)
    assert online.main(["--require-validation-availability"] if enabled else []) == 0
    assert captured == [enabled]


def test_saved_diagnosis_pins_its_inputs_without_replaying_holdout():
    from rl_defense.checkpoint import sha256_file

    root = Path(__file__).parents[1] / "results"
    diagnosis = json.loads((root / "v10-followup-diagnosis/diagnostics.json").read_text())
    for relative, digest in diagnosis["input_sha256"].items():
        assert sha256_file(root / "live-retrain-v10" / relative) == digest
    assert (
        sum(not s["eligible_for_holdout"] for rows in diagnosis["screens"].values() for s in rows)
        == 10
    )
    fixed = diagnosis["rotation"]["balanced"]
    assert (
        fixed["always_block_principal"]["reward"] > fixed["always_block_principal_long"]["reward"]
    )
    assert (
        fixed["always_block_principal"]["availability"]
        > fixed["always_block_principal_long"]["availability"]
    )


@pytest.mark.parametrize("directory", ["out", "evidence"])
def test_screened_run_refuses_stale_directories_before_mutation(tmp_path, directory):
    out, evidence = tmp_path / "out", tmp_path / "evidence"
    stale = out if directory == "out" else evidence
    stale.mkdir()
    marker = stale / "promotion_report.json"
    marker.write_bytes(b"old evidence must survive")
    args = argparse.Namespace(out=out, evidence_dir=evidence, require_validation_availability=True)
    with pytest.raises(ValueError, match="empty output directory"):
        online.run(args)
    assert marker.read_bytes() == b"old evidence must survive"
    assert sorted(stale.iterdir()) == [marker]


def rejected_files(out):
    import hashlib

    m = manifest()
    experiment = b'{"step":1}\n{"step":2}\n'
    selected = b'{"step":1}\n'
    checkpoint = b"fixture checkpoint bytes"
    (out / "candidate_online.pt").write_bytes(checkpoint)
    (out / "experiment.jsonl").write_bytes(experiment)
    (out / "selected.jsonl").write_bytes(selected)
    m["checkpoint_sha256"] = hashlib.sha256(checkpoint).hexdigest()
    m["online"]["experiment"] = {
        "experience_file": "experiment.jsonl",
        "experience_sha256": hashlib.sha256(experiment).hexdigest(),
    }
    m["lineage"] = {
        "experience_file": "selected.jsonl",
        "transitions": 1,
        "experience_sha256": hashlib.sha256(selected).hexdigest(),
    }
    (out / "candidate_online.manifest.json").write_text(json.dumps(m))
    (out / "validation_screen.json").write_text(
        json.dumps(online.validation_availability_screen(m, 0.85))
    )
    return m


def test_rejected_bundle_is_restorable_after_transient_output_is_removed(tmp_path):
    import shutil

    from rl_defense.live import evidence

    out, destination = tmp_path / "out", tmp_path / "durable"
    out.mkdir()
    destination.mkdir()  # Existing empty evidence directories are allowed.
    m = rejected_files(out)
    online.export_validation_rejection(out, destination, m)
    shutil.rmtree(out)
    assert set(evidence.verify(destination)) == {
        "checkpoint",
        "manifest",
        "validation_screen",
        "experiment",
        "selected_experience",
    }
    screen = json.loads((destination / "validation_screen.json").read_text())
    assert screen["checkpoint_sha256"] == m["checkpoint_sha256"]
    assert screen["training_seed"] == m["seed"]
    assert screen["validation_scenarios"] == m["online"]["val_scenarios"]
    assert screen["git_sha"] == m["git_sha"]
    evidence.restore(destination)
    assert (destination / "selected.jsonl").read_bytes() == b'{"step":1}\n'
    assert not (destination / "promotion_report.json").exists()


def test_corrupt_rejected_experience_does_not_publish_partial_bundle(tmp_path):
    out, destination = tmp_path / "out", tmp_path / "durable"
    out.mkdir()
    destination.mkdir()
    m = rejected_files(out)
    (out / "experiment.jsonl").write_bytes(b"corrupt\n")
    with pytest.raises(ValueError, match="sha256"):
        online.export_validation_rejection(out, destination, m)
    assert list(destination.iterdir()) == []
    assert (out / "candidate_online.pt").exists()


def test_changing_checkpoint_identity_changes_screen_provenance():
    a = manifest()
    b = copy.deepcopy(a)
    b["checkpoint_sha256"] = "c" * 64
    left = online.validation_availability_screen(a, 0.85)
    right = online.validation_availability_screen(b, 0.85)
    assert left["checkpoint_sha256"] != right["checkpoint_sha256"]
    assert left["manifest_content_sha256"] != right["manifest_content_sha256"]


def test_run_exports_rejection_before_raising_without_holdout(tmp_path, monkeypatch):
    from rl_defense.live import evidence

    out, destination = tmp_path / "out", tmp_path / "durable"
    args = argparse.Namespace(
        out=out,
        evidence_dir=destination,
        criteria=CONFIG_DIR / "promotion.yaml",
        seed=0,
        train_dir="train_v8",
        val_dir="val_v10",
        holdout_dir="holdout_v10",
        holdout_episodes=1,
        base_checkpoint="fixture-base.pt",
        rules_episodes=2,
        require_validation_availability=True,
    )
    monkeypatch.setattr(
        online,
        "load_checkpoint",
        lambda path: (
            object(),
            manifest()
            if path.name == "fixture-base.pt"
            else json.loads(path.with_suffix(".manifest.json").read_text()),
        ),
    )
    monkeypatch.setattr(online.ev, "tune_rules_v3", lambda *a, **kw: ({}, []))
    monkeypatch.setattr(online, "choose_expert", lambda *a, **kw: ("threshold_rules", {}))
    monkeypatch.setattr(online, "expert_candidates", lambda params: {"threshold_rules": object()})
    monkeypatch.setattr(online, "train_online", lambda *a, **kw: rejected_files(out))

    def forbidden(*args, **kwargs):
        pytest.fail("rejected validation must not execute holdout")

    monkeypatch.setattr(online.ev, "run_policy", forbidden)
    with pytest.raises(ValueError, match="holdout not executed"):
        online.run(args)
    assert "validation_screen" in evidence.verify(destination)
    assert (out / "candidate_online.pt").exists()
    assert not (out / "holdout_trajectories.jsonl.gz").exists()
    assert not (destination / "promotion_report.json").exists()
