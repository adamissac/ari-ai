"""The independent reviewer evaluation corpus (code-review/eval/cases) and its scorer.

Every answer key is proven by executing its evaluator-only oracle on base and head, so
the corpus labels are evidence. The scorer is checked on fixed predictions; real
precision/recall needs a live run (test_live_corpus.py, opt-in, costs money).
"""

from __future__ import annotations

import shutil
import subprocess
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from code_review import eval_corpus as ec
from code_review.evaluation import _symbol_lines
from shared.evidence import EvidenceKind
from shared.findings import FindingKind, FindingStatus

CASES = ec.load_cases()
BY_ID = {c.id: c for c in CASES}


def test_corpus_covers_every_category_with_at_least_two_cases() -> None:
    counts = Counter(c.category for c in CASES)
    assert set(counts) == set(ec.CATEGORIES)
    assert min(counts.values()) >= 2, counts


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_answer_key_is_proven_by_executing_the_oracle(case: ec.Case) -> None:
    chk = ec.check_label(case)
    assert chk.ok, chk


@pytest.mark.parametrize("case", [c for c in CASES if c.defect], ids=lambda c: c.id)
def test_defect_root_cause_symbol_exists_in_the_head_tree(case: ec.Case) -> None:
    assert case.root_cause_path and case.root_cause_symbol
    assert _symbol_lines(ec.materialize_file(case, case.root_cause_path), case.root_cause_symbol)


def test_reviewer_repo_has_two_commits_and_never_the_oracle_or_key(tmp_path: Path) -> None:
    case = BY_ID["badpatch_refund_bound"]
    repo, base, head = ec.build_repo(case, tmp_path / "repo")
    files = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    assert not any("oracle" in f or f.endswith("case.yaml") for f in files), files
    changed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", base, head],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert changed == ["payments/refunds.py"]


def test_a_broken_oracle_is_an_error_not_proof_of_a_defect(tmp_path: Path) -> None:
    src = BY_ID["defect_tax_rounding"]
    root = tmp_path / "broken"
    shutil.copytree(src.root, root)
    (root / "oracle" / "oracle_check.py").write_text(
        "def test_typo():\n    assert sales_taxx() == 1\n"  # NameError, not a behavioral failure
    )
    (case,) = ec.load_cases(tmp_path)
    chk = ec.check_label(case)
    assert chk.oracle_on_head == "error"
    assert not chk.ok and "expected failed" in chk.problems[0]


# ------------------------------------------------------------------ scoring


def _perfect() -> dict[str, ec.Prediction]:
    return {c.id: ec.Prediction(c.id, flagged=c.defect, located=c.defect) for c in CASES}


def test_perfect_predictions_score_one_everywhere() -> None:
    rep = ec.score_corpus(CASES, _perfect(), "scripted")
    assert (rep.precision, rep.recall, rep.specificity) == (1.0, 1.0, 1.0)
    assert rep.to_json()["label"].startswith("harness check only")


def test_flagging_everything_is_punished_by_precision_and_specificity() -> None:
    preds = {c.id: ec.Prediction(c.id, flagged=True, located=c.defect) for c in CASES}
    rep = ec.score_corpus(CASES, preds, "live")
    n_clean = sum(not c.defect for c in CASES)
    n_defect = len(CASES) - n_clean
    assert rep.recall == 1.0 and rep.specificity == 0.0
    assert rep.precision == round(n_defect / len(CASES), 3)
    assert rep.to_json()["label"] == "model-quality signal"


def test_a_flag_in_the_wrong_place_is_a_miss_and_failed_runs_never_help() -> None:
    preds = _perfect()
    preds["defect_tax_rounding"] = ec.Prediction("defect_tax_rounding", flagged=True, located=False)
    del preds["clean_slugify"]  # the run for this case failed
    del preds["sec_export_path"]
    rep = ec.score_corpus(CASES, preds, "live")
    assert "defect_tax_rounding" in rep.fn and rep.mislocated == ["defect_tax_rounding"]
    assert "sec_export_path" in rep.fn
    assert "clean_slugify" in rep.fp
    assert rep.by_category["security_regression"] == {"tp": 1, "fp": 0, "tn": 0, "fn": 1}


def _outcome(findings: list[Any], handoffs: list[Any] | None = None) -> Any:
    return SimpleNamespace(
        result=SimpleNamespace(findings=findings), security_handoffs=handoffs or []
    )


def _finding(path: str, lo: int, hi: int, *, kind: FindingKind = FindingKind.functional) -> Any:
    span = SimpleNamespace(start_line=lo, end_line=hi)
    ev = SimpleNamespace(kind=EvidenceKind.source_span, path=path, span=span)
    return SimpleNamespace(kind=kind, status=FindingStatus.validated, evidence=[ev])


def test_predict_locates_findings_and_hand_offs_against_the_root_cause() -> None:
    tax = BY_ID["defect_tax_rounding"]
    lines = _symbol_lines(ec.materialize_file(tax, "tax/calc.py"), "sales_tax")
    assert lines
    hit = ec.predict(cast(Any, _outcome([_finding("tax/calc.py", *lines)])), tax)
    assert hit.flagged and hit.located
    miss = ec.predict(cast(Any, _outcome([_finding("tax/calc.py", 1, 2)])), tax)
    assert miss.flagged and not miss.located

    owner = BY_ID["sec_missing_owner_check"]
    lines = _symbol_lines(ec.materialize_file(owner, "billing/invoices.py"), "get_invoice")
    assert lines
    handoff = _finding("billing/invoices.py", *lines, kind=FindingKind.security)
    assert ec.predict(cast(Any, _outcome([], [handoff])), owner).located

    clean = BY_ID["clean_slugify"]
    assert not ec.predict(cast(Any, _outcome([])), clean).flagged
