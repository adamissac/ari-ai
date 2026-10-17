#!/usr/bin/env python3
"""Execute existing owned-target integration and subsystem suites with scripted models."""

import sys

from common import ROOT, pytest, report, run


def main() -> int:
    return report(
        [
            run("Generated contracts", [sys.executable, "-m", "shared.export", "--check"]),
            run("Pinned standards", [sys.executable, "-m", "standards.catalog", "--check"]),
            pytest(
                "Backend / monitoring / reviewer / intelligence",
                "backend/tests",
                "monitoring/tests",
                "code-review/tests",
                "code-intelligence/tests",
            ),
            # Separate process: Alan's tests package and Sai's have colliding module names.
            run(
                "Security agents",
                [sys.executable, "-m", "pytest", "tests", "-q", "-ra"],
                cwd=ROOT / "security-agents",
            ),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
