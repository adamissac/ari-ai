"""Negative verification gates: infrastructure failure is never defect proof."""

from types import SimpleNamespace

import pytest

from security_agents.contracts import PlatformError
from security_agents.host_adapter import _functional_reproduced, _tests_passed, _write_generated_tests
from security_agents.tools.services import parse_pytest

TEST_PATH = "tests/generated/test_refund.py"


def failed_run(**changes):
    return {
        "exit_code": 1,
        "sandbox_run_id": "sbx_recorded",
        "failed": 1,
        "failing_tests": [TEST_PATH + "::test_bound"],
        **changes,
    }


def test_only_recorded_assertion_failure_reproduces_defect():
    assert _functional_reproduced(failed_run(), [TEST_PATH])


@pytest.mark.parametrize(
    "result,paths",
    [
        (None, [TEST_PATH]),
        (failed_run(), []),
        (failed_run(error="sandbox failed"), [TEST_PATH]),
        (failed_run(errors=1), [TEST_PATH]),
        (failed_run(timed_out=True), [TEST_PATH]),
        (failed_run(timed_out=True, exit_code=None), [TEST_PATH]),  # one quick fail, then hang
        (failed_run(exit_code=2), [TEST_PATH]),
        (failed_run(sandbox_run_id=""), [TEST_PATH]),
        (failed_run(failed=0), [TEST_PATH]),
        (failed_run(failing_tests=[]), [TEST_PATH]),
        (failed_run(failing_tests=[TEST_PATH + ".other::test_bound"]), [TEST_PATH]),
        (failed_run(), [TEST_PATH, "tests/generated/test_other.py"]),
    ],
)
def test_errors_missing_tests_and_other_files_do_not_reproduce(result, paths):
    assert not _functional_reproduced(result, paths)


def test_success_requires_an_executed_run_without_skips_or_errors():
    valid = {"exit_code": 0, "sandbox_run_id": "sbx_recorded", "passed": 2}
    assert _tests_passed(valid)
    for changed in (
        {"exit_code": 1},
        {"timed_out": True},
        {"sandbox_run_id": ""},
        {"skipped": 1},
        {"errors": 1},
    ):
        assert not _tests_passed({**valid, **changed})
    assert parse_pytest("2 passed, 1 skipped in 0.1s")["skipped"] == 1


def test_generated_tests_cannot_overwrite_existing_files_or_source(tmp_path):
    existing = tmp_path / "tests" / "test_existing.py"
    existing.parent.mkdir()
    existing.write_text("original")
    for path in ("tests/test_existing.py", "app.py"):
        with pytest.raises(PlatformError):
            _write_generated_tests(tmp_path, [SimpleNamespace(path=path, content="replacement")], "")
    assert existing.read_text() == "original"
    assert not (tmp_path / "app.py").exists()


def test_host_error_maps_kill_switch_and_survives_agent_local_codes():
    from security_agents.contracts import ErrorCode
    from security_agents.host_adapter import _host_error

    body = _host_error(ErrorCode.KILL_SWITCH, "assessments paused")
    code = body["code"] if isinstance(body, dict) else body.code.value
    assert code == "KILL_SWITCH"

    # A code absent from the shared catalog must still reach the host, not raise ValueError.
    class _Local:
        value = "AGENT_LOCAL_CODE"

    fallback = _host_error(_Local(), "x")
    assert fallback["code"] == "AGENT_LOCAL_CODE"


def test_platform_error_codes_map_onto_the_shared_catalog():
    shared_errors = pytest.importorskip("shared.errors")
    from security_agents.contracts import ErrorCode

    shared_names = {e.value for e in shared_errors.ErrorCode}
    assert {e.value for e in ErrorCode} <= shared_names
