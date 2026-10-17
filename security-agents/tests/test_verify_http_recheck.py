from __future__ import annotations

import dataclasses
import subprocess

import pytest

from security_agents.agents import verify as verify_agent
from security_agents.contracts import ErrorCode, PlatformError, VerificationCheckName
from security_agents.host_adapter import HostSink
from security_agents.sandbox.driver import DockerSandboxDriver, SandboxProfile
from security_agents.workflow import AssessmentState

from .test_agent_logic import check_run, evidence
from .test_e2e_replay import build
from .test_host_adapter import FakeHost
from .test_sandbox import ALLOWED, IMAGE, spec_for

ORIGINAL = "a" * 64
PATCHED = "b" * 64
HTTP_RECHECK = check_run(
    True,
    transport="http",
    target_contacted=True,
    target_requests=[
        {"method": "GET", "path": "/payments/pay_a1", "status": 200},
        {"method": "GET", "path": "/payments/pay_a1", "status": 403},
    ],
    target_log_sha256="c" * 64,
    target_tree_sha256=PATCHED,
)


def http_evidence(run=HTTP_RECHECK, **kw):
    return evidence(
        recheck_runs=[run],
        required_transport="http",
        original_tree_sha256=ORIGINAL,
        patched_tree_sha256=PATCHED,
        **kw,
    )


def original_check(ev):
    _, checks, _ = verify_agent.compute_verdict(ev)
    return next(c for c in checks if c.name is VerificationCheckName.ORIGINAL_CHECK_NOW_FAILS)


def test_http_recheck_against_the_patched_workspace_passes():
    check = original_check(http_evidence())
    assert check.passed, check.detail
    verdict, _, _ = verify_agent.compute_verdict(http_evidence())
    assert verdict == "accepted"


@pytest.mark.parametrize(
    ("run", "reason"),
    [
        (check_run(True), "ran inprocess"),
        ({**HTTP_RECHECK, "transport": "inprocess"}, "ran inprocess"),
        ({**HTTP_RECHECK, "target_contacted": False}, "no request"),
        ({**HTTP_RECHECK, "target_tree_sha256": ORIGINAL}, "did not serve the patched workspace"),
        ({**HTTP_RECHECK, "target_tree_sha256": None}, "did not serve the patched workspace"),
    ],
)
def test_http_recheck_never_downgrades_or_accepts_the_wrong_target(run, reason):
    check = original_check(http_evidence(run))
    assert not check.passed and reason in check.detail
    verdict, _, _ = verify_agent.compute_verdict(http_evidence(run))
    assert verdict == "rejected"


def test_unpatched_tree_is_refused_even_when_patched_digest_matches_it():
    ev = http_evidence(
        {**HTTP_RECHECK, "target_tree_sha256": ORIGINAL},
    )
    ev = dataclasses.replace(ev, patched_tree_sha256=ORIGINAL)
    check = original_check(ev)
    assert not check.passed and "unpatched snapshot" in check.detail


def test_inprocess_verify_is_unchanged():
    assert original_check(evidence()).passed


def test_http_recheck_evidence_records_requests_target_and_verdict():
    record = verify_agent.http_recheck_evidence(http_evidence(), "accepted")
    assert record["transport"] == "http" and record["verdict"] == "accepted"
    assert record["served_tree_sha256"] == PATCHED and record["original_tree_sha256"] == ORIGINAL
    assert [r["status"] for r in record["target_requests"]] == [200, 403]
    assert verify_agent.http_recheck_evidence(evidence(), "accepted") is None


def test_verify_http_without_docker_fails_closed_before_any_agent(intel, driver, library, tmp_path):
    orch, _ = build(intel, driver, library, tmp_path)
    orch.config.verify_check_transport = "http"
    res = orch.run()
    assert res.state is AssessmentState.FAILED
    assert res.error_code is ErrorCode.SANDBOX_START_FAILED
    assert "verify" in (res.error_detail or "") and res.runs == []


def test_host_cites_the_http_recheck_artifact_on_the_original_check_only():
    from types import SimpleNamespace

    host = FakeHost(gateway=None)
    sink = HostSink(host=host, commit_sha="a" * 40)
    finding = SimpleNamespace(
        verify_http_evidence=verify_agent.http_recheck_evidence(http_evidence(), "accepted")
    )
    ref = SimpleNamespace(kind="sandbox_run")
    checks = [
        SimpleNamespace(name=name, evidence=[ref], model_copy=None)
        for name in ("original_check_now_fails_to_reproduce", "diff_scope_ok")
    ]

    class Check:
        def __init__(self, name):
            self.name, self.evidence = name, [ref]

        def model_copy(self, update):
            copy = Check(self.name)
            copy.evidence = update["evidence"]
            return copy

    class Canonical:
        def __init__(self, checks):
            self.checks = checks

        def model_copy(self, update):
            return Canonical(update["checks"])

    out = sink._with_http_recheck_evidence(finding, Canonical([Check(c.name) for c in checks]))
    original, scope = out.checks
    assert len(original.evidence) == 2 and original.evidence[-1].artifact_id.startswith("art_")
    assert len(scope.evidence) == 1
    assert '"served_tree_sha256"' in host.stored[-1]


def _served_spec(snapshot):
    spec = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=ALLOWED,
        mode="pytest",
        args=["-q"],
    )
    return dataclasses.replace(
        spec, target_workspace=snapshot.root, target_app="payments_lite.app:create_app"
    )


class Recorder:
    def __init__(self, fail_on=None, exc=None):
        self.calls: list[list[str]] = []
        self.fail_on, self.exc = fail_on, exc

    def __call__(self, argv, stdin, timeout):
        self.calls.append(argv)
        if self.fail_on and argv[1] == self.fail_on and argv[2] in ("-i", "--rm"):
            if self.exc is not None:
                raise self.exc
            return subprocess.CompletedProcess(argv, 1, b"", b"failed")
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def cleaned(self) -> bool:
        verbs = [" ".join(c[1:3]) for c in self.calls]
        return "rm -f" in verbs and "network rm" in verbs


def test_target_and_network_are_removed_when_streaming_the_workspace_fails(snapshot):
    runner = Recorder(fail_on="exec")
    with pytest.raises(PlatformError):
        DockerSandboxDriver(image=IMAGE, runner=runner).run(_served_spec(snapshot))
    assert runner.cleaned()


def test_target_and_network_are_removed_after_a_check_timeout(snapshot):
    runner = Recorder(fail_on="run", exc=subprocess.TimeoutExpired(["docker"], 1))
    result = DockerSandboxDriver(image=IMAGE, runner=runner).run(_served_spec(snapshot))
    assert result.timed_out is True
    assert runner.cleaned()


def test_target_and_network_are_removed_when_the_run_is_interrupted(snapshot):
    runner = Recorder(fail_on="run", exc=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        DockerSandboxDriver(image=IMAGE, runner=runner).run(_served_spec(snapshot))
    assert runner.cleaned()
