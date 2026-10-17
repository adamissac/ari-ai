"""Tier 2 integration: the reviewer against the REAL backend AssessmentHost on PostgreSQL.

review -> persisted AgentRun/transcript/findings -> approval gate (API decision) ->
repair -> persisted PatchCandidate -> the reviewer CANNOT record a verdict for its own
patch -> an independent verify run (a labeled TEST DOUBLE standing in for Alan's Verify
agent) replays trusted tests in a fresh export and records accepted / rejected verdicts.

LLM provider: scripted FakeTransport via backend.llm.TRANSPORT_OVERRIDE (not live).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa

# Running this package alone: bootstrap like backend/tests/conftest.py. Reuse ONE embedded
# server at .dev/pgtest (never one per run: leaked postmasters exhaust SysV shared memory on
# macOS), create a fresh database for this module and drop it when the module finishes.
_OWN_DB: tuple[str, str] | None = None
if os.environ.get("APP_ENV") != "test":
    _tmp = Path(tempfile.mkdtemp(prefix="cr-artifacts-"))
    _admin_url = os.environ.get("TEST_DATABASE_URL")
    if not _admin_url:
        from backend.devdb import start

        _admin_url = start(
            Path(__file__).resolve().parents[2] / ".dev" / "pgtest", database="postgres"
        )
    _name = f"cr_test_{uuid.uuid4().hex[:8]}"
    _admin = sa.create_engine(
        _admin_url.replace("postgresql://", "postgresql+psycopg://", 1),
        isolation_level="AUTOCOMMIT",
    )
    with _admin.connect() as _c:
        _c.execute(sa.text(f'CREATE DATABASE "{_name}"'))
    _admin.dispose()
    _OWN_DB = (_admin_url, _name)
    os.environ.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": sa.engine.make_url(_admin_url)
            .set(database=_name)
            .render_as_string(hide_password=False),
            "ARTIFACT_STORE_URI": f"file://{_tmp / 'artifacts'}",
            "AUTH_DEV_LOGIN_ENABLED": "true",
            "ANTHROPIC_API_KEY": "",
        }
    )
    from backend.settings import get_settings

    get_settings.cache_clear()
    from backend.migrate import upgrade

    upgrade()


@pytest.fixture(scope="module", autouse=True)
def _drop_own_database():
    yield
    if _OWN_DB is None:
        return
    from backend.db import get_engine

    get_engine().dispose()
    admin_url, name = _OWN_DB
    admin = sa.create_engine(
        admin_url.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as c:
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


from cr_fakes import fake, make_request  # noqa: E402
from cr_scenarios import payments_lite  # noqa: E402
from test_reviewer_agent import pl_repair_script, pl_review_script  # noqa: E402

from backend import llm  # noqa: E402
from backend.db import memberships, transaction  # noqa: E402
from backend.host import AgentRunStatus, AssessmentHost, HostError  # noqa: E402
from code_review import api  # noqa: E402
from code_review.ports import RepoSource  # noqa: E402
from code_review.sandbox import LocalProcessSandbox, classify  # noqa: E402
from code_review.workspace import (  # noqa: E402
    Workspace,
    apply_unified_diff,
    diff_target_paths,
    is_protected_path,
    tree_digest,
)
from shared.assessment import AgentName, AssessmentState  # noqa: E402
from shared.base import utcnow  # noqa: E402
from shared.evidence import ArtifactKind, EvidenceKind, EvidenceRef  # noqa: E402
from shared.findings import (  # noqa: E402
    FindingStatus,
    PatchCandidate,
    VerificationCheck,
    VerificationCheckName,
    VerificationResult,
    VerificationVerdict,
)
from shared.ids import IdPrefix, new_id  # noqa: E402
from shared.scope import ApprovalSubject  # noqa: E402

S = AssessmentState


@pytest.fixture
def clients():
    from fastapi.testclient import TestClient

    from backend.main import create_app

    made = []

    def login(name: str):
        c = TestClient(create_app())
        made.append(c)
        r = c.post("/api/v1/auth/dev/login", json={"github_login": name})
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        c.me = r.json()  # type: ignore[attr-defined]
        return c

    suffix = uuid.uuid4().hex[:6]
    yield login(f"cr-alice-{suffix}"), login(f"cr-bob-{suffix}")
    for c in made:
        c.close()
    llm.TRANSPORT_OVERRIDE = None


def _assessment(alice, bob, commit_sha: str) -> dict[str, str]:
    org = alice.me["memberships"][0]["organization"]["id"]
    with transaction() as conn:
        conn.execute(
            sa.insert(memberships).values(org_id=org, user_id=bob.me["user"]["id"], role="owner")
        )
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": f"acme/payments-lite-{uuid.uuid4().hex[:6]}", "installation_id": None},
    ).json()["id"]
    sid = alice.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "sandbox",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [
                {
                    "kind": "sandbox_build",
                    "repo_id": rid,
                    "build_recipe_ref": "examples/payments-lite",
                    "exposed_ports": [],
                }
            ],
        },
    ).json()["id"]
    assert bob.post(f"/api/v1/scopes/{sid}/approve").status_code == 200
    r = alice.post(
        f"/api/v1/projects/{pid}/assessments",
        json={"scope_id": sid, "repo_id": rid, "commit_sha": commit_sha},
    )
    assert r.status_code == 202, r.text  # queued; this test drives the host directly
    return {"project": pid, "repo": rid, "assessment": r.json()["assessment"]["id"]}


def _verify_double(
    host: AssessmentHost, source: RepoSource, patch: PatchCandidate, finding
) -> VerificationResult:
    """TEST DOUBLE for the independent Verify agent: separate run, fresh export, trusted tests."""
    run_id = host.start_agent_run(
        AgentName.verify,
        f"verify:{patch.id}",
        provider_mode="fake",
        model_id=None,
        prompt_version="verify@test-double",
    )
    diff = api.read_artifact(host, patch.diff_artifact_id).decode()
    tests = api.load_test_sources(host, finding)  # the tests cited when the bug was validated
    ws = Workspace.export(source, patch.base_commit_sha)
    sbx = LocalProcessSandbox()
    try:
        scope_ok = not any(is_protected_path(p) for p in diff_target_paths(diff))
        applied, _ = apply_unified_diff(ws, diff)
        for t in tests:
            ws.write(t.path, t.content)
            ws.write(t.path.rsplit("/", 1)[0] + "/__init__.py", "")
        gen = sbx.run_pytest(ws.project_dir, [ws.project_rel(t.path) for t in tests], timeout_s=120)
        suite = sbx.run_pytest(ws.project_dir, ["tests/test_api.py"], timeout_s=120)
    finally:
        ws.close()
    art = host.store_json(
        {"generated": gen.to_json(), "suite": suite.to_json()}, ArtifactKind.test_report
    )
    ev = [
        EvidenceRef(
            kind=EvidenceKind.test_run,
            artifact_id=art.id,
            sha256=art.sha256,
            provenance="verify-double",
        )
    ]
    checks = [
        VerificationCheck(
            name=VerificationCheckName.diff_scope_ok, passed=applied and scope_ok, evidence=ev
        ),
        VerificationCheck(
            name=VerificationCheckName.no_test_tampering, passed=scope_ok, evidence=ev
        ),
        VerificationCheck(
            name=VerificationCheckName.original_check_now_fails_to_reproduce,
            passed=applied and classify(gen) == "passed",
            evidence=ev,
        ),
        VerificationCheck(
            name=VerificationCheckName.generated_tests_pass,
            passed=applied and classify(gen) == "passed",
            evidence=ev,
        ),
        VerificationCheck(
            name=VerificationCheckName.functional_suite_passes,
            passed=classify(suite) == "passed",
            evidence=ev,
        ),
    ]
    ok = all(c.passed for c in checks)
    result = VerificationResult(
        id=new_id(IdPrefix.ver),
        patch_id=patch.id,
        verdict=VerificationVerdict.accepted if ok else VerificationVerdict.rejected,
        checks=checks,
        sandbox_run_ids=[art.id],
        produced_by_run_id=run_id,
        created_at=utcnow(),
    )
    host.finish_agent_run(run_id, AgentRunStatus.succeeded, output=result.model_dump(mode="json"))
    return host.record_verification(result)


def test_reviewer_through_real_assessment_host(tmp_path: Path, clients) -> None:
    alice, bob = clients
    sc = payments_lite(tmp_path)
    source = RepoSource(sc.repo, subdir="target")
    before = tree_digest(source)
    ids = _assessment(alice, bob, sc.head_sha)
    host = AssessmentHost(ids["assessment"])
    for state in (S.SCOPE_CHECK, S.INDEXING, S.FUNCTIONAL_REVIEW):
        host.transition(state)

    transport = fake(pl_review_script(sc))
    llm.TRANSPORT_OVERRIDE = lambda: transport
    req = make_request(host, sc).model_copy(
        update={
            "snapshot_ref": make_request(host, sc).snapshot_ref.model_copy(
                update={"project_id": host.project_id, "repo_id": host.repo_id}
            )
        }
    )
    result = api.review(host, req, source=source, intelligence=False)
    [finding] = host.findings()
    assert finding.id == result.findings[0].id and finding.status is FindingStatus.validated
    run = host.agent_run(result.agent_run_id)
    assert run.agent is AgentName.reviewer and run.status is AgentRunStatus.succeeded
    assert run.provider_mode == "fake" and run.transcript_artifact_id and run.output_artifact_id
    assert len(run.tool_calls) == 6 and host.assessment.usage.llm_calls == 6

    detail = alice.get(f"/api/v1/assessments/{ids['assessment']}").json()
    assert detail["findings"][0]["status"] == "validated"
    assert [r["agent"] for r in detail["agent_runs"]] == ["reviewer"]

    for state in (S.RECON, S.VALIDATION, S.ANALYSIS, S.DIAGNOSIS, S.AWAITING_APPROVAL):
        host.transition(state)
    ap = host.request_approval(ApprovalSubject.remediation, finding.id, "fix refund bound")
    with pytest.raises(api.ReviewError) as e:  # pending approval cannot authorize a repair
        api.propose_repair(host, finding.id, ap.id, repo_id=host.repo_id, source=source)
    assert e.value.code.value == "APPROVAL_REQUIRED"
    r = bob.post(
        f"/api/v1/approvals/{ap.id}/decision", json={"decision": "approved", "reason": "go"}
    )
    assert r.status_code == 200, r.text
    host.transition(S.REMEDIATION)

    tests = api.load_test_sources(host, finding)
    repair_transport = fake(pl_repair_script(tests[0].path))
    llm.TRANSPORT_OVERRIDE = lambda: repair_transport
    rep = api.propose_repair(host, finding.id, ap.id, repo_id=host.repo_id, source=source)
    assert rep.accepted_locally and rep.patch is not None, rep.reasons
    patches = alice.get(f"/api/v1/findings/{finding.id}/patches").json()["items"]
    assert patches[0]["patch"]["id"] == rep.patch.id and patches[0]["verification"] is None
    assert host.findings()[0].status is FindingStatus.patch_proposed

    # the reviewer cannot certify its own patch
    ev = [
        EvidenceRef(
            kind=EvidenceKind.test_run,
            artifact_id=rep.test_report_artifact_id,
            sha256="0" * 64,
            provenance="x",
        )
    ]
    self_verdict = VerificationResult(
        id=new_id(IdPrefix.ver),
        patch_id=rep.patch.id,
        verdict=VerificationVerdict.accepted,
        checks=[
            VerificationCheck(
                name=VerificationCheckName.generated_tests_pass, passed=True, evidence=ev
            )
        ],
        sandbox_run_ids=["local"],
        produced_by_run_id=rep.agent_run_id,
        created_at=utcnow(),
    )
    with pytest.raises(HostError) as he:
        host.record_verification(self_verdict)
    assert he.value.code.value == "FORBIDDEN"

    # independent verify (test double) accepts the real candidate...
    verdict = _verify_double(host, source, rep.patch, finding)
    assert verdict.verdict is VerificationVerdict.accepted
    # ...and rejects a tampering candidate that edits the requirement test instead
    gen_path = tests[0].path
    bad_diff = (
        f"--- a/{gen_path}\n+++ b/{gen_path}\n@@ -1,1 +1,1 @@\n-from fastapi.testclient import TestClient\n"
        "+from fastapi.testclient import TestClient  # weakened\n"
    )
    art = host.store_text(bad_diff, ArtifactKind.diff)
    bad = rep.patch.model_copy(
        update={
            "id": new_id(IdPrefix.pat),
            "diff_artifact_id": art.id,
            "diff_sha256": art.sha256,
            "attempt": 2,
        }
    )
    host.record_patch(bad)
    assert _verify_double(host, source, bad, finding).verdict is VerificationVerdict.rejected
    assert tree_digest(source) == before


def test_review_assessment_entry_uses_recorded_snapshot(tmp_path: Path, clients) -> None:
    from backend.db import snapshots
    from shared.intelligence import Snapshot, SnapshotStatus

    alice, bob = clients
    sc = payments_lite(tmp_path)
    source = RepoSource(sc.repo, subdir="target")
    ids = _assessment(alice, bob, sc.head_sha)
    host = AssessmentHost(ids["assessment"])
    for state in (S.SCOPE_CHECK, S.INDEXING, S.FUNCTIONAL_REVIEW):
        host.transition(state)
    with pytest.raises(api.ReviewError) as e:  # nothing indexed yet: refuse, don't invent a ref
        api.review_assessment(host, source=source, intelligence=False)
    assert e.value.code.value == "SNAPSHOT_NOT_READY"

    snap = Snapshot(
        id=new_id(IdPrefix.snp),
        repo_id=host.repo_id,
        commit_sha=sc.head_sha,
        status=SnapshotStatus.ready,
        index_version="intel-test",
        created_at=utcnow(),
    )
    with transaction() as conn:
        conn.execute(
            sa.insert(snapshots).values(
                id=snap.id,
                repo_id=snap.repo_id,
                commit_sha=snap.commit_sha,
                index_version=snap.index_version,
                status=snap.status.value,
                doc=snap.model_dump(mode="json"),
            )
        )
    transport = fake(pl_review_script(sc))
    llm.TRANSPORT_OVERRIDE = lambda: transport
    outcome = api.review_assessment(host, source=source, intelligence=False)
    assert outcome.result.findings[0].status is FindingStatus.validated
    inp = host.agent_run(outcome.result.agent_run_id).input_artifact_id
    payload = json.loads(api.read_artifact(host, inp))
    ref = payload["request"]["snapshot_ref"]
    assert ref["snapshot_id"] == snap.id and ref["index_version"] == "intel-test"
    assert payload["request"]["change_intent"]["source"] == "manual"


def test_functional_remediation_helpers_respect_human_decisions(tmp_path: Path, clients) -> None:
    alice, bob = clients
    sc = payments_lite(tmp_path)
    source = RepoSource(sc.repo, subdir="target")
    ids = _assessment(alice, bob, sc.head_sha)
    host = AssessmentHost(ids["assessment"])
    for state in (S.SCOPE_CHECK, S.INDEXING, S.FUNCTIONAL_REVIEW):
        host.transition(state)
    transport = fake(pl_review_script(sc))
    llm.TRANSPORT_OVERRIDE = lambda: transport
    req = make_request(host, sc)
    req = req.model_copy(
        update={
            "snapshot_ref": req.snapshot_ref.model_copy(
                update={"project_id": host.project_id, "repo_id": host.repo_id}
            )
        }
    )
    api.review(host, req, source=source, intelligence=False)
    [finding] = host.findings()

    [ap_id] = api.request_functional_approvals(host)
    assert api.request_functional_approvals(host) == []  # idempotent: one approval per finding
    assert (
        api.repair_approved_functional_findings(host, repo_id=host.repo_id, source=source) == []
    )  # pending

    r = bob.post(
        f"/api/v1/approvals/{ap_id}/decision", json={"decision": "declined", "reason": "no"}
    )
    assert r.status_code == 200, r.text
    assert api.repair_approved_functional_findings(host, repo_id=host.repo_id, source=source) == []
    assert host.findings()[0].status is FindingStatus.validated  # declined: never repaired

    # a later, separate approval for the same finding is honored
    ap2 = host.request_approval(ApprovalSubject.remediation, finding.id, "retry")
    assert (
        bob.post(f"/api/v1/approvals/{ap2.id}/decision", json={"decision": "approved"}).status_code
        == 200
    )
    tests = api.load_test_sources(host, finding)
    repair_transport = fake(pl_repair_script(tests[0].path))
    llm.TRANSPORT_OVERRIDE = lambda: repair_transport
    [rep] = api.repair_approved_functional_findings(host, repo_id=host.repo_id, source=source)
    assert rep.accepted_locally and rep.patch is not None
    assert host.findings()[0].status is FindingStatus.patch_proposed

    # Adam (20261017T093000Z): the real host redacts before hashing, so a stored diff's
    # hash can differ from a Patch-agent diff_sha256. Reviewer patches set diff_sha256 FROM
    # the stored artifact, so the integrity-checked Verify inputs hold on the real host.
    inp = api.functional_verification_inputs(host, rep.patch)
    stored = api.read_artifact(host, rep.patch.diff_artifact_id)
    assert hashlib.sha256(stored).hexdigest() == rep.patch.diff_sha256
    assert inp.diff_text == stored.decode() and inp.protected_paths == []
