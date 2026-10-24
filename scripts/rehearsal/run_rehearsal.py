"""Two-organization pilot rehearsal driver.

Runs the full rehearsal against a locally booted control plane with the REAL
provider and the REAL Vercel sandbox — no GitHub OAuth or Adam credentials
required (dev login is gated to development/test envs).

Usage:
    ANTHROPIC_API_KEY=... VERCEL_TOKEN=... \
        ../.venv/bin/python scripts/rehearsal/run_rehearsal.py [--base-url http://127.0.0.1:8000]

Boot first (from repo root, see docs/pilot/REHEARSAL.md):
    make dev   # or: APP_ENV=development AUTH_DEV_LOGIN_ENABLED=true \
               # SECURITY_SANDBOX=vercel REPOSITORY_BINDINGS_FILE=... \
               # uv run python -m backend.main  (+ worker)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"


def _req(
    base: str, method: str, path: str, body=None, headers=None
) -> tuple[int, dict, str | None]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}"), r.headers.get("Set-Cookie")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers.get("Set-Cookie")


def _login(base: str, login: str) -> dict:
    status, me, cookie = _req(base, "POST", "/api/v1/auth/dev/login", {"github_login": login})
    assert status == 200 and cookie, (status, me)
    session = cookie.split("hackatl_session=")[1].split(";")[0]
    return {"Cookie": f"hackatl_session={session}", "X-CSRF-Token": me["csrf_token"]}


def _auth(h: dict, method: str, base: str, path: str, body=None) -> tuple[int, dict]:
    status, body_out, _ = _req(base, method, path, body, headers=h)
    return status, body_out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--repo-path", default=str(Path(__file__).resolve().parent / "target-app"))
    args = p.parse_args()
    base = args.base_url
    EVIDENCE_DIR.mkdir(exist_ok=True)
    results: list[dict] = []

    def record(step: str, ok: bool, detail: dict | str) -> None:
        results.append({"step": step, "ok": ok, "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {step}: {str(detail)[:140]}")

    # --- Org A -------------------------------------------------------------
    ha = _login(base, "rehearsal-org-a")
    s, proj_a = _auth(ha, "POST", base, "/api/v1/projects", {"name": "rehearsal-a"})
    record("org A project", s == 201, proj_a)
    if s != 201:
        return _finish(results, 1)
    pa = proj_a["id"]

    s, repo_a = _auth(
        ha, "POST", base, f"/api/v1/projects/{pa}/repositories",
        {"name": "books-target", "local_path": args.repo_path, "default_branch": "main"},
    )
    record("org A repository bind", s in (200, 201), repo_a)
    ra = repo_a.get("id")

    s, scope_a = _auth(
        ha, "POST", base, f"/api/v1/projects/{pa}/scopes",
        {"name": "rehearsal-a-scope", "repo_ids": [ra] if ra else []},
    )
    record("org A scope create", s in (200, 201), scope_a)
    if s in (200, 201):
        s2, appr = _auth(ha, "POST", base, f"/api/v1/scopes/{scope_a['id']}/approve", {})
        record("org A scope approve", s2 == 200, appr)

    s, asm_a = _auth(ha, "POST", base, f"/api/v1/projects/{pa}/assessments", {})
    record("org A assessment start (real provider+sandbox)", s in (200, 201, 202), asm_a)
    aid = asm_a.get("id")
    if aid:
        for _ in range(120):
            time.sleep(5)
            s, cur = _auth(ha, "GET", base, f"/api/v1/assessments/{aid}")
            if cur.get("status") in {"completed", "failed", "cancelled"}:
                break
        record("org A assessment finished", cur.get("status") == "completed", cur.get("status"))
        s, findings = _auth(ha, "GET", base, f"/api/v1/assessments/{aid}/findings")
        record("org A genuine findings", s == 200 and bool(findings.get("items")), 
               [f.get("title") for f in findings.get("items", [])][:8])

    # --- Org B (isolation proof) --------------------------------------------
    hb = _login(base, "rehearsal-org-b")
    s, proj_b = _auth(hb, "POST", base, "/api/v1/projects", {"name": "rehearsal-b"})
    record("org B project", s == 201, proj_b)

    s, out = _auth(hb, "GET", base, f"/api/v1/projects/{pa}")
    record("org B cannot read org A project", s in (403, 404), s)
    s, out = _auth(hb, "GET", base, f"/api/v1/assessments/{aid or 'x'}")
    record("org B cannot read org A assessment", s in (403, 404), s)
    s, out = _auth(hb, "GET", base, f"/api/v1/projects/{pa}/repositories")
    record("org B cannot list org A repositories", s in (403, 404), s)

    # --- Ingest / defense-lab surface ---------------------------------------
    s, app_b = _auth(
        hb, "POST", base, f"/api/v1/projects/{proj_b.get('id')}/applications",
        {"name": "books staging", "environment": "owned_test"},
    )
    record("org B owned_test application", s in (200, 201), app_b)

    return _finish(results, 0 if all(r["ok"] for r in results) else 1)


def _finish(results: list[dict], code: int) -> int:
    out = EVIDENCE_DIR / "rehearsal-run.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nEvidence: {out}")
    fails = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(fails)}/{len(results)} steps passed")
    return code or (1 if fails else 0)


if __name__ == "__main__":
    sys.exit(main())
