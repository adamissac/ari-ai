"""Fix delivery (ADR-0020): owner-stamped pre-approval, push, PR fallback.

The orchestrator is the TEST DOUBLE in reference_orchestrator.py. push_patch runs real git
against a local bare repository standing in for GitHub; the delivery job's GitHub calls are
faked so the wiring (modes, fallback, audit) is exercised without a network."""

from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from helpers import post_webhook, push_payload, setup_project
from reference_orchestrator import scripted_transport

from backend import delivery, llm, worker
from backend.checkouts import CheckoutError, fetch_commit
from backend.db import audit_events, jobs, memberships, repositories, transaction
from backend.delivery import BranchMoved, authority, push_patch


@pytest.fixture
def reference(settings_override):
    settings_override(orchestrator_factory="reference_orchestrator:build_orchestrator")
    llm.TRANSPORT_OVERRIDE = scripted_transport


def _set_mode(client, pid: str, mode: str, **extra: object):
    settings = client.get(f"/api/v1/projects/{pid}").json()["settings"]
    return client.patch(
        f"/api/v1/projects/{pid}", json={"settings": settings | {"delivery_mode": mode} | extra}
    )


def _actions() -> list[str]:
    with transaction() as conn:
        return [d["action"] for d in conn.execute(sa.select(audit_events.c.doc)).scalars()]


def _run_push(client, pid: str) -> str:
    assert post_webhook(client, push_payload(["app/invoices.py"])).status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    worker.drain(kinds=["run_assessment"])
    return client.get(f"/api/v1/projects/{pid}/reassessments").json()["items"][0]["assessment_id"]


