"""Regression: the sandbox target harness must seed without AttributeError.

deploy/sandbox_target.py used `AssessmentState.completed` (no such member; the enum
defines `COMPLETED = "COMPLETED"`), which aborted fixture setup before any request.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

from backend.db import assessments, transaction

_HARNESS = Path(__file__).resolve().parents[2] / "deploy" / "sandbox_target.py"


def _load_harness():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("sandbox_target_seed_test", _HARNESS)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_sandbox_seed_builds_completed_assessment_without_attribute_error():
    harness = _load_harness()

    tokens = harness._seed()

    assert "alice" in tokens and "carol" in tokens and "dave" in tokens
    alice_asm = harness.FIXTURES["alice"]["assessment"]
    with transaction() as conn:
        state = conn.execute(
            sa.select(assessments.c.state).where(assessments.c.id == alice_asm)
        ).scalar_one()
    assert state == "COMPLETED"
