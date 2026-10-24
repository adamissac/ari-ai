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


def test_retained_bounds_and_original_archive_remain_anchored():
    import gzip
    import hashlib
    import json
    import subprocess

    root = SCRIPT.parents[2]
    path = root / "docs/research/rl-product-thesis/bounds/BOUNDS.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "5e3fbd649031054e2c85815edd9b168d52cd737fa9204e644c1c9a54ea8f0262"
    )
    bounds = json.loads(path.read_text())
    original = root / module.STUDY
    index = (original / "STUDY_EVIDENCE.json").read_bytes()
    assert hashlib.sha256(index).hexdigest() == module.ANCHOR
    for name, expected in json.loads(index)["files"].items():
        assert hashlib.sha256((original / name).read_bytes()).hexdigest() == expected
    assert len(bounds["records"]) == 120
    for row in bounds["records"]:
        trace = json.loads(
            gzip.decompress(
                (original / f"{row['family']}-{row['seed']:02}-noop.json.gz").read_bytes()
            )
        )
        jobs = [j["arrival"] for j in trace["requests"]]
        legit = [(j["tick"], j["tick"] + 24, j["work"]) for j in jobs if not j["adversarial"]]
        assert module.completion_upper(legit)["completed_upper"] == row["completed_upper"]
        assert (
            module.coverage(jobs)["offered_work_removable_upper"]
            == row["offered_work_removable_upper"]
        )
        assert (
            row["observed_completion_lower_B"]
            <= row["observed_completion_lower_A"]
            <= row["completed_upper"]
            <= row["legitimate_jobs"]
        )
    # Original analytical source is retained independently of later documentation.
    raw = subprocess.check_output(
        ["git", "show", f"{bounds['source_commit']}:scripts/research/resource_bounds.py"], cwd=root
    )
    assert hashlib.sha256(raw).hexdigest() == bounds["source_sha256"]
