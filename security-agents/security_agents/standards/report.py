from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import registry

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = PACKAGE_ROOT / "tests" / "standards"

ROWS: list[tuple[str, str, str]] = [
    ("MITRE CWE", "cwe", "weaknesses and categories"),
    ("MITRE ATT&CK Enterprise", "attack_enterprise", "techniques"),
    ("MITRE D3FEND", "d3fend", "techniques"),
    ("OWASP API Security Top 10", "owasp_api", "categories"),
    ("OWASP Top 10 for LLM Applications", "owasp_llm", "risks"),
    ("CVSS v3.1 base score", "cvss31", "metric weights"),
    ("CVSS v3.1 test vectors (NVD)", "cvss31_vectors", "vector and score pairs"),
    ("NIST SP 800-115 rules of engagement", "nist_sp_800_115", "document"),
]

KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("nist_sp_800_115", ("roe", "rules_of_engagement", "800_115", "sp_800")),
    ("cvss31_vectors", ("published_base_score", "official_vectors")),
    ("cvss31", ("cvss", "roundup", "vector", "score", "rating", "impact", "exploitation", "severity", "level")),
    ("attack_enterprise", ("attack",)),
    ("d3fend", ("d3fend",)),
    ("owasp_llm", ("llm",)),
    ("owasp_api", ("owasp",)),
    ("cwe", ("cwe", "mitre", "mapping")),
]


def classify(nodeid: str) -> list[str]:
    lowered = nodeid.lower()
    hits = [name for name, words in KEYWORDS if any(word in lowered for word in words)]
    if "test_reference_data.py" in lowered and not hits:
        return ["integrity"]
    if "test_cvss31.py" in lowered and "cvss31" not in hits and "cvss31_vectors" not in hits:
        hits.append("cvss31")
    if "test_rules_of_engagement.py" in lowered and "nist_sp_800_115" not in hits:
        hits = ["nist_sp_800_115"]
    return hits or ["integrity"]


class Collector:
    def __init__(self) -> None:
        self.results: list[tuple[str, str]] = []

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.results.append((report.nodeid, report.outcome))


def run_tests(extra: list[str]) -> Collector:
    import pytest

    collector = Collector()
    pytest.main(
        [str(TEST_DIR), "-q", "-p", "no:cacheprovider", "--no-header", "-o", "console_output_style=classic", *extra],
        plugins=[collector],
    )
    return collector


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PACKAGE_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def render(collector: Collector) -> tuple[str, int]:
    tallies: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0})
    for nodeid, outcome in collector.results:
        bucket = "failed" if outcome == "failed" else ("skipped" if outcome == "skipped" else "passed")
        for name in classify(nodeid):
            tallies[name][bucket] += 1
    summary = {row["name"]: row for row in registry.summary()}
    unverified = registry.unverified()
    header = ("Standard", "Identifiers pinned", "Source version", "Passed", "Failed", "UNVERIFIED")
    lines: list[tuple[str, ...]] = [header]
    for title, name, unit in ROWS:
        row = summary[name]
        counts = tallies.get(name, {"passed": 0, "failed": 0, "skipped": 0})
        lines.append(
            (
                title,
                f"{row['identifiers']} {unit}",
                str(row["version"]),
                str(counts["passed"]),
                str(counts["failed"]),
                "; ".join(unverified.get(name, [])) or "none",
            )
        )
    integrity = tallies.get("integrity", {"passed": 0, "failed": 0, "skipped": 0})
    lines.append(("Provenance and integrity", "8 pinned files", "PROVENANCE.json", str(integrity["passed"]), str(integrity["failed"]), "none"))
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    out = []
    for index, line in enumerate(lines):
        out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)))
        if index == 0:
            out.append("  ".join("-" * width for width in widths))
    total = len(collector.results)
    failed = sum(1 for _, outcome in collector.results if outcome == "failed")
    skipped = sum(1 for _, outcome in collector.results if outcome == "skipped")
    footer = [
        "",
        f"tests run: {total}   passed: {total - failed - skipped}   failed: {failed}   skipped: {skipped}",
        "a test can count toward more than one standard row; the totals above are unique tests",
        f"git sha: {git_sha()}",
        f"environment: Python {platform.python_version()} on {platform.system()} {platform.machine()}, offline, pinned data",
        f"pinned data retrieved: {registry.provenance()['generated_at']}",
        "UNVERIFIED overall: " + ("none" if not unverified else ", ".join(sorted(unverified))),
        "live Claude checks: not part of this command; nothing here calls a model",
    ]
    return "\n".join(out + footer), failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="security_agents.standards.report")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args(argv)
    collector = run_tests(args.pytest_args)
    table, failed = render(collector)
    print()
    print("STANDARDS ALIGNMENT REPORT (offline)")
    print(table)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
