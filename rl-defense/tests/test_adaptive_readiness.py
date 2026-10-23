"""Readiness/causal-adapter tests only; no collection, training or policy evaluation."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from payments_lite.store import seeded_store

from rl_defense.research.adaptive import (
    ACTION_MASK,
    FEATURES,
    ObservedRead,
    measured_channels,
    observation,
    validate_action,
)
from rl_defense.research.adaptive_readiness import audit
from rl_defense.research.authorization import ReadGrant
from rl_defense.research.authorization_provider import PaymentsLiteAuthorizationProvider
from rl_defense.research.dataset import evidence

ROOT = Path(__file__).resolve().parents[2]
REF = evidence("unit-fixture", "0" * 64, "authored regression, not empirical evidence")


def event(
    *,
    tick=1,
    available=2,
    credential="fixture-token-alice",
    grants=(),
    status=200,
    denied=False,
    name="e1",
):
    snapshot = PaymentsLiteAuthorizationProvider(
        seeded_store(), grants, clock_domain="test", revision=0
    ).capture(credential=credential, resource="pay_a1", tick=tick)
    return ObservedRead(name, tick, available, available, snapshot, status, denied, REF)


def build(events, *, cutoff=3):
    return observation(tuple(events), window_start=0, cutoff=cutoff, clock_domain="test")


def values(obs):
    return dict(zip(FEATURES, obs.values, strict=True))


def test_prefix_invariance_future_requests_outcomes_and_permissions():
    prefix = (event(),)
    future = event(tick=10, available=11, credential="fixture-token-bob", name="future")
    assert build(prefix) == build((*prefix, future))
    changed = replace(future, snapshot=replace(future.snapshot, revision=99), status=503)
    assert build(prefix) == build((*prefix, changed, changed))
    late = replace(event(name="late"), available_tick=10)
    assert build(prefix) == build((*prefix, late))
    assert values(build((*prefix, late), cutoff=11))["request_count"] == 2


def test_capture_classification_is_not_recomputed_from_later_state():
    grant = ReadGrant("cus_bob", "cus_alice", "pay_a1", 0, 3)
    delegated = event(grants=(grant,), credential="fixture-token-bob")
    assert values(build((delegated,), cutoff=20))["delegated_count"] == 1
    revoked = event(
        grants=(replace(grant, revoked=True),), credential="fixture-token-bob", name="revoked"
    )
    expired = event(
        tick=3, available=4, grants=(grant,), credential="fixture-token-bob", name="expired"
    )
    assert values(build((revoked, expired), cutoff=5))["unauthorized_count"] == 2
    assert values(build((delegated,), cutoff=20))["context_age_max"] == 19


def test_unknowns_and_observed_costs_remain_separate_from_security_reward():
    obs = build((event(denied=True, status=429), event(grants=None, name="missing", status=503)))
    v = values(obs)
    assert v["unknown_context_count"] == 1 and v["missing_context_fraction"] == 0.5
    assert v["owner_adaptive_denial_count"] == 1
    assert v["authorization_denial_count"] is None  # 503 is not an auth denial label
    channels = measured_channels(obs)
    assert channels["owner_denial_cost"] == 1
    assert channels["adaptive_security_reward"] is None
    assert channels["operational_cost"] is None
    assert v["intervention_budget_remaining"] is None
    encoded = obs.encode()
    assert len(FEATURES) == 32 and len(encoded) == 69
    i = FEATURES.index("intervention_budget_remaining")
    assert encoded[i] == 0 and encoded[32 + i] == 0
    assert tuple(bool(x) for x in encoded[-5:]) == ACTION_MASK


def test_empty_window_is_not_known_complete_telemetry():
    v = values(build(()))
    assert v["request_count"] == 0  # count of observed events only
    assert v["missing_context_fraction"] is None
    assert v["adapter_available"] is None and v["observation_age"] is None


@pytest.mark.parametrize("action", [-1, 1, 2, 3, 4, 5, True, 0.0])
def test_unsupported_actions_rejected_independently(action):
    with pytest.raises(ValueError, match="unsupported"):
        validate_action(action)
    validate_action(0)


def test_duplicates_clock_domains_and_authority_mismatch_rejected():
    e = event()
    with pytest.raises(ValueError, match="duplicate"):
        build((e, e))
    with pytest.raises(ValueError, match="clock"):
        build((replace(e, snapshot=replace(e.snapshot, clock_domain="other")),))
    with pytest.raises(ValueError, match="authority"):
        build((replace(e, snapshot=replace(e.snapshot, authority="untrusted")),))


@pytest.mark.parametrize(
    "kwargs",
    [{"available_tick": 0}, {"started_tick": True}, {"status": 200, "adaptive_denial": True}],
)
def test_invalid_event_contract(kwargs):
    with pytest.raises(ValueError):
        replace(event(), **kwargs)


def test_fixed_train_archive_inventory_and_hard_no_go():
    result = audit(ROOT / "rl-defense/results")
    assert result["phase1"]["transitions"] == 4200
    assert result["phase1"]["episodes"] == 140
    assert result["phase1"]["current_masks_known"] == 4200
    assert result["phase1"]["behavior_probabilities_known"] == 0
    assert result["duration_train"]["transitions"] == 8400
    assert result["duration_train"]["first_current_masks_missing"] == 280
    assert result["verdict"] == "NO-GO"
    assert not result["training_authorized"] and not result["collection_authorized"]
    assert len(result["feature_coverage"]) == 32
    assert all(
        "/train/" in ref["note"] or "constrained-phase1" in ref["note"]
        for ref in result["evidence"]
    )
    saved = json.loads(
        (ROOT / "docs/research/adaptive-defense-readiness/DATASET_AUDIT.json").read_text()
    )
    # Normalize tuple serialization without writing anything to historical paths.
    assert json.loads(json.dumps(result)) == saved


def test_changed_evidence_anchor_rejected(tmp_path):
    (tmp_path / "constrained-phase1").mkdir()
    (tmp_path / "constrained-phase1/EVIDENCE.json").write_text("{}")
    with pytest.raises(ValueError, match="trust anchor"):
        audit(tmp_path)


def test_expiry_during_release_cannot_certify_completion_or_valid_denial_cost():
    grant = ReadGrant("cus_bob", "cus_alice", "pay_a1", 0, 2)
    e = event(grants=(grant,), credential="fixture-token-bob", status=429, denied=True)
    obs = build((e,))
    assert values(obs)["delegated_count"] == 1
    assert values(obs)["delegated_adaptive_denial_count"] is None
    assert measured_channels(obs)["delegated_denial_cost"] is None
    assert values(obs)["observed_disruption_count"] is None


def test_observation_contract_rejects_widened_capabilities_or_invalid_values():
    obs = build((event(),))
    for changes in (
        {"action_mask": (True, True, False, False, False)},
        {"values": (float("nan"),) * 32},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValueError, match="invalid candidate"):
            replace(obs, **changes)


def test_late_arrival_enters_a_later_window_without_backfilling_prior_window():
    late = replace(event(name="late"), available_tick=10)
    prior = build((late,), cutoff=3)
    later = observation((late,), window_start=4, cutoff=11, clock_domain="test")
    assert values(prior)["request_count"] == 0
    assert values(later)["request_count"] == 1
    assert values(later)["observation_age"] == 9
    assert prior == build((late,), cutoff=3)


def test_generator_labels_are_not_part_of_the_ingest_contract():
    with pytest.raises(TypeError, match="is_attack"):
        ObservedRead("forbidden", 1, 2, 2, event().snapshot, 200, False, REF, is_attack=True)


def test_evidence_at_cutoff_is_excluded_until_next_window():
    e = event(available=3)
    assert values(build((e,), cutoff=3))["request_count"] == 0
    next_window = observation((e,), window_start=3, cutoff=4, clock_domain="test")
    assert values(next_window)["request_count"] == 1
