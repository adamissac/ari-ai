"""Recipe `sandbox` block: pinned wheels, apt names and include paths are validated, and
only included paths are uploaded into the sandbox workspace."""

import json
from pathlib import Path

import pytest

from security_agents.contracts import PlatformError
from security_agents.sandbox.driver import SandboxProfile, SandboxSpec, _stage_workspace
from security_agents.tools.services import sandbox_setup


def test_valid_block_is_returned_as_tuples() -> None:
    out = sandbox_setup(
        {
            "sandbox": {
                "pip": ["psycopg[binary]==3.3.6"],
                "apt": ["postgresql"],
                "include": ["backend", "deploy/x.py"],
            }
        }
    )
    assert out == {
        "pip": ("psycopg[binary]==3.3.6",),
        "apt": ("postgresql",),
        "include": ("backend", "deploy/x.py"),
    }
    assert sandbox_setup({}) == {"pip": (), "apt": (), "include": ()}


@pytest.mark.parametrize(
    "block",
    [
        {"pip": ["requests"]},  # unpinned
        {"pip": ["x==1; os.system('id')"]},
        {"pip": ["--index-url=https://evil.test x==1"]},
        {"apt": ["postgresql; rm -rf /"]},
        {"apt": ["-o=APT::Foo"]},
        {"include": ["../etc"]},
        {"include": ["/etc"]},
        {"pip": "sqlalchemy==2"},
    ],
)
def test_untrusted_entries_are_refused(block) -> None:
    with pytest.raises(PlatformError):
        sandbox_setup({"sandbox": block})


def test_only_included_paths_are_staged(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    (src / "backend").mkdir(parents=True)
    (src / "backend" / "a.py").write_text("x = 1\n")
    (src / "rl-defense").mkdir()
    (src / "rl-defense" / "big.bin").write_text("y")
    (src / "deploy").mkdir()
    (src / "deploy" / "t.py").write_text("z = 1\n")
    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=src,
        mode="pytest",
        args=[],
        labels={},
        include=("backend", "deploy/t.py"),
    )
    ws = _stage_workspace(spec, tmp_path)
    assert (ws / "backend" / "a.py").is_file() and (ws / "deploy" / "t.py").is_file()
    assert not (ws / "rl-defense").exists()


def test_include_symlink_cannot_escape_the_workspace(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (tmp_path / "secret").mkdir()
    (src / "backend").symlink_to(tmp_path / "secret")
    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=src,
        mode="pytest",
        args=[],
        labels={},
        include=("backend",),
    )
    with pytest.raises(PlatformError):
        _stage_workspace(spec, tmp_path)


def test_recipe_test_roots_default_and_override(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import recipe_test_roots, under_test_roots

    assert recipe_test_roots(tmp_path) == ("tests/",)  # no recipe
    (tmp_path / "build_recipe.json").write_text(json.dumps({"test_roots": ["backend/tests", "tests"]}))
    roots = recipe_test_roots(tmp_path)
    assert roots == ("backend/tests/", "tests/")
    assert under_test_roots("backend/tests/test_x.py", roots)
    assert not under_test_roots("backend/backend/api/routes.py", roots)
    assert not under_test_roots("backend/tests2/x.py", roots)
    (tmp_path / "build_recipe.json").write_text(json.dumps({"test_roots": ["../etc"]}))
    assert recipe_test_roots(tmp_path) == ("tests/",)  # unsafe entries fall back


def test_recipe_protected_tests_returns_sorted_unique_paths(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import recipe_protected_tests

    (tmp_path / "build_recipe.json").write_text(
        json.dumps({"protected_tests": ["tests/test_b.py", "tests/test_a.py", "tests/test_b.py"]})
    )
    assert recipe_protected_tests(tmp_path) == ("tests/test_a.py", "tests/test_b.py")


def test_recipe_protected_tests_drops_outside_roots_and_traversal(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import recipe_protected_tests

    (tmp_path / "build_recipe.json").write_text(
        json.dumps(
            {
                "protected_tests": [
                    "tests/test_api.py",
                    "ledgerlite/app.py",
                    "../x.py",
                ]
            }
        )
    )
    assert recipe_protected_tests(tmp_path) == (
        "../x.py (protected-test discovery failed: SANDBOX_POLICY_VIOLATION)",
        "tests/test_api.py",
    )


@pytest.mark.parametrize("protected_tests", ["tests/test_a.py", ["tests/test_a.py", 1]])
def test_recipe_protected_tests_requires_a_list_of_strings(tmp_path: Path, protected_tests: object) -> None:
    from security_agents.sandbox.workspace import recipe_protected_tests

    (tmp_path / "build_recipe.json").write_text(json.dumps({"protected_tests": protected_tests}))
    assert recipe_protected_tests(tmp_path) == ()


def test_recipe_protected_tests_missing_or_invalid_recipe_returns_empty(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import recipe_protected_tests

    assert recipe_protected_tests(tmp_path) == ()
    (tmp_path / "build_recipe.json").write_text("{invalid")
    assert recipe_protected_tests(tmp_path) == ()


def test_recipe_protected_tests_honors_custom_test_roots(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import recipe_protected_tests

    (tmp_path / "build_recipe.json").write_text(
        json.dumps(
            {
                "test_roots": ["backend/tests"],
                "protected_tests": ["backend/tests/test_a.py", "tests/test_b.py"],
            }
        )
    )
    assert recipe_protected_tests(tmp_path) == ("backend/tests/test_a.py",)


def test_test_root_symlinks_includes_only_in_root_file_targets(tmp_path: Path) -> None:
    from security_agents.sandbox.workspace import test_root_symlinks

    root = tmp_path / "repo"
    tests_root = root / "tests"
    tests_root.mkdir(parents=True)
    source = root / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("value = 1\n")
    outside = tmp_path / "outside.py"
    outside.write_text("value = 2\n")
    (tests_root / "test_inside.py").symlink_to("../src/module.py")
    (tests_root / "test_outside.py").symlink_to(outside)
    (tests_root / "test_dangling.py").symlink_to("missing.py")

    assert test_root_symlinks(root, ("tests/",)) == ("tests/test_inside.py",)
