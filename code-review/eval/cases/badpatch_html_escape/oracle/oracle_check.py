from web.render import render_name


def test_ampersand_and_quotes_are_escaped():
    out = render_name('Tom & "Jerry"')
    assert "&amp;" in out and "&quot;" in out
