#!/usr/bin/env python3
"""Pilot release checklist, executed — not narrated.

    uv run python deploy/release_check.py --base-url http://localhost:8000 \
        [--ops-token T] [--backup-dir backups] [--max-backup-age-h 30]

Every row is PASS, FAIL, WARN or SKIP with evidence. Exit code is non-zero when
any row FAILs. Run it against a real deployment; pair it with
deploy/scripts/smoke_staging.sh for the full HTTP surface.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

results: list[tuple[str, str, str]] = []

# Every gate that must produce a row before --strict can sign off. A gate that never
# ran (e.g. --no-http, an exception, a future refactor) is a missing-evidence FAIL,
# not a silent pass.
REQUIRED_GATES: tuple[str, ...] = (
    "CI success",
    "secrets and configuration",
    "migration compatibility",
    "health check",
    "readiness + job queue availability",
    "authentication required",
    "worker/job-queue visibility",
    "first-responder OFF by default",
    "stuck assessments/jobs",
    "failed jobs (24h)",
    "recommendation-only posture",
    "emergency-stop endpoint",
    "cancellation endpoint",
    "first-responder OFF (database)",
    "backup and recovery",
    "backup readable",
    "rollback readiness",
    "read-only pilot scope",
)


def report(status: str, name: str, evidence: str) -> None:
    results.append((status, name, evidence))
    print(f"[{status:4}] {name}: {evidence}")


def get_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def req_status(url: str, method: str = "GET") -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method, data=b"{}" if method != "GET" else None)
    if method != "GET":
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, {}
    except urllib.error.HTTPError as e:
        return e.code, {}


def check_ci(strict: bool = False, allow_skipped: tuple[str, ...] = ()) -> None:
    """Every CI check must have run and succeeded.

    A skipped check (SKIPPED/NEUTRAL/no conclusion) is not evidence: gitleaks, audit or
    the regression gates being skipped must block sign-off, so they are reported by name
    and count as SKIP (blocking under --strict). Opt-in jobs an operator consciously
    accepts as skipped are named with --allow-skipped-check. An empty rollup means
    GitHub reported no checks at all and is a FAIL, never "0 checks green".
    """
    gh = subprocess.run(["which", "gh"], capture_output=True)
    if gh.returncode != 0:
        report("SKIP", "CI success", "gh CLI not installed; confirm checks on the PR page")
        return
    auth = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if auth.returncode != 0:
        report("SKIP", "CI success", "gh not authenticated; confirm checks on the PR page")
        return
    pr = subprocess.run(
        ["gh", "pr", "view", "--json", "statusCheckRollup,number"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if pr.returncode != 0:
        report("SKIP", "CI success", pr.stderr.strip()[:200] or "no PR for this branch")
        return
    checks = json.loads(pr.stdout).get("statusCheckRollup") or []
    if not checks:
        report("FAIL", "CI success", "GitHub reported no checks for this PR")
        return

    def name(c: dict[str, Any]) -> str:
        return str(c.get("name") or c.get("context") or "?")

    def names(cs: list[dict[str, Any]]) -> str:
        return ", ".join(sorted(name(c) for c in cs)[:8])

    for c in checks:  # StatusContext rows carry state/context instead of status/conclusion/name
        if "state" in c and "status" not in c:
            state = str(c.get("state") or "").upper()
            c["status"] = "COMPLETED" if state in ("SUCCESS", "FAILURE", "ERROR") else "PENDING"
            c["conclusion"] = state
    completed = [c for c in checks if c.get("status") in ("COMPLETED", "SUCCESS")]
    pending = [c for c in checks if c not in completed]
    failed = [
        c for c in completed if c.get("conclusion") not in ("SUCCESS", "SKIPPED", "NEUTRAL", None)
    ]
    skipped = [c for c in completed if c.get("conclusion") != "SUCCESS" and c not in failed]
    allowed = [c for c in skipped if name(c) in allow_skipped]
    unexplained = [c for c in skipped if c not in allowed]
    if failed:
        report("FAIL", "CI success", f"{len(failed)} failing checks: {names(failed)}")
    elif pending:
        report("WARN", "CI success", f"{len(pending)} checks still pending: {names(pending)}")
    elif unexplained:
        report(
            "SKIP" if strict else "WARN",
            "CI success",
            f"{len(unexplained)} checks skipped, not evidence: {names(unexplained)}",
        )
    else:
        detail = f"all {len(checks) - len(allowed)} checks green"
        if allowed:
            detail += f"; allow-listed skipped: {names(allowed)}"
        report("PASS", "CI success", detail)


def check_config() -> None:
    from backend.preflight import validate_config
    from backend.settings import get_settings

    s = get_settings()
    r = validate_config(s)
    for w in r.warnings:
        report("WARN", f"config: {w.split(':')[0]}", w)
    if r.ok:
        report("PASS", "secrets and configuration", f"APP_ENV={s.app_env}, no blocking errors")
    else:
        for e in r.errors:
            report("FAIL", "secrets and configuration", e)


def check_migrations() -> None:
    from backend.db import get_engine
    from backend.preflight import migration_status

    try:
        with get_engine().begin() as conn:
            st = migration_status(conn)
    except Exception as exc:
        report("FAIL", "migration compatibility", f"database unreachable: {type(exc).__name__}")
        return
    if st.at_head:
        report("PASS", "migration compatibility", f"at head {st.expected}")
    else:
        report(
            "FAIL",
            "migration compatibility",
            f"pending {st.pending} (current {st.current}); run hackatl-migrate",
        )


def check_http(base: str, ops_token: str | None) -> None:
    code, body = get_json(f"{base}/healthz")
    report(
        "PASS" if code == 200 and body.get("status") == "ok" else "FAIL",
        "health check",
        f"/healthz -> {code} {body.get('status', '')}",
    )

    code, body = get_json(f"{base}/readyz")
    if code == 200 and body.get("database") and body.get("queue"):
        report(
            "PASS",
            "readiness + job queue availability",
            f"/readyz ready (db={body.get('database')} queue={body.get('queue')})",
        )
    else:
        report("FAIL", "readiness + job queue availability", f"/readyz -> {code} {body}")

    code, _ = get_json(f"{base}/api/v1/projects")
    report(
        "PASS" if code == 401 else "FAIL",
        "authentication required",
        f"unauthenticated /api/v1/projects -> {code}",
    )

    if ops_token:
        code, body = get_json(f"{base}/api/v1/ops/status", {"X-Ops-Token": ops_token})
        if code == 200 and "queue" in body:
            q = body["queue"]["counts"]
            report("PASS", "worker/job-queue visibility", f"ops status ok; queue counts {q}")
            fr = body.get("first_responder", {})
            n = fr.get("projects_with_non_default_mode", "?")
            report(
                "PASS" if n == 0 else "FAIL",
                "first-responder OFF by default",
                f"default=off; projects with non-default mode: {n}",
            )
            check_monitoring(body)
        else:
            report("FAIL", "worker/job-queue visibility", f"ops status -> {code}")
    else:
        report("WARN", "worker/job-queue visibility", "no --ops-token; ops surface unchecked")


def check_monitoring(body: dict) -> None:
    """Stuck work and the recommendation-only posture, from GET /api/v1/ops/status."""
    stuck = body.get("stuck")
    if stuck is None:
        report("FAIL", "stuck assessments/jobs", "ops status has no 'stuck' section (old build)")
    else:
        n_jobs, n_asm = stuck.get("jobs", "?"), stuck.get("assessments", "?")
        report(
            "PASS" if n_jobs == 0 and n_asm == 0 else "FAIL",
            "stuck assessments/jobs",
            f"stuck jobs={n_jobs} {stuck.get('jobs_by_reason', {})}; stuck assessments={n_asm}",
        )
    failed = body.get("failed_jobs_24h") or {}
    report(
        "PASS" if not failed else "WARN",
        "failed jobs (24h)",
        f"{failed or 'none'}; inspect with `python -m backend.execution stuck`",
    )
    pilot = body.get("pilot") or {}
    if body.get("app_env") == "staging":
        safe = (
            pilot.get("recommendation_only") is True and pilot.get("auto_delivery_allowed") is False
        )
        report("PASS" if safe else "FAIL", "recommendation-only posture", str(pilot or "missing"))
    else:
        report("SKIP", "recommendation-only posture", f"APP_ENV={body.get('app_env')}")


def check_controls(base: str) -> None:
    code, body = get_json(f"{base}/api/openapi.json")
    if code == 200:
        paths = " ".join(body.get("paths", {}).keys())
        report(
            "PASS" if "emergency-stop" in paths else "FAIL",
            "emergency-stop endpoint",
            "present in API" if "emergency-stop" in paths else "absent",
        )
        report(
            "PASS" if "cancel" in paths else "WARN",
            "cancellation endpoint",
            "present in API" if "cancel" in paths else "not found",
        )
        return
    # OpenAPI is dev-gated by pilot hardening: probe the real routes instead.
    # An auth rejection (401/403) proves the route is mounted; 404 means absent.
    for label, method, path, warn_only in (
        (
            "emergency-stop endpoint",
            "GET",
            "/api/v1/projects/release-check-probe/emergency-stop",
            False,
        ),
        ("cancellation endpoint", "POST", "/api/v1/assessments/release-check-probe/cancel", True),
    ):
        code, _ = req_status(f"{base}{path}", method)
        if code in (401, 403):
            report("PASS", label, "mounted (unauthenticated request rejected)")
        elif code == 404:
            report("WARN" if warn_only else "FAIL", label, "route absent")
        else:
            report("WARN", label, f"probe -> {code}")


def check_first_responder_db() -> None:
    import sqlalchemy as sa

    from backend.db import first_responder_modes, get_engine

    try:
        with get_engine().begin() as conn:
            rows = conn.execute(
                sa.select(first_responder_modes.c.project_id, first_responder_modes.c.intent).where(
                    first_responder_modes.c.intent != "off"
                )
            ).all()
    except Exception as exc:
        report("FAIL", "first-responder OFF (database)", type(exc).__name__)
        return
    if rows:
        report("FAIL", "first-responder OFF (database)", f"non-off modes stored: {rows}")
    else:
        report("PASS", "first-responder OFF (database)", "no project has a non-off stored mode")


def check_backup(args: argparse.Namespace) -> None:
    d = Path(args.backup_dir)
    dumps = sorted(d.glob("*.dump"), key=lambda p: p.stat().st_mtime) if d.is_dir() else []
    if not dumps:
        report(
            "FAIL",
            "backup and recovery",
            f"no *.dump in {d}; run deploy/scripts/db_backup.sh first",
        )
        return
    newest = dumps[-1]
    age_h = (time.time() - newest.stat().st_mtime) / 3600
    if age_h > args.max_backup_age_h:
        report(
            "WARN",
            "backup and recovery",
            f"newest backup {newest.name} is {age_h:.1f}h old (> {args.max_backup_age_h}h)",
        )
    else:
        report("PASS", "backup and recovery", f"{newest.name} ({age_h:.1f}h old)")
    lst = subprocess.run(["pg_restore", "--list", str(newest)], capture_output=True)
    if lst.returncode == 0:
        report("PASS", "backup readable", f"pg_restore --list ok on {newest.name}")
    else:
        report(
            "WARN", "backup readable", "pg_restore not available to verify; restore drill is manual"
        )


def check_rollback() -> None:
    ok = (REPO / "deploy/scripts/db_restore.sh").exists() and (
        REPO / "docs/deploy/PILOT_OPERATIONS.md"
    ).exists()
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO
    ).stdout.strip()
    if ok:
        report(
            "PASS",
            "rollback readiness",
            f"restore script + runbook present; deployed-from sha {sha}",
        )
    else:
        report("FAIL", "rollback readiness", "restore script or PILOT_OPERATIONS.md missing")


def check_pilot_scope() -> None:
    from backend.settings import get_settings

    s = get_settings()
    if s.app_env in ("staging", "production") and not s.auth_dev_login_enabled:
        report(
            "PASS",
            "read-only pilot scope",
            f"APP_ENV={s.app_env}, dev login off, feature_flags={sorted(s.flags()) or 'none'}",
        )
    elif s.is_dev:
        report("WARN", "read-only pilot scope", f"APP_ENV={s.app_env} (dev build, not staging)")
    else:
        report(
            "FAIL",
            "read-only pilot scope",
            f"APP_ENV={s.app_env}, dev login={s.auth_dev_login_enabled}",
        )


def main() -> int:
    p = argparse.ArgumentParser(prog="release_check")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--ops-token", default=None)
    p.add_argument("--backup-dir", default="backups")
    p.add_argument("--max-backup-age-h", type=float, default=30.0)
    p.add_argument("--no-http", action="store_true", help="config+DB checks only")
    p.add_argument(
        "--strict",
        action="store_true",
        help="WARN/SKIP also fail: every gate must carry PASS evidence (pilot sign-off)",
    )
    p.add_argument(
        "--allow-skipped-check",
        action="append",
        default=[],
        metavar="NAME",
        help="CI check that may be SKIPPED without blocking (opt-in jobs such as 'live')",
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")

    check_ci(strict=args.strict, allow_skipped=tuple(args.allow_skipped_check))
    check_config()
    check_migrations()
    if not args.no_http:
        check_http(base, args.ops_token)
        check_controls(base)
    check_first_responder_db()
    check_backup(args)
    check_rollback()
    check_pilot_scope()

    return finalize(strict=args.strict)


def finalize(strict: bool) -> int:
    if strict:
        seen = {name for _, name, _ in results}
        for gate in REQUIRED_GATES:
            if gate not in seen:
                report("FAIL", gate, "gate produced no evidence (did not run)")
    blocking = ("FAIL", "WARN", "SKIP") if strict else ("FAIL",)
    fails = sum(1 for s, *_ in results if s in blocking)
    print("---")
    print(f"release check: {len(results)} checks, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
