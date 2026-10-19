"""Bridge between the orchestrator and the trained specialist models (``specialists`` package).

Pipeline per agent: code intelligence → specialist model → Claude (with the model's ranked
output as an advisory, provenance-labelled data block) → authorized tools → evidence.

What a specialist may do, enforced here and in the orchestrator:
  * add a ``<data label="specialist_model" provenance="trained_model">`` block to a prompt;
  * re-rank Scout hypotheses (it cannot add or drop one; citations are still validated);
  * add a finding note when Verify's evidence model disagrees with an accepted verdict.
What it can never do: approve, verify, widen scope, change a severity, an executed outcome or a
verdict. If the package or a checkpoint is unavailable, every function returns ``None`` and the
agent runs exactly as before (the fallback).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .runtime import data_block

if TYPE_CHECKING:
    from .intel import CodeIntel

try:  # The specialists package is optional at import time; absence is the fallback path.
    from specialists.runtime import Advice, Specialists
    from specialists.runtime import default as _default_specialists
except ImportError:  # pragma: no cover - exercised by the fallback test via a disabled instance
    Advice = Any  # type: ignore[misc,assignment]
    Specialists = None  # type: ignore[assignment,misc]
    _default_specialists = None  # type: ignore[assignment]

SCOUT_BLEND = 0.35  # weight of the specialist's suspicion in Scout's deterministic ranking
MAX_SPAN_CHARS = 6000


def default() -> Any | None:
    return _default_specialists() if _default_specialists else None


def _span_text(intel: CodeIntel, path: str | None, start: int, end: int) -> str:
    if not path or not intel.snapshot.exists(path):
        return ""
    lines = (intel.snapshot.root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[max(0, start - 1) : end])[:MAX_SPAN_CHARS]


def block(advice: Advice | None, note: str) -> str:
    """The prompt block for one advice, or "" when there is none."""
    if advice is None or advice.source == "unavailable" or not advice.predictions:
        return ""
    payload = {"model": advice.model_id, "source": advice.source, "predictions": advice.predictions, "how_to_use": note}
    return "\n\n" + data_block("specialist_model", payload, provenance="trained_model")


def audit_fields(advice: Advice) -> dict[str, Any]:
    return {"agent": advice.agent, "model": advice.model_id, "source": advice.source, "top": advice.top,
            "predictions": json.dumps(advice.predictions[:5]), "latency_ms": advice.latency_ms, "reason": advice.reason}


# ------------------------------------------------------------------ per agent

def scout_survey(sp: Any, intel: CodeIntel) -> tuple[list[dict[str, Any]], list[Advice]]:
    """Score every entry-point handler span; return rows ranked by suspicion (1 - P(safe))."""
    rows: list[dict[str, Any]] = []
    advices: list[Advice] = []
    for e in intel.entry_points():
        code = _span_text(intel, e.path, e.span.start_line, e.span.end_line)
        if not code:
            continue
        a = sp.advise("scout", {"code": code}, top_k=13)
        advices.append(a)
        if a.source != "model":
            continue
        safe = a.score("safe") or 0.0
        likely = next((p for p in a.predictions if p["label"] != "safe"), None)
        rows.append({"entry_point_id": e.id, "path": e.path, "lines": [e.span.start_line, e.span.end_line],
                     "suspicion": round(1.0 - safe, 4), "likely_cwe": likely["label"] if likely else None,
                     "likely_cwe_score": likely["score"] if likely else None})
    rows.sort(key=lambda r: -r["suspicion"])
    return rows, advices


def scout_block(rows: list[dict[str, Any]], model_id: str | None) -> str:
    if not rows:
        return ""
    payload = {"model": model_id, "source": "model", "entry_points_by_suspicion": rows[:15],
               "how_to_use": "A trained classifier's ranking of handler spans by how likely they hold one of 12 CWE classes. "
                             "Use it to decide what to read first. It is not evidence: read and cite the code yourself, "
                             "and do not raise a hypothesis only because a span ranks high."}
    return "\n\n" + data_block("specialist_model", payload, provenance="trained_model")


def scout_suspicion(sp: Any, intel: CodeIntel, hypothesis: Any) -> Advice | None:
    span = hypothesis.cited_spans[0]
    code = _span_text(intel, span.path, span.span.start_line if span.span else 1, span.span.end_line if span.span else 400)
    return sp.advise("scout", {"code": code}, top_k=13) if code else None


def blended_rank(hypotheses: list[Any], base_order: list[Any], suspicion: dict[str, float]) -> list[Any]:
    """Blend Scout's deterministic order with the specialist's suspicion (re-rank only)."""
    n = len(base_order)
    if n < 2 or not suspicion:
        return base_order
    base = {h.id: 1.0 - i / (n - 1) for i, h in enumerate(base_order)}
    def score(h: Any) -> tuple[float, str]:
        s = (1 - SCOUT_BLEND) * base[h.id] + SCOUT_BLEND * suspicion.get(h.id, 0.5)
        return (-s, h.id)
    return sorted(base_order, key=score)


def probe_advice(sp: Any, hypothesis: Any) -> Advice:
    return sp.advise("probe", {"hypothesis": f"{hypothesis.title}. {hypothesis.rationale[:600]}", "cwe": hypothesis.weakness_class})


def trace_advice(sp: Any, hypothesis: Any) -> Advice:
    return sp.advise("trace", {"name": hypothesis.cwe_name or hypothesis.weakness_class})


def diagnose_advice(sp: Any, intel: CodeIntel, finding: Any) -> Advice:
    span = finding.hypothesis.cited_spans[0]
    code = _span_text(intel, span.path, span.span.start_line if span.span else 1, span.span.end_line if span.span else 400)
    obs = json.dumps(dict(finding.validation.observations), default=str)[:1500] if finding.validation else ""
    return sp.advise("diagnose", {"code": code, "cwe": finding.hypothesis.weakness_class, "evidence": obs})


def patch_advice(sp: Any, intel: CodeIntel, finding: Any) -> Advice:
    span = finding.hypothesis.cited_spans[0]
    code = _span_text(intel, span.path, span.span.start_line if span.span else 1, span.span.end_line if span.span else 400)
    return sp.advise("patch", {"code": code, "cwe": finding.hypothesis.weakness_class})


def fortify_advice(sp: Any, finding: Any) -> Advice | None:
    std = finding.standards
    raw = (std.get("attack") if isinstance(std, dict) else getattr(std, "attack", None)) or []
    attack = [m.get("id") if isinstance(m, dict) else m.id for m in raw]
    attack = [a for a in attack if a]
    if not attack:
        return None
    from standards import catalog

    tech = catalog.load_json("attack-enterprise.json")["techniques"].get(attack[0])
    if not tech:
        return None
    return sp.advise("fortify", {"name": tech["name"], "tactics": " ".join(tech.get("tactics", []))})


def verify_advice(sp: Any, diff: str, test_runs: list[dict[str, Any]], unpatched_added_runs: list[dict[str, Any]]) -> Advice:
    failed_before = [str(t) for r in unpatched_added_runs for t in (r.get("failing_tests") or [])]
    passed = sum(int(r.get("passed") or 0) for r in test_runs)
    failed = sum(int(r.get("failed") or 0) for r in test_runs)
    summary = (f"{', '.join(failed_before[:5])}: failed before the patch, passed after. " if failed_before
               else "regression tests: passed before the patch, passed after. ")
    summary += f"Full suite: {passed} passed, {failed} failed."
    return sp.advise("verify", {"diff": diff[:20000], "tests": summary})
