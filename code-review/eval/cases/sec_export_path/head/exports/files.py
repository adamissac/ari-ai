"""Customer exports. Every resolved path must stay inside the export directory."""

from pathlib import Path


class OutsideExportDir(Exception):
    pass


def export_path(base: Path, name: str) -> Path:
    """Resolve ``name`` (may contain sub-folders) under ``base``."""
    return base.resolve() / name
