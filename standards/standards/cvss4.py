"""CVSS v4.0 scoring: a faithful port of FIRST's reference calculator.

Source: https://github.com/FIRSTdotorg/cvss-v4-calculator at the commit pinned in
``data/MANIFEST.json`` (``cvss_score.js``, ``cvss_lookup.js``, ``max_composed.js``,
``max_severity.js``, ``metrics.js``; BSD-2-Clause, Copyright FIRST, Red Hat, and
contributors). The MacroVector lookup table and the max-vector tables are loaded from
the vendored JSON produced by ``scripts/build_subsets.py``; nothing here is hand-typed
except the per-metric severity levels, which are copied verbatim from ``cvss_score.js``.

The score is a pure function of the vector string. No model output is ever an input to
the numeric score: callers supply metric *values* (each with its own evidence or an
explicit assumption) and this module computes the number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache
from typing import Any

from standards.catalog import load_json

VERSION = "4.0"
PREFIX = "CVSS:4.0"
BASE_METRICS = ("AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA")

_LEVELS: dict[str, dict[str, float]] = {
    "AV": {"N": 0.0, "A": 0.1, "L": 0.2, "P": 0.3},
    "PR": {"N": 0.0, "L": 0.1, "H": 0.2},
    "UI": {"N": 0.0, "P": 0.1, "A": 0.2},
    "AC": {"L": 0.0, "H": 0.1},
    "AT": {"N": 0.0, "P": 0.1},
    "VC": {"H": 0.0, "L": 0.1, "N": 0.2},
    "VI": {"H": 0.0, "L": 0.1, "N": 0.2},
    "VA": {"H": 0.0, "L": 0.1, "N": 0.2},
    "SC": {"H": 0.1, "L": 0.2, "N": 0.3},
    "SI": {"S": 0.0, "H": 0.1, "L": 0.2, "N": 0.3},
    "SA": {"S": 0.0, "H": 0.1, "L": 0.2, "N": 0.3},
    "CR": {"H": 0.0, "M": 0.1, "L": 0.2},
    "IR": {"H": 0.0, "M": 0.1, "L": 0.2},
    "AR": {"H": 0.0, "M": 0.1, "L": 0.2},
}
_DISTANCE_ORDER = ("AV", "PR", "UI", "AC", "AT", "VC", "VI", "VA", "SC", "SI", "SA", "CR", "IR", "AR")


class CVSSVectorError(ValueError):
    """The vector is not a valid CVSS v4.0 vector (unknown metric, bad value, order, missing base)."""


@dataclass(frozen=True)
class CVSSResult:
    vector: str
    score: float
    severity: str
    macrovector: str
    nomenclature: str


@cache
def _tables() -> dict[str, Any]:
    return load_json("cvss-v4.0.json")


def metric_values() -> dict[str, list[str]]:
    return {k: list(v) for k, v in _tables()["metrics"]}


def parse_vector(vector: str) -> dict[str, str]:
    """Validate and parse a vector. Rejects anything the reference calculator would reject.

    Base metrics are mandatory; optional metrics may be omitted (treated as ``X``) but
    must appear in the specification's canonical order, at most once, with a legal value.
    """
    parts = vector.strip().split("/")
    if not parts or parts[0] != PREFIX:
        raise CVSSVectorError(f"vector must start with {PREFIX}")
    expected = metric_values()
    order = list(expected)
    selected: dict[str, str] = {}
    last_index = -1
    for part in parts[1:]:
        if ":" not in part:
            raise CVSSVectorError(f"malformed metric {part!r}")
        key, value = part.split(":", 1)
        if key not in expected:
            raise CVSSVectorError(f"unknown metric {key!r}")
        if key in selected:
            raise CVSSVectorError(f"duplicate metric {key!r}")
        index = order.index(key)
        if index < last_index:
            raise CVSSVectorError(f"metric {key!r} is out of the specification order")
        last_index = index
        if value not in expected[key]:
            raise CVSSVectorError(f"illegal value {value!r} for metric {key!r}")
        selected[key] = value
    missing = [m for m in BASE_METRICS if m not in selected]
    if missing:
        raise CVSSVectorError(f"missing base metrics: {', '.join(missing)}")
    for key, values in expected.items():
        selected.setdefault(key, "X" if "X" in values else values[0])
    return selected


def build_vector(metrics: dict[str, str]) -> str:
    """Render metrics in canonical order, omitting optional metrics left at ``X``."""
    out = [PREFIX]
    for key in metric_values():
        value = metrics.get(key)
        if value is None or (value == "X" and key not in BASE_METRICS):
            continue
        out.append(f"{key}:{value}")
    vector = "/".join(out)
    parse_vector(vector)
    return vector


def _m(sel: dict[str, str], metric: str) -> str:
    """Effective value of a metric (``m()`` in cvss_score.js)."""
    selected = sel.get(metric, "X")
    if metric == "E" and selected == "X":
        return "A"
    if metric in ("CR", "IR", "AR") and selected == "X":
        return "H"
    modified = sel.get("M" + metric)
    if modified is not None and modified != "X":
        return modified
    return selected


def macrovector(sel: dict[str, str]) -> str:
    av, pr, ui = _m(sel, "AV"), _m(sel, "PR"), _m(sel, "UI")
    if av == "N" and pr == "N" and ui == "N":
        eq1 = 0
    elif (av == "N" or pr == "N" or ui == "N") and av != "P":
        eq1 = 1
    else:
        eq1 = 2

    eq2 = 0 if (_m(sel, "AC") == "L" and _m(sel, "AT") == "N") else 1

    vc, vi, va = _m(sel, "VC"), _m(sel, "VI"), _m(sel, "VA")
    if vc == "H" and vi == "H":
        eq3 = 0
    elif vc == "H" or vi == "H" or va == "H":
        eq3 = 1
    else:
        eq3 = 2

    if _m(sel, "MSI") == "S" or _m(sel, "MSA") == "S":
        eq4 = 0
    elif _m(sel, "SC") == "H" or _m(sel, "SI") == "H" or _m(sel, "SA") == "H":
        eq4 = 1
    else:
        eq4 = 2

    eq5 = {"A": 0, "P": 1, "U": 2}[_m(sel, "E")]

    eq6 = (
        0
        if (
            (_m(sel, "CR") == "H" and vc == "H")
            or (_m(sel, "IR") == "H" and vi == "H")
            or (_m(sel, "AR") == "H" and va == "H")
        )
        else 1
    )
    return f"{eq1}{eq2}{eq3}{eq4}{eq5}{eq6}"


def _parse_max(fragment: str) -> dict[str, str]:
    return dict(part.split(":", 1) for part in fragment.strip("/").split("/") if part)


def _round1(value: float) -> float:
    # JavaScript Math.round(x * 10) / 10: round half toward +infinity.
    return math.floor(value * 10 + 0.5) / 10


def _score(sel: dict[str, str], mv: str) -> float:
    if all(_m(sel, k) == "N" for k in ("VC", "VI", "VA", "SC", "SI", "SA")):
        return 0.0
    t = _tables()
    lookup: dict[str, float] = t["lookup"]
    max_composed = t["max_composed"]
    max_severity = t["max_severity"]

    def look(key: str) -> float:
        return float(lookup[key]) if key in lookup else math.nan

    value = float(lookup[mv])
    eq1, eq2, eq3, eq4, eq5, eq6 = (int(c) for c in mv)

    def key(*eqs: int) -> str:
        return "".join(str(e) for e in eqs)

    lower_eq1 = look(key(eq1 + 1, eq2, eq3, eq4, eq5, eq6))
    lower_eq2 = look(key(eq1, eq2 + 1, eq3, eq4, eq5, eq6))
    if eq3 == 1 and eq6 == 1:
        lower_eq3eq6 = look(key(eq1, eq2, eq3 + 1, eq4, eq5, eq6))
    elif eq3 == 0 and eq6 == 1:
        lower_eq3eq6 = look(key(eq1, eq2, eq3 + 1, eq4, eq5, eq6))
    elif eq3 == 1 and eq6 == 0:
        lower_eq3eq6 = look(key(eq1, eq2, eq3, eq4, eq5, eq6 + 1))
    elif eq3 == 0 and eq6 == 0:
        left = look(key(eq1, eq2, eq3, eq4, eq5, eq6 + 1))
        right = look(key(eq1, eq2, eq3 + 1, eq4, eq5, eq6))
        # JS: `left > right ? left : right` (NaN comparisons are false -> right).
        lower_eq3eq6 = left if left > right else right
    else:
        lower_eq3eq6 = look(key(eq1, eq2, eq3 + 1, eq4, eq5, eq6 + 1))
    lower_eq4 = look(key(eq1, eq2, eq3, eq4 + 1, eq5, eq6))
    lower_eq5 = look(key(eq1, eq2, eq3, eq4, eq5 + 1, eq6))

    eq1_maxes = max_composed["eq1"][str(eq1)]
    eq2_maxes = max_composed["eq2"][str(eq2)]
    eq3_eq6_maxes = max_composed["eq3"][str(eq3)][str(eq6)]
    eq4_maxes = max_composed["eq4"][str(eq4)]
    eq5_maxes = max_composed["eq5"][str(eq5)]
    max_vectors = [
        a + b + c + d + e
        for a in eq1_maxes
        for b in eq2_maxes
        for c in eq3_eq6_maxes
        for d in eq4_maxes
        for e in eq5_maxes
    ]

    dist: dict[str, float] = {}
    for max_vector in max_vectors:
        parsed = _parse_max(max_vector)
        dist = {k: _LEVELS[k][_m(sel, k)] - _LEVELS[k][parsed[k]] for k in _DISTANCE_ORDER}
        if any(d < 0 for d in dist.values()):
            continue
        break
    # As in the reference, if no max vector dominates, the last computed distances are used.

    cur_eq1 = dist["AV"] + dist["PR"] + dist["UI"]
    cur_eq2 = dist["AC"] + dist["AT"]
    cur_eq3eq6 = dist["VC"] + dist["VI"] + dist["VA"] + dist["CR"] + dist["IR"] + dist["AR"]
    cur_eq4 = dist["SC"] + dist["SI"] + dist["SA"]

    step = 0.1
    max_eq1 = max_severity["eq1"][str(eq1)] * step
    max_eq2 = max_severity["eq2"][str(eq2)] * step
    max_eq3eq6 = max_severity["eq3eq6"][str(eq3)][str(eq6)] * step
    max_eq4 = max_severity["eq4"][str(eq4)] * step

    n_lower = 0
    normalized = 0.0
    for available, current, depth in (
        (value - lower_eq1, cur_eq1, max_eq1),
        (value - lower_eq2, cur_eq2, max_eq2),
        (value - lower_eq3eq6, cur_eq3eq6, max_eq3eq6),
        (value - lower_eq4, cur_eq4, max_eq4),
    ):
        if not math.isnan(available):
            n_lower += 1
            normalized += available * (current / depth)
    if not math.isnan(value - lower_eq5):
        n_lower += 1  # EQ5 always contributes a proportion of 0

    mean = normalized / n_lower if n_lower else 0.0
    value -= mean
    value = min(10.0, max(0.0, value))
    return _round1(value)


def severity(score: float) -> str:
    """Qualitative severity rating scale (CVSS v4.0 specification, section 6)."""
    if score == 0.0:
        return "none"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    if score < 9.0:
        return "high"
    return "critical"


def nomenclature(sel: dict[str, str]) -> str:
    """CVSS-B / CVSS-BT / CVSS-BE / CVSS-BTE (specification, section 1.3)."""
    threat = sel.get("E", "X") != "X"
    env = any(
        sel.get(k, "X") != "X"
        for k in ("CR", "IR", "AR", "MAV", "MAC", "MAT", "MPR", "MUI", "MVC", "MVI", "MVA", "MSC", "MSI", "MSA")
    )
    return "CVSS-B" + ("T" if threat else "") + ("E" if env else "")


def score(vector: str) -> CVSSResult:
    sel = parse_vector(vector)
    mv = macrovector(sel)
    value = _score(sel, mv)
    return CVSSResult(
        vector=vector.strip(),
        score=value,
        severity=severity(value),
        macrovector=mv,
        nomenclature=nomenclature(sel),
    )
