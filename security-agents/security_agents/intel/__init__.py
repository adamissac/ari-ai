"""Code-intelligence consumer port and local adapter (pending INTEL-007)."""

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
    "hypothesis_key",
    "new_snapshot_id",
]
