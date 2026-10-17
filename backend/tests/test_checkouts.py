"""Connected repositories are fetched at the exact commit and bound for the agents."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backend.checkouts import CheckoutError, fetch_commit, register_binding


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> tuple[str, list[str]]:
    """A local 'GitHub' at file://<tmp>/web with repo acme/app and two commits."""
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "--quiet", "-b", "main", cwd=work)
    _git("config", "user.email", "t@example.com", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    shas = []
    for n in (1, 2):
        (work / "app.py").write_text(f"VERSION = {n}\n")
        _git("add", "app.py", cwd=work)
        _git("commit", "--quiet", "-m", f"v{n}", cwd=work)
        shas.append(_git("rev-parse", "HEAD", cwd=work))
    bare = tmp_path / "web" / "acme" / "app.git"
    bare.parent.mkdir(parents=True)
    _git("clone", "--quiet", "--bare", str(work), str(bare), cwd=tmp_path)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=bare)
    return f"file://{tmp_path / 'web'}", shas


def test_fetches_the_exact_commit_and_archives_it(tmp_path: Path, remote) -> None:
    web, (first, second) = remote
    repo = fetch_commit(
        tmp_path / "repos" / "rep_1.git", "acme/app", first, "tok", github_web_url=web
    )
    archived = subprocess.run(
        ["git", "-C", str(repo), "show", f"{first}:app.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert archived == "VERSION = 1\n"
    # A later commit is fetched into the same bare repository.
    fetch_commit(repo, "acme/app", second, "tok", github_web_url=web)
    assert "VERSION = 2" in _git("show", f"{second}:app.py", cwd=repo)


def test_token_is_never_written_to_git_config(tmp_path: Path, remote) -> None:
    web, (first, _) = remote
    repo = fetch_commit(tmp_path / "r.git", "acme/app", first, "secret-token", github_web_url=web)
    assert "secret-token" not in (repo / "config").read_text()


def test_rejects_bad_names_and_short_shas(tmp_path: Path) -> None:
    with pytest.raises(CheckoutError):
        fetch_commit(tmp_path / "r.git", "acme/app;rm -rf /", "a" * 40, "t")
    with pytest.raises(CheckoutError):
        fetch_commit(tmp_path / "r.git", "acme/app", "abc123", "t")


def test_unknown_commit_fails_closed(tmp_path: Path, remote) -> None:
    web, _ = remote
    with pytest.raises(CheckoutError):
        fetch_commit(tmp_path / "r.git", "acme/app", "f" * 40, "t", github_web_url=web)


def test_bindings_are_added_and_updated_atomically(tmp_path: Path) -> None:
    f = tmp_path / "bindings.json"
    f.write_text(json.dumps([{"repo_id": "rep_op", "local_path": "/srv/op", "subdir": "app"}]))
    register_binding(f, "rep_1", tmp_path / "repos" / "rep_1.git")
    register_binding(f, "rep_1", tmp_path / "repos" / "rep_1.git")  # idempotent
    entries = json.loads(f.read_text())
    assert [e["repo_id"] for e in entries] == ["rep_op", "rep_1"]
    assert entries[0]["subdir"] == "app"  # operator entries untouched
    assert entries[1] == {
        "repo_id": "rep_1",
        "local_path": str(tmp_path / "repos" / "rep_1.git"),
        "subdir": ".",
    }
