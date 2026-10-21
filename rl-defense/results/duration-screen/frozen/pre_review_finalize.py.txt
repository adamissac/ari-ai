"""Verify saved duration evidence and raw traces; never run an environment or policy."""

import argparse
import gzip
import importlib.util
import json
from dataclasses import asdict
from pathlib import Path

from rl_defense.checkpoint import sha256_file
from rl_defense.live.contracts import LiveTransition
from rl_defense.live.evaluate import episode_metrics


def verify(root: Path) -> dict:
    spec = importlib.util.spec_from_file_location("fixed_duration_screen", root / "run_screen.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_bundle(root)
    count = windows = 0
    for split, budget in (("train", 56), ("val", 48)):
        for policy in module.POLICIES:
            directory = root / split / policy
            rows = json.loads((directory / "episodes.json").read_text())
            expected = {(r["scenario"], r["seed"]): r for r in rows}
            if len(rows) != budget or len(expected) != budget:
                raise ValueError("missing or duplicate fixed-budget episode records")
            seen = set()
            with gzip.open(directory / "trajectories.jsonl.gz", "rt") as stream:
                for line in stream:
                    row = json.loads(line)
                    key = row["scenario"], row["seed"]
                    if row["policy"] != policy or key in seen or key not in expected:
                        raise ValueError("unexpected or duplicate saved trajectory")
                    seen.add(key)
                    transitions = [LiveTransition.model_validate(t) for t in row["transitions"]]
                    if (
                        len(transitions) != 30
                        or asdict(episode_metrics(*key, transitions)) != expected[key]
                    ):
                        raise ValueError("saved trajectory does not reproduce episode metrics")
                    count += 1
                    windows += len(transitions)
            if seen != expected.keys():
                raise ValueError("missing complete raw trajectories")
    return {"episodes": count, "windows": windows, "promotion_performed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = verify(root)
    if args.refresh_index:
        path = root / "EVIDENCE.json"
        index = json.loads(path.read_text())
        # Existing pinned bytes were verified first; add post-run reporting artifacts.
        index["files"] = {
            str(p.relative_to(root)): sha256_file(p)
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.name not in {"EVIDENCE.json", "EVIDENCE.partial"}
        }
        index["verified_counts"] = result
        temporary = path.with_suffix(".partial")
        temporary.write_text(json.dumps(index, indent=2))
        temporary.replace(path)
        verify(root)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
