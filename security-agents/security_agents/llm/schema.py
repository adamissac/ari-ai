"""Provider schema projection; Pydantic remains the argument validator."""
from typing import Any

_NUMERIC_BOUNDS = frozenset({"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"})


def provider_schema(value: Any) -> Any:
    """Copy schema nodes without numeric constraints unsupported by strict tools.

    Property names are data: a property named ``minimum`` must survive.
    """
    if isinstance(value, list):
        return [provider_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    numeric = value.get("type") in ("integer", "number")
    result = {}
    for key, item in value.items():
        if numeric and key in _NUMERIC_BOUNDS:
            continue
        if key in ("properties", "$defs", "definitions", "patternProperties"):
            result[key] = {name: provider_schema(node) for name, node in item.items()}
        else:
            result[key] = provider_schema(item)
    return result
