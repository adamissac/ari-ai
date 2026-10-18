from urls.slug import slugify


def test_basic():
    assert slugify("Red Lamp") == "red-lamp"


def test_runs_collapse_and_trim():
    assert slugify("  --Big   Mug!! ") == "big-mug"
