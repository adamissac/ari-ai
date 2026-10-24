"""Training preparation and bounded unit-receipt tests; no gradients/experiment."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from rl_defense.research.resource.env import OBS_DIM, ResourceEnv
from rl_defense.research.resource.preparation import (
    COST_NAMES,
    PreparedReplay,
    Transition,
    digest,
    fixture_episode,
    settle_episode,
    validate_episode,
    verify_unit_bundle,
    write_unit_bundle,
)
from rl_defense.research.resource.service import Config

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def episode():
    return fixture_episode(ResourceEnv(Config(horizon=4), family="mixed"), "threshold", 0)


def test_replay_preserves_reward_cost_masks_and_finite_horizon(episode):
    replay = PreparedReplay(3)
    for row in episode:
        replay.append(row)
    arrays = replay.arrays()
    assert arrays["obs"].shape == (3, OBS_DIM)
    assert arrays["costs"].shape == (3, len(COST_NAMES))
    assert arrays["next_masks"].shape == (3, 3)
    assert arrays["finite_terminal"].tolist() == [False, False, True]
    assert arrays["rewards"].tolist() == [r.reward for r in episode[-3:]]
    with pytest.raises(PermissionError, match="ineligible"):
        replay.append(episode[0], for_training=True)


@pytest.mark.parametrize("capacity", [0, 4097, True])
def test_replay_is_bounded(capacity):
    with pytest.raises(ValueError):
        PreparedReplay(capacity)


def test_replay_is_not_a_trainer():
    with pytest.raises(ValueError, match="empty"):
        PreparedReplay().arrays()
    with pytest.raises(ValueError, match="eight"):
        fixture_episode(ResourceEnv(Config(horizon=9)), "noop", 0)


@pytest.mark.parametrize(
    "change",
    [
        {"behavior_probability": 0.5},
        {"purpose": "train"},
        {"terminated": True},
        {"before_cutoff": 99999},
        {"applied": 2},
        {"profile": "production"},
    ],
)
def test_transition_contract_rejects_invalid_attribution_or_permissions(episode, change):
    raw = episode[0].model_dump()
    raw.update(change)
    with pytest.raises((ValueError, ValidationError)):
        Transition.model_validate(raw)


def test_trajectory_continuity_and_config_identity(episode):
    validate_episode(episode)
    with pytest.raises(ValueError):
        validate_episode(episode[:-1])
    wrong = episode[1].model_copy(update={"config_sha256": "0" * 64})
    with pytest.raises(ValueError, match="identity"):
        validate_episode((episode[0], wrong, *episode[2:]))
    wrong = episode[1].model_copy(update={"before_cutoff": episode[1].before_cutoff + 1})
    with pytest.raises(ValueError, match="chain"):
        validate_episode((episode[0], wrong, *episode[2:]))


def test_schema_roundtrip_and_no_label_in_policy_state(episode):
    for row in episode:
        assert Transition.model_validate_json(row.model_dump_json()) == row
        assert "adversarial" not in Transition.model_fields
        assert row.behavior_probability == 1.0
        assert np.isfinite(row.obs).all()


@pytest.fixture
def source_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    package = "rl-defense/rl_defense/research/resource"
    shutil.copytree(ROOT / package, repo / package, ignore=shutil.ignore_patterns("__pycache__"))
    protocol = "docs/research/resource-exhaustion/PREREGISTRATION.md"
    (repo / protocol).parent.mkdir(parents=True)
    shutil.copy(ROOT / protocol, repo / protocol)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "test: owned unit source",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def test_unit_bundle_provenance_verifier_and_refusal_to_overwrite(source_repo, tmp_path):
    output = tmp_path / "unit"
    anchor = write_unit_bundle(source_repo, output)
    rows = verify_unit_bundle(output, expected_index_sha256=anchor)
    assert len(rows) == 4
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["train_eligible"] is False and manifest["checkpoint"] is None
    assert manifest["training_authorized"] is False and manifest["gradients_applied"] is False
    assert manifest["purpose"] == "unit_instrumentation"
    with pytest.raises(FileExistsError):
        write_unit_bundle(source_repo, output)
    assert digest((output / "EVIDENCE.json").read_bytes()) == anchor
    with pytest.raises(ValueError, match="anchor"):
        verify_unit_bundle(output, expected_index_sha256="0" * 64)


def test_dirty_execution_source_is_rejected(source_repo, tmp_path):
    with (source_repo / "rl-defense/rl_defense/research/resource/service.py").open("a") as stream:
        stream.write("\n# uncommitted\n")
    with pytest.raises(ValueError, match="commit"):
        write_unit_bundle(source_repo, tmp_path / "unit")


@pytest.mark.parametrize("field", ["reward", "costs", "source_work"])
def test_rehashed_counterfeit_measurements_rejected(source_repo, tmp_path, field):
    output = tmp_path / "unit"
    write_unit_bundle(source_repo, output)
    index = json.loads((output / "EVIDENCE.json").read_text())
    name = "trajectory.jsonl" if field != "source_work" else "requests.json"
    if field == "source_work":
        raw = json.loads((output / name).read_text())
        raw["metrics_only_requests"][0]["consumed"] += 1
        (output / name).write_text(json.dumps(raw))
    else:
        rows = [json.loads(line) for line in (output / name).read_text().splitlines()]
        if field == "reward":
            rows[0]["reward"] -= 1
        else:
            rows[0]["costs"]["legitimate_latency_sum"] += 1
        (output / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    index["files"][name] = digest((output / name).read_bytes())
    blob = json.dumps(index).encode()
    (output / "EVIDENCE.json").write_bytes(blob)
    # Even an explicitly resealed file table cannot bless inconsistent raw work.
    with pytest.raises(ValueError, match="mismatch"):
        verify_unit_bundle(output, expected_index_sha256=digest(blob))


def test_failed_capture_is_retained_and_never_silently_replaced(source_repo, tmp_path, monkeypatch):
    import rl_defense.research.resource.preparation as prep

    def fail(env, policy, seed):
        env.reset(seed=seed)
        env.step(0)
        raise RuntimeError("owned unit failure")

    monkeypatch.setattr(prep, "fixture_episode", fail)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="owned unit failure"):
        write_unit_bundle(source_repo, output)
    failure = json.loads((output / "FAILURE.json").read_text())
    assert failure["events"] and failure["metrics_only_requests"]
    assert not (output / "EVIDENCE.json").exists()
    with pytest.raises(FileExistsError):
        write_unit_bundle(source_repo, output)


def test_settlement_removes_right_censoring_without_rewriting_policy_history():
    env = ResourceEnv(Config(horizon=2), family="high_exhaustion")
    with pytest.raises(ValueError, match="stopped"):
        settle_episode(env)
    history = fixture_episode(env, "noop", 0)
    encoded = tuple(r.model_dump_json() for r in history)
    offered = len(env.service.jobs)
    stop_clock = env.service.now
    settled = settle_episode(env)
    assert len(settled) <= 3 and not env.service.pending
    assert len(env.service.jobs) == offered
    assert env.service.now <= stop_clock + 3 * env.config.window_ticks
    assert encoded == tuple(r.model_dump_json() for r in history)
    with pytest.raises(RuntimeError):
        env.step(0)


def test_committed_unit_receipt_has_external_anchor_and_original_source():
    bundle = ROOT / "docs/research/resource-exhaustion/unit-evidence"
    rows = verify_unit_bundle(
        bundle,
        expected_index_sha256="b5f69ebc503647bebb2d42ef8cf7865eed1f5f42c16b60ececd84f09e5dcd86c",
    )
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert len(rows) == 4
    assert manifest["source_commit"] == "1b5516c808602c91152c18b7460fe9aaa9cd8404"
    # Current checkouts may be shallow in CI; the committed receipt is independently
    # anchored above. When history is present, also check the original source bytes.
    original = manifest["source_commit"]
    present = subprocess.run(
        ["git", "cat-file", "-e", original], cwd=ROOT, capture_output=True, check=False
    )
    if present.returncode == 0:
        for name, expected in manifest["source_files"].items():
            raw = subprocess.check_output(["git", "show", f"{original}:{name}"], cwd=ROOT)
            assert digest(raw) == expected
        protocol = subprocess.check_output(
            ["git", "show", f"{original}:docs/research/resource-exhaustion/PREREGISTRATION.md"],
            cwd=ROOT,
        )
        assert digest(protocol) == manifest["protocol_sha256"]
