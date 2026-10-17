"""Pillar 1 + Pillar 2 in ONE assessment through the default production path:
ORCHESTRATOR_FACTORY = security_agents.api:build_orchestrator (host mode).

A throwaway git repo holds the owned payments-lite target; the assessment is pinned to
its commit through the shared REPOSITORY_BINDINGS_FILE. Every model call - the reviewer's
and all seven security agents' - goes through the ONE backend LLMGateway. Scripted turns
(labeled provider_mode="fake"): Sai's pl_review_script for the reviewer and Alan's
fake_agents scripts for the security roles, routed by role in sa_bridge. Everything else
is real: git-pinned checkout, executed generated tests and sandboxed checks, patch +
independent Verify, PostgreSQL, API approval, durable resume via the worker, SSE."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

security_agents = pytest.importorskip("security_agents")
code_review = pytest.importorskip("code_review")
REPO_ROOT = Path(__file__).resolve().parents[2]
SAI_TESTS = Path(code_review.__file__).resolve().parents[1] / "tests"
PAYMENTS = REPO_ROOT / "examples" / "payments-lite"
if (
    not (PAYMENTS / "build_recipe.json").exists()
    or not (SAI_TESTS / "test_reviewer_agent.py").exists()
):
    pytest.skip(
        "payments-lite recipe / reviewer test scripts not available", allow_module_level=True
    )

from helpers import add_member  # noqa: E402

from backend import llm, worker  # noqa: E402

EXPECTED = ["scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        text=True,
    ).strip()


@pytest.fixture
def unified(tmp_path, settings_override, monkeypatch, client_factory):
    if str(SAI_TESTS) not in sys.path:
        sys.path.insert(0, str(SAI_TESTS))
    from cr_fakes import fake
    from sa_bridge import AlanScriptTransport
    from test_reviewer_agent import pl_repair_script, pl_review_script

    from security_agents.checks.library import BOUNDS, OWNERSHIP

    repo = tmp_path / "owned-repo"
    shutil.copytree(
        PAYMENTS,
        repo,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.egg-info", ".venv"),
    )
    (repo / "labels.yaml").unlink()  # the answer key never ships with the assessed repo
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "payments-lite")
    sha = _git(repo, "rev-parse", "HEAD")

    alice, bob = client_factory("alice"), client_factory("bob")
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": "acme/payments-lite"}
    ).json()["id"]
    bindings = tmp_path / "bindings.json"
    bindings.write_text(json.dumps([{"repo_id": rid, "local_path": str(repo), "subdir": "."}]))
    monkeypatch.delenv("SECURITY_AGENTS_TARGET_DIR", raising=False)
    monkeypatch.setenv("SECURITY_AGENTS_WORKDIR", str(tmp_path / "work"))
    settings_override(
        repository_bindings_file=str(bindings),
        security_sandbox="local-dev",
        orchestrator_factory="security_agents.api:build_orchestrator",
    )
    review_script = pl_review_script(SimpleNamespace(repo=repo))

    class _ReviewThenRepair:
        """Route reviewer-repair turns to Sai's repair script; everything else to review."""

        mode = "fake"

        def __init__(self, review: Any, repair: Any) -> None:
            self.review = review
            self.repair = repair

        def create(self, request: dict) -> Any:
            system = str(request.get("system") or "")
            if "Reviewer in repair mode" in system:
                return self.repair.create(request)
            return self.review.create(request)

    # generated-test path is unknown until review; the tamper attempt is optional
    repair = fake(list(pl_repair_script("tests/test_refund_total_bound.py")))
    fallback = _ReviewThenRepair(fake(list(review_script)), repair)
    bridge = AlanScriptTransport(repo / "target", fallback=fallback)
    llm.TRANSPORT_OVERRIDE = lambda: bridge
    sid = alice.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "payments-lite sandbox",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [
                {"kind": "sandbox_build", "repo_id": rid, "build_recipe_ref": "build_recipe.json"}
            ],
            "allowed_check_categories": [OWNERSHIP.category, BOUNDS.category],
        },
    ).json()["id"]
    assert bob.post(f"/api/v1/scopes/{sid}/approve").status_code == 200
    yield {"alice": alice, "bob": bob, "project": pid, "repo": rid, "scope": sid, "sha": sha}
    if str(SAI_TESTS) in sys.path:
        sys.path.remove(str(SAI_TESTS))


def _start(h) -> str:
    return (
        h["alice"]
        .post(
            f"/api/v1/projects/{h['project']}/assessments",
            json={"scope_id": h["scope"], "repo_id": h["repo"], "commit_sha": h["sha"]},
        )
        .json()["assessment"]["id"]
    )


def _decide(h, decision: str) -> None:
    pending = (
        h["alice"]
        .get(f"/api/v1/projects/{h['project']}/approvals", params={"status": "pending"})
        .json()["items"]
    )
    assert pending, "expected a pending remediation approval"
    for item in pending:
        r = h["bob"].post(f"/api/v1/approvals/{item['id']}/decision", json={"decision": decision})
        assert r.status_code == 200, r.text


