"""In-memory data store seeded with synthetic fixture data. Reset per app instance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Workspace:
    id: str
    name: str


@dataclass
class Item:
    id: str
    workspace_id: str
    sku: str
    quantity: int
    description: str


@dataclass
class Transfer:
    id: str
    item_id: str
    workspace_id: str
    quantity: int
    destination: str


@dataclass
class Store:
    workspaces: dict[str, Workspace] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    transfers: dict[str, Transfer] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)  # bearer token -> workspace id
    _counter: int = 0

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:04d}"

    def transfers_for(self, item_id: str) -> list[Transfer]:
        return [t for t in self.transfers.values() if t.item_id == item_id]


def seeded_store() -> Store:
    """Two synthetic workspaces with obviously fake tokens (fixture data, not secrets)."""
    s = Store()
    s.workspaces = {
        "wsp_alice": Workspace("wsp_alice", "Alice Warehouse"),
        "wsp_bob": Workspace("wsp_bob", "Bob Warehouse"),
    }
    s.tokens = {"fixture-token-alice": "wsp_alice", "fixture-token-bob": "wsp_bob"}
    s.items = {
        "item_a1": Item("item_a1", "wsp_alice", "SKU-100", 40, "Copper fittings"),
        "item_a2": Item("item_a2", "wsp_alice", "SKU-101", 12, "Pressure valves"),
        "item_b1": Item("item_b1", "wsp_bob", "SKU-200", 7, "Bearing kits"),
    }
    return s
