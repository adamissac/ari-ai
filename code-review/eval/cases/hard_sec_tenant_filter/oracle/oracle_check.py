from docs.models import Doc, User
from docs.store import list_documents


def test_an_unfiltered_list_shows_only_the_callers_tenant():
    docs = [Doc("d1", "acme", "draft", "Plan"), Doc("d3", "globex", "final", "Merger")]
    assert [d.id for d in list_documents(docs, User("u1", "acme"))] == ["d1"]
