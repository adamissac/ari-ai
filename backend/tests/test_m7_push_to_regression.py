"""M7 gate (coordination/MILESTONES.md): ONE automated chain on the owned payments-lite
sandbox, from a signed GitHub push to verified regressions, through the default production
path (security_agents host mode + code_review on the one backend gateway).

signed push -> monitoring event -> reassessment -> assessment pinned to the pushed commit
-> functional review -> seven security agents -> human approvals (security + functional)
-> candidate patches -> independent security Verify and functional Verify -> verified
regressions recorded -> persisted SSE log and hash-chained audit.

Model turns are TEST-ONLY scripted transports (provider_mode="fake", plus the functional
Verify, which makes no model call: "none"). Everything else is real: HMAC webhook, queue,
git-pinned checkout, sandboxed checks and tests, PostgreSQL, API approvals.
"""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("security_agents")
pytest.importorskip("code_review")

from helpers import post_webhook, push_payload  # noqa: E402
from test_unified_assessment import _git, unified  # noqa: E402,F401  (fixture reuse)

from backend import worker  # noqa: E402

APP = "target/payments_lite/app.py"


def _drain_all() -> None:
    while worker.drain():
        pass


@pytest.mark.parametrize("automatic", [False, True])
def test_signed_push_drives_the_full_chain_to_verified_regressions(
    unified,  # noqa: F811
    automatic,
    settings_override,
    monkeypatch,
) -> None:
    h = unified
    alice, bob, pid = h["alice"], h["bob"], h["project"]

    # The project owner sizes the monitoring budget for the full chain (review + 7 agents +
    # functional repair) through the settings API; the 150k-token default is a cheaper scan.
    settings = alice.get(f"/api/v1/projects/{pid}").json()["settings"]
    settings["monitoring_policy"]["monitoring_budget"] = {
        "max_tokens": 400_000,
        "max_usd": 10.0,
        "max_wall_clock_s": 1800,
    }
    r = alice.patch(f"/api/v1/projects/{pid}", json={"settings": settings})
    assert r.status_code == 200, r.text

    # A real second commit on the owned repo (behaviour-neutral), pushed and signed.
    repo = h["repo_path"]
    path = repo / APP
    path.write_text(path.read_text() + "\n# m7: monitored change\n")
    _git(repo, "commit", "-qam", "touch payments app")
    head = _git(repo, "rev-parse", "HEAD")
    payload = push_payload([APP], head=head, base=h["sha"])
    if automatic:
        import sqlalchemy as sa

        from backend.db import repositories, transaction

        settings_override(github_auto_commit_authors="adamissac")
        with transaction() as conn:
            conn.execute(
                sa.update(repositories)
                .where(repositories.c.project_id == pid)
                .values(installation_id=99)
            )

        class GitHub:
            def commit(self, installation, full_name, sha):
                return {"sha": sha, "author": {"login": "adamissac"}}

        monkeypatch.setattr("backend.auto_commits.GitHubApp", GitHub)

        # External GitHub checkout is represented by the real owned fixture git repo.
        # Intelligence and agents still ingest and execute the exact pushed SHA.
        def owned_checkout(repo_id, commit_sha):
            assert commit_sha == head
            assert _git(repo, "rev-parse", commit_sha) == head
            return repo

        monkeypatch.setattr("backend.checkouts.ensure_checkout", owned_checkout)
        payload["commits"][0]["id"] = head
    delivery = str(uuid.uuid4())
    assert post_webhook(alice, payload, delivery=delivery).status_code == 202
    assert post_webhook(alice, payload, delivery=delivery).status_code in (200, 202)  # redelivery
    _drain_all()

    # Monitoring event -> reassessment -> assessment pinned to the pushed commit.
    ev = alice.get(f"/api/v1/projects/{pid}/events").json()["items"]
    assert len(ev) == 1, ev
    rrq = alice.get(f"/api/v1/projects/{pid}/reassessments").json()["items"]
    assert len(rrq) == 1 and rrq[0]["status"] == "started" and rrq[0]["assessment_id"], rrq
    asm_id = rrq[0]["assessment_id"]
    a = alice.get(f"/api/v1/assessments/{asm_id}").json()["assessment"]
    assert a["trigger"] == "monitoring" and a["commit_sha"] == head
    assert a["state"] == "AWAITING_APPROVAL", a

    # Humans decide both remediations (security fix + reviewer's functional repair).
    pending = alice.get(f"/api/v1/projects/{pid}/approvals", params={"status": "pending"}).json()
    assert len(pending["items"]) == 2, pending
    for ap in pending["items"]:
        r = bob.post(f"/api/v1/approvals/{ap['id']}/decision", json={"decision": "approved"})
        assert r.status_code == 200, r.text
    _drain_all()

    detail = alice.get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED", detail["assessment"]
    runs = detail["agent_runs"]
    agents = [r["agent"] for r in runs]
    for role in ("reviewer", "scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"):
        assert role in agents, role
    by_id = {r["id"]: r for r in runs}

    # Independent Verify accepted both the security and the functional patch.
    statuses = {}
    for f in detail["findings"]:
        patches = alice.get(f"/api/v1/findings/{f['id']}/patches").json()["items"]
        assert patches, f
        ver = patches[-1]["verification"]
        assert ver and ver["verdict"] == "accepted", (f["kind"], ver)
        assert by_id[ver["produced_by_run_id"]]["agent"] == "verify"
        assert ver["produced_by_run_id"] != patches[-1]["patch"]["produced_by_run_id"]
        statuses[f["kind"]] = alice.get(f"/api/v1/findings/{f['id']}").json()["finding"]["status"]
    assert statuses == {"security": "hardened", "functional": "verified"}, statuses

    # Accepted Verify results became verified-regression candidates in intelligence memory.
    snap = detail["assessment"]["snapshot_id"]
    assert snap, "the assessment ran against an indexed snapshot"
    regs = alice.get(f"/api/v1/snapshots/{snap}/regressions").json()["items"]
    assert len(regs) >= 1, regs
    assert {r["finding_id"] for r in regs} <= {f["id"] for f in detail["findings"]}

    # Human-inspectable traces: the durable event log and an intact hash chain.
    log = alice.get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    assert log[-1]["type"] == "assessment.completed"
    audit = alice.get("/api/v1/audit", params={"project_id": pid}).json()
    assert audit["chain_verified"] is True and audit["chain_events_checked"] > 0
