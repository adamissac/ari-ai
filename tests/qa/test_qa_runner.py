"""The QA runner must preserve failures and incompleteness, without paid calls."""

import importlib.util
import subprocess
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

QA = Path(__file__).resolve().parents[2] / "scripts/devin_qa"
sys.path.insert(0, str(QA))
import common  # noqa: E402
import preflight_check as preflight  # noqa: E402


class RunnerTests(unittest.TestCase):
    def test_failure_precedes_incomplete_and_neither_is_success(self):
        self.assertEqual(common.exit_code([common.Result("a", "PASS")]), 0)
        self.assertEqual(common.exit_code([common.Result("a", "SKIP")]), 2)
        self.assertEqual(
            common.exit_code([common.Result("a", "SKIP"), common.Result("b", "FAIL")]), 1
        )

    def test_unknown_result_is_rejected(self):
        with self.assertRaises(ValueError):
            common.Result("unknown", "WARN")

    @patch("common.subprocess.run")
    def test_exit_two_only_means_incomplete_for_suite_wrappers(self, run):
        run.return_value.returncode = 2
        self.assertEqual(common.run("pytest collection error", ["pytest"]).status, "FAIL")
        self.assertEqual(common.run("wrapper", ["wrapper"], incomplete_exit=True).status, "SKIP")

    @patch("common.subprocess.run")
    def test_child_failure_is_preserved_and_live_calls_are_disabled(self, run):
        run.return_value.returncode = 7
        with patch.dict("os.environ", {"RUN_LIVE_LLM_EVAL": "1"}):
            result = common.run("child", [sys.executable, "-V"])
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(run.call_args.kwargs["env"]["RUN_LIVE_LLM_EVAL"], "0")
        self.assertEqual(run.call_args.kwargs["cwd"], common.ROOT)

    @patch("common.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_executable_is_incomplete(self, _):
        self.assertEqual(common.run("missing", ["missing"]).status, "SKIP")

    @patch("common.subprocess.run", side_effect=subprocess.TimeoutExpired("child", 1))
    def test_timeout_is_failure(self, _):
        self.assertEqual(common.run("timeout", ["child"], timeout=1).status, "FAIL")

    def test_readiness_requires_boolean_service_checks(self):
        for payload, expected in [
            (b'{"database":true,"queue":true,"webhook_secret_configured":true}', "PASS"),
            (b'{"database":true,"queue":false,"webhook_secret_configured":true}', "FAIL"),
            (b'{"database":"yes","queue":true,"webhook_secret_configured":true}', "FAIL"),
            (b"[]", "FAIL"),
            (b"not json", "FAIL"),
        ]:
            with (
                self.subTest(payload=payload),
                patch(
                    "preflight_check.urllib.request.urlopen", return_value=BytesIO(payload)
                ) as opening,
            ):
                self.assertEqual(preflight.readiness("http://127.0.0.1:8000").status, expected)
                self.assertEqual(opening.call_args.args[0], "http://127.0.0.1:8000/readyz")

    @patch("preflight_check.urllib.request.urlopen", side_effect=OSError("not running"))
    def test_unavailable_api_is_not_a_pass(self, _):
        self.assertEqual(preflight.readiness("http://127.0.0.1:8000").status, "SKIP")

    def test_entrypoints_do_not_execute_on_import(self):
        for filename in [
            "run_all_qa_tests.py",
            "test_security_workflow.py",
            "test_frontend_integration.py",
            "test_rl_workflow.py",
        ]:
            spec = importlib.util.spec_from_file_location(
                "qa_" + filename.replace(".", "_"), QA / filename
            )
            with patch("common.run", side_effect=AssertionError("executed on import")):
                spec.loader.exec_module(importlib.util.module_from_spec(spec))


if __name__ == "__main__":
    unittest.main()
