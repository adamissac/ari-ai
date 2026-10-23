"""Independent authored cases, not the RL traffic generator or attack labels."""

from dataclasses import replace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from rl_defense.research.authorization import ReadContext, ReadGrant, authorize_read


def context(**changes):
    base = ReadContext("reader", "owner", "payment-1", (), 0, 100)
    return replace(base, **changes)


def grant(**changes):
    return replace(ReadGrant("reader", "owner", "payment-1", 0, 10), **changes)


@pytest.mark.parametrize(
    ("ctx", "tick", "expected"),
    [
        (context(), 1, "deny"),
        (context(principal="owner"), 1, "allow"),
        (context(grants=(grant(),)), 0, "allow"),
        (context(grants=(grant(),)), 9, "allow"),
        (context(grants=(grant(),)), 10, "deny"),
        (context(grants=(grant(valid_from=2),)), 1, "deny"),
        (context(grants=(grant(revoked=True),)), 1, "deny"),
        (context(grants=(grant(resource="payment-2"),)), 1, "deny"),
        (context(grants=(grant(owner="other-owner"),)), 1, "deny"),
        (context(grants=(grant(principal="other-reader"),)), 1, "deny"),
        (context(principal=None), 1, "abstain"),
        (context(owner=None), 1, "abstain"),
        (context(grants=None), 1, "abstain"),
        (context(contradictory=True), 1, "abstain"),
        (context(observed_at=2), 1, "abstain"),
        (context(fresh_until=1), 1, "abstain"),
    ],
)
def test_independent_access_matrix(ctx, tick, expected):
    assert authorize_read(ctx, now=tick).outcome == expected


def test_revocation_rotation_repetition_and_new_snapshot_do_not_transfer_permission():
    permitted = context(grants=(grant(),))
    assert authorize_read(permitted, now=1).outcome == "allow"
    for _ in range(3):
        assert authorize_read(replace(permitted, principal="second"), now=1).outcome == "deny"
        assert authorize_read(context(grants=(grant(revoked=True),)), now=1).outcome == "deny"
        assert authorize_read(context(), now=1).outcome == "deny"
    assert authorize_read(permitted, now=10).outcome == "deny"
    assert authorize_read(context(principal="owner"), now=10).outcome == "allow"


def test_independent_http_fixture_never_forwards_denial_or_abstention():
    """One vulnerable read fixture, guarded externally; actual HTTP responses."""
    fixture = FastAPI()
    forwarded = []
    snapshot = context()

    @fixture.middleware("http")
    async def guard(request, call_next):
        from starlette.responses import JSONResponse

        decision = authorize_read(snapshot, now=1)
        if decision.outcome != "allow":
            return JSONResponse({}, status_code=404 if decision.outcome == "deny" else 503)
        return await call_next(request)

    @fixture.get("/payments/payment-1")
    def read():
        forwarded.append(True)
        return {"owner": "owner", "payment": "payment-1"}

    with TestClient(fixture) as client:
        assert client.get("/payments/payment-1").status_code == 404
        snapshot = context(grants=None)
        assert client.get("/payments/payment-1").status_code == 503
        assert forwarded == []
        snapshot = context(principal="owner")
        assert client.get("/payments/payment-1").status_code == 200
        snapshot = context(grants=(grant(),))
        assert client.get("/payments/payment-1").status_code == 200
        assert len(forwarded) == 2


@pytest.mark.parametrize("changes", [{"expires_at": 0}, {"valid_from": True}, {"revoked": 1}])
def test_malformed_grant_fails_closed(changes):
    with pytest.raises(ValueError):
        ReadGrant(
            **{
                **dict(principal="r", owner="o", resource="p", valid_from=0, expires_at=10),
                **changes,
            }
        )


def test_comparison_fixture_baselines_and_closed_unknown_policy():
    from rl_defense.research.feasibility import execute_request

    assert execute_request(context(), now=1, policy="unguarded") == (200, True)
    assert execute_request(context(principal="owner"), now=1, policy="blanket_deny") == (404, False)
    assert execute_request(context(), now=1, policy="exact_resource_guard") == (404, False)
    assert execute_request(context(grants=None), now=1, policy="exact_resource_guard") == (
        503,
        False,
    )
    with pytest.raises(ValueError, match="unsupported fixed policy"):
        execute_request(context(), now=1, policy="renamed")
