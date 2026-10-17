"""The README's install line must match CI's, so README setups don't silently skip tests."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _editables(text: str) -> set[str]:
    return set(re.findall(r"-e (\S+)", text))


def test_readme_install_matches_ci():
    readme = (ROOT / "rl-defense/README.md").read_text()
    ci = (ROOT / ".github/workflows/rl.yml").read_text()
    line = next(ln for ln in readme.splitlines() if "uv pip install" in ln and "-e" in ln)
    ci_line = next(ln for ln in ci.splitlines() if "uv pip install" in ln and "-e" in ln)
    assert _editables(line) == _editables(ci_line)
