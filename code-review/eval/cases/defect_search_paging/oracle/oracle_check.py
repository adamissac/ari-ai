from catalog.paging import search

ITEMS = ["red lamp", "Red chair", "blue lamp", "red mug"]


def test_first_search_page_holds_first_hits():
    assert search(ITEMS, "red", 1, per_page=2) == ["red lamp", "Red chair"]
