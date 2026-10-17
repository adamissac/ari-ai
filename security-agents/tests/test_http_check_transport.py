from __future__ import annotations

import ast
import dataclasses
import subprocess

import pytest

from security_agents.checks.library import BOUNDS, OWNERSHIP, default_library
from security_agents.contracts import AgentName, ErrorCode, PlatformError
from security_agents.sandbox.driver import DockerSandboxDriver, LocalProcessDriver, SandboxProfile
from security_agents.tools import CheckRunner, recipe_from_snapshot
from security_agents.tools.services import target_contact

from .conftest import NOW, TARGET_ID, make_ctx, make_scope
from .test_sandbox import ALLOWED, IMAGE, spec_for

OWNER_PARAMS = {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"}
UVICORN_LOG = (
    'INFO:     172.18.0.3:40112 - "GET / HTTP/1.1" 404 Not Found\n'
    'INFO:     172.18.0.3:40114 - "GET /payments/pay_a1 HTTP/1.1" 200 OK\n'
    'INFO:     172.18.0.3:40116 - "GET /payments/pay_a1 HTTP/1.1" 200 OK\n'
)


def _imports(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_http_render_reaches_the_target_over_http_and_keeps_the_assertions(intel):
    recipe = recipe_from_snapshot(intel)(None, TARGET_ID)
    library = default_library()
    inprocess = library.render(OWNERSHIP.ref, recipe, OWNER_PARAMS)
    http = library.render(OWNERSHIP.ref, recipe, OWNER_PARAMS, transport="http")
    assert "SANDBOX_TARGET_URL" in http and "TestClient" not in http
    assert _imports(http) == {"json", "os", "time", "decimal", "httpx"}
    assert "payments_lite" not in _imports(http)
    body = inprocess.split("def test_", 1)[1]
    assert http.split("def test_", 1)[1] == body


def test_http_transport_refuses_state_changing_templates(intel):
    recipe = recipe_from_snapshot(intel)(None, TARGET_ID)
    params = {"route_id": "create_refund", "read_route_id": "payment_detail", "owner_identity": "alice"}
    with pytest.raises(PlatformError) as error:
        default_library().render(BOUNDS.ref, recipe, params, transport="http")
    assert error.value.code is ErrorCode.SANDBOX_POLICY_VIOLATION


def test_unknown_transport_is_rejected(intel):
    recipe = recipe_from_snapshot(intel)(None, TARGET_ID)
    with pytest.raises(PlatformError) as error:
        default_library().render(OWNERSHIP.ref, recipe, OWNER_PARAMS, transport="socket")
    assert error.value.code is ErrorCode.SCHEMA_INVALID


def test_http_transport_without_docker_fails_closed_before_running(intel):
    class MustNotRun(LocalProcessDriver):
        def run(self, spec):
            raise AssertionError("no sandbox may start for an unsupported transport")

    runner = CheckRunner(
        driver=MustNotRun(allow=True),
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
        transport="http",
    )
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope(), now=lambda: NOW)
    ctx.artifacts["last_scope_decision"] = ALLOWED
    result = runner.run(ctx, OWNERSHIP.ref, TARGET_ID, OWNER_PARAMS)
    assert result["error"] == "HTTP_TRANSPORT_REQUIRES_DOCKER"
    assert result["matches_expectation"] is None


def test_docker_driver_captures_the_target_log_before_teardown(snapshot):
    calls: list[list[str]] = []

    def fake(argv, stdin, timeout):
        calls.append(argv)
        out = UVICORN_LOG.encode() if argv[1:2] == ["logs"] else b""
        return subprocess.CompletedProcess(argv, 0, out, b"")

    driver = DockerSandboxDriver(image=IMAGE, runner=fake)
    spec = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=ALLOWED,
        mode="pytest",
        args=["-q"],
    )
    result = driver.run(spec)
    verbs = [c[1] for c in calls]
    assert verbs.index("logs") < verbs.index("rm")
    assert "/payments/pay_a1" in result.target_log
    contact = target_contact(result.target_log, "http")
    assert contact["target_contacted"] is True
    assert [r["path"] for r in contact["target_requests"]].count("/payments/pay_a1") == 2
    assert len(contact["target_log_sha256"]) == 64


def test_no_target_log_means_no_contact_claim():
    assert target_contact("", "inprocess") == {
        "transport": "inprocess",
        "target_contacted": False,
        "target_requests": [],
        "target_log_sha256": None,
    }


def test_docker_driver_serves_the_snapshot_through_exec_and_never_uses_a_target_image(snapshot):
    calls: list[tuple[list[str], bytes | None]] = []

    def fake(argv, stdin, timeout):
        calls.append((argv, stdin))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    driver = DockerSandboxDriver(
        image=IMAGE, target_image="ghcr.io/other/target@sha256:" + "b" * 64, runner=fake
    )
    spec = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=ALLOWED,
        mode="pytest",
        args=["-q"],
    )
    spec = dataclasses.replace(
        spec, target_workspace=snapshot.root, target_app="payments_lite.app:create_app"
    )
    driver.run(spec)
    target_run = next(argv for argv, _ in calls if argv[1:3] == ["run", "-d"])
    flat = " ".join(target_run)
    assert IMAGE in target_run and "ghcr.io/other/target" not in flat
    assert "--read-only" in flat and "--user 65534:65534" in flat and "--cap-drop ALL" in flat
    assert "TARGET_APP=payments_lite.app:create_app" in target_run
    exec_call = next((argv, data) for argv, data in calls if argv[1:3] == ["exec", "-i"])
    assert exec_call[1], "the snapshot tar is streamed into the running target"
    verbs = [argv[1] for argv, _ in calls]
    assert verbs.index("exec") < verbs.index("logs") < verbs.index("rm")


@pytest.mark.parametrize("app", ["payments_lite.app:create_app; rm -rf /", "$(id):x", "", "a.b"])
def test_served_target_app_must_be_a_plain_factory_reference(snapshot, app):
    from security_agents.sandbox.driver import validate_spec

    spec = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=ALLOWED,
    )
    spec = dataclasses.replace(spec, target_workspace=snapshot.root, target_app=app)
    with pytest.raises(PlatformError) as error:
        validate_spec(spec)
    assert error.value.code is ErrorCode.SANDBOX_POLICY_VIOLATION


def test_http_runner_serves_the_assessment_workspace(intel):
    seen = []

    class Recorder:
        name = "docker"

        def run(self, spec):
            seen.append(spec)
            raise PlatformError(ErrorCode.SANDBOX_START_FAILED, "recorded")

    runner = CheckRunner(
        driver=Recorder(),
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
        transport="http",
    )
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope(), now=lambda: NOW)
    ctx.artifacts["last_scope_decision"] = ALLOWED
    with pytest.raises(PlatformError):
        runner.run(ctx, OWNERSHIP.ref, TARGET_ID, OWNER_PARAMS)
    assert seen[0].target_workspace == intel.snapshot.root
    assert seen[0].target_app == "payments_lite.app:create_app"
