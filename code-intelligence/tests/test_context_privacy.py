"""Provider-bound citation metadata has the same privacy boundary as source text."""

from pathlib import Path

import pytest
from intel_test_helpers import repository as repository
from shared.evidence import EvidenceRef
from shared.intelligence import ContextPackRequest, ContextPurpose
from shared.intelligence_memory import ExpectationDecisionRequest

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.privacy import redact_evidence
from code_intelligence.retrieval import delimited
from code_intelligence.store import SQLiteIndexStore


@pytest.mark.parametrize("purpose", ["review", "scout", "trace", "verify", "monitoring"])
def test_human_reason_secrets_are_redacted_in_context_metadata_only(
    repository: tuple[Path, str], tmp_path: Path, purpose: str
) -> None:
    root, sha = repository
    engine = IntelligenceService(
        SQLiteIndexStore(tmp_path / "index.db"),
        [RepositoryBinding("prj_fixture00", "rep_fixture00", "owned/fixture", root)],
    )
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    original = engine.store.get(ref).model_dump_json()
    expectation = engine.expectations(ref, subject="app.payments.read_payment")[0]
    # Deliberately fake canary, never a credential or provider call.
    canary = "maintenance-canary-not-a-credential"
    reason = f"Owner confirms the access rule. Authorization: Bearer {canary}"
    engine.decide_expectation(
        ref,
        expectation.id,
        ExpectationDecisionRequest(status="confirmed", reason=reason, expected_revision=0),
        actor_id="usr_fixture00",
    )
    pack = engine.build_context_pack(
        ContextPackRequest(
            snapshot_ref=ref,
            purpose=ContextPurpose(purpose),
            focus=["app.payments.read_payment"],
            token_budget=24_000,
        )
    )
    assert canary not in pack.model_dump_json()
    assert any(e.note and "[REDACTED]" in e.note for e in pack.provenance)
    assert all(canary not in c.provenance.model_dump_json() for c in pack.chunks)
    assert pack.token_count <= pack.token_budget
    effective = engine.expectations(ref, subject="app.payments.read_payment")
    assert canary not in "".join(e.model_dump_json() for e in effective)
    # Authenticated append-only history and the immutable index retain their original bytes.
    assert engine.decision_history(ref, expectation.id)[0].reason == reason
    assert engine.store.get(ref).model_dump_json() == original


@pytest.mark.parametrize(
    ("metadata", "canary"),
    [
        ("Authorization: Bearer metadata-canary", "metadata-canary"),
        ("password=metadata-canary", "metadata-canary"),
        ("https://fixture:metadata-canary@example.invalid", "fixture:metadata-canary"),
    ],
)
def test_free_form_citation_metadata_is_safe_in_structured_and_delimited_output(
    metadata: str, canary: str
) -> None:
    evidence = EvidenceRef(
        kind="source_span",
        path="app/payments.py",
        commit_sha="a" * 40,
        span={"start_line": 1, "end_line": 4},
        symbol="app.payments.read_payment",
        provenance=metadata,
        note=metadata,
    )
    safe = redact_evidence(evidence)
    assert canary not in safe.model_dump_json()
    assert canary not in delimited("source text", evidence)
    assert safe.model_dump(exclude={"note", "provenance"}) == evidence.model_dump(
        exclude={"note", "provenance"}
    )
    assert evidence.note == metadata
    assert evidence.provenance == metadata


def test_redacted_metadata_stays_within_the_canonical_short_text_limit() -> None:
    metadata = "x" * 492 + "Bearer a"
    evidence = EvidenceRef(kind="human_input", provenance=metadata, note=metadata)
    safe = redact_evidence(evidence)
    assert len(safe.provenance) <= 500
    assert safe.note is not None and len(safe.note) <= 500
    assert EvidenceRef.model_validate_json(safe.model_dump_json()) == safe
    assert evidence.note == metadata


def test_empty_citation_note_remains_absent() -> None:
    evidence = EvidenceRef(kind="human_input", provenance="authenticated-human:usr_fixture00")
    assert redact_evidence(evidence) == evidence
