"""Concurrent identical evidence must produce independently readable artifact refs."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from backend import artifacts as artifact_module
from backend.artifacts import ArtifactStore
from backend.db import transaction
from shared.evidence import ArtifactKind


def test_identical_concurrent_artifacts_are_both_readable(monkeypatch, tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path.as_uri())
    barrier = Barrier(2)
    replace = artifact_module.os.replace

    def concurrent_replace(source, destination):
        barrier.wait(timeout=10)
        return replace(source, destination)

    monkeypatch.setattr(artifact_module.os, "replace", concurrent_replace)

    def write(_):
        with transaction() as conn:
            return store.put_text(
                conn, "identical synthetic log", kind=ArtifactKind.log, project_id=None
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(write, range(2)))
    assert refs[0].id != refs[1].id
    assert refs[0].sha256 == refs[1].sha256
    with transaction() as conn:
        for ref in refs:
            meta, data = store.get(conn, ref.id)
            assert data == b"identical synthetic log"
            assert meta["sha256"] == ref.sha256
    assert len(list(tmp_path.rglob("*.*"))) == 0, "temporary files must be cleaned up"


def test_failed_artifact_publish_cleans_temporary_file(monkeypatch, tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path.as_uri())

    def fail_replace(*args):
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(artifact_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic publication failure"), transaction() as conn:
        store.put_text(conn, "synthetic log", kind=ArtifactKind.log, project_id=None)
    assert not list(tmp_path.rglob("*.*"))
