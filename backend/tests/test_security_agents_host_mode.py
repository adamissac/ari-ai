"""Executable acceptance test for Alan's host mode (security_agents.api:build_orchestrator
-> HostOrchestrator.run(host)) against the REAL backend: AssessmentHost on PostgreSQL,
the real LLMGateway (scripted transport labeled fake, see sa_bridge.py), the worker,
API approval and resume.

Regression coverage: property access, persisted run IDs, per-run usage/tool records,
and fresh-worker approval resume through an integrity-checked checkpoint.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

security_agents = pytest.importorskip("security_agents")
pytest.importorskip("security_agents.host_adapter")
TARGET = Path(security_agents.__file__).resolve().parents[2] / "examples" / "payments-lite"
if not (TARGET / "build_recipe.json").exists():
    pytest.skip(
        "security_agents checkout without payments-lite build_recipe.json", allow_module_level=True
    )

from helpers import add_member  # noqa: E402

from backend import llm, worker  # noqa: E402


def test_host_mode_full_flow_against_real_backend(
    client_factory, settings_override, monkeypatch, tmp_path
):
    from sa_bridge import AlanScriptTransport

    monkeypatch.setenv("SECURITY_AGENTS_TARGET_DIR", str(TARGET))
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL_PROCESS", "1")
    monkeypatch.setenv("SECURITY_AGENTS_WORKDIR", str(tmp_path / "w"))
    settings_override(orchestrator_factory="security_agents.api:build_orchestrator")
    from security_agents.sandbox.workspace import copy_tree

    repo = tmp_path / "repo"
    copy_tree(TARGET, repo)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "owned fixture",
        ],
        check=True,
    )
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    bridge = AlanScriptTransport(repo / "target")
    llm.TRANSPORT_OVERRIDE = lambda: bridge
    alice, bob = client_factory("alice"), client_factory("bob")
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
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
    monkeypatch.setenv("REPOSITORY_BINDINGS_FILE", str(bindings))
    monkeypatch.setenv("INTELLIGENCE_REPOSITORIES_FILE", str(registrations))
    monkeypatch.setenv("INTELLIGENCE_DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.delenv("INTELLIGENCE_PAYLOAD_STORE_FACTORY", raising=False)
    sid = alice.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "s",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "targets": [
                {"kind": "sandbox_build", "repo_id": rid, "build_recipe_ref": "build_recipe.json"}
            ],
            "allowed_check_categories": ["access_control.ownership", "input_validation.bounds"],
        },
    ).json()["id"]
    assert bob.post(f"/api/v1/scopes/{sid}/approve").status_code == 200
    asm = alice.post(
        f"/api/v1/projects/{pid}/assessments",
        json={"scope_id": sid, "repo_id": rid, "commit_sha": sha},
    ).json()["assessment"]["id"]

    worker.drain(kinds=["run_assessment"])
    detail = alice.get(f"/api/v1/assessments/{asm}").json()
    assert detail["assessment"]["state"] == "AWAITING_APPROVAL", detail["assessment"]
    pending = alice.get(f"/api/v1/projects/{pid}/approvals", params={"status": "pending"}).json()[
        "items"
    ]
    assert (
        bob.post(
            f"/api/v1/approvals/{pending[0]['id']}/decision", json={"decision": "approved"}
        ).status_code
        == 200
    )
    # Simulate a new worker process: discard the process-local orchestrator cache.
    from backend import pipeline

    pipeline._ORCHESTRATORS.clear()
    worker.drain(kinds=["run_assessment"])

    detail = alice.get(f"/api/v1/assessments/{asm}").json()
    assert detail["assessment"]["state"] == "COMPLETED", detail["assessment"]
    runs = detail["agent_runs"]
    assert [r["agent"] for r in runs] == [
        "scout",
        "probe",
        "trace",
        "diagnose",
        "patch",
        "verify",
        "fortify",
    ]
    assert all(r["usage"]["llm_calls"] > 0 and r["tool_calls"] for r in runs), (
        "per-run usage/tool calls recorded"
    )
    patches = alice.get(f"/api/v1/findings/{detail['findings'][0]['id']}/patches").json()["items"]
    assert patches and patches[-1]["verification"]["verdict"] == "accepted"

    # Vihaan's M6 observations: lifecycle persisted with history; usage ledger complete.
    finding = alice.get(f"/api/v1/findings/{detail['findings'][0]['id']}").json()["finding"]
    assert finding["status"] == "hardened", finding["status"]
    path = [(h["from_status"], h["to_status"]) for h in finding["history"]]
    assert path == [
        ("hypothesis", "validated"),
        ("validated", "diagnosed"),
        ("diagnosed", "patch_proposed"),
        ("patch_proposed", "verified"),
        ("verified", "hardened"),
    ], path
    usage = detail["assessment"]["usage"]
    assert usage["tool_calls"] == sum(len(r["tool_calls"]) for r in runs) > 0
    assert usage["llm_calls"] == sum(r["usage"]["llm_calls"] for r in runs)
    assert usage["sandbox_seconds"] > 0, "Probe/Verify sandbox time reaches the ledger"
