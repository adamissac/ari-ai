"""The seven specialist tasks: what each model reads, predicts, and is compared against.

Each task names its input fields, label space, architecture/training configuration, and the
deterministic baselines it must beat on the held-out test split. If a model does not beat the
strongest baseline on its primary metric, ``evaluate`` marks it ``promoted: false`` and the agent
integration keeps using the baseline (see ``specialists.runtime``).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .config import TrainConfig
from .data.corpus import SAFE
from .data.datasets import PROBE_CWE_TO_STRATEGY, TACTICS

Row = dict[str, Any]
Baseline = Callable[[list[Row]], Callable[[Row], Any]]  # fit(train) -> predict(row)


@dataclass(frozen=True)
class Task:
    agent: str
    model_id: str
    description: str
    fields: list[str]
    multilabel: bool
    config: TrainConfig
    primary_metric: str
    baselines: dict[str, Baseline] = field(default_factory=dict)
    char_ngrams: bool = True
    top_k: int = 3


# ------------------------------------------------------------------ baselines

# The platform's current static.analyze patterns (security_agents/tools/catalog.py), unchanged.
STATIC_ANALYZE_PATTERNS: list[tuple[str, str]] = [
    (r"\beval\(|\bexec\(", "CWE-95"),
    (r"subprocess\.|os\.system\(", "CWE-78"),
    (r"verify\s*=\s*False", "CWE-295"),
    (r"f\"\s*(SELECT|INSERT|UPDATE|DELETE)\b|%\s*\(.*\)s\"", "CWE-89"),
    (r"\bdebug\s*=\s*True", "CWE-489"),
    (r"allow_origins\s*=\s*\[\s*[\"']\*", "CWE-942"),
]


def static_analyze_baseline(_train: list[Row]) -> Callable[[Row], Any]:
    def predict(row: Row) -> str:
        for line in row["code"].splitlines():
            for pattern, cwe in STATIC_ANALYZE_PATTERNS:
                if re.search(pattern, line):
                    return cwe
        return SAFE

    return predict


def majority_baseline(train: list[Row]) -> Callable[[Row], Any]:
    top = Counter(r["label"] for r in train).most_common(1)[0][0]
    return lambda _row: top


def by_cwe_baseline(train: list[Row]) -> Callable[[Row], Any]:
    """Most frequent training label for the row's CWE (a lookup table), majority otherwise."""
    table: dict[str, Counter] = defaultdict(Counter)
    for r in train:
        table[r.get("cwe", "")][r["label"]] += 1
    top = Counter(r["label"] for r in train).most_common(1)[0][0]
    return lambda row: (
        table[row.get("cwe", "")].most_common(1)[0][0] if table.get(row.get("cwe", "")) else top
    )


def probe_lookup_baseline(train: list[Row]) -> Callable[[Row], Any]:
    """The obvious rule: map the hypothesis CWE to its WSTG test; majority when CWE is missing."""
    top = Counter(r["label"] for r in train).most_common(1)[0][0]
    return lambda row: PROBE_CWE_TO_STRATEGY.get(row.get("cwe", ""), top)


def prior_topk_baseline(k: int) -> Baseline:
    def fit(train: list[Row]) -> Callable[[Row], Any]:
        top = [
            label for label, _ in Counter(lab for r in train for lab in r["label"]).most_common(k)
        ]
        return lambda _row: top

    return fit


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2}


def knn_name_baseline(k: int, neighbours: int = 5) -> Baseline:
    """Traditional nearest-neighbour: label votes of the training rows whose names share most words."""

    def fit(train: list[Row]) -> Callable[[Row], Any]:
        indexed = [(_words(r["name"] + " " + r.get("tactics", "")), r["label"]) for r in train]
        prior = [
            label for label, _ in Counter(lab for r in train for lab in r["label"]).most_common(k)
        ]

        def predict(row: Row) -> list[str]:
            q = _words(row["name"] + " " + row.get("tactics", ""))
            scored = sorted(indexed, key=lambda item: -len(q & item[0]) / (len(q | item[0]) or 1))[
                :neighbours
            ]
            votes = Counter(lab for words, labels in scored if q & words for lab in labels)
            ranked = [label for label, _ in votes.most_common(k)]
            return (ranked + [p for p in prior if p not in ranked])[:k]

        return predict

    return fit


def tactic_frequency_baseline(k: int) -> Baseline:
    """Fortify: most frequent D3FEND labels among training techniques that share a tactic."""

    def fit(train: list[Row]) -> Callable[[Row], Any]:
        by_tactic: dict[str, Counter] = defaultdict(Counter)
        for r in train:
            for t in r["tactics"].split():
                by_tactic[t].update(r["label"])
        prior = Counter(lab for r in train for lab in r["label"])

        def predict(row: Row) -> list[str]:
            c: Counter = Counter()
            for t in row["tactics"].split():
                c.update(by_tactic.get(t, {}))
            return [label for label, _ in (c or prior).most_common(k)]

        return predict

    return fit


