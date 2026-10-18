"""Customer exports. Every resolved path must stay inside the export directory."""

from pathlib import Path


class OutsideExportDir(Exception):
    pass


def export_path(base: Path, name: str) -> Path:
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise OutsideExportDir(name)
    return path
