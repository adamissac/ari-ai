"""Firestore-rules templates against a real Firestore emulator (ADR-0023).

Needs `java`, `node`, a cached Firestore emulator JAR (`firebase setup:emulators:firestore`
or any prior `firebase emulators:start`) and `npm ci --prefix sandbox/node`. Skipped,
with the reason, when any is missing: nothing here is simulated.
"""

import glob
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from security_agents import node_recipe
from security_agents.checks.library import (
    FIRESTORE_ENUMERATION,
    FIRESTORE_OWNER,
    FIRESTORE_UNAUTHENTICATED,
    default_library,
)

from .test_node_recipe import recipe

NODE_DIR = Path(__file__).parent.parent / "sandbox" / "node"
HARNESS = Path(__file__).parent.parent / "security_agents" / "checks" / "firestore_harness.mjs"
JARS = sorted(glob.glob(os.path.expanduser("~/.cache/firebase/emulators/cloud-firestore-emulator-v*.jar")))

OWNER_ONLY = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
"""
# The classic mistake: "signed in" stands in for "is the owner".
SIGNED_IN = OWNER_ONLY.replace("request.auth != null && request.auth.uid == uid", "request.auth != null")
PUBLIC = OWNER_ONLY.replace("request.auth != null && request.auth.uid == uid", "true")


def _missing() -> str | None:
    if not shutil.which("java"):
        return "java not installed"
    if not shutil.which("node"):
        return "node not installed"
    if not JARS:
        return "no cached Firestore emulator JAR"
    if not (NODE_DIR / "node_modules" / "@firebase" / "rules-unit-testing").is_dir():
        return "run `npm ci --prefix security-agents/sandbox/node`"
    return None


pytestmark = pytest.mark.skipif(_missing() is not None, reason=_missing() or "")


@pytest.fixture(scope="module")
def emulator():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        ["java", "-jar", JARS[-1], "--host=127.0.0.1", f"--port={port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), 1).close()
            break
        except OSError:
            if time.monotonic() > deadline or proc.poll() is not None:
                proc.kill()
                pytest.fail("Firestore emulator did not start")
            time.sleep(0.3)
    yield f"127.0.0.1:{port}"
    proc.terminate()
    proc.wait(10)


def run_check(tmp_path, emulator, rules, meta, params):
    ws = tmp_path / "ws"
    (ws / ".sandbox").mkdir(parents=True)
    (ws / "firestore.rules").write_text(rules)
    resolved = node_recipe.resolved(recipe())
    rendered = default_library().render(meta.ref, resolved, params)
    (ws / ".sandbox" / "test_generated_check.py").write_text(rendered)
    shutil.copy2(HARNESS, ws / ".sandbox" / "firestore_harness.mjs")
    env = {
        "PATH": os.path.dirname(shutil.which("node")) + ":/usr/bin:/bin",
        "FIRESTORE_EMULATOR_HOST": emulator,
        "ARI_NODE_DIR": str(NODE_DIR),
        "HOME": str(tmp_path),
    }
    cp = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", ".sandbox/test_generated_check.py"],
        cwd=ws,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return cp.returncode, cp.stdout + cp.stderr


OWNER_PARAMS = {"path_id": "user_doc", "owner_identity": "alice", "other_identity": "bob"}


def test_owner_isolation_holds_under_owner_only_rules(tmp_path, emulator):
    code, out = run_check(tmp_path, emulator, OWNER_ONLY, FIRESTORE_OWNER, OWNER_PARAMS)
    assert code == 0 and "1 passed" in out, out


def test_owner_isolation_confirms_signed_in_is_not_owner(tmp_path, emulator):
    code, out = run_check(tmp_path, emulator, SIGNED_IN, FIRESTORE_OWNER, OWNER_PARAMS)
    assert code == 1 and "1 failed" in out and "passed" not in out.splitlines()[-1], out
    assert "['other_get', 'other_set']" in out  # the emulator allowed both, recorded as evidence


def test_unauthenticated_and_enumeration_templates(tmp_path, emulator):
    unauth = {"path_id": "user_doc", "owner_identity": "alice"}
    assert run_check(tmp_path / "a", emulator, SIGNED_IN, FIRESTORE_UNAUTHENTICATED, unauth)[0] == 0
    code, out = run_check(tmp_path / "b", emulator, PUBLIC, FIRESTORE_UNAUTHENTICATED, unauth)
    assert code == 1 and "['anon_get', 'anon_list']" in out, out
    assert run_check(tmp_path / "c", emulator, OWNER_ONLY, FIRESTORE_ENUMERATION, OWNER_PARAMS)[0] == 0
    code, out = run_check(tmp_path / "d", emulator, SIGNED_IN, FIRESTORE_ENUMERATION, OWNER_PARAMS)
    assert code == 1 and "list the collection" in out, out


def test_emulator_errors_are_not_evidence(tmp_path, emulator):
    """A broken rules file is an error (no verdict), never a confirmed finding."""
    code, out = run_check(tmp_path, emulator, "rules_version = '2'; garbage", FIRESTORE_OWNER, OWNER_PARAMS)
    assert code != 0 and " failed" not in out.splitlines()[-1], out
    assert "error" in out.splitlines()[-1], out


def test_a_denied_owner_is_inconclusive_not_a_finding(tmp_path, emulator):
    """Server-only collections deny everyone; the positive control turns that into no verdict."""
    deny_all = OWNER_ONLY.replace("request.auth != null && request.auth.uid == uid", "false")
    code, out = run_check(tmp_path, emulator, deny_all, FIRESTORE_OWNER, OWNER_PARAMS)
    last = out.splitlines()[-1]
    assert code != 0 and "failed" not in last and "error" in last, out
    assert "positive control failed" in out
