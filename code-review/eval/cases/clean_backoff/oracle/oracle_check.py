from hooks.retry import backoff


def test_doubles_from_one():
    assert [backoff(i) for i in range(4)] == [1, 2, 4, 8]


def test_capped():
    assert backoff(10) == 60 and backoff(40) == 60
