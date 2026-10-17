"""Tier 3 (OPT-IN, costs money): reviewer precision / recall on the independent corpus.

Runs only with ``RUN_LIVE_LLM_EVAL=1`` and a key (same rules as test_live_reviewer.py).
One review per case in code-review/eval/cases; the reviewer sees only the case repository
and PR text, and the evaluator scores it afterwards. Caps: ``CODE_REVIEW_LIVE_MAX_USD``
per case (default 1.00) and ``CODE_REVIEW_CORPUS_MAX_USD`` overall (default 6.00); the run
stops before a case that could exceed the overall cap. Writes the report JSON to
``CODE_REVIEW_CORPUS_REPORT`` (default ``code-review-corpus-report.json`` in the cwd).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from cr_fakes import InMemoryHost, make_request
from cr_scenarios import Scenario
from test_live_reviewer import _key

from backend.llm import AnthropicTransport
from backend.settings import Settings
from code_review import eval_corpus as ec
from code_review.agent import ReviewerAgentRunner
from code_review.ports import RepoSource

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_EVAL") != "1" or not _key(),
        reason="live corpus eval is opt-in: RUN_LIVE_LLM_EVAL=1 and ANTHROPIC_API_KEY (shell or .env)",
    ),
]


def test_live_reviewer_on_the_independent_corpus(tmp_path: Path) -> None:
    per_case = float(os.environ.get("CODE_REVIEW_LIVE_MAX_USD", "1.00"))
    overall = float(os.environ.get("CODE_REVIEW_CORPUS_MAX_USD", "6.00"))
    transport = AnthropicTransport(Settings(_env_file=None, anthropic_api_key=_key()))  # type: ignore[call-arg]
    cases = ec.load_cases()
    predictions: dict[str, ec.Prediction] = {}
    spent, rows = 0.0, []
    for case in cases:
        if spent + per_case > overall:
            rows.append({"case": case.id, "skipped": "overall cap"})
            continue
        repo, base, head = ec.build_repo(case, tmp_path / case.id)
        sc = Scenario(repo=repo, base_sha=base, head_sha=head, title=case.title, body=case.body)
        host = InMemoryHost(transport, max_usd=per_case)
        try:
            outcome = ReviewerAgentRunner(host, RepoSource(repo)).review(make_request(host, sc))
        except Exception as exc:  # a failed run is scored against the reviewer
            rows.append({"case": case.id, "error": f"{type(exc).__name__}: {exc}"[:300]})
        else:
            assert outcome.provider_mode == "live"
            predictions[case.id] = ec.predict(outcome, case)
            rows.append({"case": case.id, "turns": outcome.turns, **predictions[case.id].__dict__})
        spent += host.usage.usd

    report = {
        **ec.score_corpus(cases, predictions, "live").to_json(),
        "usd": round(spent, 4),
        "rows": rows,
    }
    out = Path(os.environ.get("CODE_REVIEW_CORPUS_REPORT", "code-review-corpus-report.json"))
    out.write_text(json.dumps(report, indent=2))
    print("LIVE corpus", json.dumps(report, indent=2))
    assert predictions, "no case produced a review"
