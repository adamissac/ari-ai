"""Load only the hash-pinned historical metric/schema slice, with its recorded dependencies."""

import ast
import hashlib
import importlib.util
import json
import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fragments(path: Path) -> dict[str, str]:
    text = path.read_text()
    result = {}
    for node in ast.parse(text).body:
        name = getattr(node, "name", None)
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
        if name is None:
            continue
        result[name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    return result


def load(root: Path) -> ModuleType:
    frozen = root / "frozen"
    metadata = json.loads((frozen / "FROZEN.json").read_text())
    if metadata["source_commit"] != json.loads((root / "RUN.json").read_text())["git_sha"]:
        raise ValueError("frozen evaluator source disagrees with recorded run")
    if list(sys.version_info[:2]) != metadata["python_minor"]:
        raise ValueError("historical verification requires the recorded Python minor version")
    module_path = frozen / "evaluation.py"
    if digest(module_path) != metadata["module_sha256"]:
        raise ValueError("frozen evaluation implementation changed")
    definitions = fragments(module_path)
    for source in metadata["sources"]:
        path = frozen / source["snapshot"]
        if digest(path) != source["sha256"]:
            raise ValueError("historical source snapshot changed")
        original = fragments(path)
        for name, expected in source["definitions"].items():
            if original[name] != expected or definitions[name] != expected:
                raise ValueError(f"frozen definition differs from historical source: {name}")
    run = json.loads((root / "RUN.json").read_text())
    for package, expected in metadata["packages"].items():
        if expected != run["packages"][package] or version(package) != expected:
            raise ValueError(
                f"historical verification needs {package}=={expected}; use frozen/requirements.txt"
            )
    name = "_duration_historical_evaluation"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
