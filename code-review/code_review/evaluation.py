"""Score a review against a labeled answer key (e.g. examples/payments-lite/labels.yaml).

The answer key is read ONLY here, by the evaluator, after the review finished; the
reviewer never sees it. A finding matches a planted defect when it is ``validated`` and
one of its source spans overlaps the labeled root-cause symbol. Numbers produced from
scripted (fake-provider) runs measure the harness, not model quality, and are labeled so.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from code_review.models import ReviewOutcome
from shared.evidence import EvidenceKind
from shared.findings import Finding, FindingKind, FindingStatus


@dataclass
class EvalReport:
    provider_mode: str
    true_positives: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)
    security_handoffs_matched: list[str] = field(default_factory=list)
    generated_tests_failing_on_head: int = 0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "provider_mode": self.provider_mode,
            "label": "model-quality signal"
            if self.provider_mode == "live"
            else "harness check only (scripted provider; not a model-quality metric)",
            "tp": self.true_positives,
            "fp": self.false_positives,
            "fn": self.false_negatives,
            "security_handoffs_matched": self.security_handoffs_matched,
            "generated_tests_failing_on_head": self.generated_tests_failing_on_head,
            "notes": self.notes,
        }


def _symbol_lines(source: str, symbol: str) -> tuple[int, int] | None:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == symbol:
            return node.lineno, node.end_lineno or node.lineno
    return None


def _hits(f: Finding, path: str, lines: tuple[int, int]) -> bool:
    lo, hi = lines
    return any(
        e.kind is EvidenceKind.source_span
        and e.path == path
        and e.span is not None
        and e.span.start_line <= hi
        and e.span.end_line >= lo
        for e in f.evidence
    )


def score(outcome: ReviewOutcome, labels_path: Path, repo_prefix: str = "") -> EvalReport:
    import yaml

    labels = yaml.safe_load(labels_path.read_text())
    root = labels_path.parent
    rep = EvalReport(provider_mode=outcome.provider_mode)
    rep.generated_tests_failing_on_head = sum(
        t.outcome_on_head == "failed" for t in outcome.result.generated_tests
    )
    functional = [
        f
        for f in outcome.result.findings
        if f.kind is FindingKind.functional and f.status is FindingStatus.validated
    ]
    matched: set[str] = set()
    for planted in labels.get("planted_findings", []):
        span = planted["root_cause_span"]
        rel = span["path"]
        lines = _symbol_lines((root / rel).read_text(), span["symbol"])
        if lines is None:
            rep.notes.append(f"label symbol {span['symbol']} not found in {rel}")
            continue
        repo_path = f"{repo_prefix}{rel.split('/', 1)[1]}" if repo_prefix else rel
        if planted["kind"] == "functional":
            hit = [f for f in functional if _hits(f, repo_path, lines)]
            if hit:
                rep.true_positives.append(planted["id"])
                matched.update(f.id for f in hit)
            else:
                rep.false_negatives.append(planted["id"])
        else:
            if any(_hits(f, repo_path, lines) for f in outcome.security_handoffs):
                rep.security_handoffs_matched.append(planted["id"])
    rep.false_positives = [f.title for f in functional if f.id not in matched]
    return rep
