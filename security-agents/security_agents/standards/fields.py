from __future__ import annotations

from shared.standards import StandardFramework
from standards.catalog import CatalogEntry
from standards.catalog import cwe as cwe_entry
from standards.mapping import resolve

__all__ = [
    "attack_entry",
    "cwe_entry",
    "d3fend_entry",
    "optional_attack_field",
    "optional_d3fend_field",
]


def attack_entry(identifier: str) -> CatalogEntry:
    return resolve(StandardFramework.attack, identifier)


def d3fend_entry(identifier: str) -> CatalogEntry:
    return resolve(StandardFramework.d3fend, identifier)


def optional_attack_field(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    attack_entry(value)
    return value


def optional_d3fend_field(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    d3fend_entry(value)
    return value
