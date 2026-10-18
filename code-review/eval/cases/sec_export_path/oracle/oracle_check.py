import pytest
from exports.files import OutsideExportDir, export_path


def test_parent_escape_is_refused(tmp_path):
    with pytest.raises(OutsideExportDir):
        export_path(tmp_path / "exports", "../secrets.txt")
