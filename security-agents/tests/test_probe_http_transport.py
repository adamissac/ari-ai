from __future__ import annotations

import subprocess

from security_agents.agents import probe as probe_agent
from security_agents.contracts import ErrorCode, ValidationOutcome
from security_agents.host_adapter import HostSink
from security_agents.sandbox.driver import DockerSandboxDriver
from security_agents.workflow import AssessmentState

from .test_e2e_replay import build
from .test_host_adapter import FakeHost
from .test_sandbox import IMAGE

HTTP_RUN = {
    "template_id": "access_control.ownership",
    "template_version": "1",
    "template_ref": "access_control.ownership@1",
    "parameters": {"route_id": "payment_detail"},
    "sandbox_run_id": "sbx-http-1",
    "matches_expectation": False,
    "failed": 1,
    "passed": 1,
    "driver": "docker",
    "network": "target-only",
    "transport": "http",
    "target_contacted": True,
    "target_requests": [
        {"method": "GET", "path": "/payments/pay_a1", "status": 200},
        {"method": "GET", "path": "/payments/pay_a1", "status": 200},
    ],
    "target_log_sha256": "c" * 64,
}


def _fake_docker(argv, stdin, timeout):
    return subprocess.CompletedProcess(argv, 0, b"", b"")


def _run(intel, driver, library, tmp_path, transport):
    orch, _ = build(intel, driver, library, tmp_path)
    orch.config.probe_check_transport = transport
    return orch.run()


def test_http_transport_with_the_local_driver_fails_closed_before_any_agent(intel, driver, library, tmp_path):
    res = _run(intel, driver, library, tmp_path, "http")
    assert res.state is AssessmentState.FAILED
    assert res.error_code is ErrorCode.SANDBOX_START_FAILED
    assert "Docker" in (res.error_detail or "")
    assert res.runs == []


def test_unknown_probe_transport_fails_closed(intel, driver, library, tmp_path):
    res = _run(intel, driver, library, tmp_path, "socket")
    assert res.state is AssessmentState.FAILED and res.error_code is ErrorCode.SANDBOX_START_FAILED
    assert res.runs == []


def test_http_transport_needs_a_dedicated_target_image(intel, library, tmp_path):
    docker = DockerSandboxDriver(image=IMAGE, target_image=IMAGE, runner=_fake_docker)
    res = _run(intel, docker, library, tmp_path, "http")
    assert res.state is AssessmentState.FAILED
    assert "target image" in (res.error_detail or "")
    assert res.runs == []


def test_probe_validation_result_keeps_the_http_evidence():
    out = probe_agent.ProbeOutput.model_construct(
        outcome="confirmed", observations=[], interpretation="", missing_capability=None
    )
    data = probe_agent.ProbeInput.model_construct(hypothesis_id="hyp_httptransport01")
    result = probe_agent.to_validation_result(out, data, None, [HTTP_RUN])
    assert result.outcome is ValidationOutcome.CONFIRMED
    for key in ("transport", "target_contacted", "target_requests", "target_log_sha256"):
        assert result.observations[key] == HTTP_RUN[key]


def test_host_persists_http_evidence_as_an_artifact_on_the_validation_record():
    host = FakeHost(gateway=None)
    sink = HostSink(host=host, commit_sha="a" * 40)
    out = probe_agent.ProbeOutput.model_construct(
        outcome="confirmed", observations=[], interpretation="", missing_capability=None
    )
    data = probe_agent.ProbeInput.model_construct(hypothesis_id="hyp_httptransport01")
    validation = probe_agent.to_validation_result(out, data, None, [HTTP_RUN])
    from security_agents.contracts import export

    mapped = sink._with_http_evidence(validation, export.validation_result(validation))
    kinds = [e.kind.value for e in mapped.evidence]
    assert kinds == ["sandbox_run", "tool_output"]
    assert mapped.evidence[-1].artifact_id.startswith("art_")
    assert '"/payments/pay_a1"' in host.stored[-1] and '"transport": "http"' in host.stored[-1]


def test_inprocess_validation_records_are_left_unchanged():
    host = FakeHost(gateway=None)
    sink = HostSink(host=host, commit_sha="a" * 40)
    out = probe_agent.ProbeOutput.model_construct(
        outcome="confirmed", observations=[], interpretation="", missing_capability=None
    )
    data = probe_agent.ProbeInput.model_construct(hypothesis_id="hyp_httptransport01")
    run = {**HTTP_RUN, "transport": "inprocess", "target_contacted": False, "target_requests": []}
    validation = probe_agent.to_validation_result(out, data, None, [run])
    from security_agents.contracts import export

    mapped = export.validation_result(validation)
    assert sink._with_http_evidence(validation, mapped) is mapped
    assert host.stored == []
