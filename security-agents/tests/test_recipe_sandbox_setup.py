"""Recipe `sandbox` block: pinned wheels, apt names and include paths are validated, and
only included paths are uploaded into the sandbox workspace."""

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
    import json

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
