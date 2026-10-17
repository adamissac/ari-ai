"""Tier 3 (OPT-IN, costs money): the reviewer with the REAL Anthropic provider.

Runs only with ``RUN_LIVE_LLM_EVAL=1`` and a key in the shell or the repo-root ``.env``
(never committed). Hard USD cap per phase (``CODE_REVIEW_LIVE_MAX_USD``, default 1.00).
The reviewer sees only ``examples/payments-lite/target``; the answer key is read by the
evaluator afterwards. Pass criteria (from labels.yaml, requested by Adam):

* a ``validated`` functional finding on ``create_refund`` (exp_refund_bound) whose
  generated test FAILS on the unpatched target;
* the repair is accepted only if the fresh replay passes and no protected test changed.

Prints turns, tool calls, token usage and USD so the run can be reported honestly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cr_fakes import InMemoryHost, make_request
from cr_scenarios import PAYMENTS_LITE, payments_lite

from backend.llm import AnthropicTransport
from backend.settings import Settings
from code_review.agent import ReviewerAgentRunner
from code_review.api import load_test_sources
from code_review.evaluation import score
from code_review.ports import RepoSource
from code_review.workspace import tree_digest
from shared.findings import FindingKind, FindingStatus


def _key() -> str:
    key = os.environ.get("HACKATL_LIVE_ANTHROPIC_API_KEY") or os.environ.get(
        "ANTHROPIC_API_KEY", ""
    )
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "ANTHROPIC_API_KEY":
                key = value.split("#", 1)[0].strip().strip("\"'")
    return "" if key in ("", "replace-me") else key


pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_EVAL") != "1" or not _key(),
        reason="live reviewer eval is opt-in: RUN_LIVE_LLM_EVAL=1 and ANTHROPIC_API_KEY (shell or .env)",
    ),
]


def test_live_reviewer_finds_and_repairs_refund_bound(tmp_path: Path) -> None:
    cap = float(os.environ.get("CODE_REVIEW_LIVE_MAX_USD", "1.00"))
    settings = Settings(_env_file=None, anthropic_api_key=_key())  # type: ignore[call-arg]
    transport = AnthropicTransport(settings)
    sc = payments_lite(tmp_path)
    source = RepoSource(sc.repo, subdir="target")
    before = tree_digest(source)
    host = InMemoryHost(transport, max_usd=cap)

    outcome = ReviewerAgentRunner(host, source).review(make_request(host, sc))
    run = host.runs[outcome.result.agent_run_id]
    report = score(outcome, PAYMENTS_LITE.parent / "labels.yaml").to_json()
    print(
        "LIVE review",
        json.dumps(
            {
                "model": outcome.model,
                "provider_mode": outcome.provider_mode,
                "turns": outcome.turns,
                "tools": [t.tool_name for t in run.tool_calls],
                "usage": host.usage.model_dump(),
                "eval": report,
                "rejected": outcome.rejected,
            },
            indent=2,
        ),
    )
    assert outcome.provider_mode == "live"
    assert {"write_test", "run_tests"} <= {t.tool_name for t in run.tool_calls}
    assert "fnd_planted_refund_bound" in report["tp"], report
    finding = next(
        f
        for f in outcome.result.findings
        if f.kind is FindingKind.functional and f.status is FindingStatus.validated
    )

    host.usage = host.usage.model_copy(update={"usd": 0.0})  # separate cap for the repair phase
    rep = ReviewerAgentRunner(host, source).repair(
        finding, host.approve(finding.id), load_test_sources(host, finding)
    )
    print(
        "LIVE repair",
        json.dumps(
            {
                "accepted_locally": rep.accepted_locally,
                "reasons": rep.reasons,
                "turns": rep.turns,
                "usage": host.usage.model_dump(),
                "diff": rep.diff_text[:4000],
            },
            indent=2,
        ),
    )
    assert rep.accepted_locally and rep.patch is not None, rep.reasons
    assert all(not p.startswith("target/tests/") for p in rep.patch.files_changed)
    assert tree_digest(source) == before
