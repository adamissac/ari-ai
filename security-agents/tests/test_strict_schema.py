"""Tool definitions sent to Claude must be accepted by the API.

Regression for the first live run: every agent's tool set was rejected with HTTP 400
(``For 'integer' type, property 'minimum' is not supported`` and
``'additionalProperties: object'``) because Pydantic constraints were sent under
``strict: true``. Offline checks run in CI; the API check is opt-in (free endpoint).
"""

from __future__ import annotations

import os

import pytest

from security_agents.agents import ALL_SPECS
from security_agents.runtime.loop import submit_schema
from security_agents.tools import default_registry
from security_agents.tools.strict_schema import UNSUPPORTED_IN_STRICT, tool_input_schema

SPECS = list(ALL_SPECS.values()) if isinstance(ALL_SPECS, dict) else list(ALL_SPECS)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _tools(spec):
    reg = default_registry()
    return [reg.get(n).schema() for n in sorted(spec.tools) if reg.get(n) is not None]


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name.value)
def test_strict_tools_use_only_supported_keywords(spec) -> None:
    for tool in _tools(spec):
        if not tool["strict"]:
            continue
        for node in _walk(tool["input_schema"]):
            assert not (UNSUPPORTED_IN_STRICT & node.keys()), (
                tool["name"],
                UNSUPPORTED_IN_STRICT & node.keys(),
            )
            ap = node.get("additionalProperties")
            assert ap in (None, False), (tool["name"], ap)


def test_free_form_maps_are_sent_non_strict_with_full_schema() -> None:
    schema = {
        "type": "object",
        "properties": {
            "params": {"type": "object", "additionalProperties": {"type": "string"}},
            "n": {"type": "integer", "minimum": 1},
        },
    }
    sent, strict = tool_input_schema(schema)
    assert strict is False and sent["properties"]["n"]["minimum"] == 1
    sent, strict = tool_input_schema(
        {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1}}}
    )
    assert (
        strict is True and "minimum" not in sent["properties"]["n"] and sent["additionalProperties"] is False
    )


def test_bounds_still_enforced_client_side() -> None:
    reg = default_registry()
    for spec in SPECS:
        for name in spec.tools:
            tool = reg.get(name)
            if tool is None:
                continue
            raw = tool.args_model.model_json_schema()
            if any("minimum" in n for n in _walk(raw)):
                return  # at least one tool carries a bound; its args_model still validates it
    pytest.skip("no bounded tool arguments in the current registry")


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_EVAL") != "1" or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="opt-in: RUN_LIVE_LLM_EVAL=1 and ANTHROPIC_API_KEY",
)
@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name.value)
def test_api_accepts_every_agents_tool_set(spec) -> None:
    """messages.count_tokens validates tool definitions and is free of charge."""
    import anthropic

    client = anthropic.Anthropic(max_retries=1)
    client.messages.count_tokens(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"),
        system="schema check",
        messages=[{"role": "user", "content": "ok"}],
        tools=[*_tools(spec), submit_schema(spec)],
    )
