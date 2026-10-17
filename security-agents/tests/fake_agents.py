"""Scripted agent trajectories for the deterministic end-to-end test.

These scripts stand in for the *model's* decisions only. Everything they touch
is real: the tool registry authorizes each call, the sandbox driver executes the
checks and tests, the worktree writes to disk and Verify re-checks independently.
Each script reads the previous tool results and adapts, so the loop's
request/tool-result cycle is genuinely exercised.

Labelled `fake` end to end; nothing here may be presented as live-provider
evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from security_agents.agents import (
    diagnose as diagnose_agent,
)
from security_agents.agents import (
    fortify as fortify_agent,
)
from security_agents.agents import (
    patch as patch_agent,
)
from security_agents.agents import (
    probe as probe_agent,
)
from security_agents.agents import (
    scout as scout_agent,
)
from security_agents.agents import (
    trace as trace_agent,
)
from security_agents.agents import (
    verify as verify_agent,
)
from security_agents.contracts import AgentName
from security_agents.llm import FakeTurn, last_tool_results

OWNERSHIP_REF = "access_control.ownership@1"
WEAK_HANDLER_PATH = "payments_lite/app.py"

# The fix the scripted Patch agent applies: use the ownership-scoped lookup that
# the sibling routes already use.
WEAK_LINE = "    payment = store.get_payment(payment_id)"
FIXED_LINE = "    payment = store.get_payment_for_customer(payment_id, customer.id)"

REGRESSION_TEST_PATH = "tests/test_authz_regression.py"
REGRESSION_TEST = '''"""Regression test added for the ownership finding."""

from fastapi.testclient import TestClient

from payments_lite.app import create_app

ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}


def test_non_owner_cannot_read_payment_detail():
    client = TestClient(create_app())
    assert client.get("/payments/pay_alice_1", headers=BOB).status_code == 404


def test_owner_can_still_read_payment_detail():
    client = TestClient(create_app())
    resp = client.get("/payments/pay_alice_1", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json()["id"] == "pay_alice_1"
'''


def _last_json(request) -> dict[str, Any]:
    results = last_tool_results(request)
    return results[-1].get("json", {}) if results else {}


def _all_json(request) -> list[dict[str, Any]]:
    return [r["json"] for r in last_tool_results(request) if "json" in r]


# --------------------------------------------------------------------------- scout


def scout_script() -> list:
    submit = scout_agent.SPEC.submit_tool_name()

    def turn0(_request) -> FakeTurn:
        return FakeTurn(
            text="Reading the behavioural expectations first.",
            tool_calls=[("expectations__for_subject", {"subject": WEAK_HANDLER_PATH})],
        )

    def turn1(_request) -> FakeTurn:
        return FakeTurn(
            text="Comparing the payment-detail handler with its siblings.",
            tool_calls=[
                ("graph__neighbors", {"symbol": "get_payment"}),
                ("graph__neighbors", {"symbol": "list_refunds"}),
            ],
        )

    def turn2(request) -> FakeTurn:
        # Locate the handler span from the graph result before citing it.
        payloads = _all_json(request)
        location = ""
        for p in payloads:
            if p.get("query") == "get_payment":
                location = (p.get("location") or [""])[0]
        start, end = 1, 40
        if ":" in location and "-" in location:
            span = location.rsplit(":", 1)[-1]
            start, end = (int(x) for x in span.split("-"))
        return FakeTurn(
            tool_calls=[("code__read_span", {"path": WEAK_HANDLER_PATH, "start_line": start, "end_line": end})]
        )

    def turn3(request) -> FakeTurn:
        payload = _last_json(request)
        start = int(payload.get("start_line", 1))
        end = int(payload.get("end_line", start + 8))
        return FakeTurn(
            text="The detail handler uses the unscoped lookup; its siblings scope by customer.",
            tool_calls=[
                (
                    submit,
                    {
                        "hypotheses": [
                            {
                                "title": "Payment detail route may not enforce payment ownership",
                                "weakness_class": "CWE-639",
                                "rationale": (
                                    "get_payment calls PaymentStore.get_payment, which looks a payment up by "
                                    "id alone, while the sibling routes list_refunds and create_refund call "
                                    "get_payment_for_customer and scope the lookup to the authenticated "
                                    "customer. The handler has the same authentication dependency as its "
                                    "siblings, so the difference is the ownership condition, not authentication."
                                ),
                                "expected_invariant": (
                                    "A customer can read only payments they own; another customer's payment "
                                    "is reported as not found."
                                ),
                                "cited_paths": [WEAK_HANDLER_PATH],
                                "cited_start_lines": [start],
                                "cited_end_lines": [end],
                                "expectation_ids": ["exp_tenant_isolation_payments"],
                                "entry_point_id": None,
                                "confidence": "high",
                                "suggested_check_category": "access_control.ownership",
                            }
                        ],
                        "coverage": {
                            "entry_points_reviewed": [
                                "ent_get_payments", "ent_get_payments_payment_id",
                                "ent_get_payments_payment_id_refunds",
                            ],
                            "looks_correct": [
                                "GET /payments/{payment_id}/refunds scopes the lookup by customer",
                                "POST /payments/{payment_id}/refunds scopes the lookup by customer",
                            ],
                            "skipped_with_reason": ["GET /health: no protected resource"],
                        },
                        "suspicious_instructions": [],
                    },
                )
            ],
        )

    return [turn0, turn1, turn2, turn3]


# --------------------------------------------------------------------------- probe


def probe_script() -> list:
    submit = probe_agent.SPEC.submit_tool_name()

    def turn0(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("checks__list_templates", {"category": "access_control.ownership"})])

    def turn1(request) -> FakeTurn:
        payload = _last_json(request)
        templates = payload.get("templates") or []
        ref = next(
            (t["ref"] for t in templates if t.get("category") == "access_control.ownership"), OWNERSHIP_REF
        )
        target = _target_id(request)
        return FakeTurn(
            text=f"Running {ref} against the authorized target.",
            tool_calls=[
                (
                    "checks__run_template",
                    {
                        "template_ref": ref,
                        "target_id": target,
                        "parameters": {
                            "route_id": "payment_detail",
                            "owner_identity": "alice",
                            "other_identity": "bob",
                        },
                    },
                )
            ],
        )

    def turn2(request) -> FakeTurn:
        payload = _last_json(request)
        matches = payload.get("matches_expectation")
        outcome = "confirmed" if matches is False else "refuted" if matches is True else "inconclusive"
        observations = [
            f"matches_expectation={matches}",
            f"failed={payload.get('failed')}",
            f"passed={payload.get('passed')}",
        ]
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "outcome": outcome,
                        "check_template_ref": payload.get("template_ref"),
                        "sandbox_run_id": payload.get("sandbox_run_id"),
                        "observations": observations,
                        "interpretation": (
                            "The executed check shows the expectation did not hold: a non-owner identity "
                            "received a successful response for another customer's payment."
                            if matches is False
                            else "The executed check shows the expectation held."
                        ),
                        "missing_capability": "" if matches is not None else "no conclusive check result",
                    },
                )
            ]
        )

    return [turn0, turn1, turn2]


def _target_id(request) -> str:
    """Read the authorized target id out of the task prompt data block."""
    for message in request.messages:
        if message["role"] != "user":
            continue
        content = message["content"]
        if isinstance(content, str) and "Authorized target id:" in content:
            after = content.split("Authorized target id:", 1)[1]
            return after.split("(", 1)[0].strip()
    return "tgt_payments_lite"


# --------------------------------------------------------------------------- trace


def trace_script() -> list:
    submit = trace_agent.SPEC.submit_tool_name()

    def turn0(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("graph__neighbors", {"symbol": "get_payment"})])

    def turn1(request) -> FakeTurn:
        sandbox_run_id = _sandbox_run_id_from_prompt(request)
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "steps": [
                            {
                                "description": (
                                    "An authenticated customer requests a payment id belonging to another "
                                    "customer and receives the payment record."
                                ),
                                "symbol_ref": "payments_lite.app.create_app.get_payment",
                                "verified": True,
                                "evidence_path": WEAK_HANDLER_PATH,
                                "evidence_start_line": 52,
                                "evidence_end_line": 60,
                                "evidence_artifact_id": sandbox_run_id,
                            },
                            {
                                "description": (
                                    "The record exposes the amount, currency and description of another "
                                    "customer's payment."
                                ),
                                "symbol_ref": "payments_lite.store.Payment.public",
                                "verified": False,
                                "evidence_path": "payments_lite/store.py",
                                "evidence_start_line": 20,
                                "evidence_end_line": 30,
                                "evidence_artifact_id": None,
                            },
                        ],
                        "preconditions": ["a valid customer token", "knowledge of another customer's payment id"],
                        "impact_summary": "financial payment records of other customers are readable",
                        "reachability": "authenticated",
                        "privileges_required": "low",
                        "data_sensitivity": "financial",
                        "severity_rationale": (
                            "The expectation tagged financial data sensitivity is violated on an "
                            "authenticated route, and the first step is backed by an executed check."
                        ),
                        "followup_validation_suggestions": [
                            "check the same route for refund records of other customers"
                        ],
                    },
                )
            ]
        )

    return [turn0, turn1]


def _sandbox_run_id_from_prompt(request) -> str | None:
    import re

    for message in request.messages:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        match = re.search(r'"sandbox_run_id":\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    return None


# --------------------------------------------------------------------------- diagnose


def diagnose_script() -> list:
    submit = diagnose_agent.SPEC.submit_tool_name()

    def turn0(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("code__search", {"pattern": "get_payment_for_customer"})])

    def turn1(_request) -> FakeTurn:
        return FakeTurn(
            tool_calls=[("code__read_span", {"path": WEAK_HANDLER_PATH, "start_line": 45, "end_line": 75})]
        )

    def turn2(_request) -> FakeTurn:
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "root_cause_summary": (
                            "The payment-detail handler resolves the payment with the unscoped store lookup "
                            "instead of the ownership-scoped lookup used by its sibling routes."
                        ),
                        "cause_class": "missing_check",
                        "cause_paths": [WEAK_HANDLER_PATH],
                        "cause_start_lines": [52],
                        "cause_end_lines": [60],
                        "cause_symbol": "payments_lite.app.create_app.get_payment",
                        "violated_expectation_ids": ["exp_tenant_isolation_payments"],
                        "strategy": (
                            "Resolve the payment through PaymentStore.get_payment_for_customer, passing the "
                            "authenticated customer id, so a payment owned by another customer is reported as "
                            "not found. This reuses the mechanism the sibling routes already rely on, so no "
                            "new abstraction is introduced."
                        ),
                        "constraints": [
                            "the owner must keep read access to their own payment",
                            "every /payments route must keep requiring a valid bearer token",
                        ],
                        "files_expected": [WEAK_HANDLER_PATH],
                        "tests_must_fail_before": [
                            "a non-owner requesting another customer's payment detail is refused"
                        ],
                        "tests_must_pass_after": [
                            "a non-owner receives 404 for another customer's payment detail",
                            "the owner still receives 200 for their own payment",
                        ],
                        "related_sites": [
                            "payments_lite.store.PaymentStore.get_payment is the unscoped lookup used here"
                        ],
                    },
                )
            ]
        )

    return [turn0, turn1, turn2]


# --------------------------------------------------------------------------- patch


def patch_script(
    snapshot_root: Path,
    *,
    weaken_tests: bool = False,
    out_of_scope: bool = False,
    ineffective: bool = False,
    skip_tests: bool = False,
) -> list:
    """Patch trajectory.

    `weaken_tests` / `out_of_scope` make the agent attempt writes the worktree
    must refuse. `ineffective` produces an in-scope change that does not fix the
    finding, so Verify rejects it and the remediation sub-flow retries.
    """
    submit = patch_agent.SPEC.submit_tool_name()
    app_text = (snapshot_root / WEAK_HANDLER_PATH).read_text(encoding="utf-8")
    fixed_text = app_text.replace(WEAK_LINE, FIXED_LINE)
    assert fixed_text != app_text, "fixture no longer contains the expected weak line"
    if ineffective:
        # In-scope, syntactically fine, but the ownership condition is still missing.
        fixed_text = app_text.replace(
            WEAK_LINE, WEAK_LINE + "  # TODO: scope this lookup to the customer"
        )

    def turn0(_request) -> FakeTurn:
        return FakeTurn(
            text="Reading the handler and its sibling before editing.",
            tool_calls=[("code__read_span", {"path": WEAK_HANDLER_PATH, "start_line": 45, "end_line": 75})],
        )

    def turn1(_request) -> FakeTurn:
        calls: list[tuple[str, dict[str, Any]]] = [
            ("worktree__write_file", {"path": WEAK_HANDLER_PATH, "content": fixed_text})
        ]
        if out_of_scope:
            store = (snapshot_root / "payments_lite/store.py").read_text(encoding="utf-8")
            calls.append(
                ("worktree__write_file", {"path": "payments_lite/store.py", "content": store + "\n# touched\n"})
            )
        if weaken_tests:
            weakened = (snapshot_root / "tests/test_payments.py").read_text(encoding="utf-8").replace(
                "assert client.get(\"/payments/pay_bob_1/refunds\", headers=ALICE).status_code == 404",
                "assert client.get(\"/payments/pay_bob_1/refunds\", headers=ALICE).status_code in (200, 404)",
            )
            calls.append(("worktree__write_file", {"path": "tests/test_payments.py", "content": weakened}))
        return FakeTurn(text="Applying the scoped lookup.", tool_calls=calls)

    def turn2(_request) -> FakeTurn:
        if skip_tests:
            return FakeTurn(tool_calls=[("worktree__diff", {})])
        return FakeTurn(
            tool_calls=[("worktree__write_file", {"path": REGRESSION_TEST_PATH, "content": REGRESSION_TEST})]
        )

    def turn3(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("tests__run", {"selection": "project_suite", "node_ids": []})])

    def turn4(request) -> FakeTurn:
        payload = _last_json(request)
        return FakeTurn(
            text=f"Suite result: {payload.get('passed')} passed, {payload.get('failed')} failed.",
            tool_calls=[("worktree__diff", {})],
        )

    def turn5(request) -> FakeTurn:
        diff_payload = _last_json(request)
        files = diff_payload.get("files_changed") or []
        tests_run = [
            p for p in _collect_test_payloads(request)
        ]
        passed = tests_run[-1].get("failed", 0) == 0 if tests_run else False
        run_id = tests_run[-1].get("sandbox_run_id") if tests_run else None
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "explanation": (
                            "Replaced the unscoped payment lookup with the ownership-scoped lookup already "
                            "used by the sibling routes, and added a regression test covering both the "
                            "non-owner denial and the owner's continued access."
                        ),
                        "files_changed": files,
                        "tests_added": [] if skip_tests else [REGRESSION_TEST_PATH],
                        "local_tests_passed": bool(passed),
                        "local_test_run_id": run_id,
                        "deviations_from_plan": (
                            ["also touched payments_lite/store.py"] if out_of_scope else []
                        ),
                        "blocked_reason": "",
                    },
                )
            ]
        )

    return [turn0, turn1, turn2, turn3, turn4, turn5]


def _collect_test_payloads(request) -> list[dict[str, Any]]:
    """Every tests.run payload seen so far in this conversation."""
    import json
    import re

    out: list[dict[str, Any]] = []
    for message in request.messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            text = block.get("content")
            if not isinstance(text, str) or '"pytest_args"' not in text:
                continue
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError:
                match = re.search(r'"passed":\s*(\d+).*?"failed":\s*(\d+)', text)
                if match:
                    out.append({"passed": int(match.group(1)), "failed": int(match.group(2))})
    return out


# --------------------------------------------------------------------------- verify


def verify_script() -> list:
    submit = verify_agent.SPEC.submit_tool_name()

    def turn0(request) -> FakeTurn:
        patch_id = _patch_id_from_prompt(request)
        return FakeTurn(
            text="Applying the candidate diff to a fresh checkout.",
            tool_calls=[("patch__apply_fresh", {"patch_id": patch_id})],
        )

    def turn1(request) -> FakeTurn:
        target = _verify_target_from_prompt(request)
        return FakeTurn(
            text="Re-running the original check against the patched code.",
            tool_calls=[
                (
                    "checks__run_template",
                    {
                        "template_ref": OWNERSHIP_REF,
                        "target_id": target,
                        "parameters": {
                            "route_id": "payment_detail",
                            "owner_identity": "alice",
                            "other_identity": "bob",
                        },
                    },
                )
            ],
        )

    def turn2(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("tests__run", {"selection": "project_suite", "node_ids": []})])

    def turn3(request) -> FakeTurn:
        payload = _last_json(request)
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "summary": (
                            f"Applied the diff to a fresh checkout, re-ran the original ownership check and "
                            f"the project suite ({payload.get('passed')} passed, {payload.get('failed')} "
                            f"failed)."
                        ),
                        "observed_original_check_ref": OWNERSHIP_REF,
                        "concerns": [],
                    },
                )
            ]
        )

    return [turn0, turn1, turn2, turn3]


def _patch_id_from_prompt(request) -> str:
    import re

    for message in request.messages:
        content = message.get("content")
        if isinstance(content, str):
            match = re.search(r'"patch_id":\s*"([^"]+)"', content)
            if match:
                return match.group(1)
    return "pat_unknown"


def _verify_target_from_prompt(request) -> str:
    import re

    for message in request.messages:
        content = message.get("content")
        if isinstance(content, str):
            match = re.search(r'"target_id":\s*"([^"]+)"', content)
            if match:
                return match.group(1)
    return "tgt_payments_lite"


# --------------------------------------------------------------------------- fortify


def fortify_script() -> list:
    submit = fortify_agent.SPEC.submit_tool_name()

    def turn0(_request) -> FakeTurn:
        return FakeTurn(tool_calls=[("code__search", {"pattern": "def get_payment"})])

    def turn1(_request) -> FakeTurn:
        return FakeTurn(
            tool_calls=[
                (
                    submit,
                    {
                        "recommendations": [
                            {
                                "category": "centralize_check",
                                "recommendation": (
                                    "Remove PaymentStore.get_payment, or make it private, so every route must "
                                    "resolve payments through get_payment_for_customer and the ownership "
                                    "condition cannot be omitted by accident."
                                ),
                                "reference_path": "payments_lite/store.py",
                                "reference_start_line": 55,
                                "reference_end_line": 70,
                                "effort": "small",
                                "owner_review_note": "changes the store API; review call sites",
                            },
                            {
                                "category": "policy_test",
                                "recommendation": (
                                    "Add a test that iterates every /payments route and asserts a non-owner "
                                    "identity is refused, so a new route cannot ship without the check."
                                ),
                                "reference_path": "tests/test_payments.py",
                                "reference_start_line": 1,
                                "reference_end_line": 10,
                                "effort": "medium",
                                "owner_review_note": "",
                            },
                        ],
                        "future_hypotheses": [
                            {
                                "weakness_class": "CWE-639",
                                "title": "Refund listing may expose other customers' refunds",
                                "rationale": "Same resource family; worth a check once the store API changes.",
                                "path": WEAK_HANDLER_PATH,
                                "start_line": 62,
                                "end_line": 75,
                            }
                        ],
                        "monitoring_hints": ["GET /payments/{payment_id}", "POST /payments/{payment_id}/refunds"],
                        "regression_test_names": [f"{REGRESSION_TEST_PATH}::test_non_owner_cannot_read_payment_detail"],
                    },
                )
            ]
        )

    return [turn0, turn1]


def all_scripts(snapshot_root: Path, **patch_kw: Any) -> dict[AgentName, list]:
    return {
        AgentName.SCOUT: scout_script(),
        AgentName.PROBE: probe_script(),
        AgentName.TRACE: trace_script(),
        AgentName.DIAGNOSE: diagnose_script(),
        AgentName.PATCH: patch_script(snapshot_root, **patch_kw),
        AgentName.VERIFY: verify_script(),
        AgentName.FORTIFY: fortify_script(),
    }
