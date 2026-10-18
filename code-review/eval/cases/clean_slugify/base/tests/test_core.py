from urls.core import BASE


def test_base():
    assert BASE.startswith("https://")
