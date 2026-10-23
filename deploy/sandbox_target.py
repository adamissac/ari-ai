"""Sandbox target for the security agents: the real backend app on a throwaway database.

`build_recipe.json` names `deploy.sandbox_target:create_app`. Inside the Vercel Sandbox
microVM (egress already closed) it starts a local PostgreSQL over a Unix socket, applies
the real migrations, seeds two unrelated fixture users who each own one project and one
repository, and returns the production `create_app()`. Probe's checks then call the API
as either user. Never imported by the running service.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PGDATA = Path("/tmp/ari-target-pg")
SOCKET_DIR = "/tmp"
# Fixed ids and tokens so build_recipe.json can name them; they exist only in this database.
FIXTURES = {
    "alice": {
        "user": "usr_sbxalice0000000000000000a",
        "org": "org_sbxalice0000000000000000a",
        "project": "prj_sbxalice0000000000000000a",
        "repo": "rep_sbxalice0000000000000000a",
    },
    "bob": {
        "user": "usr_sbxbob000000000000000000b",
        "org": "org_sbxbob000000000000000000b",
        "project": "prj_sbxbob000000000000000000b",
        "repo": "rep_sbxbob000000000000000000b",
    },
}
_APP = None


def _paths() -> None:
    for sub in ("backend", "shared", "monitoring", "standards", "code-intelligence"):
        p = str(ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def _postgres_url() -> str:
    if url := os.environ.get("SANDBOX_TARGET_DATABASE_URL"):  # local runs bring their own
        return url
    bins = sorted(glob.glob("/usr/lib/postgresql/*/bin"))
    pg = Path(bins[-1]) if bins else Path(shutil.which("pg_ctl") or "pg_ctl").parent
    if not (PGDATA / "PG_VERSION").exists():
        subprocess.run(
            [str(pg / "initdb"), "-D", str(PGDATA), "-U", "postgres", "-A", "trust"],
            check=True,
            capture_output=True,
        )
    status = subprocess.run([str(pg / "pg_ctl"), "-D", str(PGDATA), "status"], capture_output=True)
    if status.returncode != 0:
        opts = f"-k {SOCKET_DIR} -c listen_addresses= -c fsync=off"
        subprocess.run(
            [
                str(pg / "pg_ctl"),
                "-D",
                str(PGDATA),
                "-o",
                opts,
                "-l",
                str(PGDATA / "log"),
                "start",
                "-w",
            ],
            check=True,
            capture_output=True,
        )
    return f"postgresql+psycopg://postgres@/postgres?host={SOCKET_DIR}"


def _seed() -> dict[str, str]:
    import sqlalchemy as sa

    from backend.api.deps import _hash
    from backend.db import (
        memberships,
        organizations,
        projects,
        repositories,
        sessions,
        transaction,
        users,
    )
    from shared.tenancy import MemberRole, ProjectSettings

    tokens = {}
    with transaction() as conn:
        for name, ids in FIXTURES.items():
            if conn.execute(sa.select(users.c.id).where(users.c.id == ids["user"])).first():
                tokens[name] = f"sbx-{name}-session"
                continue
            conn.execute(sa.insert(organizations).values(id=ids["org"], name=f"{name} (personal)"))
            conn.execute(
                sa.insert(users).values(
                    id=ids["user"], github_login=f"sbx-{name}", personal_org_id=ids["org"]
                )
            )
            conn.execute(
                sa.insert(memberships).values(
                    org_id=ids["org"], user_id=ids["user"], role=MemberRole.owner.value
                )
            )
            conn.execute(
                sa.insert(projects).values(
                    id=ids["project"],
                    org_id=ids["org"],
                    name=f"{name}-app",
                    settings=ProjectSettings().model_dump(mode="json"),
                )
            )
            conn.execute(
                sa.insert(repositories).values(
                    id=ids["repo"],
                    project_id=ids["project"],
                    full_name=f"sbx-{name}/app",
                    default_branch="main",
                )
            )
            tokens[name] = f"sbx-{name}-session"
            conn.execute(
                sa.insert(sessions).values(
                    token_hash=_hash(tokens[name]),
                    user_id=ids["user"],
                    csrf_token=f"sbx-{name}-csrf",
                    expires_at=sa.func.now() + sa.text("interval '1 day'"),
                )
            )
    return tokens


def create_app():  # type: ignore[no-untyped-def]
    """The production app with `Authorization: Bearer <session>` mapped onto the session cookie."""
    global _APP
    if _APP is not None:
        return _APP
    _paths()
    os.environ["DATABASE_URL"] = _postgres_url()
    os.environ.setdefault("APP_ENV", "test")
    from backend.settings import get_settings

    get_settings.cache_clear()
    from backend import migrate
    from backend.api.deps import CSRF_HEADER, SESSION_COOKIE
    from backend.main import create_app as real_create_app

    migrate.upgrade()
    _seed()
    app = real_create_app()

    @app.middleware("http")
    async def bearer_to_cookie(request, call_next):  # type: ignore[no-untyped-def]
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer sbx-"):
            token = auth.removeprefix("Bearer ")
            name = token.removeprefix("sbx-").removesuffix("-session")
            headers = [
                (k, v)
                for k, v in request.scope["headers"]
                if k not in (b"authorization", b"cookie")
            ]
            headers.append((b"cookie", f"{SESSION_COOKIE}={token}".encode()))
            headers.append((CSRF_HEADER.lower().encode(), f"sbx-{name}-csrf".encode()))
            request.scope["headers"] = headers
        return await call_next(request)

    _APP = app
    return app
