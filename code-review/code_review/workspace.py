"""Isolated, SHA-pinned candidate workspaces.

A workspace is a *copy* of the repository tree at an exact commit, exported with
``git archive`` into a temporary directory. It has no ``.git`` and no link back to the
original repository, so nothing the agent does in it can write to the customer repo.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import io
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from code_review.ports import RepoSource

_SHA = re.compile(r"^[0-9a-f]{40}$")
GENERATED_TEST_DIR = "tests/generated"

# Files a repair may never touch: tests, test configuration, packaging and lockfiles.
_PROTECTED_NAMES = {
    "conftest.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "pyproject.toml",
    "noxfile.py",
    "uv.lock",
    "poetry.lock",
    "requirements.txt",
    "Pipfile.lock",
}
_DENY_READ = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|\.git(/.*)?)$")


class WorkspaceError(Exception):
    pass


def is_test_path(rel: str) -> bool:
    p = PurePosixPath(rel)
    return (
        "tests" in p.parts
        or "test" in p.parts
        or p.name.startswith("test_")
        or p.name.endswith("_test.py")
    )


def is_protected_path(rel: str) -> bool:
    return is_test_path(rel) or PurePosixPath(rel).name in _PROTECTED_NAMES


def is_denied_read(rel: str) -> bool:
    return bool(_DENY_READ.search(rel))


def safe_rel(raw: str) -> str:
    """Normalize a model-supplied path to a safe repository-relative POSIX path."""
    if not raw or "\x00" in raw or "\\" in raw:
        raise WorkspaceError(f"invalid path {raw!r}")
    p = PurePosixPath(raw)
    if p.is_absolute() or any(part in ("..", "") for part in p.parts) or str(p) == ".":
        raise WorkspaceError(f"path must be repository-relative without '..': {raw!r}")
    return str(p)


def _git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, timeout=60, check=False
    )
    if proc.returncode != 0:
        raise WorkspaceError(f"git {args[0]} failed: {proc.stderr.decode(errors='replace')[:300]}")
    return proc.stdout


def changed_paths_between(source: RepoSource, base_sha: str | None, head_sha: str) -> list[str]:
    if base_sha is None:
        return []
    out = _git(
        source.local_path, "diff", "--name-only", base_sha, head_sha, "--", source.subdir or "."
    )
    return sorted(line for line in out.decode().splitlines() if line)


def git_diff(source: RepoSource, base_sha: str | None, head_sha: str) -> str:
    if base_sha is None:
        return ""
    return _git(
        source.local_path,
        "diff",
        "--no-color",
        "-U5",
        base_sha,
        head_sha,
        "--",
        source.subdir or ".",
    ).decode(errors="replace")


def tree_digest(source: RepoSource) -> str:
    """Digest of the original repo state (HEAD, index and working tree) to prove no writes."""
    head = _git(source.local_path, "rev-parse", "HEAD").strip()
    status = _git(source.local_path, "status", "--porcelain", "--untracked-files=all")
    refs = _git(source.local_path, "for-each-ref", "--format=%(refname) %(objectname)")
    return hashlib.sha256(head + b"\n" + status + b"\n" + refs).hexdigest()


@dataclass
class Workspace:
    """A writable export of ``source`` at ``commit_sha``. Paths are repository-relative."""

    source: RepoSource
    commit_sha: str
    root: Path
    _owner: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)

    @classmethod
    def export(
        cls, source: RepoSource, commit_sha: str, *, parent: Path | None = None
    ) -> Workspace:
        if not _SHA.match(commit_sha):
            raise WorkspaceError("commit sha must be 40 lowercase hex chars")
        tmp = tempfile.TemporaryDirectory(prefix=f"cr-{commit_sha[:8]}-", dir=parent)
        root = Path(tmp.name).resolve() / "repo"
        root.mkdir()
        pathspec = [source.subdir] if source.subdir else []
        data = _git(source.local_path, "archive", "--format=tar", commit_sha, *pathspec)
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(root, filter="data")
        return cls(source=source, commit_sha=commit_sha, root=root, _owner=tmp)

    def clone(self) -> Workspace:
        tmp = tempfile.TemporaryDirectory(prefix=f"cr-{self.commit_sha[:8]}-copy-")
        root = Path(tmp.name).resolve() / "repo"
        shutil.copytree(self.root, root, symlinks=False)
        return Workspace(source=self.source, commit_sha=self.commit_sha, root=root, _owner=tmp)

    def close(self) -> None:
        if self._owner is not None:
            self._owner.cleanup()
            self._owner = None

    @property
    def project_dir(self) -> Path:
        return self.root / self.source.subdir if self.source.subdir else self.root

    def project_rel(self, rel: str) -> str:
        """Repository-relative path -> path relative to the project root (pytest cwd)."""
        sub = self.source.subdir.strip("/")
        if sub and not (rel == sub or rel.startswith(sub + "/")):
            raise WorkspaceError(f"{rel} is outside the project root {sub}")
        return rel[len(sub) + 1 :] if sub else rel

    def repo_rel(self, project_rel: str) -> str:
        sub = self.source.subdir.strip("/")
        return f"{sub}/{project_rel}" if sub else project_rel

    def path(self, rel: str) -> Path:
        rel = safe_rel(rel)
        p = (self.root / rel).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise WorkspaceError(f"{rel} escapes the workspace")
        return p

    def exists(self, rel: str) -> bool:
        try:
            return self.path(rel).is_file()
        except WorkspaceError:
            return False

    def read(self, rel: str) -> str:
        if is_denied_read(rel):
            raise WorkspaceError(f"reading {rel} is not permitted")
        p = self.path(rel)
        if not p.is_file():
            raise WorkspaceError(f"{rel} does not exist at {self.commit_sha[:12]}")
        return p.read_text(encoding="utf-8", errors="replace")

    def write(self, rel: str, content: str) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def files(self) -> list[str]:
        out = []
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts:
                out.append(p.relative_to(self.root).as_posix())
        return out

    def line_count(self, rel: str) -> int:
        return len(self.read(rel).splitlines())

    def digests(self, paths: list[str] | None = None) -> dict[str, str]:
        targets = paths if paths is not None else self.files()
        return {
            rel: hashlib.sha256(self.path(rel).read_bytes()).hexdigest()
            for rel in targets
            if self.exists(rel)
        }


def unified_diff(base: Workspace, new: Workspace) -> tuple[str, list[str]]:
    """Unified diff (git-style a/ b/ paths) between two workspaces, plus the changed paths."""
    base_files, new_files = set(base.files()), set(new.files())
    chunks: list[str] = []
    changed: list[str] = []
    for rel in sorted(base_files | new_files):
        old = base.read(rel).splitlines(keepends=True) if rel in base_files else []
        cur = new.read(rel).splitlines(keepends=True) if rel in new_files else []
        if old == cur:
            continue
        changed.append(rel)
        chunks.extend(
            difflib.unified_diff(
                old,
                cur,
                fromfile=f"a/{rel}" if rel in base_files else "/dev/null",
                tofile=f"b/{rel}" if rel in new_files else "/dev/null",
            )
        )
    text = "".join(c if c.endswith("\n") else c + "\n" for c in chunks)
    return text, changed


def diff_target_paths(diff_text: str) -> list[str]:
    paths = []
    for line in diff_text.splitlines():
        if line.startswith(("--- ", "+++ ")):
            raw = line[4:].split("\t")[0].strip()
            if raw == "/dev/null":
                continue
            if raw.startswith(("a/", "b/")):
                raw = raw[2:]
            paths.append(safe_rel(raw))
    return sorted(set(paths))


def apply_unified_diff(ws: Workspace, diff_text: str) -> tuple[bool, str]:
    """Apply a unified diff with ``git apply`` inside the workspace (never a repository)."""
    if not diff_text.strip():
        return False, "empty diff"
    try:
        diff_target_paths(diff_text)
    except WorkspaceError as e:
        return False, str(e)
    for args in (["--check"], []):
        proc = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn", *args, "-"],
            cwd=ws.root,
            input=diff_text.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return False, proc.stderr.decode(errors="replace")[:2000]
    return True, "applied"


def docstring_ranges(source: str) -> list[tuple[int, int]]:
    """Line ranges of module/class/function docstrings (used to classify doc citations)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                expr = body[0]
                ranges.append((expr.lineno, expr.end_lineno or expr.lineno))
    return ranges
