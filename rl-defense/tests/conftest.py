"""Make the sibling workspace packages importable under pytest.

On macOS the editable ``.pth`` finders for the workspace packages are not always
processed (see CLAUDE.md's PYTHONPATH note), so running a subset of tests can fail
to import ``shared`` / ``standards`` / ``payments_lite``. We add their source roots
to ``sys.path`` defensively; a normal editable install makes this a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # repo root
for _rel in ("shared", "standards", "examples/payments-lite/target"):
    _p = _ROOT / _rel
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
