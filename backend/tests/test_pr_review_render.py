"""The PR review explains findings only from persisted records and anchors inline
comments only to lines the pull request changed."""

from __future__ import annotations

from backend.pr_review import commentable_ranges, inline_comments, render_body

PATCH = (
    "@@ -75,5 +75,5 @@ def get_account(\n"
    "     ) -> AccountOut:\n"
    "         account = store.accounts.get(account_id)\n"
    "-        if account is None or account.customer_id != customer.id:\n"
    "+        if account is None:\n"
    '             raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")\n'
    "         return AccountOut(\n"
)
CONFIRMED = {
    "id": "fnd_confirmed",
    "title": "GET /accounts/{account_id} returns any account",
    "status": "diagnosed",
    "severity": {"level": "medium"},
    "standards": {"cwe": {"id": "CWE-639"}},
    "evidence": [{"path": "ledgerlite/app.py", "span": {"start_line": 71, "end_line": 82}}],
}
SUSPICION = {
    "id": "fnd_suspicion",
    "title": "Transfers are not atomic",
    "status": "inconclusive",
    "severity": {"level": "high"},
    "evidence": [{"path": "ledgerlite/store.py", "span": {"start_line": 39}}],
}
RECORDS = {
    "fnd_confirmed": {
        "root_cause": {"summary": "get_account never compares the owner."},
        "remediation_plan": {"strategy": "Return 404 when the caller is not the owner."},
        "validation_result": {
            "evidence": [{"kind": "sandbox_run", "symbol": "access_control.ownership@1"}]
        },
    },
    "fnd_suspicion": {"hypothesis": {"rationale": "Check-then-act on the balance."}},
}


def test_body_explains_confirmed_findings_first_with_their_executed_check():
    body, count = render_body(
        "asm_1", "prj_1", [SUSPICION, CONFIRMED], 1, "https://ari.test", RECORDS
    )
    assert count == 2
    assert "1 confirmed by an executed check, 1 not confirmed." in body
    assert body.index("GET /accounts/{account_id}") < body.index("Transfers are not atomic")
    assert "Confirmed by an executed check (`access_control.ownership@1`)" in body
    assert "CWE-639" in body and "`ledgerlite/app.py:71`" in body
    assert "get_account never compares the owner." in body
    assert "Return 404 when the caller is not the owner." in body
    # An unconfirmed finding never borrows the confirmed wording.
    assert "**High** · Not confirmed: no executed check covered it" in body
    assert "https://ari.test/projects/prj_1/assessments/asm_1" in body


def test_commentable_ranges_follow_head_side_lines_per_hunk():
    assert commentable_ranges(PATCH) == [(75, 79)]
    two = PATCH + "@@ -100,2 +100,3 @@\n context\n+added\n context\n"
    assert commentable_ranges(two) == [(75, 79), (100, 102)]
    assert commentable_ranges(None) == []


def test_inline_comment_is_clipped_to_the_changed_hunk():
    files = [{"filename": "ledgerlite/app.py", "patch": PATCH}]
    [comment] = inline_comments([CONFIRMED, SUSPICION], 1, files, RECORDS)
    assert (comment["path"], comment["start_line"], comment["line"]) == (
        "ledgerlite/app.py",
        75,
        79,
    )
    assert comment["side"] == comment["start_side"] == "RIGHT"
    assert "get_account never compares the owner." in comment["body"]
    assert "Suggested fix" in comment["body"]


def test_no_inline_comment_outside_the_diff_or_twice_on_one_location():
    files = [{"filename": "ledgerlite/app.py", "patch": PATCH}]
    duplicate = CONFIRMED | {"id": "fnd_dup", "title": "[authorization] same place"}
    assert len(inline_comments([CONFIRMED, duplicate], 1, files, RECORDS)) == 1
    assert inline_comments([SUSPICION], 1, files, RECORDS) == []
    assert inline_comments([CONFIRMED], 3, files, RECORDS) == []  # below strictness
