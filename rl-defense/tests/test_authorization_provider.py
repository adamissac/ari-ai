"""Provider boundary regression tests, not population/evaluation evidence."""

from dataclasses import replace

import pytest
from payments_lite.store import seeded_store

from rl_defense.research.authorization import ReadGrant
from rl_defense.research.authorization_provider import (
    AuthorizationContextProvider,
    PaymentsLiteAuthorizationProvider,
)

GRANT = ReadGrant("cus_bob", "cus_alice", "pay_a1", 1, 10)


def capture(grants=(), *, token="fixture-token-bob", resource="pay_a1", tick=2):
    provider: AuthorizationContextProvider = PaymentsLiteAuthorizationProvider(
        seeded_store(), grants, clock_domain="fixture-test", revision=0
    )
    return provider.capture(credential=token, resource=resource, tick=tick)


@pytest.mark.parametrize(
    ("grants", "token", "resource", "expected"),
    [
        ((), "fixture-token-alice", "pay_a1", "owner"),
        ((GRANT,), "fixture-token-bob", "pay_a1", "delegated"),
        ((), "fixture-token-bob", "pay_a1", "unauthorized"),
        ((GRANT,), "fixture-token-bob", "pay_a2", "unauthorized"),
        ((replace(GRANT, revoked=True),), "fixture-token-bob", "pay_a1", "unauthorized"),
        ((replace(GRANT, expires_at=2),), "fixture-token-bob", "pay_a1", "unauthorized"),
        ((replace(GRANT, valid_from=3),), "fixture-token-bob", "pay_a1", "unauthorized"),
        (None, "fixture-token-alice", "pay_a1", "unknown"),
        ((), "cus_alice", "pay_a1", "unknown"),
        ((), "fixture-token-alice", "missing", "unknown"),
    ],
)
def test_trusted_lookup_four_states(grants, token, resource, expected):
    snapshot = capture(grants, token=token, resource=resource)
    assert snapshot.classify(tick=2) == expected
    assert token not in repr(snapshot)


def test_expiry_clock_rollback_and_version_fail_closed():
    snapshot = capture((GRANT,))
    assert snapshot.classify(tick=1) == "unknown"
    assert snapshot.classify(tick=7) == "unknown"
    assert replace(snapshot, provider_version="2.0.0").classify(tick=2) == "unknown"
    assert replace(snapshot, revision=-1).classify(tick=2) == "unknown"
    assert replace(snapshot, clock_domain="").classify(tick=2) == "unknown"
    near_expiry = capture((GRANT,), tick=9)
    assert near_expiry.classify(tick=10) == "unauthorized"


def test_missing_or_contradictory_authority_records():
    for mutate in (
        lambda store: setattr(store.payments["pay_a1"], "id", "pay_a2"),
        lambda store: setattr(store.customers["cus_alice"], "id", "cus_bob"),
        lambda store: store.customers.pop("cus_alice"),
    ):
        store = seeded_store()
        mutate(store)
        provider = PaymentsLiteAuthorizationProvider(store, (), clock_domain="test", revision=1)
        assert (
            provider.capture(credential="fixture-token-alice", resource="pay_a1", tick=1).classify(
                tick=1
            )
            == "unknown"
        )


def test_captured_context_is_not_retroactively_backfilled():
    store = seeded_store()
    provider = PaymentsLiteAuthorizationProvider(store, (GRANT,), clock_domain="test", revision=1)
    past = provider.capture(credential="fixture-token-bob", resource="pay_a1", tick=2)
    store.payments["pay_a1"].customer_id = "cus_bob"
    current = PaymentsLiteAuthorizationProvider(store, (), clock_domain="test", revision=2).capture(
        credential="fixture-token-bob", resource="pay_a1", tick=3
    )
    assert past.classify(tick=2) == "delegated"
    assert past.context.owner == "cus_alice" and past.revision == 1
    assert current.classify(tick=3) == "owner" and current.revision == 2


def test_clock_capture_rejects_boolean_ticks():
    with pytest.raises(ValueError, match="integer"):
        capture(tick=True)
