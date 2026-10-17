#!/usr/bin/env python3
"""Execute the actual simulation suite; never install packages or act on infrastructure."""

import importlib.util

from common import Result, pytest, report


def main() -> int:
    if any(importlib.util.find_spec(name) is None for name in ("rl_defense", "torch", "gymnasium")):
        return report(
            [
                Result(
                    "RL simulation",
                    "SKIP",
                    "Install the optional RL environment described in rl-defense/README.md",
                )
            ]
        )
    return report([pytest("RL simulation", "rl-defense/tests")])


if __name__ == "__main__":
    raise SystemExit(main())
