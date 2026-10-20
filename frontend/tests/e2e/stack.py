"""Browser e2e stack: real FastAPI + PostgreSQL + worker + Next.js, then Playwright.

What is real: HTTP API, migrations, session cookies/CSRF, durable queue and worker,
pinned git checkout of the owned examples/payments-lite target, reviewer test
execution, local-dev sandbox checks, Patch/Verify, artifacts, SSE, the Next app.
What is scripted: model replies. The worker's single LLM gateway uses the same
TEST-ONLY transports as backend/tests/test_unified_assessment.py (Sai's reviewer
script + Alan's role scripts), so every agent run is persisted with
provider_mode="fake" and the UI must label it as not live. No API key is used.

Usage (from frontend/):  ../.venv/bin/python tests/e2e/stack.py [playwright args]
Env: TEST_DATABASE_URL (admin URL of an existing Postgres; default embedded pgserver),
     E2E_SKIP_BUILD=1 to reuse an existing `.next` build made with NEXT_PUBLIC_DEV_LOGIN=1.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa

FRONTEND = Path(__file__).resolve().parents[2]
ROOT = FRONTEND.parent
PAYMENTS = ROOT / "examples" / "payments-lite"
REPO_NAME = "acme/payments-lite"
WEBHOOK_SECRET = "e2e-webhook-secret-not-real"


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        text=True,
    ).strip()


def _owned_repo(tmp: Path) -> tuple[Path, str]:
    repo = tmp / "owned-repo"
    shutil.copytree(PAYMENTS, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.egg-info", ".venv"))
    (repo / "labels.yaml").unlink(missing_ok=True)  # the answer key never ships with the assessed repo
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "payments-lite")
    return repo, _git(repo, "rev-parse", "HEAD")


def _admin_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url if not url.startswith("postgresql://") else "postgresql+psycopg://" + url[len("postgresql://"):]
    from backend.devdb import start

    return start(ROOT / ".dev" / "pgtest", database="postgres")


def _wait(url: str, timeout: float = 60) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"{url} did not become ready")


def main(argv: list[str]) -> int:
    admin_url = _admin_url()
    name = f"e2e_{uuid.uuid4().hex[:10]}"
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f'CREATE DATABASE "{name}"'))
    tmp = Path(tempfile.mkdtemp(prefix="hackatl-e2e-"))
    server = thread = worker_thread = next_proc = None
    stop = threading.Event()
    try:
        repo, sha = _owned_repo(tmp)
        bindings = tmp / "bindings.json"
        bindings.write_text("[]")
        api_port = _port()
        os.environ.update(
            APP_ENV="test",
            DATABASE_URL=sa.engine.make_url(admin_url).set(database=name).render_as_string(hide_password=False),
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

        # TEST-ONLY scripted model transport (see module docstring).
        import code_review

        sys.path[:0] = [str(Path(code_review.__file__).resolve().parents[1] / "tests"), str(ROOT / "backend" / "tests")]
        from cr_fakes import fake  # type: ignore[import-not-found]
        from sa_bridge import AlanScriptTransport  # type: ignore[import-not-found]
        from test_reviewer_agent import (  # type: ignore[import-not-found]
            pl_repair_script,
            pl_review_script,
        )

        from backend import llm, worker

        # Reviewer turns, then its repair turns once the functional repair is approved.
        reviewer = [
            *pl_review_script(SimpleNamespace(repo=repo)),
            *pl_repair_script("target/tests/generated/test_cr_refund_bound.py"),
        ]
        bridge = AlanScriptTransport(repo / "target", fallback=fake(reviewer))
        llm.TRANSPORT_OVERRIDE = lambda: bridge

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
                except Exception as exc:  # surface, keep serving so the UI shows the failure
                    print(f"[e2e worker] {type(exc).__name__}: {exc}", file=sys.stderr)
                    time.sleep(0.5)

        worker_thread = threading.Thread(target=work, daemon=True)
        worker_thread.start()

        # Operator setup the UI cannot do: two org owners, a project and the repo binding
        # (REPOSITORY_BINDINGS_FILE is an operator registry, not a user-facing API).
        import httpx

        from backend.db import memberships, transaction

        base = f"http://127.0.0.1:{api_port}/api/v1"
        alice = httpx.Client(base_url=base)
        me = alice.post("/auth/dev/login", json={"github_login": "e2e-alice"}).raise_for_status().json()
        bob = httpx.Client(base_url=base).post("/auth/dev/login", json={"github_login": "e2e-bob"}).raise_for_status().json()
        with transaction() as conn:
            conn.execute(sa.insert(memberships).values(org_id=me["memberships"][0]["organization"]["id"], user_id=bob["user"]["id"], role="owner"))
        alice.headers["X-CSRF-Token"] = me["csrf_token"]
        pid = alice.post("/projects", json={"name": "payments-lite (e2e)"}).raise_for_status().json()["id"]
        rid = alice.post(f"/projects/{pid}/repositories", json={"full_name": REPO_NAME}).raise_for_status().json()["id"]
        # The commit-workspace journey completes its own runs. Keep its findings/approvals
        # separate from the original journey's exact-count assertions.
        workspace_pid = alice.post("/projects", json={"name": "commit-workspace (e2e)"}).raise_for_status().json()["id"]
        workspace_name = "acme/commit-workspace"
        workspace_rid = alice.post(f"/projects/{workspace_pid}/repositories", json={"full_name": workspace_name}).raise_for_status().json()["id"]
        bindings.write_text(json.dumps([
            {"repo_id": rid, "local_path": str(repo), "subdir": "."},
            {"repo_id": workspace_rid, "local_path": str(repo), "subdir": "."},
        ]))
        alice.close()

        web_port = _port()
        os.environ.setdefault("DEMO_ACCESS_CODE", "e2e-demo-access-code")  # demo account gate (proxy.ts)
        env = {**os.environ, "BACKEND_ORIGIN": f"http://127.0.0.1:{api_port}", "NEXT_PUBLIC_DEV_LOGIN": "1"}
        env.pop("NODE_OPTIONS", None)
        if os.environ.get("E2E_SKIP_BUILD") != "1":
            subprocess.run(["npx", "next", "build"], cwd=FRONTEND, env=env, check=True)
        next_proc = subprocess.Popen(["npx", "next", "start", "--port", str(web_port), "--hostname", "127.0.0.1"], cwd=FRONTEND, env=env)
        _wait(f"http://127.0.0.1:{web_port}/lab/bundles")

        result = subprocess.run(
            ["npx", "playwright", "test", *argv],
            cwd=FRONTEND,
            env={**env, "E2E_BASE_URL": f"http://127.0.0.1:{web_port}", "E2E_API": base, "E2E_PROJECT_ID": pid,
                 "E2E_REPO_ID": rid, "E2E_REPO": REPO_NAME, "E2E_WORKSPACE_PROJECT_ID": workspace_pid,
                 "E2E_WORKSPACE_REPO_ID": workspace_rid, "E2E_WORKSPACE_REPO": workspace_name, "E2E_COMMIT": sha, "E2E_WEBHOOK_SECRET": WEBHOOK_SECRET},
            check=False,
        )
        return result.returncode
    finally:
        stop.set()
        if next_proc:
            next_proc.terminate()
            try:
                next_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                next_proc.kill()
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        if worker_thread:
            worker_thread.join(timeout=10)
        if "backend.db" in sys.modules:
            from backend.db import get_engine

            get_engine().dispose()
        with admin.connect() as c:
            c.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
