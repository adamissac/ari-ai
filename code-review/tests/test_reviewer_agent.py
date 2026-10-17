"""Tier 2: reviewer agent loops with a scripted FakeTransport (replay mode, NOT live).

The script plays the model's tool choices; every tool really runs: SHA-pinned git
exports, file reads, pytest executions in the sandbox, fresh replays. Statuses are
asserted on what the code decided from executed evidence.
"""

from __future__ import annotations

from decimal import Decimal  # noqa: F401  (used inside generated test strings)
from pathlib import Path

import pytest
from cr_fakes import InMemoryHost, all_tool_results, call, fake, make_request, written_ids
from cr_scenarios import (
    DISCOUNT_README,
    INVOICE_HEAD,
    REFUNDS_HEAD,
    discount_rounding,
    line_of,
    payments_lite,
    tenant_auth,
)

from code_review.agent import ReviewerAgentRunner, ReviewError
from code_review.api import load_test_sources
from code_review.ports import RepoSource
from code_review.workspace import tree_digest
from shared.assessment import AgentRunStatus, ToolCallOutcome
from shared.evidence import EvidenceKind
from shared.findings import FindingKind, FindingStatus
from shared.review import IntentClaimStatus, ReviewStatus
from shared.scope import ApprovalStatus

DISCOUNT_TEST = """from decimal import Decimal

from billing.invoice import apply_discount


def test_discount_rounds_half_up_to_cents():
    # README money rules: ROUND_HALF_UP. 0.25 * 90% = 0.225 -> 0.23
    assert apply_discount(Decimal("0.25"), 10) == Decimal("0.23")
"""


def _submit(**report):
    return call("submit_result", **report)


def _discount_script() -> list:
    readme_line = line_of(DISCOUNT_README, "ROUND_HALF_UP")
    bug_line = line_of(INVOICE_HEAD, "return discounted.quantize(CENT)")
    return [
        call("read_file", path="README.md"),
        call("get_change_diff"),
        call("read_file", path="billing/invoice.py"),
        call(
            "write_test",
            name="discount_rounds_half_up",
            content=DISCOUNT_TEST,
            claim_key="c_round",
            rationale="tie value exposes the rounding mode",
        ),
        lambda req: call("run_tests", target="generated", test_id=written_ids(req)[-1]),
        call("run_tests", target="existing"),
        lambda req: _submit(
            summary="apply_discount uses banker's rounding; README requires half-up.",
            claims=[
                {
                    "key": "c_round",
                    "statement": "Discounted totals are rounded to cents with ROUND_HALF_UP.",
                    "proposed_status": "confirmed",
                    "citations": [
                        {
                            "source_kind": "doc",
                            "path": "README.md",
                            "start_line": readme_line,
                            "end_line": readme_line,
                            "quote": "rounded to cents with ROUND_HALF_UP",
                        },
                        {
                            "source_kind": "change_intent",
                            "quote": "Rounding follows the money rules in the README.",
                        },
                    ],
                }
            ],
            findings=[
                {
                    "title": "apply_discount rounds half-even instead of half-up",
                    "claim_key": "c_round",
                    "test_id": written_ids(req)[-1],
                    "suspected_spans": [
                        {
                            "source_kind": "code",
                            "path": "billing/invoice.py",
                            "start_line": bug_line,
                            "end_line": bug_line,
                            "quote": "return discounted.quantize(CENT)",
                        }
                    ],
                    "severity": "medium",
                    "rationale": "quantize() without rounding= uses the context default ROUND_HALF_EVEN",
                }
            ],
            open_questions=[],
        ),
    ]


