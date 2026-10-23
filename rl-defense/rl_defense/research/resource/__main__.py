"""Fixed four-window unit receipt only. No training, study or holdout command."""

from __future__ import annotations

import argparse
from pathlib import Path

from rl_defense.research.resource.preparation import write_unit_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new output directory; refuses existing output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    print(write_unit_bundle(root, args.output))


if __name__ == "__main__":
    main()
