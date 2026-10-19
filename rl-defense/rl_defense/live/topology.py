"""Load the route->node topology and classify real requests.

Reuses the existing hand-written mapping ``configs/topology/payments_lite.yaml``
(the same artifact ``platform_mapping`` references). Patterns look like
``"<method-glob> <path-glob>"`` (e.g. ``"* /payments*"``).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

import yaml

from rl_defense.envs.config import NODE_NAMES

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "topology"


@dataclass(frozen=True)
class NodeRoutes:
    node: str
    patterns: tuple[str, ...]
    exposed: bool
    criticality_floor: float


class RouteTopology:
    def __init__(self, nodes: list[NodeRoutes], default_node: str) -> None:
        self.nodes = nodes
        self.default_node = default_node
        self._by_name = {n.node: n for n in nodes}
        missing = set(NODE_NAMES) - set(self._by_name)
        if missing:
            raise ValueError(f"topology must cover every simulator node; missing {sorted(missing)}")

    def node_for(self, method: str, path: str) -> str:
        """Classify a request. First matching node in config order wins; else default."""
        target = f"{method.upper()} {path}"
        for n in self.nodes:
            for pat in n.patterns:
                pat_method, _, pat_path = pat.partition(" ")
                method_ok = pat_method == "*" or pat_method.upper() == method.upper()
                if method_ok and fnmatch.fnmatch(path, pat_path.strip()):
                    return n.node
                # also allow matching the combined "METHOD path" form
                if fnmatch.fnmatch(target, pat):
                    return n.node
        return self.default_node

    def node(self, name: str) -> NodeRoutes:
        return self._by_name[name]


def load_topology(path: str | Path | None = None) -> RouteTopology:
    p = Path(path) if path else CONFIG_DIR / "payments_lite.yaml"
    data = yaml.safe_load(p.read_text())
    nodes = [
        NodeRoutes(
            node=n["node"],
            patterns=tuple(n.get("route_patterns", [])),
            exposed=bool(n.get("exposed", False)),
            criticality_floor=float(n.get("criticality_floor", 0.5)),
        )
        for n in data["nodes"]
    ]
    return RouteTopology(nodes, data.get("default_node", "api"))
