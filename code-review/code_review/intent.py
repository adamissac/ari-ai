"""IntentEvidence: what a change is *supposed* to do, with citations and honest statuses.

The agent proposes claims; this module decides what they are allowed to be:

* every citation is checked against the pinned workspace (file exists, lines in range,
  quoted text actually present) — invented citations are dropped;
* ``confirmed`` requires corroboration from a project document, a docstring, an
  existing (not generated) test, or a confirmed code-intelligence expectation. PR text
  and implementation code alone can only make a claim ``inferred``;
* PR/commit text is scanned for instruction-like content; it stays data and is flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from code_review.models import CitationIn, ClaimIn, SourceKind
from code_review.workspace import (
    GENERATED_TEST_DIR,
    Workspace,
    WorkspaceError,
    docstring_ranges,
    is_test_path,
)
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.intelligence import BehavioralExpectation, ExpectationStatus
from shared.review import ChangeIntent, IntentClaim, IntentClaimStatus, IntentEvidence

PROVENANCE = "agent:reviewer"
CONFLICT_NOTE = "expectation is marked conflicting"
_DOC_SUFFIXES = {".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml"}
_SUPPORTING = {SourceKind.doc, SourceKind.docstring, SourceKind.test, SourceKind.expectation}
_CONFIDENCE = {
    IntentClaimStatus.confirmed: 0.9,
    IntentClaimStatus.inferred: 0.5,
    IntentClaimStatus.ambiguous: 0.3,
    IntentClaimStatus.conflicting: 0.3,
}

_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|rules)|disregard .{0,30}instructions"
    r"|you are now|system prompt|as an ai|do not (report|flag|mention)|mark (this|it|the)( \w+)? as"
    r" (verified|approved|safe)|approve (this|the) (pr|patch|change)|skip (the )?(tests|review)"
    r"|call the \w+ tool|submit_result)",
    re.IGNORECASE,
)


def scan_injection(text: str) -> list[str]:
    """Instruction-like fragments in untrusted text (reported, never obeyed)."""
    return sorted({m.group(0)[:120] for m in _INJECTION.finditer(text or "")})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


QUOTE_SLACK = 3
_LINE_NO = re.compile(r"^\s*\d+(?:\s{2,}|\s*[:|]\s*)")
_ELLIPSIS = re.compile(r"\.\.\.|\u2026")


def clean_quote(quote: str) -> str:
    """Drop line-number prefixes a model copies from ``read_file`` output (``  131  def …``)."""
    return "\n".join(_LINE_NO.sub("", line) for line in quote.splitlines()).strip()


def locate_quote(quote: str, lines: list[str], start: int, end: int) -> tuple[int, int] | None:
    """Find ``quote`` at the cited span, tolerating copied line numbers, indentation and
    whitespace differences, skipped lines or ``...`` elisions (every quoted line must appear,
    in order) and an anchor
    off by up to ``QUOTE_SLACK`` lines. Returns the (start, end) lines to cite, or ``None``
    when the quote is not near the citation (fabricated or wrong citation stays rejected)."""
    # Each quoted line (and each piece around "...") must appear, in order, near the citation;
    # models often skip lines without marking the elision.
    fragments = [
        _norm(f) for line in clean_quote(quote).splitlines() for f in _ELLIPSIS.split(line)
    ]
    fragments = [f for f in fragments if f]
    if not fragments:
        return (start, end)
    lo = max(1, start - QUOTE_SLACK)
    hi = min(len(lines), end + QUOTE_SLACK)
    text, owner = "", []  # normalized window text and the source line of every character
    for n in range(lo, hi + 1):
        piece = _norm(lines[n - 1])
        if not piece:
            continue
        if text:
            text += " "
            owner.append(n)
        text += piece
        owner.extend([n] * len(piece))
    pos, first, last = 0, None, None
    for frag in fragments:
        at = text.find(frag, pos)
        if at < 0:
            return None
        if first is None:
            first = owner[at]
        last = owner[at + len(frag) - 1]
        pos = at + len(frag)
    assert first is not None and last is not None
    if start <= first and last <= end:
        return (start, end)
    return (first, last)


@dataclass
class ClaimDecision:
    claim: IntentClaim
    key: str
    supported_by: set[SourceKind]
    notes: list[str] = field(default_factory=list)


@dataclass
class IntentAdjudication:
    evidence: IntentEvidence
    by_key: dict[str, ClaimDecision]
    rejected: list[str]


class CitationChecker:
    def __init__(
        self,
        ws: Workspace,
        change_intent: ChangeIntent,
        expectations: dict[str, BehavioralExpectation],
    ) -> None:
        self.ws = ws
        self.intent_text = _norm(f"{change_intent.title}\n{change_intent.body}")
        self.expectations = expectations

    def check(self, c: CitationIn) -> tuple[EvidenceRef | None, SourceKind, str]:
        """Return (evidence, effective kind, note). evidence None => citation rejected."""
        quote = (c.quote or "").strip()
        if c.source_kind is SourceKind.change_intent:
            if quote and _norm(quote) not in self.intent_text:
                return None, c.source_kind, "quoted text not found in change intent"
            ev = EvidenceRef(
                kind=EvidenceKind.change_intent,
                provenance=f"{PROVENANCE}:change_intent",
                note=(
                    f"untrusted PR/commit text: {quote}" if quote else "untrusted PR/commit text"
                )[:500],
            )
            return ev, c.source_kind, ""
        if c.source_kind is SourceKind.expectation:
            exp = self.expectations.get(c.expectation_id or "")
            if exp is None:
                return None, c.source_kind, f"unknown expectation {c.expectation_id}"
            if exp.status is ExpectationStatus.rejected:
                return None, c.source_kind, f"expectation {exp.id} was rejected by a human decision"
            base = exp.sources[0]
            ev = base.model_copy(
                update={"note": f"expectation {exp.id} ({exp.status.value}): {exp.statement}"[:500]}
            )
            kind = (
                SourceKind.expectation
                if exp.status is ExpectationStatus.confirmed
                else SourceKind.code
            )
            if exp.status is ExpectationStatus.conflicting:
                return ev, kind, CONFLICT_NOTE
            return ev, kind, "" if kind is SourceKind.expectation else "expectation not confirmed"
        if not c.path or c.start_line is None:
            return None, c.source_kind, "file citation needs path and start_line"
        try:
            text = self.ws.read(c.path)
        except WorkspaceError as e:
            return None, c.source_kind, str(e)
        lines = text.splitlines()
        end = c.end_line or c.start_line
        if c.start_line > len(lines) or end > len(lines) or end < c.start_line:
            return None, c.source_kind, f"lines {c.start_line}-{end} outside {c.path}"
        start = c.start_line
        anchor_note = ""
        if quote:
            located = locate_quote(quote, lines, start, end)
            if located is None:
                return (
                    None,
                    c.source_kind,
                    f"quote not present at {c.path}:{start}-{end} (±{QUOTE_SLACK})",
                )
            if located != (start, end):
                anchor_note = f"re-anchored {start}-{end} -> {located[0]}-{located[1]}"
                start, end = located
            quote = clean_quote(quote)
        kind = self._effective_kind(c.source_kind, c.path, text, start, end)
        ev = EvidenceRef(
            kind=EvidenceKind.source_span,
            path=c.path,
            commit_sha=self.ws.commit_sha,
            span=SourceSpan(start_line=start, end_line=end),
            provenance=PROVENANCE,
            note=(f"{kind.value}: {quote}" if quote else kind.value)[:500],
        )
        notes = [
            n
            for n in (anchor_note, "" if kind is c.source_kind else f"reclassified as {kind.value}")
            if n
        ]
        return ev, kind, "; ".join(notes)

    @staticmethod
    def _effective_kind(kind: SourceKind, path: str, text: str, start: int, end: int) -> SourceKind:
        suffix = PurePosixPath(path).suffix
        if kind is SourceKind.doc:
            return kind if suffix in _DOC_SUFFIXES else SourceKind.code
        if kind is SourceKind.docstring:
            if suffix != ".py":
                return SourceKind.doc if suffix in _DOC_SUFFIXES else SourceKind.code
            inside = any(a <= start and end <= b for a, b in docstring_ranges(text))
            return kind if inside else SourceKind.code
        if kind is SourceKind.test:
            generated = path.startswith(GENERATED_TEST_DIR) or f"/{GENERATED_TEST_DIR}/" in path
            return kind if is_test_path(path) and not generated else SourceKind.code
        return SourceKind.code


def adjudicate_claims(
    claims: list[ClaimIn],
    ws: Workspace,
    change_intent: ChangeIntent,
    expectations: dict[str, BehavioralExpectation],
    open_questions: list[str],
    injection_flags: list[str],
) -> IntentAdjudication:
    checker = CitationChecker(ws, change_intent, expectations)
    by_key: dict[str, ClaimDecision] = {}
    rejected: list[str] = []
    out: list[IntentClaim] = []
    questions = list(open_questions)
    for claim in claims:
        if claim.key in by_key:
            rejected.append(f"claim {claim.key}: duplicate key")
            continue
        refs: list[EvidenceRef] = []
        kinds: set[SourceKind] = set()
        notes: list[str] = []
        for cit in claim.citations:
            ev, kind, note = checker.check(cit)
            if ev is None:
                rejected.append(f"claim {claim.key}: citation rejected ({note})")
                continue
            refs.append(ev)
            kinds.add(kind)
            if note:
                notes.append(note)
        if not refs:
            rejected.append(f"claim {claim.key}: no verifiable citation; dropped")
            continue
        status = IntentClaimStatus(claim.proposed_status.value)
        if CONFLICT_NOTE in notes:  # a human/index decision says sources disagree: never confirm
            status = IntentClaimStatus.conflicting
        if status is IntentClaimStatus.confirmed and not kinds & _SUPPORTING:
            status = IntentClaimStatus.inferred
            notes.append("downgraded to inferred: only PR text or implementation code supports it")
        if status in (IntentClaimStatus.ambiguous, IntentClaimStatus.conflicting):
            questions.append(f"Please confirm the intended behavior: {claim.statement}"[:500])
        exp_id = next(
            (c.expectation_id for c in claim.citations if c.expectation_id in expectations), None
        )
        ic = IntentClaim(
            statement=claim.statement,
            status=status,
            citations=refs,
            expectation_id=exp_id,
            confidence=_CONFIDENCE[status],
        )
        out.append(ic)
        by_key[claim.key] = ClaimDecision(claim=ic, key=claim.key, supported_by=kinds, notes=notes)
    if injection_flags:
        questions.append(
            "Change text contains instruction-like content that was treated as data: "
            + "; ".join(injection_flags)[:400]
        )
    deduped = list(dict.fromkeys(questions))
    return IntentAdjudication(
        evidence=IntentEvidence(claims=out, open_questions=deduped[:20]),
        by_key=by_key,
        rejected=rejected,
    )
