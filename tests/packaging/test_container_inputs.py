"""Build-context checks without a Docker daemon; Linux image proof is separate."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_copies_every_workspace_member(tmp_path: Path) -> None:
    dockerfile = (ROOT / "backend/Dockerfile").read_text()
    members = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"][
        "members"
    ]
    for member in members:
        assert re.search(rf"^COPY {re.escape(member)}/ {re.escape(member)}/$", dockerfile, re.M), (
            member
        )
    # Reconstruct the Docker COPY inputs, then resolve the frozen lock without
    # creating/installing an environment or executing target source.
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy(ROOT / name, tmp_path / name)
    for member in members:
        shutil.copytree(
            ROOT / member,
            tmp_path / member,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.egg-info"
            ),
        )
    result = subprocess.run(
        [
            "uv",
            "sync",
            "--python",
            "3.12",
            "--frozen",
            "--no-dev",
            "--dry-run",
            "--project",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_build_context_excludes_local_credentials_and_artifacts() -> None:
    patterns = set((ROOT / ".dockerignore").read_text().splitlines())
    assert {
        ".git",
        ".dev",
        ".serena",
        "**/.env",
        "**/.env.*",
        "**/*.pem",
        "**/*.key",
        "**/.venv",
        "**/node_modules",
        "hackatl-agentic-security",
    } <= patterns
    assert "!**/.env.example" in patterns
