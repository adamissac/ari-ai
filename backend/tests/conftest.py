"""Backend test fixtures: a REAL PostgreSQL database (DATABASE_URL, or an embedded
pgserver instance), migrations applied via Alembic, isolated artifact dir."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa

_TMP = Path(tempfile.mkdtemp(prefix="hackatl-test-"))
WEBHOOK_SECRET = "test-webhook-secret-not-real"


def _database_url() -> str:
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        from backend.devdb import start

        base = start(_TMP / "pgdata", database="postgres")
    name = f"hackatl_test_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(
        base.replace("postgresql://", "postgresql+psycopg://", 1)
        if base.startswith("postgresql://")
        else base,
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as c:
        c.execute(sa.text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    url = sa.engine.make_url(base).set(database=name)
    return url.render_as_string(hide_password=False)


def _live_key() -> str:
    """The real key for the opt-in live smoke, read BEFORE tests blank ANTHROPIC_API_KEY.
    Source: the shell environment, else the repo-root .env (git-ignored)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "ANTHROPIC_API_KEY":
                key = value.split("#", 1)[0].strip().strip("\"'")
    return "" if key in ("", "replace-me") else key


os.environ["HACKATL_LIVE_ANTHROPIC_API_KEY"] = _live_key()

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": _database_url(),
        "ARTIFACT_STORE_URI": f"file://{_TMP / 'artifacts'}",
        "AUTH_DEV_LOGIN_ENABLED": "true",
        "GITHUB_WEBHOOK_SECRET": WEBHOOK_SECRET,
        "ANTHROPIC_API_KEY": "",
        "ORCHESTRATOR_FACTORY": "security_agents.api:build_orchestrator",
        "CODE_INTELLIGENCE_FACTORY": "code_intelligence.api:build_service",
        "WORKER_LEASE_S": "30",
    }
)

from backend.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from backend.migrate import upgrade  # noqa: E402

upgrade()

_TABLES = [
    "idempotency_keys",
    "rl_evaluations",
    "defense_recommendations",
    "reassessment_requests",
    "monitoring_events",
    "webhook_deliveries",
    "jobs",
    "verification_results",
    "patch_candidates",
    "finding_records",
    "findings",
    "agent_runs",
    "assessment_events",
    "assessments",
    "approvals",
    "authorized_scopes",
    "snapshots",
    "repositories",
    "projects",
    "sessions",
    "memberships",
    "users",
    "artifacts",
    "audit_events",
    "organizations",
]


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    from backend import llm
    from backend.db import get_engine

    yield
    llm.TRANSPORT_OVERRIDE = None
    get_settings.cache_clear()
    with get_engine().begin() as c:
        c.execute(sa.text("ALTER TABLE audit_events DISABLE TRIGGER USER"))
        c.execute(sa.text("TRUNCATE " + ", ".join(_TABLES) + " CASCADE"))
        c.execute(sa.text("ALTER TABLE audit_events ENABLE TRIGGER USER"))


@pytest.fixture
def settings_override(monkeypatch: pytest.MonkeyPatch):
    def apply(**values: str) -> None:
        for k, v in values.items():
            monkeypatch.setenv(k.upper(), v)
        get_settings.cache_clear()

    return apply


@pytest.fixture
def client_factory():
    from fastapi.testclient import TestClient

    from backend.main import create_app

    clients = []

    def make(login: str | None = None):
        c = TestClient(create_app())
        clients.append(c)
        if login:
            r = c.post("/api/v1/auth/dev/login", json={"github_login": login})
            assert r.status_code == 200, r.text
            c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
            c.me = r.json()  # type: ignore[attr-defined]
        return c

    yield make
    for c in clients:
        c.close()
