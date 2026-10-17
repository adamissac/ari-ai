"""Cross-owner end to end: Alan's real seven-agent runtime (security_agents, from
feat/alan/seven-agent-runtime) hosted by backend.adapters.security_agents inside the
worker, against the owned payments-lite target pinned to an exact git commit.

Real here: tool registry + scope_guard, the sandboxed ownership check, the patch
diff in a worktree, the independent Verify re-check, PostgreSQL persistence, the
human approval via the API, SSE. Scripted here: the LLM turns (Alan's FakeLLM
scripts) — every AgentRun is labeled provider_mode="fake". Skips when
security_agents or its test scripts are not installed."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

security_agents = pytest.importorskip("security_agents")
ALAN_ROOT = Path(security_agents.__file__).resolve().parents[2]
PAYMENTS = ALAN_ROOT / "examples" / "payments-lite"
if (
    not (ALAN_ROOT / "security-agents" / "tests" / "fake_agents.py").exists()
    or not (PAYMENTS / "build_recipe.json").exists()
):
    pytest.skip(
        "security_agents test scripts / its payments-lite layout not available",
        allow_module_level=True,
    )
sys.path.insert(0, str(ALAN_ROOT / "security-agents"))

from helpers import add_member  # noqa: E402

from backend import worker  # noqa: E402
from backend.adapters import security_agents as adapter  # noqa: E402
from security_agents.checks.library import BOUNDS, OWNERSHIP  # noqa: E402
from security_agents.llm import FakeLLM, ProviderGateway  # noqa: E402
from tests import fake_agents  # noqa: E402  (Alan's deterministic role scripts)

EXPECTED = ["scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"]


@pytest.fixture
def hosted(tmp_path, settings_override, client_factory):
    sha = subprocess.check_output(
        ["git", "-C", str(ALAN_ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    alice, bob = client_factory("alice"), client_factory("bob")
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": "acme/payments-lite"}
    ).json()["id"]
    bindings = tmp_path / "bindings.json"
    bindings.write_text(
        json.dumps(
            [{"repo_id": rid, "local_path": str(ALAN_ROOT), "subdir": "examples/payments-lite"}]
        )
    )
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
    sid = alice.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "payments-lite sandbox",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [
                {
                    "kind": "sandbox_build",
                    "repo_id": rid,
                    "build_recipe_ref": "build_recipe.json",
                    "exposed_ports": [8000],
                }
            ],
            "allowed_check_categories": [OWNERSHIP.category, BOUNDS.category],
        },
    ).json()["id"]
    assert bob.post(f"/api/v1/scopes/{sid}/approve").status_code == 200
    yield {"alice": alice, "bob": bob, "project": pid, "repo": rid, "scope": sid, "sha": sha}
    adapter.GATEWAY_OVERRIDE = None


def _run_worker_until_approval(h, decision: str) -> str:
    asm_id = (
        h["alice"]
        .post(
            f"/api/v1/projects/{h['project']}/assessments",
            json={"scope_id": h["scope"], "repo_id": h["repo"], "commit_sha": h["sha"]},
        )
        .json()["assessment"]["id"]
    )
    errors: list[BaseException] = []

    def work() -> None:
        try:
            worker.drain(kinds=["run_assessment"])
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    pending = []
    for _ in range(600):
        pending = (
            h["alice"]
            .get(f"/api/v1/projects/{h['project']}/approvals", params={"status": "pending"})
            .json()["items"]
        )
        state = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()["assessment"]["state"]
        if pending or state in ("FAILED", "COMPLETED", "CANCELLED", "BUDGET_EXHAUSTED"):
            break
        time.sleep(0.1)
    assert pending, h["alice"].get(f"/api/v1/assessments/{asm_id}").json()["assessment"]
    detail = h["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "AWAITING_APPROVAL"
    assert [r["agent"] for r in detail["agent_runs"]] == ["scout", "probe", "trace", "diagnose"]
    r = h["bob"].post(
        f"/api/v1/approvals/{pending[0]['id']}/decision",
        json={"decision": decision, "reason": "e2e"},
    )
    assert r.status_code == 200, r.text
    t.join(timeout=300)
    assert not t.is_alive() and not errors, errors
    worker.drain(kinds=["run_assessment"])  # the approval's resume job must be a no-op
    return asm_id


def test_seven_agents_hosted_end_to_end_with_human_approval(hosted) -> None:
    alice = hosted["alice"]
    asm_id = _run_worker_until_approval(hosted, "approved")
    detail = alice.get(f"/api/v1/assessments/{asm_id}").json()
    a = detail["assessment"]
    assert a["state"] == "COMPLETED", a
    runs = detail["agent_runs"]
    assert [r["agent"] for r in runs] == EXPECTED
    assert all(r["status"] == "succeeded" and r["provider_mode"] == "fake" for r in runs)
    assert all(r["tool_calls"] and r["transcript_artifact_id"] for r in runs)
    assert len({r["prompt_version"] for r in runs}) == 7
    assert a["usage"]["llm_calls"] >= 14 and a["usage"]["tool_calls"] >= 7

    finding = detail["findings"][0]
    assert finding["kind"] == "security" and finding["status"] == "hardened"
    assert "verified" in [h["to_status"] for h in finding["history"]]
    assert finding["severity"]["level"] == "high"
    assert any(
        e["kind"] == "source_span" and e["path"] == "payments_lite/app.py"
        for e in finding["evidence"]
    )
    assert any(e["kind"] == "sandbox_run" for e in finding["evidence"])
    records = {r["type"] for r in alice.get(f"/api/v1/findings/{finding['id']}").json()["records"]}
    assert {
        "hypothesis",
        "validation_result",
        "attack_path",
        "root_cause",
        "remediation_plan",
        "hardening",
    } <= records

    patches = alice.get(f"/api/v1/findings/{finding['id']}/patches").json()["items"]
    assert patches and patches[-1]["verification"]["verdict"] == "accepted"
    verify_run = patches[-1]["verification"]["produced_by_run_id"]
    patch_run = patches[-1]["patch"]["produced_by_run_id"]
    by_id = {r["id"]: r["agent"] for r in runs}
    assert by_id[verify_run] == "verify" and by_id[patch_run] == "patch"
    diff = alice.get(f"/api/v1/artifacts/{patches[-1]['patch']['diff_artifact_id']}")
    assert diff.status_code == 200 and b"+++" in diff.content

    log = alice.get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    states = [e["state"] for e in log if e["type"] == "assessment.state_changed"]
    assert states == [
        "CREATED",
        "SCOPE_CHECK",
        "INDEXING",
        "FUNCTIONAL_REVIEW",
        "RECON",
        "VALIDATION",
        "ANALYSIS",
        "DIAGNOSIS",
        "AWAITING_APPROVAL",
        "REMEDIATION",
        "HARDENING",
        "REPORTING",
        "COMPLETED",
    ]
    assert sum(e["type"] == "agent_run.finished" for e in log) == 7


def test_declined_remediation_never_patches(hosted) -> None:
    asm_id = _run_worker_until_approval(hosted, "declined")
    detail = hosted["alice"].get(f"/api/v1/assessments/{asm_id}").json()
    assert detail["assessment"]["state"] == "COMPLETED"
    assert [r["agent"] for r in detail["agent_runs"]] == ["scout", "probe", "trace", "diagnose"]
    assert detail["findings"][0]["status"] == "diagnosed"


def test_missing_binding_fails_honestly(hosted, settings_override, tmp_path) -> None:
    empty = tmp_path / "none.json"
    empty.write_text("[]")
    settings_override(repository_bindings_file=str(empty))
    asm_id = (
        hosted["alice"]
        .post(
            f"/api/v1/projects/{hosted['project']}/assessments",
            json={
                "scope_id": hosted["scope"],
                "repo_id": hosted["repo"],
                "commit_sha": hosted["sha"],
            },
        )
        .json()["assessment"]["id"]
    )
    worker.drain(kinds=["run_assessment"])
    a = hosted["alice"].get(f"/api/v1/assessments/{asm_id}").json()["assessment"]
    assert a["state"] == "FAILED" and a["error"]["code"] == "SUBSYSTEM_UNAVAILABLE"
