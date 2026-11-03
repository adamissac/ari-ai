"""Evidence-harness worker: a REAL hackatl-worker process with TEST-ONLY scripted
model transports installed, so restart/recovery exercises exercise the genuine job
lifecycle (claim, lease heartbeat, handler, checkpoint, drain) without paid calls.

Same scripted-transport pattern as frontend/tests/e2e/stack.py and
backend/tests/test_unified_assessment.py: provider_mode is recorded "fake" on every
agent run; results are honest about being scripted-model, never presented as live.

Invoked as a subprocess by restart_recovery.py, never imported by product code.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
REPO = Path(os.environ["EVIDENCE_REPO_DIR"])  # owned-repo root; its target/ drives tools
TARGET = REPO / "target"
HOLD = os.environ.get("EVIDENCE_HOLD_FILE")  # set only for the worker a scenario must interrupt


class _HoldAtModelCall:
    """Deterministic interruption point: while the hold file exists, every model call
    touches ``<hold>.reached`` and blocks, so the controller can SIGKILL this worker
    mid-attempt instead of racing it to the approval pause."""

    mode = "fake"

    def __init__(self, inner: Any, hold: Path) -> None:
        self.inner = inner
        self.hold = hold

    def create(self, request: dict) -> Any:
        while self.hold.exists():
            Path(f"{self.hold}.reached").touch()
            time.sleep(0.1)
        return self.inner.create(request)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def _held(transport: Any) -> Any:
    return _HoldAtModelCall(transport, Path(HOLD)) if HOLD else transport


def _install_scripted_transports() -> None:
    import code_review

    for p in (
        Path(code_review.__file__).resolve().parents[1] / "tests",
        ROOT / "backend" / "tests",
    ):
        sys.path.insert(0, str(p))
    from cr_fakes import fake  # type: ignore[import-not-found]
    from sa_bridge import AlanScriptTransport  # type: ignore[import-not-found]
    from test_reviewer_agent import pl_repair_script, pl_review_script  # type: ignore

    from backend import llm

    review_script = list(pl_review_script(SimpleNamespace(repo=REPO)))
    repair_script = list(pl_repair_script("tests/test_refund_total_bound.py"))
    repair = fake(list(repair_script))

    class _ReviewThenRepair:
        """Reviewer repair turns take the repair script; all else the review script.
        Same routing as backend/tests/test_unified_assessment.py."""

        mode = "fake"

        def __init__(self, review: Any, repair_t: Any) -> None:
            self.review = review
            self.repair_t = repair_t

        def create(self, request: dict) -> Any:
            if "Reviewer in repair mode" in str(request.get("system") or ""):
                return self.repair_t.create(request)
            return self.review.create(request)

    fallback = _ReviewThenRepair(fake(review_script), repair)
    bridge = _held(AlanScriptTransport(TARGET, fallback=fallback))
    llm.TRANSPORT_OVERRIDE = lambda: bridge

    original_build_gateway = llm.build_gateway
    per_assessment: dict[str, AlanScriptTransport] = {}

    def isolated_gateway(**kwargs: Any) -> llm.LLMGateway:
        owner = getattr(kwargs.get("charge"), "__self__", None)
        assessment_id = getattr(owner, "assessment_id", None)
        if assessment_id and kwargs.get("transport") is None:
            per_assessment.setdefault(
                assessment_id,
                _held(
                    AlanScriptTransport(
                        TARGET,
                        fallback=_ReviewThenRepair(fake(review_script), fake(list(repair_script))),
                    )
                ),
            )
            kwargs["transport"] = per_assessment[assessment_id]
        return original_build_gateway(**kwargs)

    llm.build_gateway = isolated_gateway


def main() -> int:
    from backend import worker

    _install_scripted_transports()
    if os.environ.get("EVIDENCE_PROBE"):
        # Trivial in-process handler for queue exactly-once / drain evidence.
        worker.HANDLERS["evidence_probe"] = lambda ctx: {"probe": True}
    return worker.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
