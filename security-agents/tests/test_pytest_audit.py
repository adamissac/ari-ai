from __future__ import annotations

import pytest

from security_agents.tools.pytest_audit import compare_pytest_audits


def _audit(
    *,
    hooks: list[dict[str, object]] | None = None,
    nodeids: list[str] | None = None,
    outcomes: dict[str, str] | None = None,
    complete: bool = True,
) -> dict[str, object]:
    entries = (
        hooks
        if hooks is not None
        else [
            {
                "hook": "pytest_collection_modifyitems",
                "module": "checks",
                "qualname": "modify",
                "file": "tests/conftest.py",
                "flags": [],
                "code_sha256": "a" * 64,
            }
        ]
    )
    ids = nodeids if nodeids is not None else ["tests/test_api.py::test_value"]
    return {
        "version": 1,
        "complete": complete,
        "phases": {"collection": entries, "final": entries},
        "nodeids": ids,
        "outcomes": outcomes if outcomes is not None else {ids[0]: "passed"},
    }


def test_identical_pytest_audits_have_no_findings() -> None:
    audit = _audit()
    assert compare_pytest_audits(audit, audit) == []


@pytest.mark.parametrize(
    ("baseline_hooks", "patched_hooks", "finding"),
    [
        ([], [_audit()["phases"]["collection"][0]], "hook added or changed"),
        ([_audit()["phases"]["collection"][0]], [], "hook removed or changed"),
        (
            [_audit()["phases"]["collection"][0]],
            [
                {
                    **_audit()["phases"]["collection"][0],
                    "code_sha256": "b" * 64,
                }
            ],
            "hook added or changed",
        ),
    ],
    ids=["added", "removed", "changed-code"],
)
def test_hook_changes_are_reported(
    baseline_hooks: list[dict[str, object]],
    patched_hooks: list[dict[str, object]],
    finding: str,
) -> None:
    findings = compare_pytest_audits(_audit(hooks=baseline_hooks), _audit(hooks=patched_hooks))
    assert any(finding in detail for detail in findings)


def test_missing_nodeid_is_reported() -> None:
    baseline = _audit()
    patched = _audit(nodeids=[], outcomes={})
    assert any(
        "protected tests not collected: tests/test_api.py::test_value" in finding
        for finding in compare_pytest_audits(baseline, patched)
    )


@pytest.mark.parametrize("outcome", ["skipped", "xfailed"])
def test_passed_test_that_is_skipped_or_xfailed_is_reported(outcome: str) -> None:
    baseline = _audit()
    patched = _audit(outcomes={"tests/test_api.py::test_value": outcome})
    assert compare_pytest_audits(baseline, patched) == [
        f"test no longer executes: tests/test_api.py::test_value -> {outcome}"
    ]


def test_passed_to_failed_is_left_to_the_suite_check() -> None:
    baseline = _audit()
    patched = _audit(outcomes={"tests/test_api.py::test_value": "failed"})
    assert compare_pytest_audits(baseline, patched) == []


@pytest.mark.parametrize("side", ["baseline", "patched"])
@pytest.mark.parametrize("kind", ["missing", "incomplete"])
def test_missing_or_incomplete_audit_fails_closed(side: str, kind: str) -> None:
    baseline = _audit()
    patched = _audit()
    if side == "baseline":
        baseline = None if kind == "missing" else _audit(complete=False)
    else:
        patched = None if kind == "missing" else _audit(complete=False)
    expected = f"{side} pytest audit missing, malformed, or incomplete"
    assert compare_pytest_audits(baseline, patched) == [expected]