def test_discount_rounding_defect_validated_with_multi_turn_trace(tmp_path: Path) -> None:
    sc = discount_rounding(tmp_path)
    source = RepoSource(sc.repo)
    before = tree_digest(source)
    transport = fake(_discount_script())
    host = InMemoryHost(transport)
    outcome = ReviewerAgentRunner(host, source).review(make_request(host, sc))
    res = outcome.result

    # a real multi-turn loop: 7 model turns, tools executed between them
    assert outcome.turns == 7 and outcome.provider_mode == "fake"
    run = host.runs[res.agent_run_id]
    assert run.status is AgentRunStatus.succeeded and run.model_id == "claude-opus-5-5"
    assert [t.tool_name for t in run.tool_calls] == [
        "read_file",
        "get_change_diff",
        "read_file",
        "write_test",
        "run_tests",
        "run_tests",
        "submit_result",
    ]
    assert all(t.outcome is ToolCallOutcome.ok for t in run.tool_calls)
    # review mode exposes no edit tools; untrusted PR text is delimited, not obeyed
    first = transport.requests[0]
    names = {t["name"] for t in first["tools"]}
    assert "edit_file" not in names and "apply_patch" not in names and "write_test" in names
    assert "<untrusted_change_intent>" in first["messages"][0]["content"]
    assert "Ignore previous instructions" in first["messages"][0]["content"]

    # tool outputs the model saw are the real executions
    seen = all_tool_results(transport.requests[-1])
    assert "outcome_on_head=failed reproducible=True" in seen
    assert "existing suite: passed" in seen

    [finding] = res.findings
    assert finding.kind is FindingKind.functional and finding.status is FindingStatus.validated
    assert finding.commit_sha == sc.head_sha and finding.produced_by_run_id == res.agent_run_id
    assert (
        "introduced" not in finding.history[0].reason
    )  # base has no apply_discount: errors on base
    kinds = {e.kind for e in finding.evidence}
    assert {EvidenceKind.source_span, EvidenceKind.test_run, EvidenceKind.artifact} <= kinds
    report = next(e for e in finding.evidence if e.kind is EvidenceKind.test_run)
    data = host.artifact_json(report.artifact_id)
    assert data["classification"] == ["failed", "failed"]
    assert data["runs"][0]["exit_code"] == 1
    assert data["runs"][0]["cases"][0]["exc_type"] == "AssertionError"
    assert "0.22" in data["runs"][0]["stdout"]  # the real wrong value from the code under test

    [gt] = res.generated_tests
    assert (
        gt.outcome_on_head == "failed"
        and gt.path == "tests/generated/test_cr_discount_rounds_half_up.py"
    )
    [claim] = res.intent_evidence.claims
    assert claim.status is IntentClaimStatus.confirmed
    assert any("instruction-like" in q for q in res.intent_evidence.open_questions)
    assert res.status is ReviewStatus.completed
    assert tree_digest(source) == before  # no writes to the original repository


def test_failing_test_against_unconfirmed_rule_stays_hypothesis(tmp_path: Path) -> None:
    sc = discount_rounding(tmp_path)
    cap_test = (
        "from decimal import Decimal\nimport pytest\nfrom billing.invoice import apply_discount\n\n"
        "def test_discount_capped_at_50_percent():\n"
        "    with pytest.raises(ValueError):\n"
        "        apply_discount(Decimal('100.00'), 60)\n"
    )
    script = [
        call(
            "write_test",
            name="discount_cap",
            content=cap_test,
            claim_key="c_cap",
            rationale="guess",
        ),
        lambda req: call("run_tests", target="generated", test_id=written_ids(req)[-1]),
        lambda req: _submit(
            summary="Discounts above 50% are accepted.",
            claims=[
                {
                    "key": "c_cap",
                    "statement": "Promo discounts are capped at 50 percent.",
                    "proposed_status": "confirmed",
                    "citations": [{"source_kind": "change_intent"}],
                },
                {
                    "key": "c_fake",
                    "statement": "Invented requirement",
                    "proposed_status": "confirmed",
                    "citations": [
                        {
                            "source_kind": "doc",
                            "path": "README.md",
                            "start_line": 999,
                            "end_line": 999,
                        }
                    ],
                },
            ],
            findings=[
                {
                    "title": "discount above 50% accepted",
                    "claim_key": "c_cap",
                    "test_id": written_ids(req)[-1],
                    "suspected_spans": [
                        {
                            "source_kind": "code",
                            "path": "billing/invoice.py",
                            "start_line": 16,
                            "end_line": 17,
                        }
                    ],
                    "severity": "low",
                    "rationale": "no cap",
                },
                {
                    "title": "finding for a rejected claim",
                    "claim_key": "c_fake",
                    "suspected_spans": [
                        {
                            "source_kind": "code",
                            "path": "billing/invoice.py",
                            "start_line": 1,
                            "end_line": 1,
                        }
                    ],
                    "severity": "high",
                    "rationale": "x",
                },
            ],
        ),
    ]
    host = InMemoryHost(fake(script))
    outcome = ReviewerAgentRunner(host, RepoSource(sc.repo)).review(make_request(host, sc))
    res = outcome.result
    [claim] = res.intent_evidence.claims  # invented citation dropped the second claim
    assert claim.status is IntentClaimStatus.inferred  # PR text alone cannot confirm
    [finding] = res.findings
    assert finding.status is FindingStatus.hypothesis  # test fails, but the rule is unconfirmed
    assert res.status is ReviewStatus.needs_clarification
    assert any("unconfirmed rule" in q for q in res.intent_evidence.open_questions)
    assert any("outside README.md" in r for r in outcome.rejected)
    assert any("c_fake" in r for r in outcome.rejected)
    data = host.artifact_json(
        next(e for e in finding.evidence if e.kind is EvidenceKind.test_run).artifact_id
    )
    assert data["runs"][0]["cases"][0]["exc_type"] == "Failed"  # DID NOT RAISE


