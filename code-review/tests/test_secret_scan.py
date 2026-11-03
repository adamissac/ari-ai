"""Committed credentials are reported deterministically, without the model."""

from __future__ import annotations

from pathlib import Path

from cr_fakes import InMemoryHost, call, fake, make_request
from cr_scenarios import Scenario, _commit, _init, _write

from code_review.agent import ReviewerAgentRunner
from code_review.ports import RepoSource
from code_review.secrets import scan_added_secrets
from shared.findings import FindingKind, FindingStatus

AWS_ID = (
    "AKIA" + "IOSFODNN7EXAMPLE"
)  # AWS's documented example key, split so scanners skip this file
AWS_SECRET = "/".join(["wJalrXUtnFEMI", "K7MDENG", "bPxRfiCYEXAMPLEKEY"])  # documented example

CONFIG = f'''import os

DATABASE_URL = os.environ["DATABASE_URL"]
AWS_ACCESS_KEY_ID = "{AWS_ID}"
AWS_SECRET_ACCESS_KEY = "{AWS_SECRET}"
'''


def test_scan_reports_added_lines_only_with_new_line_numbers() -> None:
    diff = (
        "diff --git a/app/config.py b/app/config.py\n"
        "--- a/app/config.py\n"
        "+++ b/app/config.py\n"
        "@@ -1,3 +1,4 @@\n"
        " import os\n"
        f'-OLD_KEY = "{AWS_ID}"\n'
        "+API_KEY = os.environ['API_KEY']\n"
        f'+AWS_ACCESS_KEY_ID = "{AWS_ID}"\n'
        " \n"
    )
    hits = scan_added_secrets(diff)
    assert [(h.path, h.line, h.kind) for h in hits] == [("app/config.py", 3, "aws_access_key_id")]


def test_environment_lookups_and_placeholders_are_not_secrets() -> None:
    diff = (
        "+++ b/settings.py\n@@ -0,0 +1,3 @@\n"
        "+aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']\n"
        "+token = 'changeme'\n"
        "+KEY = 'AKIA_NOT_A_REAL_KEY'\n"
    )
    assert scan_added_secrets(diff) == []


def test_review_hands_off_a_committed_credential_without_the_model(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _write(repo, {"app/__init__.py": "", "app/config.py": "import os\n"})
    base = _commit(repo, "base")
    _write(repo, {"app/config.py": CONFIG})
    head = _commit(repo, "feat: archive statements to S3")
    sc = Scenario(repo, base, head, "feat: archive statements to S3", "")
    # The model reports nothing: the finding must come from the scan.
    host = InMemoryHost(fake([call("submit_result", summary="config change only")]))
    outcome = ReviewerAgentRunner(host, RepoSource(repo)).review(make_request(host, sc))
    [finding] = outcome.security_handoffs
    assert finding.kind is FindingKind.security and finding.status is FindingStatus.hypothesis
    assert finding.title.startswith("[CWE-798]") and "app/config.py" in finding.title
    assert finding.standards is not None and finding.standards.cwe.id == "CWE-798"
    assert sorted(e.span.start_line for e in finding.evidence) == [4, 5]
    assert finding in outcome.result.findings
    rendered = finding.model_dump_json()
    assert AWS_ID not in rendered and AWS_SECRET not in rendered
