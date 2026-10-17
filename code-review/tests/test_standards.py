import pytest
from pydantic import ValidationError

from code_review.models import FindingIn, SecurityConcernIn


def test_optional_functional_weakness_is_validated_without_forcing_a_mapping():
    args = dict(
        title="Behavior mismatch",
        claim_key="c1",
        suspected_spans=[dict(source_kind="code", path="app.py")],
        severity="low",
        rationale="Wrong result",
    )
    assert FindingIn(**args).weakness_class is None
    assert FindingIn(**args, weakness_class="CWE-841").weakness_class == "CWE-841"
    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        FindingIn(**args, weakness_class="CWE-99999")
    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        SecurityConcernIn(
            title="Concern",
            weakness_class="CWE-99999",
            spans=[dict(source_kind="code", path="app.py")],
            rationale="Unsupported",
        )