CUMULATIVE_TEST = """from decimal import Decimal

import pytest

from payments.refunds import Payment, RefundTooLarge, refund


def test_cumulative_refunds_never_exceed_payment():
    payments = {"pay_1": Payment("pay_1", "alice", Decimal("100.00"))}
    refund(payments, "alice", "pay_1", Decimal("60.00"))
    with pytest.raises(RefundTooLarge):
        refund(payments, "alice", "pay_1", Decimal("50.00"))
"""


def test_fix_commit_that_weakens_tenant_auth_is_handed_to_scout(tmp_path: Path) -> None:
    sc = tenant_auth(tmp_path)
    start = line_of(REFUNDS_HEAD, "def refund(")
    end = line_of(REFUNDS_HEAD, "payment.refunds.append(amount)")
    script = [
        call("edit_file", path="payments/refunds.py", old_text="x", new_text="y"),  # not allowed
        call("read_file", path="payments/refunds.py"),
        call("get_change_diff"),
        call(
            "write_test",
            name="cumulative_bound",
            content=CUMULATIVE_TEST,
            claim_key="c_bound",
            rationale="fix intent",
        ),
        lambda req: call("run_tests", target="generated", test_id=written_ids(req)[-1]),
        call("run_tests", target="existing"),
        _submit(
            summary="Cumulative bound now holds; ownership check was removed.",
            claims=[
                {
                    "key": "c_bound",
                    "statement": "Total refunds for a payment never exceed its original amount.",
                    "proposed_status": "confirmed",
                    "citations": [
                        {
                            "source_kind": "docstring",
                            "path": "payments/refunds.py",
                            "start_line": 4,
                            "end_line": 4,
                        }
                    ],
                },
                {
                    "key": "c_tenant",
                    "statement": "A customer may only refund payments they own.",
                    "proposed_status": "confirmed",
                    "citations": [
                        {
                            "source_kind": "docstring",
                            "path": "payments/refunds.py",
                            "start_line": 3,
                            "end_line": 3,
                            "quote": "A customer may only refund payments they own",
                        }
                    ],
                },
            ],
            findings=[],
            security_concerns=[
                {
                    "title": "refund() no longer calls require_owner",
                    "weakness_class": "CWE-639",
                    "claim_key": "c_tenant",
                    "spans": [
                        {
                            "source_kind": "code",
                            "path": "payments/refunds.py",
                            "start_line": start,
                            "end_line": end,
                        }
                    ],
                    "rationale": "the diff removed the ownership check while fixing the bound",
                }
            ],
        ),
    ]
    host = InMemoryHost(fake(script))
    outcome = ReviewerAgentRunner(host, RepoSource(sc.repo)).review(make_request(host, sc))
    res = outcome.result
    run = host.runs[res.agent_run_id]
    assert run.tool_calls[0].tool_name == "edit_file"
    assert run.tool_calls[0].outcome is ToolCallOutcome.denied
    assert all(c.status is IntentClaimStatus.confirmed for c in res.intent_evidence.claims)
    [gt] = res.generated_tests
    assert gt.outcome_on_head == "passed"  # the intended fix works on head
    seen = all_tool_results(host.transport.requests[-1])
    assert "outcome_on_base=failed" in seen  # ...and the bug existed on base
    assert not [f for f in res.findings if f.kind is FindingKind.functional]
    [sec] = outcome.security_handoffs
    assert sec.kind is FindingKind.security and sec.status is FindingStatus.hypothesis
    assert sec.title.startswith("[CWE-639]") and "handoff to scout" in sec.history[0].reason
    assert host.findings() == [sec]
    assert res.status is ReviewStatus.completed


