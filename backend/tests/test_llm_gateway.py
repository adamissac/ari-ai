"""Tier 1: LLM gateway with FakeTransport (deterministic CI; NOT live proof).
Tier 3 (opt-in): one real provider tool-loop smoke when RUN_LIVE_LLM_EVAL=1 and a key exist."""

from __future__ import annotations

import json
import os

import pytest
from pydantic import BaseModel, Field

from backend.llm import FakeTransport, LLMError, Tool, build_gateway, cost_usd
from backend.settings import Settings
from shared.assessment import ToolCallOutcome
from shared.errors import ErrorCode
from shared.tenancy import Usage


class ReadFile(BaseModel):
    path: str = Field(max_length=200)


class Verdict(BaseModel):
    vulnerable: bool
    reason: str = Field(max_length=300)


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, anthropic_api_key=None, **kw)


def _tool_use(name: str, inp: dict, tid: str = "tu_1") -> dict:
    return {
        "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1000, "output_tokens": 200},
    }


def test_missing_key_is_explicit_llm_unavailable() -> None:
    with pytest.raises(LLMError) as e:
        build_gateway(settings=_settings())
    assert e.value.code is ErrorCode.LLM_UNAVAILABLE


def test_tool_loop_executes_allowed_tools_denies_others_and_validates_output() -> None:
    files = {"app/invoices.py": "def get_invoice(id, user): return db.get(id)"}
    charged: list[Usage] = []
    transport = FakeTransport(
        [
            _tool_use("read_file", {"path": "app/invoices.py"}, "tu_1"),
            _tool_use("run_shell", {"cmd": "rm -rf /"}, "tu_2"),  # not in allowlist
            _tool_use("submit_result", {"vulnerable": "maybe"}, "tu_3"),  # schema-invalid
            _tool_use("submit_result", {"vulnerable": True, "reason": "no tenant filter"}, "tu_4"),
        ]
    )
    gw = build_gateway(settings=_settings(), transport=transport, charge=charged.append)
    result = gw.run_tool_loop(
        agent="scout",
        system="You are Scout.",
        user_content="Inspect app/invoices.py",
        tools=[Tool("read_file", "Read a repository file", ReadFile, lambda i: files[i.path])],
        output_model=Verdict,
    )
    assert result.final == Verdict(vulnerable=True, reason="no tenant filter")
    assert result.turns == 4 and result.provider_mode == "fake"
    outcomes = [(r.tool_name, r.outcome, r.error_code) for r in result.tool_calls]
    assert outcomes == [
        ("read_file", ToolCallOutcome.ok, None),
        ("run_shell", ToolCallOutcome.denied, ErrorCode.TOOL_NOT_ALLOWED),
        ("submit_result", ToolCallOutcome.error, ErrorCode.SCHEMA_INVALID),
        ("submit_result", ToolCallOutcome.ok, None),
    ]
    # tool output was fed back to the model on the next turn
    second = transport.requests[1]["messages"]
    assert files["app/invoices.py"] in str(second[-1]["content"])
    assert "TOOL_NOT_ALLOWED" in str(transport.requests[2]["messages"][-1]["content"])
    assert len(charged) == 4 and result.usage.input_tokens == 4000 and result.usage.llm_calls == 4
    assert result.usage.usd == pytest.approx(
        4 * cost_usd("claude-haiku-5-5", {"input_tokens": 1000, "output_tokens": 200})
    )


