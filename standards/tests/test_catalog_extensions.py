import pytest

from standards import catalog


def test_pinned_integrity():
    catalog.verify_integrity()


@pytest.mark.parametrize(
    ("lookup", "identifier"),
    [
        (catalog.attack_technique, "T1078"),
        (catalog.d3fend_technique, "D3-NI"),
        (catalog.cwe, "CWE-639"),
        (catalog.capec, "CAPEC-1"),
        (catalog.owasp_llm, "LLM01:2025"),
    ],
)
def test_official_ids(lookup, identifier):
    result = lookup(identifier)
    assert result.id == identifier and result.name and result.catalog_version
    result.detail["mutated"] = True
    assert "mutated" not in lookup(identifier).detail


@pytest.mark.parametrize(
    ("lookup", "identifier"),
    [
        (catalog.attack_technique, "T9999"),
        (catalog.cwe, "CWE-99999"),
        (catalog.owasp_llm, "LLM01:2024"),
    ],
)
def test_unknown_rejected(lookup, identifier):
    with pytest.raises(KeyError):
        lookup(identifier)


def test_category_and_retired_status_available_for_historical_reading():
    assert catalog.cwe("CWE-840").detail["kind"] == "category"


def test_official_d3fend_relationships_resolve():
    data = catalog.load_json("attack-d3fend.json")
    for source, targets in data.items():
        catalog.attack_technique(source)
        for target in targets:
            catalog.d3fend_technique(target)


def test_idor_is_not_given_an_invented_attack_chain():
    assert catalog.capec_for_cwe("CWE-639") == []
    assert catalog.attack_for_capec("CAPEC-1")


def test_rules_are_proposed_defenses_and_conservative():
    assert catalog.rl_d3fend("isolate")[0].id == "D3-NI"
    assert catalog.rl_d3fend("noop") == []
    assert catalog.fortify_d3fend("config") == []
