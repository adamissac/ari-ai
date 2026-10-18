from exports.files import export_path


def test_plain_name(tmp_path):
    assert export_path(tmp_path, "a.csv") == (tmp_path / "a.csv").resolve()
