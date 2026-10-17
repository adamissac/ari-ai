"""Code-intelligence consumer port and local adapter (pending INTEL-007)."""

from .labels import answer_key, load_expectations
from .port import (
    CodeIntel,
    FindingsHistory,
    LocalIntel,
    Span,
    SymbolInfo,
    hypothesis_key,
    new_snapshot_id,
)

__all__ = [
    "CodeIntel",
    "FindingsHistory",
    "LocalIntel",
    "Span",
    "SymbolInfo",
    "answer_key",
    "hypothesis_key",
    "load_expectations",
    "new_snapshot_id",
]
