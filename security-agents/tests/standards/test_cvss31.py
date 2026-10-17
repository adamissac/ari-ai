from __future__ import annotations

import itertools

import pytest

from security_agents.standards import cvss, registry

pytestmark = pytest.mark.standards

VECTORS = registry.load("cvss31_vectors")["vectors"]


def test_at_least_ten_official_vectors_are_pinned():
    assert len(VECTORS) >= 10
    assert sum(1 for v in VECTORS if "/S:C/" in v["vector"]) >= 1


@pytest.mark.parametrize("case", VECTORS, ids=[f"{v['cve']}" for v in VECTORS])
def test_calculator_reproduces_the_published_base_score(case):
    result = cvss.score_vector(case["vector"])
    assert result.score == case["base_score"], case
    assert result.rating == case["rating"], case


@pytest.mark.parametrize(
    "value,expected",
    [(4.02, 4.1), (4.00, 4.0), (4.000001, 4.0), (4.000011, 4.1), (0.0, 0.0), (9.99, 10.0), (1.2000003, 1.2)],
)
def test_roundup_follows_the_specification(value, expected):
    assert cvss.roundup(value) == expected


def test_roundup_avoids_floating_point_artifacts():
    assert cvss.roundup(0.1 + 0.2) == 0.3


def test_vector_round_trips_in_canonical_order():
    metrics = cvss.parse_vector("CVSS:3.1/C:H/I:N/A:N/AV:N/AC:L/PR:L/UI:N/S:U")
    assert metrics.vector() == "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"


@pytest.mark.parametrize(
    "vector,message",
    [
        ("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "must start with"),
        ("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "must start with"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H", "missing mandatory"),
        ("CVSS:3.1/AV:N/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "more than once"),
        ("CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "not a CVSS v3.1 base metric value"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/E:F", "base score only"),
    ],
)
def test_malformed_vectors_are_rejected(vector, message):
    with pytest.raises(cvss.CvssError, match=message):
        cvss.score_vector(vector)


ALL_VECTORS = [
    dict(zip(cvss.BASE_ORDER, combo, strict=True))
    for combo in itertools.product(*(cvss.ALLOWED[key] for key in cvss.BASE_ORDER))
]


def test_every_score_is_between_zero_and_ten_with_one_decimal():
    for values in ALL_VECTORS:
        score = cvss.base_score(cvss.BaseMetrics(**values)).score
        assert 0.0 <= score <= 10.0
        assert round(score, 1) == score


def test_rating_bands_match_the_specification_table():
    bands = registry.load("cvss31")["rating_bands"]
    assert [(b["rating"], b["min"], b["max"]) for b in bands] == [
        ("none", 0.0, 0.0),
        ("low", 0.1, 3.9),
        ("medium", 4.0, 6.9),
        ("high", 7.0, 8.9),
        ("critical", 9.0, 10.0),
    ]
    for values in ALL_VECTORS:
        result = cvss.base_score(cvss.BaseMetrics(**values))
        band = next(b for b in bands if b["min"] <= result.score <= b["max"])
        assert result.rating == band["rating"]


def test_no_impact_means_a_zero_score():
    for values in ALL_VECTORS:
        if values["C"] == values["I"] == values["A"] == "N":
            assert cvss.base_score(cvss.BaseMetrics(**values)).score == 0.0


@pytest.mark.parametrize("metric", ["C", "I", "A"])
def test_raising_an_impact_metric_never_lowers_the_score(metric):
    ladder = ["N", "L", "H"]
    for values in ALL_VECTORS:
        current = ladder.index(values[metric])
        if current == len(ladder) - 1:
            continue
        higher = {**values, metric: ladder[current + 1]}
        before = cvss.base_score(cvss.BaseMetrics(**values)).score
        after = cvss.base_score(cvss.BaseMetrics(**higher)).score
        assert after >= before, (values, metric)


def test_easier_exploitation_never_lowers_the_score():
    easier = {"AV": ["P", "L", "A", "N"], "AC": ["H", "L"], "PR": ["H", "L", "N"], "UI": ["R", "N"]}
    for metric, ladder in easier.items():
        for values in ALL_VECTORS:
            current = ladder.index(values[metric])
            if current == len(ladder) - 1:
                continue
            higher = {**values, metric: ladder[current + 1]}
            assert (
                cvss.base_score(cvss.BaseMetrics(**higher)).score
                >= cvss.base_score(cvss.BaseMetrics(**values)).score
            ), (values, metric)


def test_weights_come_from_the_pinned_specification():
    weights = registry.load("cvss31")["weights"]
    assert weights["AV"] == {"Network": 0.85, "Adjacent": 0.62, "Local": 0.55, "Physical": 0.2}
    assert weights["PR_scope_changed"]["Low"] == 0.68
    assert registry.load("cvss31")["equations_quoted"]["roundup_appendix_a"].startswith("function Roundup")


def test_score_is_labelled_base_score_only():
    result = cvss.score_vector("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N")
    assert result.kind == "CVSS v3.1 base score only (severity, not risk)"
    assert cvss.severity_level(result) == "medium"


def test_every_published_score_carries_its_vector():
    for values in ALL_VECTORS[:200]:
        result = cvss.base_score(cvss.BaseMetrics(**values))
        assert result.vector.startswith("CVSS:3.1/") and result.score is not None
