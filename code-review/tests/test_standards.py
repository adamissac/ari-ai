import pytest
from pydantic import ValidationError

from code_review.models import FindingIn, SecurityConcernIn


def test_optional_functional_weakness_is_validated_without_forcing_a_mapping():
    """Catalog validation happens in adjudication, not in the model: one unsuitable optional
    CWE must not void the whole ReviewerReport (Sai's #49 review, blocker 1)."""
    from code_review.standards import classify_weakness_safely
    from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan

    args = dict(
        title="Behavior mismatch",
        claim_key="c1",
        suspected_spans=[dict(source_kind="code", path="app.py")],
        severity="low",
        rationale="Wrong result",
    )
    assert FindingIn(**args).weakness_class is None
    assert FindingIn(**args, weakness_class="CWE-841").weakness_class == "CWE-841"
    # well-formed but unknown / category ids are accepted by the model...
    assert FindingIn(**args, weakness_class="CWE-99999").weakness_class == "CWE-99999"
    SecurityConcernIn(
        title="Concern",
        weakness_class="CWE-99999",
        spans=[dict(source_kind="code", path="app.py")],
        rationale="Unsupported",
    )
    with pytest.raises(ValidationError):
        FindingIn(**args, weakness_class="not-a-cwe")  # format is still enforced
    # ...and adjudication drops them with a reason instead of failing the review.
    ev = [
        EvidenceRef(
            kind=EvidenceKind.source_span,
            path="app.py",
            commit_sha="a" * 40,
            span=SourceSpan(start_line=1, end_line=2),
            provenance="test",
        )
    ]
    ok, why = classify_weakness_safely("CWE-841", ev, 0.6)
    assert ok is not None and why is None and ok.cwe.id == "CWE-841"
    for bad in ("CWE-99999", "CWE-840"):
        std, why = classify_weakness_safely(bad, ev, 0.6)
        assert std is None and why and bad in why
