"""A deploy sends SIGTERM: the worker finishes the job in hand, takes no new one, exits 0."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = """
import sys, time
from backend import worker
calls = []
def run_one(owner, kinds=None):
    calls.append(1)
    time.sleep(1.5)  # a job in progress when SIGTERM arrives
    print("finished", len(calls), flush=True)
    return "job"
worker.run_one = run_one
sys.exit(worker.main([]))
"""


def test_sigterm_lets_the_running_job_finish_and_takes_no_new_one():
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            str(Path(__file__).resolve().parents[2] / d)
            for d in ("backend", "shared", "monitoring", "standards")
        ),
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", SCRIPT], stdout=subprocess.PIPE, text=True, env=env
    )
    time.sleep(1.0)  # inside the first job
    proc.send_signal(signal.SIGTERM)
    out, _ = proc.communicate(timeout=20)
    assert proc.returncode == 0
    assert out.strip().splitlines() == ["finished 1"]
