"""Regression archives must come from an unchanged, accepted Verify workspace."""

from types import SimpleNamespace

import pytest

from security_agents.contracts import VerificationCheck, VerificationCheckName, VerificationResult
from security_agents.regressions import (
    RegressionEvidenceUnavailable,
    read_sources,
    verified_bundle,
)


def objects():
    candidate = SimpleNamespace(
        id="pat_test", finding_id="fnd_test", tests_added=["tests/test_regression.py"]
    )
    verification = VerificationResult(
        patch_id=candidate.id,
        verdict="accepted",
        verify_run_id="run_verify",
        sandbox_run_ids=["sbx_run"],
        checks=[VerificationCheck(name=name, passed=True) for name in VerificationCheckName],
    )
    return candidate, verification


def test_archive_retains_actual_sources_and_original_hash(tmp_path):
    import hashlib

    (tmp_path / "tests").mkdir()
    source = "def test_regression():\n    assert True\n"
    (tmp_path / "tests/test_regression.py").write_text(source)
    candidate, verification = objects()
    initial = read_sources(tmp_path, candidate.tests_added)
    bundle = verified_bundle(candidate, verification, tmp_path, initial)
    assert bundle["tests"][0]["source"] == source
    assert (
        bundle["tests"][0]["original_verified_source_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    )
    assert bundle["verify_run_id"] == verification.verify_run_id
    assert "individual node execution is not claimed" in bundle["limitations"]
    (tmp_path / "tests/test_regression.py").write_text("assert False")
    with pytest.raises(RegressionEvidenceUnavailable, match="changed"):
        verified_bundle(candidate, verification, tmp_path, initial)


@pytest.mark.parametrize("path", ["../outside.py", "/etc/passwd", "tests/missing.py", "app.py"])
def test_missing_or_escaping_source_is_not_archived(tmp_path, path):
    from security_agents.contracts import PlatformError

    with pytest.raises((RegressionEvidenceUnavailable, PlatformError)):
        read_sources(tmp_path, [path])


def test_symlink_and_empty_test_lists_are_not_archived(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "outside.py").write_text("assert True")
    (tmp_path / "tests/test_link.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(RegressionEvidenceUnavailable, match="symlink"):
        read_sources(tmp_path, ["tests/test_link.py"])
    with pytest.raises(RegressionEvidenceUnavailable):
        read_sources(tmp_path, [])


def test_rejected_or_incomplete_verification_has_no_archive(tmp_path):
    candidate, verification = objects()
    verification.verdict = "rejected"
    with pytest.raises(RegressionEvidenceUnavailable, match="accepted"):
        verified_bundle(candidate, verification, tmp_path, {})
    verification.verdict = "accepted"
    verification.checks = verification.checks[:1]
    with pytest.raises(RegressionEvidenceUnavailable, match="all checks"):
        verified_bundle(candidate, verification, tmp_path, {})