def test_request_shape_targets_haiku_5_5_and_redacts_secrets() -> None:
    transport = FakeTransport(
        [{"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}]
    )
    gw = build_gateway(
        settings=_settings(agent_model_overrides="fortify=claude-sonnet-5-5"), transport=transport
    )
    gw.create_message(
        agent="scout",
        system="sys",
        messages=[
            {
                "role": "user",
                "content": "config has key sk-ant-api03-SECRETSECRET and ghp_" + "a" * 36,
            }
        ],
    )
    req = transport.requests[0]
    assert req["model"] == "claude-haiku-5-5"
    assert req["thinking"] == {"type": "adaptive"} and req["output_config"]["effort"] == "high"
    assert "SECRETSECRET" not in str(req) and "REDACTED" in str(req)
    assert gw.model_for("fortify") == "claude-sonnet-5-5"


def test_retries_transient_errors_then_gives_up() -> None:
    sleeps: list[float] = []
    ok = {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}
    transport = FakeTransport([LLMError(ErrorCode.LLM_UNAVAILABLE, "429", retryable=True), ok])
    gw = build_gateway(settings=_settings(), transport=transport, sleep=sleeps.append)
    assert gw.create_message(
        agent="probe", system="s", messages=[{"role": "user", "content": "x"}]
    ).content
    assert len(sleeps) == 1
    transport = FakeTransport([LLMError(ErrorCode.LLM_UNAVAILABLE, "500", retryable=True)] * 10)
    gw = build_gateway(
        settings=_settings(llm_max_retries=2), transport=transport, sleep=sleeps.append
    )
    with pytest.raises(LLMError, match="after 3 attempt"):
        gw.create_message(agent="probe", system="s", messages=[{"role": "user", "content": "x"}])
    transport = FakeTransport([LLMError(ErrorCode.LLM_UNAVAILABLE, "401 credential rejected")])
    gw = build_gateway(settings=_settings(), transport=transport, sleep=sleeps.append)
    with pytest.raises(LLMError, match="after 1 attempt"):
        gw.create_message(agent="probe", system="s", messages=[{"role": "user", "content": "x"}])


def test_refusal_and_truncation_are_typed_errors() -> None:
    for stop, code in (
        ("refusal", ErrorCode.LLM_REFUSAL),
        ("max_tokens", ErrorCode.LLM_OUTPUT_TRUNCATED),
    ):
        transport = FakeTransport(
            [{"content": [], "stop_reason": stop, "stop_details": {"category": "cyber"}}]
        )
        gw = build_gateway(settings=_settings(), transport=transport)
        with pytest.raises(LLMError) as e:
            gw.create_message(
                agent="probe", system="s", messages=[{"role": "user", "content": "x"}]
            )
        assert e.value.code is code


def test_budget_gate_runs_before_each_call() -> None:
    calls = {"n": 0}

    def ensure() -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise LLMError(ErrorCode.BUDGET_EXHAUSTED, "budget")

    transport = FakeTransport([_tool_use("read_file", {"path": "a"})] * 3)
    gw = build_gateway(settings=_settings(), transport=transport, ensure_budget=ensure)
    with pytest.raises(LLMError) as e:
        gw.run_tool_loop(
            agent="scout",
            system="s",
            user_content="u",
            tools=[Tool("read_file", "r", ReadFile, lambda i: "x")],
            output_model=Verdict,
        )
    assert e.value.code is ErrorCode.BUDGET_EXHAUSTED and len(transport.requests) == 1


def test_turn_limit_is_enforced() -> None:
    transport = FakeTransport([_tool_use("read_file", {"path": "a"}, f"t{i}") for i in range(3)])
    gw = build_gateway(settings=_settings(), transport=transport)
    with pytest.raises(LLMError, match="no valid result within 3 turns"):
        gw.run_tool_loop(
            agent="scout",
            system="s",
            user_content="u",
            max_turns=3,
            tools=[Tool("read_file", "r", ReadFile, lambda i: "x")],
            output_model=Verdict,
        )
    # Only the final turn asks the model to submit now.
    notes = ["final turn" in json.dumps(r["messages"][-1]) for r in transport.requests]
    assert notes == [False, False, True]


@pytest.mark.live_llm
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_EVAL") != "1"
    or not os.environ.get("HACKATL_LIVE_ANTHROPIC_API_KEY"),
    reason="live provider smoke is opt-in: RUN_LIVE_LLM_EVAL=1 and ANTHROPIC_API_KEY (shell or .env)",
)
def test_live_provider_tool_loop_smoke() -> None:
    """Real Claude call with a real tool round-trip on a tiny owned snippet. Never runs in CI."""
    settings = Settings(
        _env_file=None,
        anthropic_api_key=os.environ["HACKATL_LIVE_ANTHROPIC_API_KEY"],
        anthropic_effort="low",
    )
    gw = build_gateway(settings=settings)
    src = "def get_invoice(invoice_id, user):\n    return INVOICES[invoice_id]  # no owner check\n"
    result = gw.run_tool_loop(
        agent="scout",
        system="You review tiny Python snippets for authorization flaws.",
        user_content="Use read_file on app/invoices.py, then submit whether it lets a user read another user's invoice.",
        tools=[Tool("read_file", "Read a file from the owned demo repo", ReadFile, lambda i: src)],
        output_model=Verdict,
        max_turns=6,
    )
    assert gw.provider_mode == "live"
    assert any(
        r.tool_name == "read_file" and r.outcome is ToolCallOutcome.ok for r in result.tool_calls
    )
    assert result.usage.input_tokens > 0 and result.usage.usd > 0
    print(
        f"LIVE model={result.model} turns={result.turns} usage={result.usage.model_dump()} verdict={result.final}"
    )


class _RecordingMessages:
    def __init__(self, calls: list[tuple[str, dict]], kind: str) -> None:
        self.calls, self.kind = calls, kind

    def create(self, **kw):
        from types import SimpleNamespace

        self.calls.append((self.kind, kw))
        return SimpleNamespace(
            id="msg_1",
            model=kw["model"],
            content=[],
            stop_reason="end_turn",
            stop_details=None,
            usage=SimpleNamespace(model_dump=lambda **_: {"input_tokens": 1, "output_tokens": 1}),
        )


def _live_transport_calls(model: str) -> list[tuple[str, dict]]:
    from types import SimpleNamespace

    from backend.llm import AnthropicTransport

    t = AnthropicTransport(
        Settings(_env_file=None, anthropic_api_key="sk-test", anthropic_model=model)
    )
    calls: list[tuple[str, dict]] = []
    t._client = SimpleNamespace(
        messages=_RecordingMessages(calls, "messages"),
        beta=SimpleNamespace(messages=_RecordingMessages(calls, "beta")),
    )
    try:
        t.create({"model": model, "max_tokens": 10, "messages": []})
    except Exception:  # response parsing is not what this test checks
        pass
    return calls


def test_default_model_is_haiku_5_5_and_live_requests_send_no_fallbacks() -> None:
    assert Settings(_env_file=None).anthropic_model == "claude-haiku-5-5"
    [(kind, kw)] = _live_transport_calls("claude-haiku-5-5")
    assert kind == "messages" and kw["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in str(kw) and "betas" not in kw


def test_server_fallback_is_kept_for_models_that_support_it() -> None:
    [(kind, kw)] = _live_transport_calls("claude-opus-5-5")
    assert kind == "beta" and kw["extra_body"] == {"fallbacks": "default"}


def test_production_uses_only_haiku_despite_stale_environment_overrides():
    settings = _settings(
        app_env="production",
        anthropic_model="claude-opus-5-5",
        agent_model_overrides="scout=claude-sonnet-5-5,patch=claude-opus-5-5",
    )
    transport = FakeTransport(
        [{"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}] * 8
    )
    gw = build_gateway(settings=settings, transport=transport, charge=lambda usage: None)
    for role in ("reviewer", "scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"):
        assert gw.model_for(role) == "claude-haiku-5-5"
