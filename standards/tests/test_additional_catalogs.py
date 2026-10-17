"""Canonical additional catalogs (offline)."""

import pytest

from standards import catalog, owasp_api


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


def test_project_mapping_returns_independent_lists():
    original = owasp_api.project_mapping()["API1:2023"]
    owasp_api.project_mapping()["API1:2023"].append("CWE-99999")
    assert owasp_api.project_mapping()["API1:2023"] == original


def test_sarif_schema_is_pinned_with_its_oasis_stage_and_notice():
    from standards.catalog import load_json, manifest

    data = load_json("sarif-2.1.0.json")
    assert data["version"] == "2.1.0"
    assert data["stage"] == "OASIS Standard incorporating Approved Errata"
    assert data["date"] == "28 August 2023"
    assert data["notice"].startswith("Copyright © OASIS Open")
    assert "2.1.0" in data["schema"]["title"]
    entry = manifest()["files"]["sarif-2.1.0.json"]
    assert len(entry["upstream"]) == 2 and all(len(u["sha256"]) == 64 for u in entry["upstream"])
