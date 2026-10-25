"""Independent readiness-synchronized control for the existing SIGTERM test."""

import os
import select
import signal
import subprocess
import sys
from pathlib import Path

from test_worker_drain import SCRIPT


def test_busy_worker_drains_after_observed_job_start():
    code = SCRIPT.replace("worker._BUSY.set()", 'worker._BUSY.set(); print("ready", flush=True)')
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            str(Path(__file__).resolve().parents[2] / d)
            for d in ("backend", "shared", "monitoring", "standards")
        ),
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, env=env
    )
    try:
        assert select.select([proc.stdout], [], [], 15)[0], "worker did not enter test job"
        assert proc.stdout.readline().strip() == "ready"
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=20)
        assert proc.returncode == 0
        assert out.strip().splitlines() == ["finished 1"]
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
