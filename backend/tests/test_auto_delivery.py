"""Auto delivery (ADR-0020): owner-stamped pre-approval and push of Verify-accepted patches.

The orchestrator is the TEST DOUBLE in reference_orchestrator.py; push_patch runs real git
against a local bare repository standing in for GitHub."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from helpers import post_webhook, push_payload, setup_project
from reference_orchestrator import scripted_transport

from backend import llm, worker
from backend.checkouts import CheckoutError
from backend.db import audit_events, jobs, transaction
from backend.delivery import push_patch


@pytest.fixture
def reference(settings_override):
    settings_override(orchestrator_factory="reference_orchestrator:build_orchestrator")
    llm.TRANSPORT_OVERRIDE = scripted_transport


def _set_mode(client, pid: str, mode: str, **extra: object):
    settings = client.get(f"/api/v1/projects/{pid}").json()["settings"]
    return client.patch(
        f"/api/v1/projects/{pid}", json={"settings": settings | {"delivery_mode": mode} | extra}
    )


def test_server_stamps_the_authorizing_owner(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    r = _set_mode(alice, ids["project"], "auto", auto_delivery_enabled_by="usr_forged123")
    assert r.status_code == 200, r.text
    s = r.json()["settings"]
    assert s["delivery_mode"] == "auto"
    assert s["auto_delivery_enabled_by"] == alice.me["user"]["id"]
    # A later save by another owner keeps the original authorizer.
    assert (
        _set_mode(bob, ids["project"], "auto").json()["settings"]["auto_delivery_enabled_by"]
        == alice.me["user"]["id"]
    )
    s = _set_mode(bob, ids["project"], "review").json()["settings"]
    assert s["delivery_mode"] == "review" and s["auto_delivery_enabled_by"] is None


def test_review_mode_keeps_the_human_gate(client_factory, reference) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    assert post_webhook(alice, push_payload(["app/invoices.py"])).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    worker.drain(kinds=["run_assessment"])
    pending = alice.get(
        f"/api/v1/projects/{ids['project']}/approvals", params={"status": "pending"}
    ).json()["items"]
    assert len(pending) == 1


def test_auto_mode_approves_in_owner_name_and_queues_delivery(client_factory, reference) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    assert _set_mode(alice, ids["project"], "auto").status_code == 200
    assert post_webhook(alice, push_payload(["app/invoices.py"])).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    worker.drain(kinds=["run_assessment"])  # pauses, auto-approves, resumes

    asm_id = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"][0][
        "assessment_id"
    ]
    detail = alice.get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED"
    approved = alice.get(
        f"/api/v1/projects/{ids['project']}/approvals", params={"status": "approved"}
    ).json()["items"]
    remediation = [a for a in approved if a["subject_type"] == "remediation"]
    assert remediation and remediation[0]["decided_by"] == alice.me["user"]["id"]

    with transaction() as conn:
        kinds = conn.execute(sa.select(jobs.c.kind)).scalars().all()
    assert "deliver_verified_patch" in kinds
    # The test repository is not connected through the GitHub App: nothing is pushed.
    worker.drain(kinds=["deliver_verified_patch"])
    with transaction() as conn:
        actions = conn.execute(sa.select(audit_events.c.doc)).scalars().all()
    actions = [d["action"] for d in actions]
    assert "approval.auto_approved" in actions and "delivery.failed" in actions
    assert "delivery.pushed" not in actions


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip


def _remote(tmp_path: Path) -> tuple[Path, Path]:
    """A bare 'GitHub' repo at <root>/acme/app.git with one commit on main."""
    root = tmp_path / "gh"
    remote = root / "acme" / "app.git"
    remote.mkdir(parents=True)
    _git("init", "--bare", "--quiet", "-b", "main", str(remote), cwd=tmp_path)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "--quiet", "-b", "main", cwd=seed)
    (seed / "app.py").write_text("def owner(a, b):\n    return True\n")
    _git("add", ".", cwd=seed)
    _git("commit", "--quiet", "-m", "init", cwd=seed)
    _git("push", "--quiet", str(remote), "main", cwd=seed)
    local = tmp_path / "local.git"
    _git("init", "--bare", "--quiet", str(local), cwd=tmp_path)
    return root, local


DIFF = b"""--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def owner(a, b):
-    return True
+    return a == b
"""


def test_push_patch_commits_onto_branch_tip(tmp_path: Path) -> None:
    root, local = _remote(tmp_path)
    sha = push_patch(
        local, "acme/app", "main", DIFF, "tok", "fix: owner", github_web_url=f"file://{root}"
    )
    remote = root / "acme" / "app.git"
    assert _git("rev-parse", "main", cwd=remote).strip() == sha
    assert "return a == b" in _git("show", "main:app.py", cwd=remote)
    assert _git("log", "-1", "--format=%an", "main", cwd=remote).strip() == "Ari"


def test_push_patch_refuses_a_patch_that_no_longer_applies(tmp_path: Path) -> None:
    root, local = _remote(tmp_path)
    push_patch(local, "acme/app", "main", DIFF, "tok", "fix", github_web_url=f"file://{root}")
    before = _git("rev-parse", "main", cwd=root / "acme" / "app.git")
    with pytest.raises(CheckoutError, match="no longer applies"):
        push_patch(local, "acme/app", "main", DIFF, "tok", "fix", github_web_url=f"file://{root}")
    assert _git("rev-parse", "main", cwd=root / "acme" / "app.git") == before


@pytest.mark.parametrize("branch", ["../x", "main;rm", ""])
def test_push_patch_rejects_bad_branch(tmp_path: Path, branch: str) -> None:
    with pytest.raises(CheckoutError):
        push_patch(tmp_path, "acme/app", branch, DIFF, "tok", "fix")