def test_new_projects_default_to_auto_and_server_stamps_the_authorizer(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    p = alice.post("/api/v1/projects", json={"name": "fresh"}).json()
    assert p["settings"]["delivery_mode"] == "auto"
    assert p["settings"]["delivery_authorized_by"] == alice.me["user"]["id"]
    pid = ids["project"]
    r = _set_mode(alice, pid, "auto", delivery_authorized_by="usr_forged123")
    assert r.json()["settings"]["delivery_authorized_by"] == alice.me["user"]["id"]
    # Same mode saved by another owner keeps the original authorizer; a mode change restamps.
    assert (
        _set_mode(bob, pid, "auto").json()["settings"]["delivery_authorized_by"]
        == (alice.me["user"]["id"])
    )
    s = _set_mode(bob, pid, "pull_request").json()["settings"]
    assert s["delivery_authorized_by"] == bob.me["user"]["id"]


def test_a_member_cannot_create_a_project_that_delivers_code(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    from helpers import add_member

    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, bob.me["user"]["id"], "member")
    r = bob.post("/api/v1/projects", json={"name": "m", "org_id": org_id})
    assert r.status_code == 201, r.text
    assert r.json()["settings"]["delivery_mode"] == "manual"


def test_manual_mode_keeps_the_human_gate(client_factory, reference) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    _run_push(alice, ids["project"])
    pending = alice.get(
        f"/api/v1/projects/{ids['project']}/approvals", params={"status": "pending"}
    ).json()["items"]
    assert len(pending) == 1


def test_authority_ends_when_the_authorizer_stops_being_an_owner(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    _set_mode(alice, ids["project"], "auto")
    with transaction() as conn:
        assert authority(conn, ids["project"]) == ("auto", alice.me["user"]["id"])
        conn.execute(
            sa.update(memberships)
            .where(memberships.c.user_id == alice.me["user"]["id"])
            .values(role="viewer")
        )
        assert authority(conn, ids["project"]) is None


def test_auto_approves_in_owner_name_and_queues_delivery(client_factory, reference) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    _set_mode(alice, ids["project"], "auto")
    asm_id = _run_push(alice, ids["project"])
    assert alice.get(f"/api/v1/assessments/{asm_id}").json()["assessment"]["state"] == "COMPLETED"
    approved = alice.get(
        f"/api/v1/projects/{ids['project']}/approvals", params={"status": "approved"}
    ).json()["items"]
    remediation = [a for a in approved if a["subject_type"] == "remediation"]
    assert remediation and remediation[0]["decided_by"] == alice.me["user"]["id"]
    with transaction() as conn:
        assert "deliver_verified_patch" in conn.execute(sa.select(jobs.c.kind)).scalars().all()
    # The test repository is not connected through the GitHub App: nothing is pushed.
    worker.drain(kinds=["deliver_verified_patch"])
    assert {"approval.auto_approved", "delivery.failed"} <= set(_actions())


def test_switching_on_unblocks_a_run_already_waiting(client_factory, reference) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    asm_id = _run_push(alice, ids["project"])
    assert (
        alice.get(f"/api/v1/assessments/{asm_id}").json()["assessment"]["state"]
        == "AWAITING_APPROVAL"
    )
    _set_mode(alice, ids["project"], "pull_request")
    worker.drain(kinds=["run_assessment"])
    assert alice.get(f"/api/v1/assessments/{asm_id}").json()["assessment"]["state"] == "COMPLETED"


class FakeApp:
    """Stands in for GitHubApp; records what delivery asked GitHub to do."""

    calls: list[tuple] = []
    token_error: Exception | None = None

    def __init__(self, settings=None) -> None: ...

    def installation_token(self, installation_id: int, *, write: bool = False) -> str:
        if FakeApp.token_error:
            raise FakeApp.token_error
        assert write
        return "tok"

    def open_pull_request(self, installation_id, full_name, **kw) -> str:
        FakeApp.calls.append(("pr", kw["head"], kw["base"]))
        return "https://github.com/acme/payments-lite/pull/1"


@pytest.fixture
def wired(client_factory, reference, settings_override, tmp_path, monkeypatch):
    """A completed auto/pull_request run whose repository 'is connected', GitHub faked."""
    settings_override(security_workdir=str(tmp_path))
    FakeApp.calls, FakeApp.token_error = [], None
    monkeypatch.setattr("backend.github.GitHubApp", FakeApp)
    monkeypatch.setattr(delivery, "fetch_commit", lambda *a, **k: None)

    def push(*a, require_tip=False, **k):
        FakeApp.calls.append(("push", a[6], require_tip))
        if require_tip and FakeApp.moved:
            raise BranchMoved("main moved since the assessed commit")
        return "c" * 40

    FakeApp.moved = False
    monkeypatch.setattr(delivery, "push_patch", push)

    def start(mode: str) -> None:
        alice, bob = client_factory("alice"), client_factory("bob")
        ids = setup_project(alice, bob)
        _set_mode(alice, ids["project"], mode)
        _run_push(alice, ids["project"])
        with transaction() as conn:
            conn.execute(sa.update(repositories).values(installation_id=7))

    return start


def test_auto_pushes_to_the_default_branch(wired) -> None:
    wired("auto")
    worker.drain(kinds=["deliver_verified_patch"])
    assert FakeApp.calls == [("push", "main", True)]
    assert "delivery.pushed" in _actions()


def test_auto_falls_back_to_a_pr_when_the_branch_moved(wired) -> None:
    FakeApp.moved = True
    wired("auto")
    worker.drain(kinds=["deliver_verified_patch"])
    assert [c[0] for c in FakeApp.calls] == ["push", "push", "pr"]
    assert "delivery.pr_opened" in _actions() and "delivery.pushed" not in _actions()


def test_pull_request_mode_never_touches_the_default_branch(wired) -> None:
    wired("pull_request")
    worker.drain(kinds=["deliver_verified_patch"])
    pushes = [c for c in FakeApp.calls if c[0] == "push"]
    assert len(pushes) == 1 and pushes[0][1].startswith("ari/fix-") and not pushes[0][2]
    assert ("pr", pushes[0][1], "main") in FakeApp.calls


def test_missing_app_permission_is_recorded(wired) -> None:
    resp = httpx.Response(403, request=httpx.Request("POST", "https://api.github.com/x"))
    FakeApp.token_error = httpx.HTTPStatusError("403", request=resp.request, response=resp)
    wired("auto")
    worker.drain(kinds=["deliver_verified_patch"])
    assert "delivery.failed" in _actions() and "delivery.pushed" not in _actions()


def test_switching_to_manual_skips_queued_delivery(wired, client_factory) -> None:
    wired("auto")
    alice = client_factory("alice")
    pid = alice.get("/api/v1/projects").json()["items"][0]["id"]
    _set_mode(alice, pid, "manual")
    worker.drain(kinds=["deliver_verified_patch"])
    assert "delivery.skipped" in _actions() and FakeApp.calls == []


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip


def _remote(tmp_path: Path) -> tuple[Path, Path, str]:
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
    base = _git("rev-parse", "main", cwd=remote).strip()
    fetch_commit(local, "acme/app", base, "tok", github_web_url=f"file://{root}")
    return root, remote, base


DIFF = b"""--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def owner(a, b):
-    return True
+    return a == b
"""


def test_push_patch_commits_onto_the_default_branch(tmp_path: Path) -> None:
    root, remote, base = _remote(tmp_path)
    sha = push_patch(
        tmp_path / "local.git", "acme/app", base, DIFF, "tok", "fix", "main",
        require_tip=True, github_web_url=f"file://{root}",
    )  # fmt: skip
    assert _git("rev-parse", "main", cwd=remote).strip() == sha
    assert "return a == b" in _git("show", "main:app.py", cwd=remote)
    assert _git("log", "-1", "--format=%an", "main", cwd=remote).strip() == "Ari"


def test_push_patch_refuses_when_the_branch_moved(tmp_path: Path) -> None:
    root, remote, base = _remote(tmp_path)
    local = tmp_path / "local.git"
    push_patch(local, "acme/app", base, DIFF, "t", "fix", "main", require_tip=True,
               github_web_url=f"file://{root}")  # fmt: skip
    tip = _git("rev-parse", "main", cwd=remote)
    with pytest.raises(BranchMoved):
        push_patch(local, "acme/app", base, DIFF, "t", "fix", "main", require_tip=True,
                   github_web_url=f"file://{root}")  # fmt: skip
    assert _git("rev-parse", "main", cwd=remote) == tip


def test_push_patch_to_a_new_branch_leaves_main_alone(tmp_path: Path) -> None:
    root, remote, base = _remote(tmp_path)
    push_patch(tmp_path / "local.git", "acme/app", base, DIFF, "t", "fix", "ari/fix-1",
               github_web_url=f"file://{root}")  # fmt: skip
    assert _git("rev-parse", "main", cwd=remote).strip() == base
    assert "return a == b" in _git("show", "ari/fix-1:app.py", cwd=remote)


def test_push_patch_rejects_a_patch_that_does_not_apply(tmp_path: Path) -> None:
    root, _, base = _remote(tmp_path)
    with pytest.raises(CheckoutError, match="does not apply"):
        push_patch(tmp_path / "local.git", "acme/app", base, b"garbage", "t", "fix", "x",
                   github_web_url=f"file://{root}")  # fmt: skip


@pytest.mark.parametrize("branch", ["../x", "main;rm", ""])
def test_push_patch_rejects_bad_branch(tmp_path: Path, branch: str) -> None:
    with pytest.raises(CheckoutError):
        push_patch(tmp_path, "acme/app", "a" * 40, DIFF, "tok", "fix", branch)