_TEST_DELETED = re.compile(r"^-\s*(assert|expect\()", re.M)
_TEST_SKIPPED = re.compile(r"^\+.*(pytest\.mark\.skip|\.skip\(|xit\()", re.M)


def verify_rules_baseline(_train: list[Row]) -> Callable[[Row], Any]:
    """Hand-written diff heuristics a reviewer might script."""

    def predict(row: Row) -> str:
        diff, tests = row["diff"], row["tests"]
        if _TEST_DELETED.search(diff) or _TEST_SKIPPED.search(diff):
            return "test_weakened"
        changed = [
            line[1:].strip()
            for line in diff.splitlines()
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        if all(not c or c.startswith(("#", "//")) for c in changed):
            return "no_security_change"
        if "failed before the patch" in tests:
            return "adequate"
        return "incomplete_fix"

    return predict


# ------------------------------------------------------------------ the seven tasks

TASKS: dict[str, Task] = {
    "scout": Task(
        agent="scout",
        model_id="ari-scout-vulnclass",
        description="Classify a code span as one of 12 CWE weakness classes, other-vulnerable, or safe; the safe-probability ranks suspicious paths.",
        fields=["code"],
        multilabel=False,
        primary_metric="macro_f1",
        config=TrainConfig(input_dim=16384, hidden=96, epochs=40, lr=2e-3, dropout=0.25),
        baselines={
            "static_analyze_patterns": static_analyze_baseline,
            "majority": majority_baseline,
        },
    ),
    "probe": Task(
        agent="probe",
        model_id="ari-probe-strategy",
        description="Rank OWASP WSTG validation strategies for a hypothesis (text + a possibly wrong CWE).",
        fields=["hypothesis", "cwe"],
        multilabel=False,
        primary_metric="accuracy",
        config=TrainConfig(input_dim=8192, hidden=48, epochs=60, lr=3e-3, dropout=0.2),
        baselines={"cwe_lookup": probe_lookup_baseline, "majority": majority_baseline},
    ),
    "trace": Task(
        agent="trace",
        model_id="ari-trace-tactics",
        description="Predict the MITRE ATT&CK tactics an attacker reaches through a weakness (via CAPEC), from the CWE name.",
        fields=["name"],
        multilabel=True,
        primary_metric="f1_at_k",
        config=TrainConfig(
            input_dim=4096,
            hidden=0,
            epochs=200,
            lr=1e-2,
            weight_decay=1e-4,
            dropout=0.0,
            batch_size=16,
            patience=20,
        ),
        baselines={"prior_top3": prior_topk_baseline(3), "knn_name": knn_name_baseline(3)},
        top_k=3,
    ),
    "diagnose": Task(
        agent="diagnose",
        model_id="ari-diagnose-rootcause",
        description="Classify the root cause (CauseClass) from the vulnerable span, CWE and the executed validation's observation.",
        fields=["code", "cwe", "evidence"],
        multilabel=False,
        primary_metric="macro_f1",
        config=TrainConfig(input_dim=16384, hidden=64, epochs=40, lr=2e-3, dropout=0.25),
        baselines={"cwe_lookup": by_cwe_baseline, "majority": majority_baseline},
    ),
    "patch": Task(
        agent="patch",
        model_id="ari-patch-strategy",
        description="Choose the minimal remediation strategy for a confirmed weakness from the vulnerable span and CWE.",
        fields=["code", "cwe"],
        multilabel=False,
        primary_metric="macro_f1",
        config=TrainConfig(input_dim=16384, hidden=64, epochs=40, lr=2e-3, dropout=0.25),
        baselines={"cwe_lookup": by_cwe_baseline, "majority": majority_baseline},
    ),
    "fortify": Task(
        agent="fortify",
        model_id="ari-fortify-d3fend",
        description="Rank MITRE D3FEND countermeasures for an ATT&CK technique an attack path reaches.",
        fields=["name", "tactics"],
        multilabel=True,
        primary_metric="f1_at_k",
        config=TrainConfig(
            input_dim=4096,
            hidden=0,
            epochs=200,
            lr=1e-2,
            weight_decay=1e-4,
            dropout=0.0,
            batch_size=16,
            patience=20,
        ),
        baselines={
            "tactic_frequency": tactic_frequency_baseline(5),
            "knn_name": knn_name_baseline(5),
        },
        top_k=5,
    ),
    "verify": Task(
        agent="verify",
        model_id="ari-verify-evidence",
        description="Flag whether a patch's diff and executed test evidence look adequate, incomplete, test-weakening or cosmetic. Advisory only.",
        fields=["diff", "tests"],
        multilabel=False,
        primary_metric="macro_f1",
        config=TrainConfig(input_dim=16384, hidden=64, epochs=40, lr=2e-3, dropout=0.25),
        baselines={"diff_rules": verify_rules_baseline, "majority": majority_baseline},
    ),
}

TACTIC_LABELS = TACTICS
