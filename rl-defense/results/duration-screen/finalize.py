"""Verify saved duration results with the frozen implementation; never execute a policy."""

import argparse
import gzip
import importlib.util
import json
from dataclasses import asdict
from pathlib import Path
from types import ModuleType


def loader(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "duration_frozen_loader", root / "frozen_loader.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_summary(root: Path) -> ModuleType:
    root = root.resolve()
    code = loader(root)
    index = json.loads((root / "EVIDENCE.json").read_text())
    for name, expected in index["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or code.digest(path) != expected:
            raise ValueError(f"screen artifact changed: {name}")
    if "historical_index" in index:
        historical = index["historical_index"]
        previous = json.loads((root / historical["path"]).read_text())
        for name, expected in previous["files"].items():
            path = (root / historical["replacements"].get(name, name)).resolve()
            if not path.is_relative_to(root) or code.digest(path) != expected:
                raise ValueError(f"historical artifact changed: {name}")
    module = code.load(root)
    rows = {
        split: {
            name: json.loads((root / split / name / "episodes.json").read_text())
            for name in module.POLICIES
        }
        for split in ("train", "val")
    }
    recomputed = module.decide(rows["val"])
    recomputed["training"] = {
        name: module.summarize([module.EpisodeMetrics(**r) for r in values])
        for name, values in rows["train"].items()
    }
    recomputed["training_by_scenario"] = {
        name: module.summarize_by_scenario([module.EpisodeMetrics(**r) for r in values])
        for name, values in rows["train"].items()
    }
    if json.loads(json.dumps(recomputed)) != json.loads((root / "summary.json").read_text()):
        raise ValueError("saved training/validation summary does not reproduce")
    return module


def verify(root: Path) -> dict:
    module = verify_summary(root)
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
                    transitions = [
                        module.LiveTransition.model_validate(t) for t in row["transitions"]
                    ]
                    if (
                        len(transitions) != 30
                        or asdict(module.episode_metrics(*key, transitions)) != expected[key]
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
        code = loader(root)
        index["files"] = {
            str(p.relative_to(root)): code.digest(p)
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
