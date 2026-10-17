"""Code-intelligence consumer port and local adapter (pending INTEL-007)."""

from .code_intelligence_adapter import CodeIntelligenceAdapter
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
    "CodeIntelligenceAdapter",
    "FindingsHistory",
    "LocalIntel",
    "Span",
    "SymbolInfo",
    "answer_key",
    "hypothesis_key",
    "load_expectations",
    "new_snapshot_id",
]
