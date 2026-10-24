"""Manual e2e stack: same real backend as stack.py, but keeps the API + worker
alive and prints connection info instead of running Playwright / `next start`.
Point `next dev` at it with BACKEND_ORIGIN printed below.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stack


def main() -> int:
    # Reuse stack.py's machinery by monkeypatching its main loop's tail:
    # easiest is to copy main() and replace the next-build/playwright tail.
    import json
    import os
    import shutil
    import socket
    import subprocess
    import tempfile
    import threading
    import uuid
    from typing import Any

    import sqlalchemy as sa

    ROOT = stack.ROOT
    PAYMENTS = stack.PAYMENTS
    REPO_NAME = stack.REPO_NAME
    WEBHOOK_SECRET = stack.WEBHOOK_SECRET
    _port = stack._port
    _git = stack._git
    _owned_repo = stack._owned_repo
    _admin_url = stack._admin_url
    _wait = stack._wait

    admin_url = _admin_url()
    name = f"e2e_{uuid.uuid4().hex[:10]}"
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f'CREATE DATABASE "{name}"'))
    tmp = Path(tempfile.mkdtemp(prefix="hackatl-e2e-manual-"))
    server = thread = worker_thread = helper = None
    fixture_stop: list[Any] = []
    stop = threading.Event()
    try:
        repo, sha = _owned_repo(tmp)
        bindings = tmp / "bindings.json"
        bindings.write_text("[]")
        api_port = _port()
        os.environ.update(
            APP_ENV="test",
            DATABASE_URL=sa.engine.make_url(admin_url)
            .set(database=name)
            .render_as_string(hide_password=False),
            ARTIFACT_STORE_URI=(tmp / "artifacts").as_uri(),
            AUTH_DEV_LOGIN_ENABLED="true",
            ANTHROPIC_API_KEY="",
            GITHUB_WEBHOOK_SECRET=WEBHOOK_SECRET,
            RATE_LIMIT_PER_MINUTE="100000",
            REPOSITORY_BINDINGS_FILE=str(bindings),
            SECURITY_SANDBOX="local-dev",
            SECURITY_AGENTS_WORKDIR=str(tmp / "work"),
            ORCHESTRATOR_FACTORY="security_agents.api:build_orchestrator",
            CODE_INTELLIGENCE_FACTORY="code_intelligence.api:build_service",
        )
        os.environ.pop("SECURITY_AGENTS_TARGET_DIR", None)
        from backend.settings import get_settings

        get_settings.cache_clear()
        from backend.migrate import upgrade

        upgrade()

        import code_review

        sys.path[:0] = [
            str(Path(code_review.__file__).resolve().parents[1] / "tests"),
            str(ROOT / "backend" / "tests"),
        ]
        from cr_fakes import fake  # type: ignore[import-not-found]
        from sa_bridge import AlanScriptTransport  # type: ignore[import-not-found]
        from test_reviewer_agent import (  # type: ignore[import-not-found]
            pl_repair_script,
            pl_review_script,
        )

        from backend import llm, worker
        from types import SimpleNamespace

        reviewer = [
            *pl_review_script(SimpleNamespace(repo=repo)),
            *pl_repair_script("target/tests/generated/test_cr_refund_bound.py"),
        ]
        bridge = AlanScriptTransport(repo / "target", fallback=fake(reviewer))
        llm.TRANSPORT_OVERRIDE = lambda: bridge
        original_build_gateway = llm.build_gateway
        assessment_transports: dict[str, Any] = {}

        def isolated_gateway(**kwargs: Any) -> Any:
            owner = getattr(kwargs.get("charge"), "__self__", None)
            assessment_id = getattr(owner, "assessment_id", None)
            if assessment_id and kwargs.get("transport") is None:
                if assessment_id not in assessment_transports:
                    assessment_transports[assessment_id] = AlanScriptTransport(
                        repo / "target", fallback=fake(reviewer)
                    )
                kwargs["transport"] = assessment_transports[assessment_id]
            return original_build_gateway(**kwargs)

        llm.build_gateway = isolated_gateway

        import uvicorn

        from backend.main import create_app

        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", api_port))
        server = uvicorn.Server(uvicorn.Config(create_app(), log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        _wait(f"http://127.0.0.1:{api_port}/healthz")

        def work() -> None:
            while not stop.is_set():
                try:
                    if not worker.drain(max_jobs=10):
                        time.sleep(0.2)
                except Exception as exc:
                    print(f"[e2e worker] {type(exc).__name__}: {exc}", file=sys.stderr)
                    time.sleep(0.5)

        worker_thread = threading.Thread(target=work, daemon=True)
        worker_thread.start()

        import httpx

        from backend.db import memberships, transaction

        base = f"http://127.0.0.1:{api_port}/api/v1"
        alice = httpx.Client(base_url=base)
        me = (
            alice.post("/auth/dev/login", json={"github_login": "e2e-alice"})
            .raise_for_status()
            .json()
        )
        bob = (
            httpx.Client(base_url=base)
            .post("/auth/dev/login", json={"github_login": "e2e-bob"})
            .raise_for_status()
            .json()
        )
        with transaction() as conn:
            conn.execute(
                sa.insert(memberships).values(
                    org_id=me["memberships"][0]["organization"]["id"],
                    user_id=bob["user"]["id"],
                    role="owner",
                )
            )
        alice.headers["X-CSRF-Token"] = me["csrf_token"]
        pid = (
            alice.post("/projects", json={"name": "payments-lite (e2e)", "settings": {"delivery_mode": "manual"}})
            .raise_for_status()
            .json()["id"]
        )
        rid = (
            alice.post(f"/projects/{pid}/repositories", json={"full_name": REPO_NAME})
            .raise_for_status()
            .json()["id"]
        )
        workspace_pid = (
            alice.post("/projects", json={"name": "commit-workspace (e2e)", "settings": {"delivery_mode": "manual"}})
            .raise_for_status()
            .json()["id"]
        )
        workspace_name = "acme/commit-workspace"
        workspace_rid = (
            alice.post(
                f"/projects/{workspace_pid}/repositories", json={"full_name": workspace_name}
            )
            .raise_for_status()
            .json()["id"]
        )
        bindings.write_text(
            json.dumps(
                [
                    {"repo_id": rid, "local_path": str(repo), "subdir": "."},
                    {"repo_id": workspace_rid, "local_path": str(repo), "subdir": "."},
                ]
            )
        )

        print("=" * 60, flush=True)
        print("MANUAL STACK READY", flush=True)
        print(f"API:      {base}", flush=True)
        print(f"PROJECT:  {pid}", flush=True)
        print(f"REPO:     {rid}  ({REPO_NAME})", flush=True)
        print(f"WS_PROJ:  {workspace_pid}", flush=True)
        print(f"WS_REPO:  {workspace_rid}  ({workspace_name})", flush=True)
        print(f"COMMIT:   {sha}", flush=True)
        print(f"ALICE CSRF: {me['csrf_token']}", flush=True)
        print("dev-login: POST /auth/dev/login {github_login: 'e2e-alice'}", flush=True)
        print("=" * 60, flush=True)
        sys.stdout.flush()

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if helper is not None:
            helper.shutdown()
        while fixture_stop:
            fixture_stop.pop()()
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        if worker_thread:
            worker_thread.join(timeout=10)
        if "backend.db" in sys.modules:
            from backend.db import get_engine

            get_engine().dispose()
        try:
            with admin.connect() as c:
                c.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        except Exception:
            pass
        admin.dispose()
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
