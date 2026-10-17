"""CVSS v4.0 port against FIRST's published examples and FIRST's own calculator output."""

from __future__ import annotations

import pytest

from standards import cvss4
from standards.catalog import load_json
from standards.cvss4 import CVSSVectorError

GOLDEN = load_json("cvss-v4.0-first-js-golden.json")
EXAMPLES = load_json("cvss-v4.0-first-examples.json")["examples"]
REFERENCE = {v["vector"]: v["score"] for v in GOLDEN["vectors"]}


def test_golden_file_is_large_and_pinned_to_first_commit() -> None:
    assert len(GOLDEN["vectors"]) >= 3000
    assert "c5b0d409ae9f57c44264c6ce5f27d89298e1d32a" in GOLDEN["generator"]


def test_matches_first_reference_calculator_on_every_golden_vector() -> None:
    diffs = [
        (v["vector"], v["score"], cvss4.score(v["vector"]).score)
        for v in GOLDEN["vectors"]
        if cvss4.score(v["vector"]).score != v["score"]
    ]
    assert diffs == []


@pytest.mark.parametrize(
    "example",
    [e for e in EXAMPLES if e.get("table_score") is not None],
    ids=lambda e: e["vector"],
)
def test_first_examples_comparison_table_scores(example: dict[str, object]) -> None:
    assert cvss4.score(str(example["vector"])).score == example["table_score"]


def test_first_examples_page_inconsistencies_are_explained_by_the_reference_code() -> None:
    """Where the page's detail heading disagrees with us, FIRST's own code agrees with us."""
    disagreements = [e for e in EXAMPLES if cvss4.score(e["vector"]).score != e["detail_score"]]
    assert len(disagreements) <= 8
    for e in disagreements:
        assert REFERENCE[e["vector"]] == cvss4.score(e["vector"]).score
        if e.get("table_score") is not None:
            assert e["table_score"] == cvss4.score(e["vector"]).score


@pytest.mark.parametrize(
    ("vector", "expected", "severity"),
    [
        ("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H", 10.0, "critical"),
        ("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N", 0.0, "none"),
        ("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N", 9.3, "critical"),
    ],
)
def test_known_scores(vector: str, expected: float, severity: str) -> None:
    result = cvss4.score(vector)
    assert (result.score, result.severity) == (expected, severity)
    assert result.nomenclature == "CVSS-B"


def test_nomenclature_tracks_threat_and_environmental_groups() -> None:
    base = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
    assert cvss4.score(base + "/E:U").nomenclature == "CVSS-BT"
    assert cvss4.score(base + "/CR:L").nomenclature == "CVSS-BE"
    assert cvss4.score(base + "/E:U/CR:L").nomenclature == "CVSS-BTE"
    assert cvss4.score(base + "/E:U").score < cvss4.score(base).score


@pytest.mark.parametrize(
    "vector",
    [
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N",
        "CVSS:4.0/AC:L/AV:N/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
        "CVSS:4.0/AV:N/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
        "CVSS:4.0/AV:Q/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/ZZ:1",
        "",
    ],
)
def test_malformed_vectors_are_rejected(vector: str) -> None:
    with pytest.raises(CVSSVectorError):
        cvss4.score(vector)


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (0.0, "none"),
        (0.1, "low"),
        (3.9, "low"),
        (4.0, "medium"),
        (6.9, "medium"),
        (7.0, "high"),
        (8.9, "high"),
        (9.0, "critical"),
        (10.0, "critical"),
    ],
)
def test_severity_bands(score: float, label: str) -> None:
    assert cvss4.severity(score) == label


def test_build_vector_round_trips() -> None:
    vector = "CVSS:4.0/AV:L/AC:H/AT:P/PR:L/UI:A/VC:L/VI:N/VA:H/SC:L/SI:H/SA:N/E:P"
    assert cvss4.build_vector(cvss4.parse_vector(vector)) == vector
