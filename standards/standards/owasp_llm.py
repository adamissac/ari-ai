"""OWASP Top 10 for LLM Applications (2025) coverage matrix for this platform.

    uv run python -m standards.owasp_llm --check       # structural validation (offline)
    uv run python -m standards.owasp_llm --run-tests   # execute every listed test, report per risk
    uv run python -m standards.owasp_llm --render      # write docs/security/OWASP_LLM_TOP10_COVERAGE.md

The matrix is data (``data/owasp-llm-coverage.json``). Validation refuses a matrix that:
misses or duplicates a risk id, uses an id not in the pinned OWASP list, claims
``implemented_tested`` without a listed test, names a control file/symbol or a test that
does not exist in the repository, or claims customer-application assessment support
without a listed test.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from standards.catalog import load_json, owasp_llm, owasp_llm_ids

STATUSES = ("implemented_tested", "partial", "gap", "not_applicable")
CUSTOMER_STATUSES = ("supported_tested", "partial", "unsupported")
DOC_PATH = Path("docs/security/OWASP_LLM_TOP10_COVERAGE.md")


@dataclass(frozen=True)
class MatrixProblem:
    risk: str
    problem: str


def matrix() -> dict[str, Any]:
    return dict(load_json("owasp-llm-coverage.json"))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _symbol_defined(path: Path, symbol: str) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = rf"^\s*(def|class|async def)\s+{re.escape(symbol)}\b|^\s*{re.escape(symbol)}\s*[:=]"
    return re.search(pattern, text, flags=re.MULTILINE) is not None


def validate(root: Path | None = None) -> list[MatrixProblem]:
    root = root or repo_root()
    data = matrix()
    problems: list[MatrixProblem] = []
    seen: list[str] = [row["risk"] for row in data["rows"]]
    for missing in sorted(set(owasp_llm_ids()) - set(seen)):
        problems.append(MatrixProblem(missing, "risk missing from the matrix"))
    for dup in sorted({r for r in seen if seen.count(r) > 1}):
        problems.append(MatrixProblem(dup, "risk listed more than once"))
    for row in data["rows"]:
        risk = row["risk"]
        try:
            owasp_llm(risk)
        except KeyError:
            problems.append(MatrixProblem(risk, "not an OWASP LLM Top 10 2025 identifier"))
            continue
        if row["status"] not in STATUSES:
            problems.append(MatrixProblem(risk, f"unknown status {row['status']!r}"))
        if row["status"] == "implemented_tested" and not row["tests"]:
            problems.append(MatrixProblem(risk, "implemented_tested requires at least one test"))
        if row["status"] in ("implemented_tested", "partial") and not row["controls"]:
            problems.append(MatrixProblem(risk, f"{row['status']} requires at least one control"))
        if not row.get("limitations"):
            problems.append(MatrixProblem(risk, "limitations must be stated"))
        cust = row["customer_assessment"]
        if cust["status"] not in CUSTOMER_STATUSES:
            problems.append(MatrixProblem(risk, f"unknown customer status {cust['status']!r}"))
        if cust["status"] != "unsupported" and not cust.get("tests"):
            problems.append(
                MatrixProblem(risk, "customer assessment support requires a listed test")
            )
        for control in row["controls"]:
            file_part, _, symbol = control["location"].partition("::")
            path = root / file_part
            if not path.exists():
                problems.append(MatrixProblem(risk, f"control file {file_part} does not exist"))
            elif symbol and not _symbol_defined(path, symbol):
                problems.append(MatrixProblem(risk, f"{symbol} is not defined in {file_part}"))
        for test in [*row["tests"], *cust.get("tests", [])]:
            file_part, _, name = test.partition("::")
            path = root / file_part
            if not path.exists():
                problems.append(MatrixProblem(risk, f"test file {file_part} does not exist"))
            elif not re.search(
                rf"^def {re.escape(name)}\b", path.read_text(encoding="utf-8"), re.MULTILINE
            ):
                problems.append(MatrixProblem(risk, f"test {name} not found in {file_part}"))
    return problems


def run_tests(root: Path | None = None) -> dict[str, tuple[int, str]]:
    """Run each risk's listed tests in its package directory; returns risk -> (exit code, tail)."""
    root = root or repo_root()
    results: dict[str, tuple[int, str]] = {}
    for row in matrix()["rows"]:
        if not row["tests"]:
            continue
        by_pkg: dict[str, list[str]] = {}
        for test in row["tests"]:
            pkg = test.split("/", 1)[0]
            by_pkg.setdefault(pkg, []).append(test.split("/", 1)[1])
        code, tail = 0, []
        for pkg, nodes in by_pkg.items():
            proc = subprocess.run(
                ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *nodes],
                cwd=root / pkg,
                capture_output=True,
                text=True,
            )
            code = code or proc.returncode
            tail.append(
                f"{pkg}: {proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-200:]}"
            )
        results[row["risk"]] = (code, "; ".join(tail))
    return results


