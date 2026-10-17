"""Unit tests for the security pillar foundation (FakeLLM / no network / no Docker)."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from security_agents.contracts import (
    AgentName,
    AuthorizedScope,
    ErrorCode,
    Hypothesis,
    PlatformError,
    ScopeStatus,
    ScopeTarget,
)
from security_agents.llm import FakeLLM, FakeTurn, LLMRequest, ProviderGateway, parse_overrides
from security_agents.redact import REDACTED, redact_text
from security_agents.sandbox.driver import (
    DockerSandboxDriver,
    LocalProcessDriver,
    SandboxProfile,
    SandboxSpec,
)
from security_agents.sandbox.workspace import apply_diff, copy_tree, safe_rel_path, unified_diff
from security_agents.scope_guard import ActionRequest, check

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
PAYMENTS_LITE = Path(__file__).resolve().parents[2] / "examples" / "payments-lite"


def make_scope(**kw) -> AuthorizedScope:
    base = dict(
        id="scp_1", project_id="prj_1", name="payments-lite lab",
        targets=[ScopeTarget(target_id="tgt_payments", repo_id="rep_1", build_recipe_ref="build_recipe.json")],
        allowed_check_categories=["access_control.ownership"],
        status=ScopeStatus.ACTIVE, requested_by="usr_a", approved_by="usr_b",