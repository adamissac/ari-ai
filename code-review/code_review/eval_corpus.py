"""Independent evaluation corpus for the reviewer: clean changes, functional defects,
security regressions and bad patches, each with an answer key and an evaluator-only oracle.

Layout (``code-review/eval/cases/<case_id>/``):

* ``base/``   files of the base commit;
* ``head/``   files the change adds or replaces (overlaid on ``base/``);
* ``case.yaml``  PR title/body the reviewer sees, plus the answer key (``expected``);
* ``oracle/oracle_check.py``  a behavioral test that proves the label. The reviewer never
  sees it or the answer key; only this module reads them, before or after a review.

``check_labels`` executes every oracle so the answer key is evidence, not assertion.
``score_corpus`` turns per-case predictions into precision / recall / specificity. Numbers
from scripted (fake-provider) runs measure the harness only and are labeled so.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from code_review.evaluation import _hits, _symbol_lines
from code_review.models import ReviewOutcome
from shared.findings import FindingKind, FindingStatus

CASES_DIR = Path(__file__).resolve().parents[1] / "eval" / "cases"
CATEGORIES = ("clean", "functional_defect", "security_regression", "bad_patch")


@dataclass(frozen=True)
class Case:
    id: str
    root: Path
    category: str
    title: str
    body: str
    defect: bool
    kind: str | None = None
    root_cause_path: str | None = None
    root_cause_symbol: str | None = None

    @property
    def oracle(self) -> Path:
        return self.root / "oracle" / "oracle_check.py"


def load_cases(root: Path = CASES_DIR) -> list[Case]:
    cases = []
    for d in sorted(p for p in root.iterdir() if (p / "case.yaml").is_file()):
        meta: dict[str, Any] = yaml.safe_load((d / "case.yaml").read_text())  # type: ignore[no-untyped-call]
        exp = meta["expected"]
        rc = exp.get("root_cause") or {}
        if meta["category"] not in CATEGORIES:
            raise ValueError(f"{d.name}: unknown category {meta['category']!r}")
        cases.append(
            Case(
                id=d.name,
                root=d,
                category=meta["category"],
                title=meta["title"],
                body=meta["body"],
                defect=bool(exp["defect"]),
                kind=exp.get("kind"),
                root_cause_path=rc.get("path"),
                root_cause_symbol=rc.get("symbol"),
            )
        )
    return cases


def _copy(src: Path, dst: Path) -> None:
    for f in src.rglob("*"):
        if f.is_file():
            target = dst / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)


def materialize(case: Case, dst: Path, *, head: bool) -> Path:
    """Write the base tree (and the head overlay when ``head``) to ``dst``. No oracle, no key."""
    dst.mkdir(parents=True, exist_ok=True)
    _copy(case.root / "base", dst)
    if head:
        _copy(case.root / "head", dst)
    return dst


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "eval-corpus",
    "GIT_AUTHOR_EMAIL": "eval@example.test",
    "GIT_COMMITTER_NAME": "eval-corpus",
    "GIT_COMMITTER_EMAIL": "eval@example.test",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
}


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, env=_GIT_ENV, check=True
    )
    return out.stdout.strip()


def build_repo(case: Case, dst: Path) -> tuple[Path, str, str]:
    """A throwaway git repo with the base commit and the head commit; returns (repo, base, head)."""
    materialize(case, dst, head=False)
    _git(dst, "init", "-q", "-b", "main")
    _git(dst, "add", "-A")
    _git(dst, "commit", "-q", "-m", "base")
    base = _git(dst, "rev-parse", "HEAD")
    _copy(case.root / "head", dst)
    _git(dst, "add", "-A")
    _git(dst, "commit", "-q", "-m", case.title)
    return dst, base, _git(dst, "rev-parse", "HEAD")


_PLUGIN_DIR = Path(__file__).resolve().parent  # holds _pytest_report.py (the reviewer's own plugin)
_BEHAVIORAL = {"AssertionError", "Failed"}  # Failed: pytest.fail / pytest.raises that did not raise


def _pytest(tree: Path, *targets: str) -> str:
    """Run pytest on ``targets`` against ``tree``: 'passed', 'failed' or 'error'.

    'failed' means every failing test failed behaviorally (AssertionError, or a
    ``pytest.raises`` that did not raise), using the same report plugin as the reviewer's
    sandbox. Anything else (NameError, ImportError, collection errors) is 'error', so a
    broken oracle can never pass as proof of a defect.
    """
    with tempfile.TemporaryDirectory(prefix="eval-report-") as out:
        report = Path(out) / "report.json"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.pathsep.join([str(tree), str(_PLUGIN_DIR)]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "CR_REPORT_PATH": str(report),
        }
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                "_pytest_report",
                "--rootdir",
                str(tree),
                *targets,
            ],
            cwd=tree,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        cases = json.loads(report.read_text())["cases"] if report.is_file() else []
    if proc.returncode == 0:
        return "passed"
    failing = [c for c in cases if c["outcome"] in ("failed", "error")]
    if (
        proc.returncode == 1
        and failing
        and all(c["outcome"] == "failed" and c["exc_type"] in _BEHAVIORAL for c in failing)
    ):
        return "failed"
    return "error"


@dataclass
class LabelCheck:
    case_id: str
    category: str
    existing_tests_on_head: str
    oracle_on_head: str
    oracle_on_base: str
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check_label(case: Case) -> LabelCheck:
    """Execute the oracle on base and head and confirm the answer key is true.

    * every case: the project's own tests pass on head (the defect is not already caught);
    * clean: the oracle passes on head;
    * functional_defect / security_regression: the oracle fails on head; a security
      regression must also pass on base (the change removed the protection);
    * bad_patch: the head differs from base, and the oracle fails on both (the claimed
      fix did not fix it).
    """
    with tempfile.TemporaryDirectory(prefix=f"eval-{case.id}-") as tmp:
        base = materialize(case, Path(tmp) / "base", head=False)
        head = materialize(case, Path(tmp) / "head", head=True)
        oracle_dir = Path(tmp) / "oracle"
        oracle_dir.mkdir()
        oracle = shutil.copy(case.oracle, oracle_dir / "oracle_check.py")
        chk = LabelCheck(
            case_id=case.id,
            category=case.category,
            existing_tests_on_head=_pytest(head, "tests"),
            oracle_on_head=_pytest(head, str(oracle)),
            oracle_on_base=_pytest(base, str(oracle)),
        )
    if chk.existing_tests_on_head != "passed":
        chk.problems.append(f"project tests on head: {chk.existing_tests_on_head}")
    want_head = "passed" if case.category == "clean" else "failed"
    if chk.oracle_on_head != want_head:
        chk.problems.append(f"oracle on head: {chk.oracle_on_head}, expected {want_head}")
    if case.category == "security_regression" and chk.oracle_on_base != "passed":
        chk.problems.append(f"oracle on base: {chk.oracle_on_base}, expected passed (regression)")
    if case.category == "bad_patch" and chk.oracle_on_base != "failed":
        chk.problems.append(
            f"oracle on base: {chk.oracle_on_base}, expected failed (pre-existing bug)"
        )
    if case.defect != (case.category != "clean"):
        chk.problems.append("expected.defect disagrees with the category")
    if case.defect and not (case.root_cause_path and case.root_cause_symbol):
        chk.problems.append("defect case without a root_cause path and symbol")
    return chk


def check_labels(cases: Iterable[Case] | None = None) -> list[LabelCheck]:
    return [check_label(c) for c in (load_cases() if cases is None else cases)]


# ------------------------------------------------------------------ scoring


@dataclass(frozen=True)
class Prediction:
    case_id: str
    flagged: bool  # any validated functional finding or security hand-off
    located: bool  # one of them cites the labeled root-cause symbol


def predict(outcome: ReviewOutcome, case: Case) -> Prediction:
    """What the reviewer said about one case, located against the answer key."""
    validated = [
        f
        for f in outcome.result.findings
        if f.kind is FindingKind.functional and f.status is FindingStatus.validated
    ]
    candidates = [*validated, *outcome.security_handoffs]
    located = False
    if case.defect and case.root_cause_path and case.root_cause_symbol:
        source = materialize_file(case, case.root_cause_path)
        lines = _symbol_lines(source, case.root_cause_symbol)
        located = lines is not None and any(
            _hits(f, case.root_cause_path, lines) for f in candidates
        )
    return Prediction(case.id, flagged=bool(candidates), located=located)


def materialize_file(case: Case, rel: str) -> str:
    head = case.root / "head" / rel
    return (head if head.is_file() else case.root / "base" / rel).read_text()


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


@dataclass
class CorpusReport:
    provider_mode: str
    tp: list[str] = field(default_factory=list)
    fp: list[str] = field(default_factory=list)
    tn: list[str] = field(default_factory=list)
    fn: list[str] = field(default_factory=list)
    mislocated: list[str] = field(default_factory=list)
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def precision(self) -> float | None:
        return _ratio(len(self.tp), len(self.tp) + len(self.fp))

    @property
    def recall(self) -> float | None:
        return _ratio(len(self.tp), len(self.tp) + len(self.fn))

    @property
    def specificity(self) -> float | None:
        return _ratio(len(self.tn), len(self.tn) + len(self.fp))

    def to_json(self) -> dict[str, Any]:
        return {
            "provider_mode": self.provider_mode,
            "label": "model-quality signal"
            if self.provider_mode == "live"
            else "harness check only (scripted provider; not a model-quality metric)",
            "precision": self.precision,
            "recall": self.recall,
            "specificity": self.specificity,
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "mislocated": self.mislocated,
            "by_category": self.by_category,
        }


def score_corpus(
    cases: Iterable[Case], predictions: Mapping[str, Prediction], provider_mode: str
) -> CorpusReport:
    """Confusion matrix over the corpus.

    A defect case is a true positive only when a finding cites the labeled root cause; a
    flag elsewhere is a false negative recorded as ``mislocated``. Any flag on a clean case
    is a false positive. A case with no prediction (the run failed) is scored against the
    reviewer, FN for a defect case and FP for a clean one, so failures never improve the score.
    """
    rep = CorpusReport(provider_mode=provider_mode)
    for case in cases:
        p = predictions.get(case.id)
        row = rep.by_category.setdefault(case.category, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
        if case.defect:
            if p is not None and p.located:
                rep.tp.append(case.id)
                row["tp"] += 1
            else:
                rep.fn.append(case.id)
                row["fn"] += 1
                if p is not None and p.flagged:
                    rep.mislocated.append(case.id)
        elif p is not None and not p.flagged:
            rep.tn.append(case.id)
            row["tn"] += 1
        else:
            rep.fp.append(case.id)
            row["fp"] += 1
    return rep


def main() -> int:  # pragma: no cover - thin CLI over check_labels
    checks = check_labels()
    for c in checks:
        status = "ok" if c.ok else "BAD: " + "; ".join(c.problems)
        print(
            f"{c.case_id:28} {c.category:20} tests={c.existing_tests_on_head:6} "
            f"oracle head={c.oracle_on_head:6} base={c.oracle_on_base:6} {status}"
        )
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
