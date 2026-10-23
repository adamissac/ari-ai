"""Real payments-lite HTTP integration; no formal study rerun or RL scenarios."""

import asyncio
from dataclasses import replace

import httpx
import pytest
from payments_lite.app import create_app
from payments_lite.store import seeded_store

from rl_defense.research.authorization import ReadGrant
from rl_defense.research.payment_read_lab import PaymentReadLab

ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}
GRANT = ReadGrant("cus_bob", "cus_alice", "pay_a1", 0, 10)


def test_real_app_before_after_and_exact_request_binding():
    async def check():
        original = seeded_store()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(original)), base_url="http://fixture"
        ) as vulnerable:
            assert (await vulnerable.get("/payments/pay_a1", headers=BOB)).status_code == 200
        lab = PaymentReadLab(original, grants=(), clock=lambda: 1)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=lab), base_url="http://fixture"
        ) as client:
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 404
            own = await client.get("/payments/pay_a1", headers=ALICE)
            assert own.status_code == 200 and own.json()["customer_id"] == "cus_alice"
            await lab.replace_grants((GRANT,))
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 200
            assert (await client.get("/payments/pay_a2", headers=BOB)).status_code == 404
            assert (await client.get("/payments/pay_b1", headers=BOB)).status_code == 200
            assert (
                await client.get(
                    "/payments/pay_a2?owner=cus_bob&grant=true",
                    headers={**BOB, "X-Principal": "cus_alice", "X-Owner": "cus_bob"},
                )
            ).status_code == 404
            assert (await client.get("/payments/%70ay_a1", headers=BOB)).status_code == 404
            assert (
                await client.post("/payments", headers=ALICE, json={"amount": "1.00"})
            ).status_code == 404
        assert original.payments["pay_a1"].customer_id == "cus_alice"

    asyncio.run(check())


def test_expiry_revocation_rotation_ownership_and_unknown_are_current():
    async def check():
        tick = [1]
        lab = PaymentReadLab(seeded_store(), grants=(GRANT,), clock=lambda: tick[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=lab), base_url="http://fixture"
        ) as client:
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 200
            tick[0] = 10
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 404
            tick[0] = 1
            await lab.replace_grants((replace(GRANT, revoked=True),))
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 404
            await lab.replace_grants(None)
            before = lab.forwarded
            assert (await client.get("/payments/pay_a1", headers=ALICE)).status_code == 503
            assert lab.forwarded == before
            await lab.replace_grants(())
            await lab.bind_token("fixture-token-bob-rotated", "cus_bob")
            await lab.bind_token("fixture-token-bob", None)
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 503
            rotated = {"Authorization": "Bearer fixture-token-bob-rotated"}
            assert (await client.get("/payments/pay_a1", headers=rotated)).status_code == 404
            await lab.transfer_payment("pay_a1", "cus_bob")
            assert (await client.get("/payments/pay_a1", headers=rotated)).status_code == 200
            assert (await client.get("/payments/pay_a1", headers=ALICE)).status_code == 404
            assert (
                await client.get(
                    "/payments/pay_a1",
                    headers=[
                        ("Authorization", ALICE["Authorization"]),
                        ("Authorization", rotated["Authorization"]),
                    ],
                )
            ).status_code == 503

    asyncio.run(check())


@pytest.mark.parametrize(("expiry", "after"), [(10, 10), (100, 6), (100, 0)])
def test_revocation_is_serialized_and_mid_request_expiry_discards_body(expiry, after):
    async def check():
        tick = [1]
        lab = PaymentReadLab(
            seeded_store(), grants=(replace(GRANT, expires_at=expiry),), clock=lambda: tick[0]
        )
        original = lab._app
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed(scope, receive, send):
            await original(scope, receive, send)
            entered.set()
            await release.wait()

        lab._app = delayed
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=lab), base_url="http://fixture"
        ) as client:
            read = asyncio.create_task(client.get("/payments/pay_a1", headers=BOB))
            await entered.wait()
            revoke = asyncio.create_task(lab.replace_grants(()))
            await asyncio.sleep(0)
            assert not revoke.done()
            tick[0] = after
            release.set()
            response = await read
            assert response.status_code == 503 and "amount" not in response.text
            await revoke
            lab._app = original
            tick[0] = 1
            assert (await client.get("/payments/pay_a1", headers=BOB)).status_code == 404

    asyncio.run(check())


@pytest.mark.parametrize("failure", ["timeout", "body_budget"])
def test_downstream_failure_bounds_release_no_payment_body(failure):
    async def check():
        lab = PaymentReadLab(seeded_store(), grants=(), clock=lambda: 1, response_timeout_s=0.01)

        async def broken(scope, receive, send):
            if failure == "timeout":
                await asyncio.Event().wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"x" * 65537})

        lab._app = broken
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=lab), base_url="http://fixture"
        ) as client:
            response = await client.get("/payments/pay_a1", headers=ALICE)
            assert response.status_code == 503 and response.json() == {}
        await lab.replace_grants(None)  # failure releases the update lock

    asyncio.run(check())


def test_unknown_and_contradictory_store_facts_never_forward():
    async def check():
        source = seeded_store()
        source.payments["pay_a1"].customer_id = "missing-owner"
        source.payments["pay_a2"].id = "contradictory-id"
        lab = PaymentReadLab(source, grants=(), clock=lambda: 1)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=lab), base_url="http://fixture"
        ) as client:
            for path in ("/payments/pay_a1", "/payments/pay_a2", "/payments/absent"):
                assert (await client.get(path, headers=ALICE)).status_code == 503
            assert (await client.get("/payments/pay_b1")).status_code == 503
            assert (
                await client.get("/payments/pay_b1", headers={"Authorization": "Bearer invalid"})
            ).status_code == 503
        assert lab.forwarded == 0

    asyncio.run(check())
