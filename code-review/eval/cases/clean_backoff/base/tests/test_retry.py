from hooks.retry import CAP_S


def test_cap():
    assert CAP_S == 60
