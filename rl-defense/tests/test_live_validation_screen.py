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
        "online": {
            "selected_env_step": 15000,
            "selected_noop_margin": 0.3,
            "selection_history": [
                {"env_step": 0, "noop_margin": 0.0, "val_availability": 0.99},
                {"env_step": 15000, "noop_margin": 0.3, "val_availability": availability},
            ],
        }
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
    monkeypatch.setattr(online, "load_checkpoint", lambda path: (object(), {}))
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
