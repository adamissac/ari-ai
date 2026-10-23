from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from conftest import WEBHOOK_SECRET

from backend.db import memberships, transaction
from backend.github import sign

HEAD = "b" * 40
BASE = "a" * 40
REPO = "acme/payments-lite"


def add_member(org_id: str, user_id: str, role: str = "owner") -> None:
    with transaction() as conn:
        conn.execute(sa.insert(memberships).values(org_id=org_id, user_id=user_id, role=role))


def setup_project(alice: Any, bob: Any, *, approve: bool = True) -> dict[str, str]:
    """Alice owns a project with a connected repo and requests a scope; Bob (co-owner) approves it."""
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, bob.me["user"]["id"])
    p = alice.post(
        "/api/v1/projects",
        json={
            "name": "payments-lite",
            # manual: tests drive the human approval gate; delivery modes have their own tests
            "settings": {"monitoring_policy": {"enabled": True}, "delivery_mode": "manual"},
        },
    )
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": REPO, "installation_id": None}
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert (
        alice.patch(f"/api/v1/repositories/{rid}", json={"automatic_assessments": True}).status_code
        == 200
    )
    expires = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    s = alice.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "sandbox",
            "expires_at": expires,
            "targets": [
                {
                    "kind": "sandbox_build",
                    "repo_id": rid,
                    "build_recipe_ref": "examples/payments-lite/sandbox.yaml",
                    "exposed_ports": [8080],
                }
            ],
            "allowed_check_categories": ["authorization.ownership"],
        },
    )
    assert s.status_code == 201, s.text
    sid = s.json()["id"]
    if approve:
        a = bob.post(f"/api/v1/scopes/{sid}/approve")
        assert a.status_code == 200, a.text
    return {"org": org_id, "project": pid, "repo": rid, "scope": sid}


def push_payload(
    paths: list[str], head: str = HEAD, base: str = BASE, repo: str = REPO
) -> dict[str, Any]:
    return {
        "ref": "refs/heads/main",
        "before": base,
        "after": head,
        "forced": False,
        "deleted": False,
        "repository": {"full_name": repo, "id": 1},
        "sender": {"login": "dev"},
        "installation": {"id": 99},
        "head_commit": {"timestamp": "2026-10-17T01:02:03Z", "message": "token ghp_" + "x" * 36},
        "commits": [{"added": [], "modified": paths, "removed": []}],
    }


def post_webhook(
    client: Any,
    payload: dict[str, Any],
    *,
    event: str = "push",
    delivery: str | None = None,
    secret: str = WEBHOOK_SECRET,
    signature: str | None = None,
) -> Any:
    raw = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery or str(uuid.uuid4()),
        "X-Hub-Signature-256": signature if signature is not None else sign(secret.encode(), raw),
        "Content-Type": "application/json",
    }
    return client.post("/api/v1/webhooks/github", content=raw, headers=headers)
