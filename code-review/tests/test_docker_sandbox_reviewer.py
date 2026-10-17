"""The reviewer through the REAL Docker sandbox (Alan's DockerSandboxDriver).

Opt-in: runs only with ``RUN_DOCKER_SANDBOX=1`` and ``SANDBOX_IMAGE`` (CI builds
``security-agents/sandbox`` and runs this in the ``docker-reviewer`` job). Proves the
reviewer's ``CODE_REVIEW_SANDBOX=docker`` path end to end: per-test exception types
come back through ``/out``, the network is denied by the kernel (``--network none``),
host env doesn't leak, and a full scripted review still validates the defect.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_SANDBOX") != "1" or not os.environ.get("SANDBOX_IMAGE"),
    reason="real Docker sandbox is opt-in: RUN_DOCKER_SANDBOX=1 and SANDBOX_IMAGE",
)

docker_driver = pytest.importorskip("security_agents.sandbox.driver")

from cr_fakes import InMemoryHost, fake, make_request  # noqa: E402
from cr_scenarios import discount_rounding  # noqa: E402
from test_reviewer_agent import _discount_script  # noqa: E402

from code_review.agent import ReviewerAgentRunner  # noqa: E402
from code_review.ports import RepoSource  # noqa: E402
from code_review.sandbox import classify  # noqa: E402
from code_review.shared_sandbox import SharedSandboxAdapter  # noqa: E402
from code_review.workspace import Workspace  # noqa: E402
from shared.evidence import EvidenceKind  # noqa: E402
from shared.findings import FindingStatus  # noqa: E402


@pytest.fixture
def adapter() -> SharedSandboxAdapter:
    return SharedSandboxAdapter(docker_driver.DockerSandboxDriver())


def test_docker_sandbox_classifies_and_isolates(tmp_path: Path, adapter, monkeypatch) -> None:
    monkeypatch.setenv("CR_HOST_CANARY", "must-not-leak")
    sc = discount_rounding(tmp_path)
    ws = Workspace.export(RepoSource(sc.repo), sc.head_sha)
    try:
        ws.write("tests/generated/test_a.py", "def test_a():\n    assert 1 == 2\n")
        ws.write("tests/generated/test_b.py", "import nope_missing\n\ndef test_b():\n    pass\n")
        ws.write(
            "tests/generated/test_iso.py",
            "import os\nimport _socket\nimport pytest\n\n"
            "def test_isolated():\n"
            "    assert 'CR_HOST_CANARY' not in os.environ\n"
            "    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)\n"
            "    with pytest.raises(OSError):\n"
            "        s.connect(('1.1.1.1', 80))\n",
        )
        run = lambda t: adapter.run_pytest(ws.project_dir, [t], timeout_s=120)  # noqa: E731
        a = run("tests/generated/test_a.py")
        assert a.driver.startswith("security_agents:docker"), a.driver
        assert classify(a) == "failed" and a.cases and a.cases[0].exc_type == "AssertionError", (
            a.stdout
        )
        assert classify(run("tests/generated/test_b.py")) == "error"
        iso = run("tests/generated/test_iso.py")
        assert classify(iso) == "passed", iso.stdout + iso.stderr
        assert classify(run("tests/test_invoice.py")) == "passed"
    finally:
        ws.close()


def test_reviewer_validates_defect_in_docker(tmp_path: Path, adapter) -> None:
    sc = discount_rounding(tmp_path)
    host = InMemoryHost(fake(_discount_script()))
    outcome = ReviewerAgentRunner(host, RepoSource(sc.repo), sandbox=adapter).review(
        make_request(host, sc)
    )
    [finding] = outcome.result.findings
    assert finding.status is FindingStatus.validated
    ev = next(e for e in finding.evidence if e.kind is EvidenceKind.test_run)
    data = host.artifact_json(ev.artifact_id)
    assert data["runs"][0]["driver"].startswith("security_agents:docker")
    assert "process-dev" not in data["runs"][0]["isolation_level"]
