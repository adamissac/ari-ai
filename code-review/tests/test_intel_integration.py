"""The reviewer consuming the REAL code-intelligence index (Sarosh, on main).

payments-lite is indexed with ``IntelligenceService`` + ``SQLiteIndexStore`` at the exact
commit; the reviewer's ``list_expectations`` / ``get_context_pack`` tools return real index
data. Extracted index expectations are ``ambiguous`` (repository rules are not confirmed
human intent), so citing one alone cannot confirm a claim; a docstring can.
Model turns are scripted (FakeTransport); index, tools and pytest run for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("code_intelligence.api")

from cr_fakes import InMemoryHost, all_tool_results, call, fake, make_request, written_ids  # noqa: E402
from cr_scenarios import line_of, payments_lite  # noqa: E402
from test_reviewer_agent import PL_TEST  # noqa: E402

from code_intelligence.api import IntelligenceService, RepositoryBinding  # noqa: E402
from code_intelligence.store import SQLiteIndexStore  # noqa: E402
from code_review.agent import ReviewerAgentRunner  # noqa: E402
from code_review.ports import RepoSource  # noqa: E402
from shared.findings import FindingStatus  # noqa: E402
from shared.review import IntentClaimStatus  # noqa: E402


def test_reviewer_uses_real_index_expectations_and_context(tmp_path: Path) -> None:
    sc = payments_lite(tmp_path)
    host = InMemoryHost(fake([]))
    svc = IntelligenceService(
        SQLiteIndexStore(tmp_path / "intel.db"),
        [
            RepositoryBinding(
                host.project_id,
                "rep_fixture0001",
                "acme/payments-lite",
                sc.repo,
                include_prefix="target/",
            )
        ],
    )
    ref = svc.index_repository(host.project_id, "rep_fixture0001", sc.head_sha)
    exp = next(
        e
        for e in svc.expectations(ref, limit=100)
        if e.statement.startswith("Total refunds")
        and e.sources[0].path == "target/payments_lite/app.py"
        and e.sources[0].span
        and e.sources[0].span.start_line > 100
    )
    app = (sc.repo / "target/payments_lite/app.py").read_text()
    doc = line_of(
        app, "Total refunds for a payment must never exceed the payment's original amount."
    )
    bug = line_of(app, "if body.amount > p.amount:")
    exp_cite = {"source_kind": "expectation", "expectation_id": exp.id}
    host.transport = fake(
        [
            call("list_expectations"),
            call("get_context_pack", focus=["POST /refunds"]),
            call(
                "write_test",
                name="refund_bound",
                content=PL_TEST,
                claim_key="c_bound",
                rationale="index rule",
            ),
            lambda req: call("run_tests", target="generated", test_id=written_ids(req)[-1]),
            lambda req: call(
                "submit_result",
                summary="Index rule + docstring: cumulative refunds must not exceed the amount.",
                claims=[
                    {
                        "key": "c_bound",
                        "statement": "Total refunds for a payment never exceed its original amount.",
                        "proposed_status": "confirmed",
                        "citations": [
                            exp_cite,
                            {
                                "source_kind": "docstring",
                                "path": "target/payments_lite/app.py",
                                "start_line": doc,
                                "end_line": doc,
                            },
                        ],
                    },
                    {
                        "key": "c_index_only",
                        "statement": "Total refunds never exceed the amount (index only).",
                        "proposed_status": "confirmed",
                        "citations": [exp_cite],
                    },
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
    )
    req = make_request(host, sc).model_copy(update={"snapshot_ref": ref})
    outcome = ReviewerAgentRunner(
        host, RepoSource(sc.repo, subdir="target"), intelligence=svc
    ).review(req)

    seen = all_tool_results(host.transport.requests[-1])
    assert exp.id in seen and "[ambiguous/" in seen  # real index expectations shown to the model
    assert "context pack ctx_" in seen and "UNAVAILABLE" not in seen
    claims = {c.statement: c for c in outcome.result.intent_evidence.claims}
    assert (
        claims["Total refunds for a payment never exceed its original amount."].status
        is IntentClaimStatus.confirmed
    )
    assert (
        claims["Total refunds never exceed the amount (index only)."].status
        is IntentClaimStatus.inferred
    )
    [finding] = outcome.result.findings
    assert finding.status is FindingStatus.validated
    assert finding.expectation_ids == [exp.id]  # linked back to the index's expectation
    run = host.runs[outcome.result.agent_run_id]
    assert [t.tool_name for t in run.tool_calls][:2] == ["list_expectations", "get_context_pack"]


def test_human_decisions_from_real_service_drive_reviewer_claims(tmp_path: Path) -> None:
    """Consumer proof for #38/#39: a human decision recorded in the REAL intelligence memory
    surfaces through ``expectations(ref)`` and the reviewer honors it (confirmed confirms,
    rejected is dropped). Model turns scripted; service, memory and adjudication real."""
    from shared.intelligence import ExpectationStatus
    from shared.intelligence_memory import ExpectationDecisionRequest

    sc = payments_lite(tmp_path)
    host = InMemoryHost(fake([]))
    svc = IntelligenceService(
        SQLiteIndexStore(tmp_path / "intel.db"),
        [
            RepositoryBinding(
                host.project_id,
                "rep_fixture0001",
                "acme/payments-lite",
                sc.repo,
                include_prefix="target/",
            )
        ],
    )
    ref = svc.index_repository(host.project_id, "rep_fixture0001", sc.head_sha)
    exps = svc.expectations(ref, limit=200)
    bound = next(
        e
        for e in exps
        if e.statement.startswith("Total refunds")
        and e.sources[0].path == "target/payments_lite/app.py"
    )
    other = next(
        e for e in exps if e.id != bound.id and e.statement.startswith("Test test_partial_refund")
    )
    assert bound.status is ExpectationStatus.ambiguous  # extracted, not human intent

    svc.decide_expectation(
        ref,
        bound.id,
        ExpectationDecisionRequest(
            status="confirmed", reason="product owner confirmed", expected_revision=0
        ),
        actor_id="usr_fixtureowner01",
    )
    svc.decide_expectation(
        ref,
        other.id,
        ExpectationDecisionRequest(
            status="rejected", reason="obsolete test intent", expected_revision=0
        ),
        actor_id="usr_fixtureowner01",
    )
    decided = {e.id: e for e in svc.expectations(ref, limit=200)}
    assert decided[bound.id].status is ExpectationStatus.confirmed
    assert any(s.kind.value == "human_input" for s in decided[bound.id].sources)

    host.transport = fake(
        [
            call("list_expectations"),
            call(
                "submit_result",
                summary="Decided intent only.",
                claims=[
                    {
                        "key": "c_human",
                        "statement": "Refund total bound (human-confirmed).",
                        "proposed_status": "confirmed",
                        "citations": [{"source_kind": "expectation", "expectation_id": bound.id}],
                    },
                    {
                        "key": "c_rejected",
                        "statement": "Partial refund rule (rejected).",
                        "proposed_status": "confirmed",
                        "citations": [{"source_kind": "expectation", "expectation_id": other.id}],
                    },
                ],
            ),
        ]
    )
    req = make_request(host, sc).model_copy(update={"snapshot_ref": ref})
    outcome = ReviewerAgentRunner(
        host, RepoSource(sc.repo, subdir="target"), intelligence=svc
    ).review(req)
    seen = all_tool_results(host.transport.requests[-1])
    assert f"{bound.id} [confirmed/" in seen
    claims = {c.statement: c for c in outcome.result.intent_evidence.claims}
    assert claims["Refund total bound (human-confirmed)."].status is IntentClaimStatus.confirmed
    assert claims["Refund total bound (human-confirmed)."].expectation_id == bound.id
    assert "Partial refund rule (rejected)." not in claims
    assert any(
        "rejected by a human decision" in r or "unknown expectation" in r for r in outcome.rejected
    )
