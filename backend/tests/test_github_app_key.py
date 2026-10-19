"""The GitHub App key can come from a file or, on hosts like Railway, an env variable."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from backend.github import GitHubApp, GitHubNotConfigured, _private_key
from backend.settings import Settings

PEM = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"


def _app_with_client(client: httpx.Client) -> GitHubApp:
    app = GitHubApp.__new__(GitHubApp)
    app.settings = Settings(github_app_id="1")
    app._client = client
    app._tokens = {}
    app._key = PEM
    app._app_jwt = lambda: "app-jwt"  # type: ignore[method-assign]
    return app


def test_key_from_env_accepts_escaped_newlines() -> None:
    s = Settings(github_app_id="1", github_app_private_key=SecretStr(PEM.replace("\n", "\\n")))
    assert _private_key(s) == PEM


def test_key_file_wins_over_env(tmp_path: Path) -> None:
    f = tmp_path / "app.pem"
    f.write_text(PEM)
    s = Settings(
        github_app_id="1",
        github_app_private_key_path=SecretStr(str(f)),
        github_app_private_key=SecretStr("other"),
    )
    assert _private_key(s) == PEM


def test_placeholder_key_means_not_configured() -> None:
    s = Settings(github_app_id="1", github_app_private_key="replace-me")  # type: ignore[arg-type]
    with pytest.raises(GitHubNotConfigured):
        GitHubApp(settings=s)


def test_pem_pasted_into_the_path_variable_is_used_as_the_key() -> None:
    s = Settings(github_app_id="1", github_app_private_key_path=SecretStr(PEM.replace("\n", "\\n")))
    assert _private_key(s) == PEM


def test_user_installation_uses_app_jwt_and_returns_none_for_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer app-jwt"
        if request.url.path == "/users/alice/installation":
            return httpx.Response(200, json={"id": 42, "account": {"type": "User"}})
        if request.url.path == "/users/missing/installation":
            return httpx.Response(404)
        return httpx.Response(403)

    with httpx.Client(
        base_url="https://api.github.test", transport=httpx.MockTransport(handler)
    ) as client:
        app = _app_with_client(client)
        assert app.user_installation("alice") == {"id": 42, "account": {"type": "User"}}
        assert app.user_installation("missing") is None
        with pytest.raises(httpx.HTTPStatusError):
            app.user_installation("forbidden")


def test_installation_repositories_paginates_at_most_ten_pages() -> None:
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.headers["Authorization"] == "Bearer app-jwt"
            return httpx.Response(201, json={"token": "installation-token"})
        assert request.url.path == "/installation/repositories"
        assert request.headers["Authorization"] == "Bearer installation-token"
        assert request.url.params["per_page"] == "100"
        page = int(request.url.params["page"])
        requested_pages.append(page)
        repos = [
            {
                "full_name": f"owner/repo-{page}-{index}",
                "default_branch": None if page == 1 and index == 0 else "trunk",
                "private": index == 0,
            }
            for index in range(100)
        ]
        return httpx.Response(200, json={"repositories": repos})

    with httpx.Client(
        base_url="https://api.github.test", transport=httpx.MockTransport(handler)
    ) as client:
        repos = _app_with_client(client).installation_repositories(42)

    assert requested_pages == list(range(1, 11))
    assert len(repos) == 1000
    assert repos[0] == {
        "full_name": "owner/repo-1-0",
        "installation_id": 42,
        "default_branch": "main",
        "private": True,
    }
