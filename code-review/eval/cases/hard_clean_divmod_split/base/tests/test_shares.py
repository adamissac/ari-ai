import pytest
from split.shares import split


def test_even_split():
    assert split(900, 3) == [300, 300, 300]


def test_leftover_cents_go_to_the_first_people():
    assert split(1000, 3) == [334, 333, 333]


def test_nobody_to_split_with():
    with pytest.raises(ValueError):
        split(100, 0)
