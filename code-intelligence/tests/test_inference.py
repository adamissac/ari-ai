"""Fake provider exercises the shared gateway; real provider remains explicitly opt-in."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from backend.llm import FakeTransport, build_gateway
from backend.settings import Settings
from intel_test_helpers import repository as repository
from shared.intelligence import ContextPackRequest
from test_service import service

from code_intelligence.api import IntelligenceService
from code_intelligence.inference import ClaudeExpectationProvider, validate_proposals
from code_intelligence.models import IntelligenceError
from code_intelligence.store import SQLiteIndexStore


def prepared(repository: tuple[Path, str], tmp_path: Path):
    root, sha = repository
    engine = service(root, tmp_path / "baseline.sqlite")
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    pack = engine.build_context_pack(ContextPackRequest(snapshot_ref=ref, purpose="review"))
    subject = engine.get_symbol(ref, "app.payments.read_payment")
    source = next(p for p in pack.provenance if p.symbol == subject.qualified_name)
    proposal = dict(
        subject_id=subject.id,
        statement="Only the owning customer may read a payment.",
        kind="ownership",
        sources=[source.model_dump(mode="json")],
    )
    return engine, ref, pack, proposal


def submit(proposal: dict) -> dict:
    return {
        "content": [
            {
                "type": "tool_use",
                "id": "final",
                "name": "submit_result",
                "input": {"proposals": [proposal]},
            }
        ],
        "stop_reason": "tool_use",
    }


def test_fake_gateway_denies_execution_and_persists_inference_trace(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    engine, ref, _, proposal = prepared(repository, tmp_path)
    fake = FakeTransport(
        [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "denied",
                        "name": "run_shell",
                        "input": {"cmd": "echo never"},
                    }
                ],
                "stop_reason": "tool_use",
            },
            submit(proposal),
        ]
    )
    gateway = build_gateway(
        settings=Settings(_env_file=None, anthropic_api_key=None), transport=fake
    )
    provider = ClaudeExpectationProvider(gateway)
    inferred = IntelligenceService(
        SQLiteIndexStore(tmp_path / "inferred.sqlite"),
        list(engine.repositories.values()),
        expectation_provider=provider,
    )
    result_ref = inferred.index_repository(ref.project_id, ref.repo_id, ref.commit_sha)
    index = inferred.store.get(result_ref)
    rules = [e for e in index.expectations if e.origin == "inferred"]
    assert len(rules) == 1 and rules[0].confidence == 0.3 and rules[0].status == "inferred"
    trace = index.inference_trace
    assert trace is not None and trace.provider_mode == "fake" and trace.turns == 2
    assert trace.usage.llm_calls == 2
    assert trace.tool_calls[0].outcome == "denied"
    assert "UNTRUSTED DATA" in fake.requests[0]["system"]
    assert [t["name"] for t in fake.requests[0]["tools"]] == ["submit_result"]
    assert service(repository[0], tmp_path / "inferred.sqlite").store.get(result_ref) == index


def test_model_cannot_invent_citation_or_promote_trust(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    engine, ref, pack, proposal = prepared(repository, tmp_path)
    proposal["sources"][0]["commit_sha"] = "f" * 40
    fake = FakeTransport([submit(proposal)])
    provider = ClaudeExpectationProvider(
        build_gateway(settings=Settings(_env_file=None, anthropic_api_key=None), transport=fake)
    )
    result = provider.propose(pack)
    with pytest.raises(IntelligenceError, match="citation"):
        validate_proposals(engine.store.get(ref), pack, result.proposals)
    assert "confidence" not in fake.requests[0]["tools"][0]["input_schema"]["properties"]


@pytest.mark.live_llm
def test_opt_in_real_claude_expectation_inference(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    if os.environ.get("RUN_LIVE_LLM_EVAL") != "1":
        pytest.skip("set RUN_LIVE_LLM_EVAL=1 for a bounded real Claude inference run")
    settings = Settings()
    if not settings.anthropic_api_key:
        pytest.skip("authorized Anthropic key unavailable")
    engine, ref, pack, _ = prepared(repository, tmp_path)
    result = ClaudeExpectationProvider(build_gateway(settings=settings)).propose(pack)
    rules = validate_proposals(engine.store.get(ref), pack, result.proposals)
    assert result.trace.provider_mode == "live" and result.trace.turns >= 1
    assert all(rule.confidence == 0.3 and rule.origin == "inferred" for rule in rules)
    print(
        f"LIVE intelligence model={result.trace.model} turns={result.trace.turns} "
        f"rules={len(rules)} usage={result.trace.usage.model_dump()}"
    )
