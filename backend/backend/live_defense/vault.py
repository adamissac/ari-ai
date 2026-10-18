"""Per-application signing secrets, encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).

The key comes only from ``LIVE_DEFENSE_SECRET_KEY`` (a deployment secret, never in the
repository). Without it no application can be connected and no control can be signed:
we fail closed rather than store a plaintext secret. Plaintext exists only in memory
while signing, and once in the response that creates the application.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from backend.settings import get_settings


class SecretKeyUnavailable(RuntimeError):
    """LIVE_DEFENSE_SECRET_KEY is missing or not a valid Fernet key."""


def _fernet() -> Fernet:
    key = get_settings().live_defense_secret_key
    if key is None:
        raise SecretKeyUnavailable(
            "LIVE_DEFENSE_SECRET_KEY is not configured; signing secrets cannot be stored"
        )
    try:
        return Fernet(key.get_secret_value().encode())
    except (ValueError, TypeError) as exc:
        raise SecretKeyUnavailable("LIVE_DEFENSE_SECRET_KEY is not a valid Fernet key") from exc


def key_configured() -> bool:
    try:
        _fernet()
    except SecretKeyUnavailable:
        return False
    return True


def new_signing_secret() -> str:
    return "ari_sig_" + secrets.token_urlsafe(32)


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretKeyUnavailable(
            "stored signing secret cannot be decrypted with the configured key"
        ) from exc


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """``sha256=<hex HMAC-SHA256(secret, timestamp + "." + body)>``: binds the body to a time."""
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(secret: str, timestamp: str, body: bytes, header: str | None) -> bool:
    return bool(header) and hmac.compare_digest(sign(secret, timestamp, body), header or "")
