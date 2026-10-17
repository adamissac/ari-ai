from __future__ import annotations

import subprocess
from pathlib import Path


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "-c", "core.hooksPath=/dev/null", *args],
        text=True,
    ).strip()


def commit(path: Path, message: str = "fixture") -> str:
    git(path, "add", ".")
    git(
        path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        message,
    )
    return git(path, "rev-parse", "HEAD")
