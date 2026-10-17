"""Pinned snapshots, Patch worktrees and diff artifacts.

Paths supplied by models are always normalised through `safe_rel_path` and
resolved under a platform-chosen root; anything that escapes is rejected with
SANDBOX_POLICY_VIOLATION.
"""

from __future__ import annotations

import difflib
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..contracts import ErrorCode, PlatformError

IGNORED_DIRS = frozenset({".git", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"})


def safe_rel_path(raw: str) -> str:
    """Normalise a model/tool-supplied relative path or raise. Never touches disk."""
    if not raw or len(raw) > 400 or "\x00" in raw or "\\" in raw:
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "invalid path")
    p = PurePosixPath(raw)
    if p.is_absolute():
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "absolute paths are not allowed")
    parts = [part for part in p.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "path escapes root")
    if any(part in IGNORED_DIRS for part in parts):
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "path targets a protected directory")
    return "/".join(parts)


def resolve_under(root: Path, rel: str) -> Path:
    rel = safe_rel_path(rel)
    root_r = root.resolve()
    candidate = (root_r / rel).resolve()
    if candidate != root_r and root_r not in candidate.parents:
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "path escapes root via symlink")
    return candidate


def _iter_files(root: Path) -> list[str]:
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if p.is_file() and not p.is_symlink():
            out.append(rel.as_posix())
    return out


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for rel in _iter_files(root):
        h.update(rel.encode())
        h.update(b"\0")
        h.update((root / rel).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        symlinks=False,
        ignore=shutil.ignore_patterns(*IGNORED_DIRS),
        dirs_exist_ok=False,
    )


@dataclass(frozen=True)
class SnapshotHandle:
    """A read-only, pinned copy of the target repository at one commit."""

    snapshot_id: str
    repo_id: str
    commit_sha: str
    root: Path
    pinned_by: str  # "git" (real commit) or "directory-digest" (dev/test only)

    @classmethod
    def from_git(cls, repo: Path, sha: str, subdir: str, dest: Path, *, snapshot_id: str, repo_id: str) -> SnapshotHandle:
        full = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", f"{sha}^{{commit}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        dest.mkdir(parents=True, exist_ok=False)
        archive = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", full, subdir],
            check=True, capture_output=True,
        ).stdout
        with tempfile.NamedTemporaryFile(suffix=".tar") as tf:
            tf.write(archive)
            tf.flush()
            with tarfile.open(tf.name) as tar:
                tar.extractall(dest, filter="data")
        root = dest / subdir
        _make_read_only(root)
        return cls(snapshot_id=snapshot_id, repo_id=repo_id, commit_sha=full, root=root, pinned_by="git")

    @classmethod
    def from_directory(cls, src: Path, dest: Path, *, snapshot_id: str, repo_id: str) -> SnapshotHandle:
        """Pin a directory (dev/demo only; no git history).

        `commit_sha` is the first 40 hex characters of the tree digest so the
        value satisfies the canonical 40-hex `commit_sha` contract; the real
        provenance is `pinned_by="directory-digest"`, never a git commit.
        """
        copy_tree(src, dest)
        _make_read_only(dest)
        return cls(
            snapshot_id=snapshot_id,
            repo_id=repo_id,
            commit_sha=tree_digest(dest)[:40],
            root=dest,
            pinned_by="directory-digest",
        )

    def files(self) -> list[str]:
        return _iter_files(self.root)

    def exists(self, rel: str) -> bool:
        try:
            return resolve_under(self.root, rel).is_file()
        except PlatformError:
            return False

    def line_count(self, rel: str) -> int:
        return len(resolve_under(self.root, rel).read_text(encoding="utf-8", errors="replace").splitlines())


def _make_read_only(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            p.chmod(0o444)


def fresh_checkout(snapshot: SnapshotHandle, dest: Path) -> Path:
    """Writable copy of the pinned snapshot (for a Patch worktree or a Verify run)."""
    copy_tree(snapshot.root, dest)
    for p in dest.rglob("*"):
        if p.is_file():
            p.chmod(0o644)
    return dest


# --------------------------------------------------------------------------- diffs


def _read_lines(p: Path) -> list[str] | None:
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8").splitlines(keepends=True)


def unified_diff(base_root: Path, new_root: Path, paths: list[str]) -> str:
    """git-apply-compatible unified diff for `paths` between two trees."""
    chunks: list[str] = []
    for rel in sorted(set(paths)):
        a = _read_lines(base_root / rel)
        b = _read_lines(new_root / rel)
        if a == b:
            continue
        chunks.append(f"diff --git a/{rel} b/{rel}\n")
        if a is None:
            chunks.append("new file mode 100644\n")
        elif b is None:
            chunks.append("deleted file mode 100644\n")
        lines = list(
            difflib.unified_diff(
                a or [],
                b or [],
                fromfile=f"a/{rel}" if a is not None else "/dev/null",
                tofile=f"b/{rel}" if b is not None else "/dev/null",
                n=3,
            )
        )
        for line in lines:
            if line.endswith("\n"):
                chunks.append(line)
            else:
                chunks.append(line + "\n\\ No newline at end of file\n")
    return "".join(chunks)


def changed_paths(base_root: Path, new_root: Path) -> list[str]:
    base = set(_iter_files(base_root))
    new = set(_iter_files(new_root))
    out = []
    for rel in sorted(base | new):
        if rel not in base or rel not in new or (base_root / rel).read_bytes() != (new_root / rel).read_bytes():
            out.append(rel)
    return out


def diff_paths(diff_text: str) -> list[str]:
    """Paths touched by a git-style diff (both sides), normalised and validated."""
    out: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" ")
            for token in parts[2:4]:
                if token.startswith(("a/", "b/")):
                    out.add(safe_rel_path(token[2:]))
        elif line.startswith(("--- ", "+++ ")):
            token = line[4:].split("\t", 1)[0].strip()
            if token != "/dev/null" and token.startswith(("a/", "b/")):
                out.add(safe_rel_path(token[2:]))
    return sorted(out)


def apply_diff(root: Path, diff_text: str) -> tuple[bool, str]:
    """Apply a diff to `root` with `git apply` (trusted host tool; executes no repo code)."""
    diff_paths(diff_text)  # validates every path first
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as fh:
        fh.write(diff_text)
        patch_file = fh.name
    # Never let git discover an enclosing repository: paths stay relative to `root`.
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "GIT_CEILING_DIRECTORIES": str(root.resolve().parent)}
    try:
        check = subprocess.run(
            ["git", "apply", "--check", "--whitespace=nowarn", patch_file],
            cwd=root, capture_output=True, text=True, timeout=30, env=env,
        )
        if check.returncode != 0:
            return False, check.stderr.strip()[:2000]
        res = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", patch_file],
            cwd=root, capture_output=True, text=True, timeout=30, env=env,
        )
        return res.returncode == 0, res.stderr.strip()[:2000]
    finally:
        Path(patch_file).unlink(missing_ok=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
