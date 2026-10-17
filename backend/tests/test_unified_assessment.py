"""Pillar 1 + Pillar 2 in ONE assessment, through the real backend.

A throwaway git repo holds the owned payments-lite target (Alan's layout: build_recipe.json
+ target/). The worker hosts Alan's seven-agent runtime (backend.adapters.security_agents);
at FUNCTIONAL_REVIEW the adapter runs Sai's reviewer (code_review) on the same commit.

Scripted model turns on both sides (labeled provider_mode="fake"):
  * reviewer: Sai's pl_review_script through the real backend LLMGateway transport;
  * security agents: Alan's fake_agents scripts through his FakeLLM gateway.
Everything else is real: git-pinned checkout, reviewer test execution, sandboxed checks,
patch + independent Verify, PostgreSQL persistence, API approval, SSE.
Skips unless security_agents and code_review (with their test scripts) are installed."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

security_agents = pytest.importorskip("security_agents")
code_review = pytest.importorskip("code_review")
ALAN_ROOT = Path(security_agents.__file__).resolve().parents[2]
SAI_TESTS = Path(code_review.__file__).resolve().parents[1] / "tests"
PAYMENTS = ALAN_ROOT / "examples" / "payments-lite"
if (
    not (PAYMENTS / "build_recipe.json").exists()
    or not (SAI_TESTS / "test_reviewer_agent.py").exists()
):
    pytest.skip(
        "teammates' test scripts / payments-lite recipe not available", allow_module_level=True
    )

from helpers import add_member  # noqa: E402

from backend import llm, worker  # noqa: E402
from backend.adapters import security_agents as adapter  # noqa: E402


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
def unified(tmp_path, settings_override, client_factory):
    sys.path[:0] = [str(SAI_TESTS), str(ALAN_ROOT / "security-agents")]
    from cr_fakes import fake
    from test_reviewer_agent import pl_review_script

    from security_agents.checks.library import BOUNDS, OWNERSHIP
    from security_agents.llm import FakeLLM, ProviderGateway
    from tests import fake_agents

    repo = tmp_path / "owned-repo"
    shutil.copytree(
        PAYMENTS,
        repo,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.egg-info", ".venv"),
    )
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
    settings_override(
        repository_bindings_file=str(bindings),
        security_sandbox="local-dev",
        security_workdir=str(tmp_path / "work"),
        approval_poll_s="0.1",
        approval_timeout_s="60",
        orchestrator_factory="backend.adapters.security_agents:build_orchestrator",
    )
    adapter.GATEWAY_OVERRIDE = lambda root: ProviderGateway(
        FakeLLM(fake_agents.all_scripts(root)), default_model="claude-opus-5-5"
    )
    review_script = pl_review_script(SimpleNamespace(repo=repo))
    llm.TRANSPORT_OVERRIDE = lambda: fake(list(review_script))
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
    adapter.GATEWAY_OVERRIDE = None
    for p in (str(SAI_TESTS), str(ALAN_ROOT / "security-agents")):
        if p in sys.path:
            sys.path.remove(p)


def test_review_then_seven_agents_in_one_assessment(unified) -> None:
    h = unified
    asm_id = (
        h["alice"]
        .post(
            f"/api/v1/projects/{h['project']}/assessments",
            json={"scope_id": h["scope"], "repo_id": h["repo"], "commit_sha": h["sha"]},
        )
        .json()["assessment"]["id"]
    )
    errors: list[BaseException] = []
    t = threading.Thread(target=lambda: _drain(errors), daemon=True)
    t.start()
    pending = []
    for _ in range(900):
        pending = (
            h["alice"]
            .get(f"/api/v1/projects/{h['project']}/approvals", params={"status": "pending"})
            .json()["items"]
        )
        if pending or not t.is_alive():
            break
        time.sleep(0.1)
    assert pending, h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert (
        h["bob"]
        .post(f"/api/v1/approvals/{pending[0]['id']}/decision", json={"decision": "approved"})
        .status_code
        == 200
    )
    t.join(timeout=300)
    assert not errors, errors
    worker.drain(kinds=["run_assessment"])

    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED", detail["assessment"]
    agents = [r["agent"] for r in detail["agent_runs"]]
    assert agents[0] == "reviewer", agents
    assert agents[1:] == ["scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"]
    kinds = {f["kind"] for f in detail["findings"]}
    assert kinds == {"functional", "security"}, detail["findings"]
    functional = next(f for f in detail["findings"] if f["kind"] == "functional")
    assert "refund" in functional["title"].lower()
    log = h["alice"].get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    assert any(
        "functional review" in e["message"] for e in log if e["type"] == "assessment.progress"
    )


def _drain(errors: list[BaseException]) -> None:
    try:
        worker.drain(kinds=["run_assessment"])
    except BaseException as exc:  # pragma: no cover
        errors.append(exc)