# ------------------------------------------------------------ repair


PL_TEST = """from fastapi.testclient import TestClient

from payments_lite.app import create_app

ALICE = {"Authorization": "Bearer fixture-token-alice"}


def test_total_refunds_never_exceed_payment_amount():
    client = TestClient(create_app())
    first = client.post("/refunds", json={"payment_id": "pay_a1", "amount": "100.00"}, headers=ALICE)
    assert first.status_code == 201
    second = client.post("/refunds", json={"payment_id": "pay_a1", "amount": "50.00"}, headers=ALICE)
    assert second.status_code == 422, second.text
"""


def pl_review_script(sc) -> list:
    app = (sc.repo / "target/payments_lite/app.py").read_text()
    doc = line_of(
        app, "Total refunds for a payment must never exceed the payment's original amount."
    )
    bug = line_of(app, "if body.amount > p.amount:")
    script = [
        call("read_file", path="target/payments_lite/app.py"),
        call("search_code", pattern="refunds_for|require_owner", path_prefix="target/"),
        call(
            "write_test",
            name="refund_bound",
            content=PL_TEST,
            claim_key="c_bound",
            rationale="cumulative",
        ),
        lambda req: call("run_tests", target="generated", test_id=written_ids(req)[-1]),
        call("run_tests", target="existing"),
        lambda req: _submit(
            summary="create_refund compares only the new refund with the payment amount.",
            claims=[
                {
                    "key": "c_bound",
                    "statement": "Total refunds for a payment must never exceed the original amount.",
                    "proposed_status": "confirmed",
                    "citations": [
                        {
                            "source_kind": "docstring",
                            "path": "target/payments_lite/app.py",
                            "start_line": doc,
                            "end_line": doc,
                            "quote": "Total refunds for a payment must never exceed",
                        }
                    ],
                }
            ],
            findings=[
                {
                    "title": "Refunds can exceed the payment amount in total",
                    "claim_key": "c_bound",
                    "test_id": written_ids(req)[-1],
                    "suspected_spans": [
                        {
                            "source_kind": "code",
                            "path": "target/payments_lite/app.py",
                            "start_line": bug,
                            "end_line": bug,
                        }
                    ],
                    "severity": "medium",
                    "rationale": "existing refunds are not summed",
                }
            ],
        ),
    ]
    return script


def pl_repair_script(test_path: str) -> list:
    return [
        call("read_file", path="target/payments_lite/app.py", start_line=140, end_line=165),
        call("edit_file", path=test_path, old_text="422", new_text="201"),  # tamper: denied
        call(
            "edit_file",
            path="target/payments_lite/app.py",
            old_text="        if body.amount > p.amount:\n",
            new_text=(
                '        already = sum((r.amount for r in store.refunds_for(p.id)), Decimal("0"))\n'
                "        if already + body.amount > p.amount:\n"
            ),
        ),
        call("run_tests", target="all"),
        call(
            "submit_result",
            summary="Sum prior refunds before comparing with the payment amount.",
            rationale="one-line condition change in create_refund",
            root_cause="bound compared only the new refund",
        ),
    ]


def _pl_review(tmp_path: Path):
    sc = payments_lite(tmp_path)
    host = InMemoryHost(fake(pl_review_script(sc)))
    source = RepoSource(sc.repo, subdir="target")
    outcome = ReviewerAgentRunner(host, source).review(make_request(host, sc))
    return sc, host, source, outcome


