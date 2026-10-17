"""Helpers for verifying a reviewer (code_review) patch for a FUNCTIONAL defect.

The reviewer works on repository-relative paths; this package's snapshot root may be a
``build_recipe.json`` ``target_dir`` inside the repository. ``detect_prefix`` finds the
leading directories to drop so the diff applies to the snapshot, deterministically from
the files the diff modifies (they must already exist in the snapshot).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from ..contracts import ErrorCode, PlatformError
from ..sandbox.workspace import SnapshotHandle, diff_paths


def detect_prefix(diff_text: str, snapshot: SnapshotHandle) -> str:
    """Leading path (``""`` or ``"a/b/"``) whose removal makes every modified file exist."""
    modified = [p for p in diff_paths(diff_text) if not p.startswith("/dev/null")]
    existing = [p for p in modified if not _is_test(p)] or modified
    if not existing:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "functional patch modifies no files")
    depth = max(len(PurePosixPath(p).parts) for p in existing)
    for n in range(depth):
        parts = PurePosixPath(existing[0]).parts[:n]
        prefix = "/".join(parts) + "/" if parts else ""
        if all(
            p.startswith(prefix) and (snapshot.root / p[len(prefix) :]).is_file() for p in existing
        ):
            return prefix
    raise PlatformError(
        ErrorCode.SCHEMA_INVALID,
        f"functional patch paths do not map onto the assessed snapshot: {existing[:5]}",
    )


def rebase_path(path: str, prefix: str) -> str:
    if prefix and not path.startswith(prefix):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"{path} is outside {prefix}")
    return path[len(prefix) :]


def rebase_diff(diff_text: str, prefix: str) -> str:
    if not prefix:
        return diff_text
    out = []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            line = line.replace(f" a/{prefix}", " a/").replace(f" b/{prefix}", " b/")
        elif line.startswith(("--- a/", "+++ b/")):
            line = line[:6] + rebase_path(line[6:], prefix)
        out.append(line)
    return "".join(out)


def new_file_diff(files: list[tuple[str, str]]) -> str:
    """A git-style diff that adds each (path, content) as a new file, byte for byte."""
    chunks = []
    for path, content in files:
        lines = content.splitlines(keepends=True)
        chunks.append(f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n")
        chunks.append(f"@@ -0,0 +1,{len(lines)} @@\n")
        for line in lines:
            chunks.append("+" + line)
        if lines and not lines[-1].endswith("\n"):
            chunks.append("\n\\ No newline at end of file\n")
    return "".join(chunks)


def _is_test(path: str) -> bool:
    name = PurePosixPath(path).name
    return "tests" in PurePosixPath(path).parts or name.startswith("test_")
