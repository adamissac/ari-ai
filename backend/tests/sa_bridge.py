"""TEST-ONLY bridge: drive Alan's deterministic role scripts (security_agents FakeLLM)
through the REAL backend LLMGateway via its transport seam. Every response is labeled
provider_mode="fake". Routing is by the role's system prompt; the runtime's
``submit_<role>_output`` tool is renamed to the gateway's ``submit_result``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.llm import ProviderResponse


class AlanScriptTransport:
    mode = "fake"

    def __init__(self, snapshot_root: Path) -> None:
        import sys

        from security_agents.agents import ALL_SPECS
        from security_agents.llm import FakeLLM

        tests_dir = Path(__import__("security_agents").__file__).resolve().parents[1]
        if str(tests_dir) not in sys.path:
            sys.path.insert(0, str(tests_dir))
        from tests import fake_agents

        self.specs = list(ALL_SPECS.values()) if isinstance(ALL_SPECS, dict) else list(ALL_SPECS)
        self.fake = FakeLLM(fake_agents.all_scripts(snapshot_root))
        self.requests: list[dict[str, Any]] = []

    def create(self, request: dict[str, Any]) -> ProviderResponse:
        from security_agents.llm.types import LLMRequest

        self.requests.append(request)
        spec = next(s for s in self.specs if request["system"].startswith(s.system_prompt))
        resp = self.fake.complete(
            LLMRequest(
                agent=spec.name,
                model=request["model"],
                system=request["system"],
                messages=request["messages"],
                tools=request.get("tools", []),
                max_tokens=request["max_tokens"],
            )
        )
        content = [
            {**b, "name": "submit_result"}
            if b.get("type") == "tool_use" and b["name"].startswith("submit_")
            else b
            for b in resp.content
        ]
        return ProviderResponse(
            id=resp.response_id or "msg_fake",
            model=request["model"],
            content=content,
            stop_reason=resp.stop_reason,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )
