"""Real HTTP/DB transport proof; no worker, target execution or model call.

Uses the shared local pgtest server with an exclusively owned temporary database.
Drops only that database; never stops another developer's server.
"""
from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    from backend.devdb import start

    admin_url = start(ROOT / ".dev" / "pgtest", database="postgres")
    name = f"transport_{uuid.uuid4().hex}"
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    server = None
    thread = None
    sock = None
    try:
        with tempfile.TemporaryDirectory(prefix="transport-artifacts-") as artifacts:
            os.environ.update(
                APP_ENV="test",
                DATABASE_URL=sa.engine.make_url(admin_url).set(database=name).render_as_string(hide_password=False),
                ARTIFACT_STORE_URI=Path(artifacts).as_uri(),
                AUTH_DEV_LOGIN_ENABLED="true",
                ANTHROPIC_API_KEY="",
                RATE_LIMIT_PER_MINUTE="1000",
            )
            from backend.settings import get_settings

            get_settings.cache_clear()
            from backend.migrate import upgrade

            upgrade()
            from backend.api.auth import upsert_user
            from backend.db import get_engine, memberships, transaction, users

            with transaction() as conn:
                alice = upsert_user(conn, "transport-alice", None, None)
                bob = upsert_user(conn, "transport-bob", None, None)
                org = conn.execute(sa.select(users.c.personal_org_id).where(users.c.id == alice)).scalar_one()
                conn.execute(sa.insert(memberships).values(org_id=org, user_id=bob, role="owner"))
            import uvicorn
            from backend.main import create_app

            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(create_app(), log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Transport test API failed to start")
                time.sleep(0.02)
            result = subprocess.run(
                ["node", "--test", str(Path(__file__).with_name("real-backend.integration.mjs"))],
                env={**os.environ, "TRANSPORT_TEST_API": f"http://127.0.0.1:{port}/api/v1"},
                timeout=45,
                check=False,
            )
            if result.returncode:
                raise SystemExit(result.returncode)
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        if sock:
            sock.close()
        if "backend.db" in __import__("sys").modules:
            from backend.db import get_engine

            get_engine().dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


if __name__ == "__main__":
    main()
