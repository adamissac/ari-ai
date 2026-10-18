from web.render import render_name


def test_plain():
    assert render_name("Ann") == "<span class=name>Ann</span>"
