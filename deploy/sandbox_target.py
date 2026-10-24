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
        "scope": "scp_sbxalice0000000000000000a",
        "assessment": "asm_sbxalice000000000000000a",
        "finding": "fnd_sbxalice0000000000000000a",
    },
    "bob": {
        "user": "usr_sbxbob000000000000000000b",
        "org": "org_sbxbob000000000000000000b",
        "project": "prj_sbxbob000000000000000000b",
        "repo": "rep_sbxbob000000000000000000b",
        "scope": "scp_sbxbob00000000000000000b",
        "assessment": "asm_sbxbob000000000000000b",
        "finding": "fnd_sbxbob00000000000000000b",
    },
    # Role-differentiated identities: their own orgs plus a cross-membership in
    # alice's org so role-gated routes can be probed (viewer vs member vs owner).
    "carol": {
        "user": "usr_sbxcarol0000000000000000c",
        "org": "org_sbxcarol0000000000000000c",
        "project": "prj_sbxcarol0000000000000000c",
        "repo": "rep_sbxcarol0000000000000000c",
    },
    "dave": {
        "user": "usr_sbxdave00000000000000000d",
        "org": "org_sbxdave00000000000000000d",
        "project": "prj_sbxdave00000000000000000d",
        "repo": "rep_sbxdave00000000000000000d",
    },
}
# name -> (org whose project they can reach, role in that org)
EXTRA_MEMBERSHIPS = {
    "carol": ("alice", "viewer"),
    "dave": ("alice", "member"),
}
SEED_COMMIT = "4f3d2c1b5a6978091a2b3c4d5e6f708192a3b4c5"
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
    from datetime import timedelta

    import sqlalchemy as sa

    from backend.api.deps import _hash
    from backend.db import (
        assessments,
        authorized_scopes,
        findings,
        memberships,
        organizations,
        projects,
        repositories,
        sessions,
        transaction,
        users,
    )
    from shared.assessment import Assessment, AssessmentState, AssessmentTrigger
    from shared.base import utcnow
    from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
    from shared.findings import Finding, FindingKind, FindingStatus
    from shared.scope import (
        AuthorizedScope,
        CheckCategory,
        ScopeStatus,
        ScopeTarget,
    )
    from shared.tenancy import Budget, MemberRole, ProjectSettings

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
        for name, (owner, role) in EXTRA_MEMBERSHIPS.items():
            if not conn.execute(
                sa.select(memberships.c.user_id).where(
                    memberships.c.org_id == FIXTURES[owner]["org"],
                    memberships.c.user_id == FIXTURES[name]["user"],
                )
            ).first():
                conn.execute(
                    sa.insert(memberships).values(
                        org_id=FIXTURES[owner]["org"],
                        user_id=FIXTURES[name]["user"],
                        role=role,
                    )
                )
        now = utcnow()
        for name in ("alice", "bob"):
            ids = FIXTURES[name]
            if conn.execute(
                sa.select(assessments.c.id).where(assessments.c.id == ids["assessment"])
            ).first():
                continue
            scope = AuthorizedScope(
                id=ids["scope"],
                project_id=ids["project"],
                name="sbx authorized sandbox",
                targets=[ScopeTarget(repo_id=ids["repo"], build_recipe_ref="build_recipe.json")],
                allowed_check_categories=[
                    c.value
                    for c in (
                        CheckCategory.access_control_ownership,
                        CheckCategory.access_control_authentication,
                        CheckCategory.access_control_role,
                        CheckCategory.input_validation_bounds,
                    )
                ],
                status=ScopeStatus.active,
                requested_by=ids["user"],
                approved_by=ids["user"],
                approved_at=now,
                expires_at=now + timedelta(days=30),
            )
            conn.execute(
                sa.insert(authorized_scopes).values(
                    id=scope.id,
                    project_id=ids["project"],
                    status=scope.status.value,
                    expires_at=scope.expires_at,
                    doc=scope.model_dump(mode="json"),
                )
            )
            asm = Assessment(
                id=ids["assessment"],
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=SEED_COMMIT,
                trigger=AssessmentTrigger.monitoring,
                state=AssessmentState.completed,
                budget=Budget(),
                created_by=ids["user"],
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
            conn.execute(
                sa.insert(assessments).values(
                    id=asm.id,
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    scope_id=ids["scope"],
                    commit_sha=SEED_COMMIT,
                    trigger=asm.trigger.value,
                    state=asm.state.value,
                    doc=asm.model_dump(mode="json"),
                )
            )
            fnd = Finding(
                id=ids["finding"],
                assessment_id=ids["assessment"],
                commit_sha=SEED_COMMIT,
                kind=FindingKind.security,
                title="[CWE-862] sandbox fixture finding for authorization checks",
                status=FindingStatus.hardened,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.source_span,
                        path="backend/backend/api/routes.py",
                        commit_sha=SEED_COMMIT,
                        span=SourceSpan(start_line=1, end_line=2),
                        provenance="sandbox_target.seed",
                    )
                ],
                confidence=0.9,
                created_at=now,
                updated_at=now,
            )
            conn.execute(
                sa.insert(findings).values(
                    id=fnd.id,
                    project_id=ids["project"],
                    assessment_id=ids["assessment"],
                    kind=fnd.kind.value,
                    status=fnd.status.value,
                    doc=fnd.model_dump(mode="json"),
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
