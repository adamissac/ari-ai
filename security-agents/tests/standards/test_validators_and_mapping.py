from __future__ import annotations

import pytest

from security_agents.standards import mapping, registry
from security_agents.standards.validators import (
    StandardsViolation,
    validate_attack_technique,
    validate_cwe,
    validate_d3fend,
    validate_owasp_api,
    validate_owasp_llm,
)

pytestmark = pytest.mark.standards


def test_known_cwe_is_accepted_with_its_catalog_metadata():
    record = validate_cwe("CWE-639")
    assert record.name == "Authorization Bypass Through User-Controlled Key"
    assert record.mapping_usage == "Allowed"
    assert record.catalog_version == "4.20"
    assert record.needs_review is False


def test_allowed_with_review_is_accepted_and_flagged():
    record = validate_cwe("CWE-863")
    assert record.mapping_usage == "Allowed-with-Review"
    assert record.needs_review is True


@pytest.mark.parametrize("identifier", ["CWE-99999", "CWE-0", "CWE-123456"])
def test_invented_cwe_is_rejected(identifier):
    with pytest.raises(StandardsViolation, match="not"):
        validate_cwe(identifier)


@pytest.mark.parametrize("identifier", ["CWE-840", "CWE-16", "CWE-1059"])
def test_cwe_marked_prohibited_by_mitre_is_rejected(identifier):
    with pytest.raises(StandardsViolation, match="Prohibited"):
        validate_cwe(identifier)


@pytest.mark.parametrize("identifier", ["CWE-284", "CWE-285", "CWE-287", "CWE-20", "CWE-200"])
def test_cwe_marked_discouraged_by_mitre_is_rejected(identifier):
    with pytest.raises(StandardsViolation, match="Discouraged"):
        validate_cwe(identifier)


@pytest.mark.parametrize("identifier", ["639", "cwe-639", "CWE639", "CWE-", ""])
def test_malformed_cwe_is_rejected(identifier):
    with pytest.raises(StandardsViolation):
        validate_cwe(identifier)


def test_known_attack_technique_and_sub_technique():
    technique = validate_attack_technique("T1190")
    assert technique.name == "Exploit Public-Facing Application"
    assert technique.version == "20.0"
    sub = next(k for k, v in registry.load("attack_enterprise")["techniques"].items() if v["sub_technique"] and not v["revoked"] and not v["deprecated"])
    assert validate_attack_technique(sub).sub_technique is True


@pytest.mark.parametrize("identifier", ["T9999", "T0000", "T1190.999", "TA0001", "T190", ""])
def test_invented_or_malformed_attack_technique_is_rejected(identifier):
    with pytest.raises(StandardsViolation):
        validate_attack_technique(identifier)


def test_revoked_or_deprecated_attack_technique_is_rejected():
    techniques = registry.load("attack_enterprise")["techniques"]
    retired = [k for k, v in techniques.items() if v["revoked"] or v["deprecated"]]
    assert retired, "the pinned bundle should contain retired techniques to test against"
    for identifier in retired[:5]:
        with pytest.raises(StandardsViolation, match="revoked|deprecated"):
            validate_attack_technique(identifier)


def test_d3fend_validation():
    assert validate_d3fend("D3-AMED").label == "Access Mediation"
    assert validate_d3fend("D3-DLV").label == "Domain Logic Validation"
    for identifier in ("D3-NOPE", "D3-", "AMED", "D3-amed"):
        with pytest.raises(StandardsViolation):
            validate_d3fend(identifier)


def test_owasp_validation():
    assert validate_owasp_api("API1:2023").title == "Broken Object Level Authorization"
    assert validate_owasp_llm("LLM01:2025").title == "Prompt Injection"
    for identifier in ("API11:2023", "API1:2019", "API1"):
        with pytest.raises(StandardsViolation):
            validate_owasp_api(identifier)
    for identifier in ("LLM11:2025", "LLM01:2023", "LLM1:2025"):
        with pytest.raises(StandardsViolation):
            validate_owasp_llm(identifier)


def test_every_cwe_in_the_owasp_table_exists_and_is_permitted_by_mitre():
    for category, cwes in mapping.CWE_TO_OWASP_API_2023.items():
        validate_owasp_api(category)
        for cwe in cwes:
            record = validate_cwe(cwe)
            assert record.kind == "weakness", cwe
            assert record.mapping_usage in ("Allowed", "Allowed-with-Review"), (cwe, record.mapping_usage)


def test_owasp_table_covers_every_category_or_explains_why_not():
    categories = set(registry.load("owasp_api")["categories"])
    assert set(mapping.CWE_TO_OWASP_API_2023) == categories
    for category, cwes in mapping.CWE_TO_OWASP_API_2023.items():
        if not cwes:
            assert category in mapping.UNMAPPED_REASONS


def test_each_cwe_maps_to_at_most_one_category():
    seen = mapping.mapped_cwes()
    assert len(seen) == len(set(seen))


def test_owasp_tag_is_labelled_project_mapping():
    tag = mapping.owasp_api_tag("CWE-639")
    assert tag.category == "API1:2023"
    assert tag.kind == "project mapping"
    unmapped = mapping.owasp_api_tag("CWE-1284")
    assert unmapped.category is None
    assert "no applicable" in unmapped.note
