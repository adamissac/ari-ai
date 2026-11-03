"""Race-condition and destination-reference templates, executed for real.

A small ledger package is written per test in a vulnerable and a fixed variant (the
same shapes the live pilot-rehearsal-target run exposed: a check-then-act balance
update and a transfer that debits before checking its destination). Each template
must confirm the vulnerable variant and clear the fixed one."""

from __future__ import annotations

import pytest

from security_agents.checks.library import (
    CONCURRENT_BOUND,
    DESTINATION,
    NONEXISTENT_DESTINATION,
    default_library,
)
from security_agents.contracts import ErrorCode, PlatformError
from security_agents.tools import CheckRunner

from .conftest import TARGET_ID
from .test_checks import probe_ctx

LEDGER = """
import threading
import time
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

RACY = {racy}
CHECK_DESTINATION = {check_destination}


class TransferIn(BaseModel):
    from_account: str
    to_account: str
    amount: Decimal


def create_app():
    app = FastAPI()
    owners = {{"acc_a1": "alice", "acc_a2": "alice", "acc_b1": "bob"}}
    balances = {{"acc_a1": Decimal("500.00"), "acc_a2": Decimal("0.00"), "acc_b1": Decimal("250.00")}}
    lock = threading.Lock()

    def who(authorization: str = Header()):
        name = {{"Bearer t-alice": "alice", "Bearer t-bob": "bob"}}.get(authorization)
        if name is None:
            raise HTTPException(401)
        return name

    @app.get("/accounts/{{account_id}}")
    def account(account_id: str, user: str = Depends(who)):
        if owners.get(account_id) != user:
            raise HTTPException(404)
        return {{"id": account_id, "balance": str(balances[account_id])}}

    @app.post("/transfers", status_code=201)
    def transfer(body: TransferIn, user: str = Depends(who)):
        if owners.get(body.from_account) != user:
            raise HTTPException(404)
        if CHECK_DESTINATION and body.to_account not in balances:
            raise HTTPException(422, "unknown destination")
        with (threading.Lock() if RACY else lock):
            if body.amount > balances[body.from_account]:
                raise HTTPException(422, "insufficient funds")
            current = balances[body.from_account]
            time.sleep(0.05)  # fraud-score call between the read and the write
            balances[body.from_account] = current - body.amount
            if body.to_account in balances:
                balances[body.to_account] += body.amount
        return {{"ok": True}}

    return app
"""

RECIPE = {
    "recipe_version": 1,
    "kind": "python_asgi",
    "app_factory": "ledger.app:create_app",
    "identities": {
        "alice": {"auth_header": "Bearer t-alice"},
        "bob": {"auth_header": "Bearer t-bob"},
    },
    "resources": {
        "account": {
            "alice": {"id": "acc_a1", "amount": "500.00"},
            "bob": {"id": "acc_b1", "amount": "250.00"},
        }
    },
    "routes": [
        {
            "id": "get_account",
            "method": "GET",
            "path_template": "/accounts/{account_id}",
            "resource": "account",
        },
        {
            "id": "create_transfer",
            "method": "POST",
            "path_template": "/transfers",
            "resource": "account",
            "balance_field": "balance",
            "body_template": {
                "from_account": "{resource_id}",
                "to_account": "{destination}",
                "amount": "{amount}",
            },
        },
    ],
}

PARAMS = {"route_id": "create_transfer", "read_route_id": "get_account", "owner_identity": "alice"}


def _runner(driver, tmp_path, *, racy: bool, check_destination: bool) -> CheckRunner:
    pkg = tmp_path / "ws" / "ledger"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "app.py").write_text(LEDGER.format(racy=racy, check_destination=check_destination))
    return CheckRunner(
        driver=driver,
        library=default_library(),
        workspace_provider=lambda _ctx: tmp_path / "ws",
        recipe_provider=lambda _ctx, _target: RECIPE,
    )


def test_race_template_confirms_a_check_then_act_balance_update(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, racy=True, check_destination=True)
    # The race template sends to a real destination: bind {destination} to bob's account.
    result = runner.run(probe_ctx(intel), CONCURRENT_BOUND.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is False, result.get("stdout_tail")
    assert result["category"] == "input_validation.bounds"


def test_race_template_clears_a_locked_balance_update(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, racy=False, check_destination=True)
    result = runner.run(probe_ctx(intel), CONCURRENT_BOUND.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is True, result.get("stdout_tail")


def test_destination_template_confirms_value_burned_on_a_missing_destination(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, racy=False, check_destination=False)
    result = runner.run(probe_ctx(intel), DESTINATION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is False, result.get("stdout_tail")


def test_destination_template_clears_a_validated_destination(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, racy=False, check_destination=True)
    result = runner.run(probe_ctx(intel), DESTINATION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is True, result.get("stdout_tail")


def test_destination_render_binds_the_destination_and_nothing_free_form():
    lib = default_library()
    src = lib.render(DESTINATION.ref, RECIPE, PARAMS)
    assert NONEXISTENT_DESTINATION in src
    owned = lib.render(DESTINATION.ref, RECIPE, {**PARAMS, "destination_identity": "bob"})
    assert "'to_account': 'acc_b1'" in owned
    with pytest.raises(PlatformError) as e:
        lib.render(DESTINATION.ref, RECIPE, {**PARAMS, "destination_identity": "alice"})
    assert e.value.code is ErrorCode.SCHEMA_INVALID


@pytest.mark.parametrize("parallel", [1, 17, "eight"])
def test_race_render_bounds_the_parallelism(parallel):
    with pytest.raises(PlatformError) as e:
        default_library().render(CONCURRENT_BOUND.ref, RECIPE, {**PARAMS, "parallel": parallel})
    assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_templates_need_a_declared_value_field():
    recipe = {**RECIPE, "routes": [RECIPE["routes"][0], {**RECIPE["routes"][1], "balance_field": None}]}
    for ref in (CONCURRENT_BOUND.ref, DESTINATION.ref):
        with pytest.raises(PlatformError) as e:
            default_library().render(ref, recipe, PARAMS)
        assert e.value.code is ErrorCode.SCHEMA_INVALID


def test_race_template_is_inconclusive_when_no_request_is_accepted(driver, intel, tmp_path):
    """A request the API rejects outright proves nothing about a race: never 'confirmed'."""
    runner = _runner(driver, tmp_path, racy=True, check_destination=True)
    recipe = {**RECIPE, "identities": {**RECIPE["identities"], "alice": {"auth_header": "Bearer nope"}}}
    runner.recipe_provider = lambda _ctx, _target: recipe
    result = runner.run(probe_ctx(intel), CONCURRENT_BOUND.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is None, result.get("stdout_tail")


def test_destination_template_is_inconclusive_when_the_owner_cannot_read(driver, intel, tmp_path):
    runner = _runner(driver, tmp_path, racy=False, check_destination=False)
    recipe = {**RECIPE, "identities": {**RECIPE["identities"], "alice": {"auth_header": "Bearer nope"}}}
    runner.recipe_provider = lambda _ctx, _target: recipe
    result = runner.run(probe_ctx(intel), DESTINATION.ref, TARGET_ID, PARAMS)
    assert result["matches_expectation"] is None, result.get("stdout_tail")
