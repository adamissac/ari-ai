"""Mathematical toy arrays, not generated service workloads or a new policy study."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/research/resource_bounds.py"
spec = importlib.util.spec_from_file_location("resource_bounds", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_deadline_interval_proves_more_than_total_capacity():
    bound = module.completion_upper([(0, 1, 1)] * 3, workers=2)
    assert bound["completed_upper"] == 2
    assert bound["binding_interval"] == [0, 1, 3, 2]


def test_relaxed_capacity_pass_does_not_prove_nonparallel_feasibility():
    # One2-unit job cannot complete on a single worker in one tick, even with2
    # workers. The relaxed interval upper bound deliberately cannot exclude it.
    assert module.completion_upper([(0, 1, 2)], workers=2)["completed_upper"] == 1


def test_nonoverlapping_windows_and_empty_input():
    assert module.completion_upper([(0, 1, 1), (1, 2, 1)], 1)["completed_upper"] == 2
    assert module.completion_upper([])["completed_upper"] == 0
    with pytest.raises(ValueError):
        module.completion_upper([(1, 1, 1)])


def test_coverage_relaxes_quota_but_never_more_than_eight_windows():
    jobs = [
        {"tick": 8 * i, "source": 0, "route": 1, "work": 3, "adversarial": True} for i in range(30)
    ]
    assert module.coverage(jobs) == {
        "adversarial_offered_work": 90,
        "offered_work_removable_upper": 24,
        "unfiltered_offered_work_lower": 66,
    }


def test_interval_bound_never_excludes_exact_tiny_single_worker_solution():
    from itertools import permutations, product

    cases = ((0, 2, 1), (0, 2, 2), (1, 3, 1), (0, 1, 2))
    for jobs in product(cases, repeat=3):
        optimum = 0
        for size in range(1, 4):
            for order in permutations(jobs, size):
                clock = 0
                for release, deadline, work in order:
                    clock = max(clock, release) + work
                    if clock > deadline:
                        break
                else:
                    optimum = max(optimum, size)
        assert module.completion_upper(list(jobs), workers=1)["completed_upper"] >= optimum
