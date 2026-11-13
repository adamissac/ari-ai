"""Control-channel HMAC secrets at rest.

With ``CONTROL_SECRET_KEY`` set (a Fernet key), secrets are stored encrypted as
``fernet:v1:<token>``. Without it they stay plaintext, as before. Reading accepts both, so
rows written before the key existed keep working.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken  # via pyjwt[crypto]

from backend.settings import get_settings

PREFIX = "fernet:v1:"


def _fernet() -> Fernet | None:
    key = get_settings().control_secret_key
    return Fernet(key.get_secret_value().encode()) if key and key.get_secret_value() else None


def seal(secret: str) -> str:
    box = _fernet()
    return secret if box is None else PREFIX + box.encrypt(secret.encode()).decode()


def unseal(stored: str) -> str:
    if not stored.startswith(PREFIX):
        return stored
    box = _fernet()
    if box is None:
        raise RuntimeError("CONTROL_SECRET_KEY is unset but a sealed control secret exists")
    try:
        return box.decrypt(stored[len(PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("CONTROL_SECRET_KEY does not open this control secret") from exc
