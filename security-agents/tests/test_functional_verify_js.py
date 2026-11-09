"""Functional Verify replays the reviewer's generated JS tests through `nodetest`."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from code_review import api as review_api
from shared.findings import VerificationVerdict
from shared.ids import IdPrefix, new_id

from security_agents.host_adapter import _verify_functional_patch
from security_agents.sandbox.driver import SandboxResult

SOURCE = "assets/js/roster-summary.js"
GENERATED = "tests/generated/cr_key.test.js"
RELATED = "tests/roster.test.js"
UNRELATED = "tests/other.test.js"
FIX = (
    f"diff --git a/{SOURCE} b/{SOURCE}\n--- a/{SOURCE}\n+++ b/{SOURCE}\n"
    "@@ -1 +1 @@\n-export const key = 'BUG';\n+export const key = 'FIXED';\n"
)
NOT_A_FIX = FIX.replace("'FIXED'", "'STILL_BUG'")


class FakeDriver:
    """Decides test outcomes from the workspace it is handed, as a real run would."""

    isolation_level = "fake"

    def __init__(
        self, name="local-process", *, bug_reproduces=True, regression=False, title="keeps keys distinct"
    ):
        self.name = name
        self.bug_reproduces = bug_reproduces
        self.regression = regression
        self.title = title
        self.specs = []

    def run(self, spec):
        self.specs.append(spec)
        fixed = "FIXED" in (spec.workspace / SOURCE).read_text()
        suites = []
        for target in (a for a in spec.args if a.endswith(".test.js")):
            ok = fixed or not self.bug_reproduces
            if target != GENERATED:
                ok = not (self.regression and fixed)
            status = "passed" if ok else "failed"
            suites.append(
                {
                    "name": f"/vercel/sandbox/{target}",
                    "status": status,
                    "assertionResults": [{"fullName": self.title, "status": status, "failureMessages": []}],
                }
            )
        failed = any(s["status"] == "failed" for s in suites)
        return SandboxResult(
            run_id=f"sbx_{len(self.specs)}",
            driver=self.name,
            isolation_level="fake",
            profile="test-runner",
            network=spec.network,
            exit_code=1 if failed else 0,
            stdout="",
            stderr="",
            out_files={"node_tests.json": json.dumps({"testResults": suites}).encode()},
            duration_s=0.1,
            timed_out=False,
            started_at=datetime.now(UTC),
            labels={},
        )


class FakeHost:
    def __init__(self):
        self.verifications = []
        self.statuses = []
        self.reports = []
        self.progress_lines = []
        self.finished = []

    def progress(self, line):
        self.progress_lines.append(line)

    def start_agent_run(self, *_args, **_kwargs):
        return new_id(IdPrefix.run)

    def finish_agent_run(self, _run_id, status, **_kwargs):
        self.finished.append(str(getattr(status, "value", status)))

    def store_json(self, payload, **_kwargs):
        self.reports.append(payload)
        return SimpleNamespace(id=new_id(IdPrefix.art), sha256="0" * 64)

    def record_verification(self, verification):
        self.verifications.append(verification)

    def set_finding_status(self, finding_id, status, **_kwargs):
        self.statuses.append(status)

    def record(self, *_args):
        pass


def verify(tmp_path, monkeypatch, driver, *, diff=FIX, baseline=()):
    snapshot = tmp_path / "snapshot"
    for rel, text in {
        "package.json": json.dumps({"devDependencies": {"vitest": "^2"}}),
        "package-lock.json": "{}",
        SOURCE: "export const key = 'BUG';\n",
        RELATED: "import '../assets/js/roster-summary.js';\n",
        UNRELATED: "import '../assets/js/elsewhere.js';\n",
    }.items():
        (snapshot / rel).parent.mkdir(parents=True, exist_ok=True)
        (snapshot / rel).write_text(text)
    inputs = SimpleNamespace(
        diff_text=diff,
        generated_tests=[SimpleNamespace(path=GENERATED, content="it('keeps keys distinct', () => {});\n")],
        protected_paths=[],
        baseline_failing=list(baseline),
    )
    monkeypatch.setattr(review_api, "functional_verification_inputs", lambda _host, _patch: inputs)
    context = SimpleNamespace(
        artifacts={},
        audit=SimpleNamespace(emit=lambda *_a, **_k: None),
        agent=SimpleNamespace(value="verify"),
        run_id=None,
    )

    def no_pytest_runner(*_args, **_kwargs):
        raise AssertionError("JS tests must not reach the pytest runner")

    orchestrator = SimpleNamespace(
        workdir=tmp_path / "work",
        intel=SimpleNamespace(snapshot=SimpleNamespace(root=snapshot)),
        driver=driver,
        result=SimpleNamespace(usage=SimpleNamespace(sandbox_seconds=0.0)),
        _context=lambda *_a, **_k: context,
        _read_services=dict,
        _test_runner=no_pytest_runner,
    )
    (tmp_path / "work").mkdir()
    host = FakeHost()
    outcome = SimpleNamespace(
        patch=SimpleNamespace(
            id=new_id(IdPrefix.pat), finding_id=new_id(IdPrefix.fnd), files_changed=[SOURCE]
        )
    )
    _verify_functional_patch(host, orchestrator, outcome)
    return host


def test_js_fix_is_accepted_on_a_bare_nodetest_replay(tmp_path, monkeypatch):
    driver = FakeDriver()
    host = verify(tmp_path, monkeypatch, driver)

    assert [v.verdict for v in host.verifications] == [VerificationVerdict.accepted]
    assert all(c.passed for c in host.verifications[0].checks)
    assert host.statuses == ["verified"]
    assert len(driver.specs) == 3
    for spec in driver.specs:
        assert spec.mode == "nodetest" and spec.network == "none"
        assert spec.args[:2] == ["vitest", "run"]
        assert spec.node_stack["emulators"] == [] and spec.node_stack["serve"] is None
    assert GENERATED in driver.specs[0].args and RELATED not in driver.specs[0].args
    suite_args = driver.specs[2].args
    assert RELATED in suite_args and GENERATED in suite_args
    assert UNRELATED not in suite_args  # the whole jsdom suite is OOM-killed in the microVM
    assert host.reports[0]["suite"]["related_tests_only"] is True


@pytest.mark.parametrize(
    "driver,diff,detail",
    [
        (FakeDriver(), NOT_A_FIX, "patched=False"),
        (FakeDriver(regression=True), FIX, f"{RELATED}::keeps_keys_distinct"),
        (FakeDriver(bug_reproduces=False), FIX, "unpatched_failed=False"),
    ],
    ids=["patch-does-not-fix", "new-suite-failure", "tests-pass-unpatched"],
)
def test_js_fix_is_rejected_when_the_replay_disproves_it(tmp_path, monkeypatch, driver, diff, detail):
    host = verify(tmp_path, monkeypatch, driver, diff=diff)

    assert [v.verdict for v in host.verifications] == [VerificationVerdict.rejected]
    assert detail in host.verifications[0].reasons[0]
    assert host.statuses == ["patch_rejected"]


def test_rejection_with_long_js_test_titles_is_still_recorded(tmp_path, monkeypatch):
    host = verify(tmp_path, monkeypatch, FakeDriver(regression=True, title="agrees on every state " * 40))

    assert [v.verdict for v in host.verifications] == [VerificationVerdict.rejected]
    assert len(host.verifications[0].reasons[0]) == 500
    assert host.statuses == ["patch_rejected"]


def test_failure_already_in_the_baseline_does_not_reject(tmp_path, monkeypatch):
    # The regression flag fails RELATED on the patched tree; here the reviewer saw it fail first.
    host = verify(
        tmp_path,
        monkeypatch,
        FakeDriver(regression=True),
        baseline=[f"{RELATED}::keeps_keys_distinct"],
    )
    assert [v.verdict for v in host.verifications] == [VerificationVerdict.accepted]


@pytest.mark.parametrize("flag", ["CODE_REVIEW_NODE_ON_VERCEL", "SECURITY_AGENTS_NODE_ON_VERCEL"])
def test_either_flag_enables_node_on_vercel(tmp_path, monkeypatch, flag):
    monkeypatch.setenv(flag, "1")
    host = verify(tmp_path, monkeypatch, FakeDriver("vercel-sandbox"))
    assert [v.verdict for v in host.verifications] == [VerificationVerdict.accepted]


def test_vercel_without_a_flag_never_accepts(tmp_path, monkeypatch):
    monkeypatch.delenv("CODE_REVIEW_NODE_ON_VERCEL", raising=False)
    monkeypatch.delenv("SECURITY_AGENTS_NODE_ON_VERCEL", raising=False)
    driver = FakeDriver("vercel-sandbox")
    host = verify(tmp_path, monkeypatch, driver)

    assert host.verifications == [] and driver.specs == []
    assert host.finished == ["failed"]
