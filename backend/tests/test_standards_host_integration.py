"""Standards travel from scripted Trace through real host persistence."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from backend.db import finding_records, findings, transaction
from shared.findings import Finding


@pytest.mark.parametrize("complete", [False, True])
def test_standards_survive_real_host_flow(
    client_factory, settings_override, monkeypatch, tmp_path, complete
):
    from sa_bridge import AlanScriptTransport
    from test_security_agents_host_mode import test_host_mode_full_flow_against_real_backend

    original = AlanScriptTransport.create

    def create(self, request):
        response = original(self, request)
        if complete and request["system"].startswith("You are Trace"):
            for block in response.content:
                if block.get("type") == "tool_use" and block.get("name") == "submit_result":
                    payload = block["input"]
                    import re

                    match = re.search(
                        r'"sandbox_run_id":\s*"([^"]+)"',
                        json.dumps(request["messages"]).replace('\\"', '"'),
                    )
                    assert match, "Trace must receive the actual executed run identifier"
                    metrics = dict(
                        AV="N",
                        AC="L",
                        AT="N",
                        PR="L",
                        UI="N",
                        VC="H",
                        VI="N",
                        VA="N",
                        SC="N",
                        SI="N",
                        SA="N",
                    )
                    payload["cvss_metrics"] = metrics
                    payload["cvss_metric_artifacts"] = {
                        metric: match.group(1) for metric in metrics
                    }
        return response

    monkeypatch.setattr(AlanScriptTransport, "create", create)
    test_host_mode_full_flow_against_real_backend(
        client_factory, settings_override, monkeypatch, tmp_path
    )
    with transaction() as conn:
        docs = conn.execute(select(findings.c.doc)).scalars().all()
        records = (
            conn.execute(
                select(finding_records.c.doc).where(finding_records.c.record_type == "hardening")
            )
            .scalars()
            .all()
        )
    with transaction() as conn:
        types = conn.execute(select(finding_records.c.record_type)).scalars().all()
    assert records and any(record.get("d3fend") for record in records), types
    assert all(
        ref["control_status"] == "proposed"
        for record in records
        for ref in record.get("d3fend", [])
    )
    security_findings = [Finding.model_validate(doc) for doc in docs if doc["kind"] == "security"]
    assert security_findings
    for finding in security_findings:
        assert finding.standards and finding.standards.cwe
        assert finding.standards.cwe.id == "CWE-639"
        assert finding.standards.attack
        assert all(ref.review_status == "proposed" for ref in finding.standards.attack)
        if complete:
            assert finding.standards.cvss and finding.standards.cvss.complete
            assert finding.standards.cvss.score is not None
            assert finding.severity and finding.severity.cvss == finding.standards.cvss
        else:
            assert finding.standards.cvss is None or not finding.standards.cvss.complete
