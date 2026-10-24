"""Analytical unit tests only; never launch the registered campaign."""

import time

import pytest

from rl_defense.research.resource.study import check_budget, measures, violations


def row(*, active=64, completed=90, denied=5, timeouts=5):
    return {
        "final": {
            "legitimate_offered": 100,
            "legitimate_completed": completed,
            "legitimate_rate_denied": denied,
            "legitimate_capacity_denied": 0,
            "legitimate_timeouts": timeouts,
            "legitimate_latency_sum": 16 * completed,
            "adversarial_work": 10,
            "recovery_count": 0,
            "recovery_ticks_sum": 0,
        },
        "costs": {"applications": 4, "active_ticks": active, "overhead_units": 4},
        "exhausted_ticks": 0,
    }


def test_acceptance_thresholds_are_inclusive_and_diagnostic_static_is_ineligible():
    assert violations([row()]) == []
    assert violations([row(active=240)]) == ["active_ticks"]
    assert "completion" in violations([row(completed=89)])
    assert "denial" in violations([row(denied=6)])
    assert "timeout" in violations([row(timeouts=6)])


def test_zero_completions_cannot_certify_latency_and_ratios_use_counts():
    assert measures([row(completed=0)])["latency"] is None
    assert "latency" in violations([row(completed=0)])
    assert measures([row(completed=90), row(completed=100)])["completion"] == 0.95


def test_wall_budget_is_execution_failure():
    with pytest.raises(RuntimeError, match="budget"):
        check_budget(time.monotonic() - 601)


def test_integrity_failure_retains_partial_evidence_and_never_seals(tmp_path, monkeypatch):
    import shutil
    import subprocess
    from pathlib import Path

    import rl_defense.research.resource.study as study

    source = Path(study.__file__).resolve().parents[4]
    root = tmp_path / "source"
    package = "rl-defense/rl_defense/research/resource"
    protocol = "docs/research/resource-exhaustion/PREREGISTRATION.md"
    shutil.copytree(source / package, root / package, ignore=shutil.ignore_patterns("__pycache__"))
    (root / protocol).parent.mkdir(parents=True)
    shutil.copyfile(source / protocol, root / protocol)
    for command in (
        ["git", "init"],
        ["git", "config", "user.name", "Unit"],
        ["git", "config", "user.email", "unit@example.invalid"],
        ["git", "add", "."],
        ["git", "commit", "-m", "unit source"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    # Fault injection must not inherit peak RSS from earlier unrelated torch tests.
    # The real memory guard is exercised separately below; production is unchanged.
    monkeypatch.setattr(study, "rss", lambda: 0)
    monkeypatch.setattr(study, "action", lambda policy, obs: 99)
    output = tmp_path / "failed"
    with pytest.raises(IndexError):
        study.run(root, output)
    assert (output / "FAILURE.json").exists()
    assert not (output / "STUDY_EVIDENCE.json").exists()
    with pytest.raises(FileExistsError):
        study.run(root, output)


def test_retained_formal_study_is_complete_and_accounted():
    from pathlib import Path

    from rl_defense.research.resource.verify_study import verify

    evidence = (
        Path(__file__).resolve().parents[2]
        / "docs/research/resource-exhaustion/feasibility-001/evidence"
    )
    assert verify(evidence, "931fbd6737f963a1fe661ab029d08b7f4a26fe09e42805c291c9d1a1a2a0246c") == {
        "episodes": 600,
        "decisions": 18000,
        "paired_workloads": 120,
    }
    with pytest.raises(ValueError, match="anchor"):
        verify(evidence, "0" * 64)


def test_memory_budget_is_execution_failure(monkeypatch):
    import rl_defense.research.resource.study as study

    monkeypatch.setattr(study, "rss", lambda: 512 * 1024**2 + 1)
    with pytest.raises(RuntimeError, match="budget"):
        study.check_budget(time.monotonic())
