"""Canonical additional catalogs and legacy runtime compatibility (offline)."""

import pytest

from standards import catalog, cvss31, owasp_api


@pytest.mark.parametrize("case", catalog.load_json("cvss-v3.1-nvd-vectors.json")["vectors"])
def test_cvss31_published_vectors(case):
    result = cvss31.score_vector(case["vector"])
    assert result.score == case["base_score"]
    assert result.rating == case["rating"]


def test_owasp_api_is_a_distinct_framework_with_conservative_mapping():
    entry = owasp_api.owasp_api("API1:2023")
    assert entry.framework == "owasp_api"
    assert "Authorization" in entry.name
    assert owasp_api.owasp_api_tag("CWE-639").category == "API1:2023"
    assert owasp_api.mapping_problems() == []
    with pytest.raises(catalog.UnknownIdentifier):
        owasp_api.owasp_api("API1:2025")


def test_nist_roe_and_additional_catalogs_are_integrity_checked():
    verified = catalog.verify_all()
    for name in (
        "cvss-v3.1.json",
        "owasp-api-2023.json",
        "nist-sp800-115.json",
        "rules/cwe_owasp_api.json",
    ):
        assert name in verified
    assert catalog.load_json("nist-sp800-115.json")["planning_sections"]
