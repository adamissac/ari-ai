from catalog.paging import page

ITEMS = [f"p{i}" for i in range(25)]


def test_first_page_holds_first_items():
    assert page(ITEMS, 1) == ITEMS[:10]


def test_last_partial_page():
    assert page(ITEMS, 3) == ITEMS[20:]


def test_past_the_end_is_empty():
    assert page(ITEMS, 9) == []
