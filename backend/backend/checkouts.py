"""Checkouts of connected GitHub repositories, fetched on demand at an exact commit.

The reviewer, code intelligence and the security agents all read repositories from the
operator's bindings file (`REPOSITORY_BINDINGS_FILE`, entries `{repo_id, local_path,
subdir}`) and archive the commit they need with `git archive`. For a repository connected
through the GitHub App this module keeps a bare clone under `SECURITY_WORKDIR/repos`,
fetches exactly the requested commit with a short-lived read-only installation token, and
adds the repository to the bindings file, so every consumer works unchanged.

The token is sent as an HTTP header for the one fetch and never written to git config,
the bindings file or logs. Nothing fetched here is executed on this host.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import sqlalchemy as sa

from backend.db import repositories, transaction
from backend.settings import Settings, get_settings
from shared.errors import ErrorCode

FULL_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CheckoutError(RuntimeError):
    """The repository could not be fetched at the requested commit."""

    code = ErrorCode.SNAPSHOT_NOT_READY


TokenFor = Callable[[int], str]


def auth_env(token: str) -> dict[str, str]:
    """Hand git the token as an HTTP header through the environment, not argv (argv is
    visible to every process on the host via ps)."""
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {auth}",
    }


def _git(
    *args: str,
    cwd: Path | None = None,
    timeout: float = 300,
    extra_env: dict[str, str] | None = None,
) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(extra_env or {})
    proc = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        # stderr can echo the remote URL but never the header, which is not logged by git.
        raise CheckoutError(f"git {args[0]} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def _has_commit(repo: Path, sha: str) -> bool:
    try:
        _git("-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}")
    except CheckoutError:
        return False
    return True


def fetch_commit(
    repo_dir: Path,
    full_name: str,
    sha: str,
    token: str,
    *,
    github_web_url: str = "https://github.com",
) -> Path:
    """Ensure the bare repository at `repo_dir` contains `sha`. Returns `repo_dir`."""
    if not FULL_NAME_RE.match(full_name):
        raise CheckoutError(f"invalid repository name {full_name!r}")
    if not SHA_RE.match(sha):
        raise CheckoutError("commit must be a full 40-character SHA")
    if not (repo_dir / "HEAD").is_file():
        repo_dir.mkdir(parents=True, exist_ok=True)
        _git("init", "--bare", "--quiet", str(repo_dir))
    if _has_commit(repo_dir, sha):
        return repo_dir
    _git(
        "-C",
        str(repo_dir),
        "fetch",
        "--quiet",
        "--depth=1",
        "--no-tags",
        f"{github_web_url.rstrip('/')}/{full_name}.git",
        sha,
        extra_env=auth_env(token),
    )
    if not _has_commit(repo_dir, sha):
        raise CheckoutError(f"{full_name} has no commit {sha}")
    return repo_dir


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(path.suffix + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def register_binding(bindings_file: Path, repo_id: str, local_path: Path) -> None:
    """Add or update `{repo_id, local_path}` in the bindings file, atomically."""
    with _locked(bindings_file):
        entries: list[dict[str, object]] = []
        if bindings_file.is_file():
            entries = list(json.loads(bindings_file.read_text(encoding="utf-8") or "[]"))
        entry = {"repo_id": repo_id, "local_path": str(local_path), "subdir": "."}
        others = [e for e in entries if e.get("repo_id") != repo_id]
        current = next((e for e in entries if e.get("repo_id") == repo_id), None)
        if current == entry:
            return
        fd, tmp = tempfile.mkstemp(dir=bindings_file.parent, prefix=".bindings-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump([*others, entry], f, indent=2)
        os.replace(tmp, bindings_file)


def ensure_checkout(
    repo_id: str,
    commit_sha: str,
    *,
    settings: Settings | None = None,
    token_for: TokenFor | None = None,
) -> Path | None:
    """Fetch a GitHub App-connected repository at `commit_sha` and bind it.

    Returns the bare repository path, or None when the repository is not connected
    through the App (operator bindings and dev fixtures keep working as before).
    """
    s = settings or get_settings()
    with transaction() as conn:
        row = (
            conn.execute(
                sa.select(repositories.c.full_name, repositories.c.installation_id).where(
                    repositories.c.id == repo_id
                )
            )
            .mappings()
            .first()
        )
    if row is None or row["installation_id"] is None:
        return None
    if s.repository_bindings_file is None or s.security_workdir is None:
        raise CheckoutError(
            "REPOSITORY_BINDINGS_FILE and SECURITY_WORKDIR must be set to fetch connected repositories"
        )
    if token_for is None:
        from backend.github import GitHubApp

        token_for = GitHubApp(settings=s).installation_token
    repo_dir = s.security_workdir / "repos" / f"{repo_id}.git"
    with _locked(repo_dir):
        fetch_commit(
            repo_dir,
            str(row["full_name"]),
            commit_sha,
            token_for(int(row["installation_id"])),
            github_web_url=s.github_web_url,
        )
    register_binding(s.repository_bindings_file, repo_id, repo_dir)
    return repo_dir
