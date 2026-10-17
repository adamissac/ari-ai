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
    from test_reviewer_agent import pl_review_script

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
    registrations = tmp_path / "intelligence.json"
    registrations.write_text(
        json.dumps(
            [
                {
                    "project_id": pid,
                    "repo_id": rid,
                    "full_name": "acme/payments-lite",
                    "local_path": str(repo),
                    "include_prefix": "target",
                }
            ]
        )
    )
    monkeypatch.setenv("INTELLIGENCE_REPOSITORIES_FILE", str(registrations))
    monkeypatch.setenv("INTELLIGENCE_DB_PATH", str(tmp_path / "intelligence.sqlite"))
    monkeypatch.delenv("INTELLIGENCE_PAYLOAD_STORE_FACTORY", raising=False)
    monkeypatch.delenv("SECURITY_AGENTS_TARGET_DIR", raising=False)
    monkeypatch.setenv("SECURITY_AGENTS_WORKDIR", str(tmp_path / "work"))
    settings_override(
        repository_bindings_file=str(bindings),
        security_sandbox="local-dev",
        orchestrator_factory="security_agents.api:build_orchestrator",
    )
    review_script = pl_review_script(SimpleNamespace(repo=repo))
    bridge = AlanScriptTransport(repo / "target", fallback=fake(list(review_script)))
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
    r = h["bob"].post(f"/api/v1/approvals/{pending[0]['id']}/decision", json={"decision": decision})
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
    assert [r["agent"] for r in runs] == ["reviewer", *EXPECTED]
    assert all(r["status"] == "succeeded" and r["provider_mode"] == "fake" for r in runs)
    assert all(r["usage"]["llm_calls"] > 0 for r in runs), "every run's model usage is recorded"
    assert a["usage"]["llm_calls"] == sum(r["usage"]["llm_calls"] for r in runs), (
        "one gateway, one ledger"
    )
    kinds = {f["kind"] for f in detail["findings"]}
    assert kinds == {"functional", "security"}, detail["findings"]
    security = next(f for f in detail["findings"] if f["kind"] == "security")
    patches = h["alice"].get(f"/api/v1/findings/{security['id']}/patches").json()["items"]
    assert patches and patches[-1]["verification"]["verdict"] == "accepted"
    by_id = {r["id"]: r["agent"] for r in runs}
    assert by_id[patches[-1]["verification"]["produced_by_run_id"]] == "verify"
    log = h["alice"].get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    assert any(
        "functional review" in e["message"] for e in log if e["type"] == "assessment.progress"
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
