from docs.models import Doc, User
from docs.store import list_documents

DOCS = [
    Doc("d1", "acme", "draft", "Plan"),
    Doc("d2", "acme", "final", "Budget plan"),
    Doc("d3", "globex", "final", "Merger plan"),
]


def test_title_search_ignores_case_and_tenant_boundaries_hold():
    found = list_documents(DOCS, User("u1", "acme"), title_contains="PLAN")
    assert [d.id for d in found] == ["d2", "d1"]


def test_filters_combine():
    found = list_documents(DOCS, User("u1", "acme"), status="draft", title_contains="plan")
    assert [d.id for d in found] == ["d1"]
