"""GitHub integration: webhook signature verification, GitHub App auth, least-privilege reads."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.settings import Settings, get_settings


def verify_signature(secret: bytes, raw_body: bytes, header: str | None) -> bool:
    """Constant-time check of ``X-Hub-Signature-256`` over the exact raw request body."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header.strip().encode())


def sign(secret: bytes, raw_body: bytes) -> str:
    """Produce a valid signature header (local fixtures and replay tooling)."""
    return "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


class GitHubNotConfigured(RuntimeError):
    pass


@dataclass
class _Token:
    value: str
    expires_at: float


def _private_key(settings: Settings) -> str | None:
    if settings.github_app_private_key_path:
        return settings.github_app_private_key_path.read_text()
    if settings.github_app_private_key:
        return settings.github_app_private_key.get_secret_value().replace("\\n", "\n")
    return None


class GitHubApp:
    """Short-lived installation tokens (ADR-0009). Never uses PATs."""

    def __init__(
        self, settings: Settings | None = None, client: httpx.Client | None = None
    ) -> None:
        self.settings = settings or get_settings()
        key = _private_key(self.settings)
        if not (self.settings.github_app_id and key):
            raise GitHubNotConfigured(
                "GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY not configured"
            )
        self._key = key
        self._client = client or httpx.Client(base_url=self.settings.github_api_url, timeout=20.0)
        self._tokens: dict[int, _Token] = {}

    def _app_jwt(self) -> str:
        import jwt

        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self.settings.github_app_id},
            self._key,
            algorithm="RS256",
        )

    def installation_token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached and cached.expires_at - time.time() > 120:
            return cached.value
        r = self._client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._app_jwt()}",
                "Accept": "application/vnd.github+json",
            },
            json={"permissions": {"contents": "read", "metadata": "read"}},
        )
        r.raise_for_status()
        data = r.json()
        self._tokens[installation_id] = _Token(data["token"], time.time() + 3000)
        return data["token"]

    def _get(self, installation_id: int, path: str, **params: Any) -> Any:
        r = self._client.get(
            path,
            params=params or None,
            headers={
                "Authorization": f"Bearer {self.installation_token(installation_id)}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        r.raise_for_status()
        return r.json()

    def compare_paths(
        self, installation_id: int, full_name: str, base: str, head: str
    ) -> tuple[list[str], bool]:
        """Changed paths between two SHAs. Returns (paths, complete)."""
        data = self._get(
            installation_id, f"/repos/{full_name}/compare/{base}...{head}", per_page=100
        )
        files = data.get("files") or []
        paths = sorted({f["filename"] for f in files if isinstance(f.get("filename"), str)})
        return paths, len(files) < 300

    def commit(self, installation_id: int, full_name: str, sha: str) -> dict[str, Any]:
        return self._get(installation_id, f"/repos/{full_name}/commits/{sha}")
