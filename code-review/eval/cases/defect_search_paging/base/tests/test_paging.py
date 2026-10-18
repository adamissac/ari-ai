from catalog.paging import page


def test_rejects_page_zero():
    import pytest

    with pytest.raises(ValueError):
        page(["a"], 0)
