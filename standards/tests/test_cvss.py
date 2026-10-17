import pytest

from standards import catalog, cvss4


def test_first_javascript_oracle_vectors():
    data = catalog.load_json("cvss-v4.0-first-js-golden.json")
    assert len(data["vectors"]) == 3047
    for example in data["vectors"]:
        assert cvss4.score(example["vector"]).score == example["score"]


def test_explicit_vector_and_invalid_inputs():
    metrics = dict(
        AV="N", AC="L", AT="N", PR="N", UI="N", VC="H", VI="H", VA="H", SC="H", SI="H", SA="H"
    )
    result = cvss4.score(cvss4.build_vector(metrics))
    assert result.score == 10.0 and result.severity == "critical"
    with pytest.raises(ValueError):
        cvss4.build_vector({"AV": "N"})
    with pytest.raises(ValueError):
        cvss4.score(result.vector + "/AV:N")


def test_published_example_disagreements_are_not_hidden():
    examples = catalog.load_json("cvss-v4.0-first-examples.json")["examples"]
    matching = [e for e in examples if cvss4.score(e["vector"]).score == e.get("detail_score")]
    assert len(examples) == 47
    assert len(matching) == 39
    oracle = {
        e["vector"]: e["score"]
        for e in catalog.load_json("cvss-v4.0-first-js-golden.json")["vectors"]
    }
    for example in examples:
        assert cvss4.score(example["vector"]).score == oracle[example["vector"]]
    # The page contains inconsistent headline, table, and detail scores; the
    # independently generated FIRST JavaScript oracle above is authoritative.
    assert any(
        e.get("table_score") != e.get("detail_score") for e in examples if "table_score" in e
    )
