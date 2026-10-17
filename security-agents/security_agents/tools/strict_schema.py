"""Make tool input schemas acceptable to the Anthropic API's strict tool use.

Strict tool schemas reject numeric constraints (``minimum``/``maximum``/``multipleOf``
and the exclusive forms), string length constraints, complex array constraints, and any
``additionalProperties`` other than ``false``. Pydantic emits all of these. Verified
against the live API (``messages.count_tokens``): every agent's tool set was rejected
before this module existed.

* Constraints are removed from the schema SENT to the model only. The registry still
  validates every tool input with the Pydantic ``args_model``, so bounds are enforced.
* A schema containing a free-form map (``additionalProperties`` is a schema) cannot be
  expressed in strict mode without forbidding every key, so such a tool is sent
  non-strict with its full schema instead.
"""

from __future__ import annotations

import copy
from typing import Any

UNSUPPORTED_IN_STRICT = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "minItems", "maxItems", "uniqueItems", "minProperties", "maxProperties",
})


def _has_free_form_map(node: Any) -> bool:
    if isinstance(node, dict):
        ap = node.get("additionalProperties")
        if ap is not None and ap is not False:
            return True
        return any(_has_free_form_map(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_free_form_map(v) for v in node)
    return False


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        out = {k: _strip(v) for k, v in node.items() if k not in UNSUPPORTED_IN_STRICT}
        if out.get("type") == "object" or "properties" in out:
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


def tool_input_schema(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return ``(schema_to_send, strict)`` for a Pydantic-generated input schema."""
    if _has_free_form_map(schema):
        return copy.deepcopy(schema), False
    return _strip(schema), True
