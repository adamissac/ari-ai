"""Static source inventory only. Does not import or run agents/providers."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROLES = ("scout", "probe", "trace", "diagnose", "patch", "verify", "fortify")


def inventory(root: Path) -> dict[str, Any]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    roles = {}
    for role in ROLES:
        path = root / f"security-agents/security_agents/agents/{role}.py"
        blob = path.read_bytes()
        tree = ast.parse(blob)
        specs = [
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SPEC" for t in node.targets)
        ]
        if len(specs) != 1 or not isinstance(specs[0], ast.Call):
            raise ValueError("exactly one declarative AgentSpec required")
        fields = {k.arg: ast.unparse(k.value) for k in specs[0].keywords if k.arg is not None}
        schemas = {
            n.name: [
                k.target.id
                for k in n.body
                if isinstance(k, ast.AnnAssign) and isinstance(k.target, ast.Name)
            ]
            for n in tree.body
            if isinstance(n, ast.ClassDef)
            and n.name in (fields["input_model"], fields["output_model"])
        }
        original = subprocess.check_output(
            ["git", "show", f"{commit}:{path.relative_to(root)}"], cwd=root
        )
        if original != blob:
            raise ValueError("uncommitted producer source")
        roles[role] = {
            "path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "declarative_spec": fields,
            "schema_field_names": schemas,
        }
    return {
        "schema": "first-responder-source-inventory/0.1",
        "source_commit": commit,
        "purpose": "read_only_static_audit_not_execution",
        "roles": roles,
        "grok_contract": "not_supplied_or_agreed",
        "training_authorized": False,
        "provider_calls": 0,
        "agent_invocations": 0,
    }


if __name__ == "__main__":
    output = Path(sys.argv[1])
    data = inventory(Path(__file__).resolve().parents[2])
    with output.open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")
