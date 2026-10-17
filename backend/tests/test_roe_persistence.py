"""Rules of engagement (NIST SP 800-115 App. B alignment) issued by the security-agents
orchestrator at SCOPE_CHECK are persisted by the host and served by
GET /assessments/{id}/rules-of-engagement (Alan's 20261017T100625Z ask; ACKed 102000Z)."""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("security_agents")
pytest.importorskip("code_review")

from test_unified_assessment import _decide, _start, unified  # noqa: E402,F401

from backend import worker  # noqa: E402
from backend.host import AssessmentHost, HostError  # noqa: E402


def test_issued_roe_is_persisted_served_and_checked(unified, client_factory) -> None:  # noqa: F811
    h = unified
    alice = h["alice"]
    asm_id = _start(h)
    worker.drain(kinds=["run_assessment"])
    _decide(h, "approved")
    worker.drain(kinds=["run_assessment"])

    r = alice.get(f"/api/v1/assessments/{asm_id}/rules-of-engagement")
    assert r.status_code == 200, r.text
    roe = r.json()
    assert roe["scope_id"] == h["scope"] and roe["project_id"] == h["project"]
    assert roe["digest"] and roe["permitted_agents"] and roe["prohibited_actions"]
    assert "800-115" in roe["alignment"]
    audit = alice.get("/api/v1/audit", params={"project_id": h["project"]}).json()
    assert any(e["action"] == "roe.recorded" for e in audit["items"])
    assert audit["chain_verified"] is True

    # Access control: a non-member gets 404, never the document.
    assert (
        client_factory("eve").get(f"/api/v1/assessments/{asm_id}/rules-of-engagement").status_code
        == 404
    )

    # The host checks what it is handed: tampered body, or another scope/project, is refused.
    host = AssessmentHost(asm_id)
    tampered = copy.deepcopy(roe)
    tampered["prohibited_actions"] = []
    with pytest.raises(HostError, match="digest"):
        host.record_roe(tampered)
    other = copy.deepcopy(roe)
    other["scope_id"] = "scp_00000000other"
    with pytest.raises(HostError, match="another project or scope"):
        host.record_roe(other)


def test_no_roe_issued_is_404(unified) -> None:  # noqa: F811
    asm_id = _start(unified)  # created, never run: nothing issued yet
    r = unified["alice"].get(f"/api/v1/assessments/{asm_id}/rules-of-engagement")
    assert r.status_code == 404
