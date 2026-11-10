from docs.models import Doc, User
from docs.store import list_documents

DOCS = [
    Doc("d1", "acme", "draft", "Plan"),
    Doc("d2", "acme", "final", "Budget"),
    Doc("d3", "globex", "final", "Merger"),
]


def test_status_filter_stays_inside_the_tenant():
    found = list_documents(DOCS, User("u1", "acme"), status="final")
    assert [d.id for d in found] == ["d2"]


def test_results_are_sorted_by_title():
    own = [Doc("a", "acme", "draft", "Zed"), Doc("b", "acme", "draft", "Alpha")]
    assert [d.id for d in list_documents(own, User("u1", "acme"))] == ["b", "a"]