def render() -> str:
    data = matrix()
    lines = [
        "# OWASP Top 10 for LLM Applications (2025): platform coverage matrix",
        "",
        "> Generated by `uv run python -m standards.owasp_llm --render` from",
        "> `standards/standards/data/owasp-llm-coverage.json`. Do not edit by hand.",
        "",
        f"Matrix version {data['matrix_version']}, assessed {data['assessed_at']}, against the",
        "[OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)",
        "(pinned in `standards/standards/data/owasp-llm.json`). A newer OWASP GenAI LLM Top 10 2026",
        "release exists and is not yet assessed.",
        "",
        "**What this is not.** This is a self-assessment of this platform's own agents, retrieval,",
        "tools, models and data flows. A status names tests that exercise a control; it does not",
        "mean the risk is prevented or detected, and it is not a certification or compliance",
        "statement. The platform currently has **no** check templates that assess these risks in",
        "a customer's application (every customer column says `unsupported`).",
        "",
        "Status: `implemented_tested` = control present and the listed tests exercise it;",
        "`partial` = some attack surfaces controlled; `gap` = no control;",
        "`not_applicable` = attack surface absent today.",
        "",
        "| Risk | Platform status | Customer-app assessment |",
        "|---|---|---|",
    ]
    for row in data["rows"]:
        name = owasp_llm(row["risk"]).name
        lines.append(
            f"| {row['risk']} {name} | `{row['status']}` | `{row['customer_assessment']['status']}` |"
        )
    for row in data["rows"]:
        name = owasp_llm(row["risk"]).name
        lines += ["", f"## {row['risk']} {name}", "", f"**Status:** `{row['status']}`", ""]
        if row["attack_surfaces"]:
            lines.append("**Attack surfaces:** " + "; ".join(row["attack_surfaces"]) + ".")
            lines.append("")
        if row["controls"]:
            lines.append("**Controls (owner):**")
            lines.append("")
            lines += [f"- {c['name']}: `{c['location']}` ({c['owner']})" for c in row["controls"]]
            lines.append("")
        if row["tests"]:
            lines.append("**Executable tests:**")
            lines.append("")
            lines += [f"- `{t}`" for t in row["tests"]]
            lines.append("")
        lines.append(f"**Limitations:** {row['limitations']}")
        lines.append("")
        cust = row["customer_assessment"]
        lines.append(f"**Customer-application assessment:** `{cust['status']}`. {cust['note']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--run-tests", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args(argv)
    rc = 0
    if args.check or not (args.run_tests or args.render):
        problems = validate()
        for prob in problems:
            print(f"{prob.risk}: {prob.problem}", file=sys.stderr)
        rc = 1 if problems else 0
        print(f"matrix: {len(problems)} problems")
    if args.render:
        out = repo_root() / DOC_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(), encoding="utf-8")
        print("wrote", DOC_PATH)
    if args.run_tests:
        for risk, (code, tail) in run_tests().items():
            print(f"{risk}: {'PASS' if code == 0 else 'FAIL'} ({tail})")
            rc = rc or code
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