def test_payments_lite_refund_bound_reproduced_then_repaired(tmp_path: Path) -> None:
    sc, host, source, outcome = _pl_review(tmp_path)
    before = tree_digest(source)
    [finding] = outcome.result.findings
    assert finding.status is FindingStatus.validated
    assert outcome.result.generated_tests[0].outcome_on_head == "failed"

    approval = host.approve(finding.id)
    tests = load_test_sources(host, finding)
    assert [t.path for t in tests] == ["target/tests/generated/test_cr_refund_bound.py"]
    host.transport = fake(pl_repair_script(tests[0].path))
    rep = ReviewerAgentRunner(host, source).repair(finding, approval, tests)
    assert rep.accepted_locally, rep.reasons
    run = host.runs[rep.agent_run_id]
    assert run.step_key == f"repair:{finding.id}" and run.status is AgentRunStatus.succeeded
    assert (
        run.tool_calls[1].tool_name == "edit_file"
        and run.tool_calls[1].outcome is ToolCallOutcome.error
    )
    seen = all_tool_results(host.transport.requests[-1])
    assert (
        "protected" in seen
        and "outcome_on_head=passed" in seen
        and "existing suite: passed" in seen
    )

    patch = rep.patch
    assert patch is not None and host.patches == [patch]
    assert patch.files_changed == ["target/payments_lite/app.py"]
    assert patch.base_commit_sha == sc.head_sha and patch.produced_by_run_id == rep.agent_run_id
    diff = host.read_artifact(patch.diff_artifact_id).decode()
    assert "already + body.amount > p.amount" in diff and "tests/" not in diff
    replay = host.artifact_json(rep.test_report_artifact_id)
    by_label = {r["label"]: r["classification"] for r in replay["runs"]}
    assert by_label[f"generated:{tests[0].test_id}"] == "passed"  # failed before, passes after
    assert by_label["existing@candidate"] == "passed" and by_label["existing@pristine"] == "passed"
    # the reviewer proposes; it never marks its own patch verified
    assert rep.finding.status is FindingStatus.patch_proposed
    assert host.findings()[0].status is FindingStatus.patch_proposed
    assert tree_digest(source) == before


def test_repair_that_only_tampers_produces_no_patch(tmp_path: Path) -> None:
    sc, host, source, outcome = _pl_review(tmp_path)
    [finding] = outcome.result.findings
    approval = host.approve(finding.id)
    tests = load_test_sources(host, finding)
    host.transport = fake(
        [
            call("edit_file", path=tests[0].path, old_text="422", new_text="201"),
            call(
                "apply_patch",
                diff="--- a/target/tests/test_api.py\n+++ b/target/tests/test_api.py\n@@ -1 +1 @@\n-x\n+y\n",
            ),
            call("edit_file", path="target/pyproject.toml", old_text="pytest", new_text="nope"),
            call("submit_result", summary="gave up", rationale="-", root_cause="-"),
        ]
    )
    rep = ReviewerAgentRunner(host, source).repair(finding, approval, tests)
    assert not rep.accepted_locally and rep.patch is None and host.patches == []
    assert rep.reasons == ["no implementation change was made"]
    run = host.runs[rep.agent_run_id]
    assert [t.outcome for t in run.tool_calls[:3]] == [ToolCallOutcome.error] * 3
    assert host.findings()[0].status is FindingStatus.validated


def test_repair_requires_approved_remediation_for_that_finding(tmp_path: Path) -> None:
    sc, host, source, outcome = _pl_review(tmp_path)
    [finding] = outcome.result.findings
    tests = load_test_sources(host, finding)
    runner = ReviewerAgentRunner(host, source)
    with pytest.raises(ReviewError) as e:
        runner.repair(finding, host.approve(finding.id, status=ApprovalStatus.declined), tests)
    assert e.value.code.value == "APPROVAL_REQUIRED"
    with pytest.raises(ReviewError) as e:
        runner.repair(finding, host.approve("fnd_someotherfinding"), tests)
    assert e.value.code.value == "APPROVAL_REQUIRED"
    assert host.patches == [] and len(host.runs) == 1  # no repair run was even started
