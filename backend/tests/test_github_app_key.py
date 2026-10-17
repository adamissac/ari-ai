"""The GitHub App key can come from a file or, on hosts like Railway, an env variable."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from backend.github import GitHubApp, GitHubNotConfigured, _private_key
from backend.settings import Settings

PEM = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"


def test_key_from_env_accepts_escaped_newlines() -> None:
    s = Settings(github_app_id="1", github_app_private_key=SecretStr(PEM.replace("\n", "\\n")))
    assert _private_key(s) == PEM


def test_key_file_wins_over_env(tmp_path: Path) -> None:
    f = tmp_path / "app.pem"
    f.write_text(PEM)
    s = Settings(
        github_app_id="1",
        github_app_private_key_path=f,
        github_app_private_key=SecretStr("other"),
    )
    assert _private_key(s) == PEM


def test_placeholder_key_means_not_configured() -> None:
    s = Settings(github_app_id="1", github_app_private_key="replace-me")  # type: ignore[arg-type]
    with pytest.raises(GitHubNotConfigured):
        GitHubApp(settings=s)
