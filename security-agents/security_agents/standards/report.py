from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parent
for extra in ("shared", "standards", "code-intelligence"):
    candidate = str(REPO_ROOT / extra)
    if candidate not in sys.path:
        sys.path.append(candidate)

from standards.catalog import load_json, manifest, verify_all  # noqa: E402

TEST_DIRS = (REPO_ROOT / "standards" / "tests", PACKAGE_ROOT / "tests" / "standards")

ROWS: list[tuple[str, str, str, str, str]] = [
    ("MITRE CWE", "cwe", "cwe.json", "entries", "weaknesses and categories"),
    ("MITRE ATT&CK Enterprise", "attack", "attack-enterprise.json", "techniques", "techniques"),
    ("MITRE D3FEND", "d3fend", "d3fend.json", "techniques", "techniques"),
    ("OWASP API Security Top 10", "owasp_api", "owasp-api-2023.json", "categories", "categories"),
    ("OWASP Top 10 for LLM Applications", "owasp_llm", "owasp-llm-2026.json", "risks", "risks"),
    ("CVSS v3.1 base score", "cvss31", "cvss-v3.1.json", "weights", "metric weight tables"),
    ("CVSS v3.1 test vectors (NVD)", "cvss31_vectors", "cvss-v3.1-nvd-vectors.json", "vectors", "vectors"),
    ("CVSS v4.0 base score (alongside)", "cvss40", "cvss-v4.0.json", "lookup", "macrovector entries"),
    (
        "NIST SP 800-115 rules of engagement",
        "sp800115",
        "nist-sp800-115.json",
        "roe_template_sections",
        "RoE sections",
    ),
    ("OASIS SARIF 2.1.0 export", "sarif", "sarif-2.1.0.json", "schema.definitions", "schema definitions"),
]

FILE_DEFAULTS: dict[str, str] = {
    "test_cvss31.py": "cvss31",
    "test_cvss4.py": "cvss40",
    "test_cvss.py": "cvss40",
    "test_cvss_assess.py": "cvss40",
    "test_rules_of_engagement.py": "sp800115",
    "test_incident.py": "integrity",
    "test_sarif.py": "sarif",
}

KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("sarif", ("sarif",)),
    ("sp800115", ("roe", "rules_of_engagement", "800_115", "sp800115", "probe_without")),
    ("cvss31_vectors", ("nvd", "published")),
    ("cvss31", ("cvss31", "cvss_v3", "v31", "roundup", "severity", "score")),
    ("attack", ("attack",)),
    ("d3fend", ("d3fend",)),
    ("owasp_llm", ("llm",)),
    ("owasp_api", ("owasp", "api_2023")),
    ("cwe", ("cwe",)),
]


def classify(nodeid: str) -> list[str]:
    lowered = nodeid.lower()
    filename = lowered.split("::", 1)[0].rsplit("/", 1)[-1]
    hits = [name for name, words in KEYWORDS if any(word in lowered for word in words)]
    default = FILE_DEFAULTS.get(filename)
    if default == "sp800115":
        return ["sp800115"]
    if default and default not in hits and not (default == "cvss31" and "cvss31_vectors" in hits):
        hits.append(default)
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
        [
            *(str(path) for path in TEST_DIRS),
            "-q",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "--rootdir",
            str(PACKAGE_ROOT),
            "-o",
            "console_output_style=classic",
            *extra,
        ],
        plugins=[collector],
    )
    return collector


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PACKAGE_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def unverified_items() -> dict[str, list[str]]:
    items: dict[str, list[str]] = defaultdict(list)
    files = manifest()["files"]
    for _title, key, name, _count, _unit in ROWS:
        license_text = str(files.get(name, {}).get("license", ""))
        if license_text.startswith("UNVERIFIED"):
            items[key].append("license terms: " + license_text.split(":", 1)[1].strip()[:80])
    return dict(items)


def render(collector: Collector) -> tuple[str, int]:
    tallies: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0})
    for nodeid, outcome in collector.results:
        bucket = "failed" if outcome == "failed" else ("skipped" if outcome == "skipped" else "passed")
        for name in classify(nodeid):
            tallies[name][bucket] += 1
    files = manifest()["files"]
    unverified = unverified_items()
    header = ("Standard", "Identifiers pinned", "Source version", "Passed", "Failed", "UNVERIFIED")
    lines: list[tuple[str, ...]] = [header]
    for title, key, name, count_key, unit in ROWS:
        data = load_json(name)
        value: Any = data
        for part in count_key.split("."):
            value = value.get(part, []) if isinstance(value, dict) else []
        count = len(value) if isinstance(value, (list, dict)) else value
        counts = tallies.get(key, {"passed": 0, "failed": 0, "skipped": 0})
        lines.append(
            (
                title,
                f"{count} {unit}",
                str(files[name].get("version") or data.get("version", "")),
                str(counts["passed"]),
                str(counts["failed"]),
                "; ".join(unverified.get(key, [])) or "none",
            )
        )
    integrity = tallies.get("integrity", {"passed": 0, "failed": 0, "skipped": 0})
    checked = verify_all()
    lines.append(
        (
            "Manifest sha256 and integrity",
            f"{len(checked)} pinned files",
            "MANIFEST.json",
            str(integrity["passed"]),
            str(integrity["failed"]),
            "none",
        )
    )
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
        "UNVERIFIED overall: " + ("none" if not unverified else ", ".join(sorted(unverified))),
        "labels: mapped to / aligned with; no certification is claimed; CVSS is base score only (severity, not risk)",
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
    return 1 if failed or not collector.results else 0


if __name__ == "__main__":
    sys.exit(main())