def test_review_then_seven_agents_in_one_assessment(unified) -> None:
    h = unified
    asm_id = _start(h)
    worker.drain(kinds=["run_assessment"])
    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "AWAITING_APPROVAL", detail["assessment"]
    _decide(h, "approved")
    worker.drain(kinds=["run_assessment"])  # the approval's resume job continues remediation

    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    a = detail["assessment"]
    assert a["state"] == "COMPLETED", a
    assert a["commit_sha"] == h["sha"]
    runs = detail["agent_runs"]
    agents = [r["agent"] for r in runs]
    assert agents[0] == "reviewer"
    for role in EXPECTED:
        assert role in agents, role
    assert all(r["status"] == "succeeded" and r["provider_mode"] == "fake" for r in runs)
    model_runs = [
        r for r in runs if not str(r.get("step_key") or "").startswith("functional-verify:")
    ]
    assert model_runs and all(r["usage"]["llm_calls"] > 0 for r in model_runs), (
        "every model-backed run records usage"
    )
    assert any(str(r.get("step_key") or "").startswith("functional-verify:") for r in runs)
    assert a["usage"]["llm_calls"] == sum(r["usage"]["llm_calls"] for r in runs), (
        "one gateway, one ledger"
    )
    assert a["usage"]["tool_calls"] == sum(len(r["tool_calls"]) for r in runs) > 0
    assert a["usage"]["sandbox_seconds"] > 0, "Probe/Verify sandbox time reaches the ledger"
    kinds = {f["kind"] for f in detail["findings"]}
    assert kinds == {"functional", "security"}, detail["findings"]
    security = next(f for f in detail["findings"] if f["kind"] == "security")
    sec_body = h["alice"].get(f"/api/v1/findings/{security['id']}").json()["finding"]
    assert sec_body["status"] == "hardened", sec_body["status"]
    path = [(chg["from_status"], chg["to_status"]) for chg in sec_body["history"]]
    assert path == [
        ("hypothesis", "validated"),
        ("validated", "diagnosed"),
        ("diagnosed", "patch_proposed"),
        ("patch_proposed", "verified"),
        ("verified", "hardened"),
    ], path
    patches = h["alice"].get(f"/api/v1/findings/{security['id']}/patches").json()["items"]
    assert patches and patches[-1]["verification"]["verdict"] == "accepted"
    by_id = {r["id"]: r["agent"] for r in runs}
    assert by_id[patches[-1]["verification"]["produced_by_run_id"]] == "verify"
    functional = next(f for f in detail["findings"] if f["kind"] == "functional")
    fun_body = h["alice"].get(f"/api/v1/findings/{functional['id']}").json()["finding"]
    assert fun_body["status"] == "verified", fun_body["status"]
    fun_path = [(chg["from_status"], chg["to_status"]) for chg in fun_body["history"]]
    assert ("validated", "patch_proposed") in fun_path
    assert ("patch_proposed", "verified") in fun_path
    fun_patches = h["alice"].get(f"/api/v1/findings/{functional['id']}/patches").json()["items"]
    assert fun_patches, "validated functional defects must be repaired after approval"
    fun_ver = fun_patches[-1]["verification"]
    assert fun_ver["verdict"] == "accepted", fun_ver
    assert by_id[fun_ver["produced_by_run_id"]] == "verify"
    check_names = {c["name"] for c in fun_ver["checks"]}
    assert check_names == {
        "diff_scope_ok",
        "no_test_tampering",
        "original_check_now_fails_to_reproduce",
        "functional_suite_passes",
        "generated_tests_pass",
    }
    assert all(c["passed"] for c in fun_ver["checks"]), fun_ver["checks"]
    log = h["alice"].get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    assert any(
        "functional review" in e["message"] for e in log if e["type"] == "assessment.progress"
    )
    assert any(
        "checkpoint saved" in e["message"] for e in log if e["type"] == "assessment.progress"
    )


def test_declined_remediation_never_patches(unified) -> None:
    h = unified
    asm_id = _start(h)
    worker.drain(kinds=["run_assessment"])
    _decide(h, "declined")
    worker.drain(kinds=["run_assessment"])
    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED"
    assert "patch" not in [r["agent"] for r in detail["agent_runs"]]


def test_resume_survives_lost_in_memory_orchestrator(unified) -> None:
    """Worker restart: pipeline cache + in-memory pause are gone; checkpoint remains."""
    from backend import pipeline

    h = unified
    asm_id = _start(h)
    worker.drain(kinds=["run_assessment"])
    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "AWAITING_APPROVAL"
    pipeline._ORCHESTRATORS.clear()
    _decide(h, "approved")
    worker.drain(kinds=["run_assessment"])
    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED", detail["assessment"]
    security = next(f for f in detail["findings"] if f["kind"] == "security")
    body = h["alice"].get(f"/api/v1/findings/{security['id']}").json()["finding"]
    assert body["status"] == "hardened", body["status"]
    patches = h["alice"].get(f"/api/v1/findings/{security['id']}/patches").json()["items"]
    assert patches and patches[-1]["verification"]["verdict"] == "accepted"


def test_unbound_repository_fails_honestly(unified, settings_override, tmp_path) -> None:
    empty = tmp_path / "none.json"
    empty.write_text("[]")
    settings_override(repository_bindings_file=str(empty))
    asm_id = _start(unified)
    worker.drain(kinds=["run_assessment"])
    a = unified["alice"].get(f"/api/v1/assessments/{asm_id}").json()["assessment"]
    assert a["state"] == "FAILED" and a["error"]["code"] in (
        "SNAPSHOT_NOT_READY",
        "SUBSYSTEM_UNAVAILABLE",
    ), a
