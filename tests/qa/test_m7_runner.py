"""M7 runner failures must never touch an existing development database."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/devin_qa"))
import verify_m7_demo as m7  # noqa: E402


class M7RunnerTests(unittest.TestCase):
    def test_selected_interpreter_no_uv_or_shared_database_lifecycle(self):
        for child_exit, expected in [(0, 2), (1, 1), (2, 1)]:
            with (
                self.subTest(exit=child_exit),
                tempfile.TemporaryDirectory() as directory,
                patch.object(m7, "ROOT", Path(directory)),
                patch.object(m7, "run_command") as run,
            ):
                run.side_effect = [(0, "Python", ""), (child_exit, "test output", "error")]
                self.assertEqual(m7.main([]), expected)
                self.assertEqual(len(run.call_args_list), 2)
                command = run.call_args_list[1].args[0]
                self.assertEqual(command[:3], [sys.executable, "-m", "pytest"])
                report = json.loads((Path(directory) / ".dev/qa/m7-evidence.json").read_text())
                self.assertNotIn("branch", report)
                self.assertEqual(report["summary"]["failed"], int(child_exit != 0))

    @patch.object(m7.subprocess, "run")
    def test_live_opt_out_overrides_parent_and_caller(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "ok", "")
        with patch.dict("os.environ", {"RUN_LIVE_LLM_EVAL": "1"}):
            m7.run_command([sys.executable, "-V"], env={"RUN_LIVE_LLM_EVAL": "1"})
        self.assertEqual(run.call_args.kwargs["env"]["RUN_LIVE_LLM_EVAL"], "0")

    @patch.object(m7.subprocess, "run", side_effect=FileNotFoundError("missing"))
    def test_missing_process_is_a_failure(self, _):
        code, stdout, stderr = m7.run_command(["missing"])
        self.assertNotEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("missing", stderr)


if __name__ == "__main__":
    unittest.main()
