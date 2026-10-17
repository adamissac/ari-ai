"""Executable acceptance test for Alan's host mode (security_agents.api:build_orchestrator
-> HostOrchestrator.run(host)) against the REAL backend: AssessmentHost on PostgreSQL,
the real LLMGateway (scripted transport labeled fake, see sa_bridge.py), the worker,
API approval and resume.

Expected to fail until the issues below are fixed on feat/alan/seven-agent-runtime
(reported in coordination/messages/*-srihith-to-alan-host-mode-findings.md, issue #17):
  1. calls host.scope() / host.assessment() — they are properties;
  2. calls llm.provider_mode() — it is a property (str);
  3. on_patch cites a fabricated run id (run_ids["patch"] is never populated);
  4. finish_agent_run is called without usage/tool_calls;
  5. resume state lives only in memory (lost across workers/restarts).
xfail is non-strict: this flips to XPASS when host mode works end to end.
"""

from __future__ import annotations

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


@pytest.mark.xfail(
    reason="security_agents host mode not yet conformant with backend.host (see module docstring)",
    strict=False,
)
def test_host_mode_full_flow_against_real_backend(
    client_factory, settings_override, monkeypatch, tmp_path
):
    from sa_bridge import AlanScriptTransport

    monkeypatch.setenv("SECURITY_AGENTS_TARGET_DIR", str(TARGET))
    monkeypatch.setenv("SECURITY_AGENTS_WORKDIR", str(tmp_path / "w"))
    settings_override(orchestrator_factory="security_agents.api:build_orchestrator")
    bridge = AlanScriptTransport(TARGET / "target")
    llm.TRANSPORT_OVERRIDE = lambda: bridge
    alice, bob = client_factory("alice"), client_factory("bob")
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": "acme/payments-lite"}
    ).json()["id"]
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
        json={"scope_id": sid, "repo_id": rid, "commit_sha": "b" * 40},
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
