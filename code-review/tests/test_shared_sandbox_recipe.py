"""The reviewer's sandbox runs use the recipe's `sandbox` block like the security agents."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from code_review.shared_sandbox import SharedSandboxAdapter


class _Capture:
    name = "capture"
    isolation_level = "test"

    def __init__(self) -> None:
        self.specs: list = []

    def run(self, spec):
        self.specs.append(spec)
        return SimpleNamespace(
            out_files={},
            exit_code=0,
            stdout="",
            stderr="",
            duration_s=0.0,
            timed_out=False,
            run_id="r1",
            isolation_level="test",
        )


def test_reviewer_runs_get_recipe_packages_and_upload_only_includes_plus_targets(tmp_path: Path):
    (tmp_path / "build_recipe.json").write_text(
        json.dumps(
            {"sandbox": {"pip": ["sqlalchemy==2.1.5"], "include": ["backend", "pyproject.toml"]}}
        )
    )
    driver = _Capture()
    adapter = SharedSandboxAdapter(driver)
    adapter.run_pytest(
        tmp_path, ["tests/generated/test_x.py::test_a", "backend/tests/test_y.py"], timeout_s=30
    )
    spec = driver.specs[0]
    assert spec.pip == ("sqlalchemy==2.1.5",)
    assert spec.include == ("backend", "pyproject.toml", "tests")


def test_without_a_recipe_the_whole_workspace_is_used(tmp_path: Path):
    driver = _Capture()
    SharedSandboxAdapter(driver).run_pytest(tmp_path, ["tests/test_a.py"], timeout_s=30)
    assert driver.specs[0].include == () and driver.specs[0].pip == ()
