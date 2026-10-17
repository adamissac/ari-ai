"""The reviewer running its tests through Alan's shared sandbox driver (SandboxPort adapter).

Uses ``LocalProcessDriver(allow=True)`` — dev-only, labeled not-a-security-boundary — because
Docker is not available on the development machine. Skipped when security_agents is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("security_agents.sandbox.driver")

from cr_fakes import InMemoryHost, fake, make_request  # noqa: E402
from cr_scenarios import discount_rounding  # noqa: E402
from test_reviewer_agent import _discount_script  # noqa: E402

from code_review.agent import ReviewerAgentRunner  # noqa: E402
from code_review.ports import RepoSource  # noqa: E402
from code_review.sandbox import classify  # noqa: E402
from code_review.shared_sandbox import SharedSandboxAdapter, build_sandbox  # noqa: E402
from code_review.workspace import Workspace  # noqa: E402
from security_agents.sandbox.driver import LocalProcessDriver  # noqa: E402
from shared.evidence import EvidenceKind  # noqa: E402
from shared.findings import FindingStatus  # noqa: E402


@pytest.fixture
def adapter() -> SharedSandboxAdapter:
    return SharedSandboxAdapter(LocalProcessDriver(allow=True))


def test_shared_driver_reports_behavior_tooling_and_network_guard(tmp_path: Path, adapter) -> None:
    sc = discount_rounding(tmp_path)
    ws = Workspace.export(RepoSource(sc.repo), sc.head_sha)
    try:
        ws.write("tests/generated/test_a.py", "def test_a():\n    assert 1 == 2\n")
        ws.write("tests/generated/test_b.py", "import nope_missing\n\ndef test_b():\n    pass\n")
        ws.write(
            "tests/generated/test_net.py",
            "import socket\nimport pytest\n\ndef test_net():\n"
            "    with pytest.raises(PermissionError):\n"
            "        socket.create_connection(('example.com', 80), timeout=1)\n",
        )
        run = lambda t: adapter.run_pytest(ws.project_dir, [t], timeout_s=60)  # noqa: E731
        a = run("tests/generated/test_a.py")
        assert classify(a) == "failed" and a.cases[0].exc_type == "AssertionError"
        assert a.driver.startswith("security_agents:local-process#sbx_")
        assert a.isolation_level == "process-dev:not-a-security-boundary"
        assert classify(run("tests/generated/test_b.py")) == "error"
        assert classify(run("tests/generated/test_net.py")) == "passed"  # network denied in sandbox
        assert classify(run("tests/test_invoice.py")) == "passed"
    finally:
        ws.close()


def test_reviewer_validates_defect_through_shared_driver(tmp_path: Path, adapter) -> None:
    sc = discount_rounding(tmp_path)
    host = InMemoryHost(fake(_discount_script()))
    outcome = ReviewerAgentRunner(host, RepoSource(sc.repo), sandbox=adapter).review(
        make_request(host, sc)
    )
    [finding] = outcome.result.findings
    assert finding.status is FindingStatus.validated
    ev = next(e for e in finding.evidence if e.kind is EvidenceKind.test_run)
    assert ev.provenance.startswith("code_review.sandbox:security_agents:local-process")
    data = host.artifact_json(ev.artifact_id)
    assert data["runs"][0]["isolation_level"] == "process-dev:not-a-security-boundary"


def test_build_sandbox_selection(monkeypatch) -> None:
    assert build_sandbox("local").name == "local-process"
    monkeypatch.delenv("SANDBOX_ALLOW_LOCAL_PROCESS", raising=False)
    with pytest.raises(Exception, match="local-process driver disabled"):
        build_sandbox("shared-local")  # dev driver refuses without explicit opt-in
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL_PROCESS", "1")
    assert build_sandbox("shared-local").name == "security_agents:local-process"
    with pytest.raises(ValueError):
        build_sandbox("bogus")


def test_outside_dev_the_reviewer_never_runs_customer_tests_on_the_host(monkeypatch) -> None:
    """#244 P0: one isolation policy with the security agents; no host-process fallback."""
    from code_review import shared_sandbox
    from code_review.agent import ReviewError

    monkeypatch.delenv("CODE_REVIEW_SANDBOX", raising=False)
    monkeypatch.setenv("SANDBOX_IMAGE", "python@sha256:" + "0" * 64)  # drivers need a pin
    monkeypatch.setattr(shared_sandbox, "_environment", lambda: ("production", "docker"))
    assert build_sandbox().name == "security_agents:docker"  # default follows the agents
    for kind in ("local", "shared-local"):
        with pytest.raises(ReviewError) as refused:
            build_sandbox(kind)
        assert refused.value.code.value == "SANDBOX_POLICY_VIOLATION"
    monkeypatch.setenv("CODE_REVIEW_SANDBOX", "local")  # an env override cannot reopen it
    with pytest.raises(ReviewError):
        build_sandbox()
    monkeypatch.delenv("CODE_REVIEW_SANDBOX")
    monkeypatch.setattr(shared_sandbox, "_environment", lambda: ("production", "vercel"))
    assert build_sandbox().name == "security_agents:vercel-sandbox"
    # A local-dev security setting never downgrades the reviewer outside dev/test.
    monkeypatch.setattr(shared_sandbox, "_environment", lambda: ("staging", "local-dev"))
    assert build_sandbox().name == "security_agents:docker"
    # Development/test keep the previous local default.
    monkeypatch.setattr(shared_sandbox, "_environment", lambda: ("test", "docker"))
    assert build_sandbox().name == "local-process"
