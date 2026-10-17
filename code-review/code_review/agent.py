"""ReviewerAgentRunner: the reviewer runtime agent (``AgentName.reviewer``).

Two bounded multi-turn Claude tool loops run through the backend LLM gateway:

* **review** — derive intent evidence, investigate, write and execute behavioral tests,
  submit a ``ReviewerReport``;
* **repair** — after a human approval, edit an isolated candidate workspace until the
  failing generated test passes, submit a ``RepairReport``.

The model proposes; deterministic code here decides. Finding statuses come from executed
test outcomes, claim statuses from verified citations, and a patch exists only after a
fresh replay of trusted tests outside the agent's workspace. The reviewer never marks
its own patch verified; that is the independent Verify agent's job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from code_review import PROMPT_VERSION, REPAIR_PROMPT_VERSION
from code_review.intent import (
    CitationChecker,
    IntentAdjudication,
    adjudicate_claims,
    scan_injection,
)
from code_review.models import (
    CitationIn,
    GeneratedTestSource,
    RepairOutcome,
    RepairReport,
    ReviewerReport,
    ReviewOutcome,
)
from code_review.ports import ExecResult, IntelligencePort, RepoSource, ReviewHost, SandboxPort
from code_review.sandbox import LocalProcessSandbox, classify
from code_review.tools import (
    ReviewBudget,
    ReviewerToolbox,
    TestExecution,
    WrittenTest,
    sha256_text,
)
from code_review.workspace import (
    Workspace,
    apply_unified_diff,
    changed_paths_between,
    git_diff,
    is_protected_path,
    unified_diff,
)
from shared.assessment import AgentName, AgentRunStatus
from shared.base import utcnow
from shared.errors import ErrorBody, ErrorCode
from shared.evidence import ArtifactKind, ArtifactRef, EvidenceKind, EvidenceRef
from shared.findings import (
    Finding,
    FindingKind,
    FindingStatus,
    PatchCandidate,
    SeverityAssessment,
    SeverityFactors,
    SeverityLevel,
    StatusChange,
)
from shared.ids import IdPrefix, new_id
from shared.intelligence import BehavioralExpectation
from shared.review import (
    GeneratedTest,
    IntentClaimStatus,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
)
from shared.scope import Approval, ApprovalStatus, ApprovalSubject

ACTOR = "agent:reviewer"
BUNDLE_KIND = "generated-test-bundle"
_CONF = {
    FindingStatus.validated: 0.9,
    FindingStatus.hypothesis: 0.4,
    FindingStatus.inconclusive: 0.3,
    FindingStatus.refuted: 0.1,
}


class ReviewError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _prompt(name: str) -> str:
    return resources.files("code_review").joinpath(f"prompts/{name}").read_text(encoding="utf-8")


def _ev_for_run(report: ArtifactRef, label: str, driver: str) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.test_run,
        artifact_id=report.id,
        sha256=report.sha256,
        provenance=f"code_review.sandbox:{driver}",
        note=label[:500],
    )


@dataclass
class ReviewerAgentRunner:
    host: ReviewHost
    source: RepoSource
    sandbox: SandboxPort = field(default_factory=LocalProcessSandbox)
    intelligence: IntelligencePort | None = None
    budget: ReviewBudget = field(default_factory=ReviewBudget)

    # ================================================================ review
    def review(
        self, request: ReviewRequest, *, focus_statements: list[str] | None = None
    ) -> ReviewOutcome:
        ci = request.change_intent
        if ci.head_sha != request.snapshot_ref.commit_sha:
            raise ReviewError(
                ErrorCode.VALIDATION_FAILED, "change_intent.head_sha must equal the snapshot commit"
            )
        head = Workspace.export(self.source, ci.head_sha)
        base = Workspace.export(self.source, ci.base_sha) if ci.base_sha else None
        try:
            return self._review(request, head, base, focus_statements or [])
        finally:
            head.close()
            if base is not None:
                base.close()

    def _load_expectations(
        self, request: ReviewRequest
    ) -> tuple[dict[str, BehavioralExpectation], str]:
        if self.intelligence is None:
            return {}, "code-intelligence not connected"
        try:
            exps = self.intelligence.expectations(request.snapshot_ref, limit=100)
        except Exception as e:  # missing/unready snapshot: say so, never invent
            return {}, f"code-intelligence unavailable for this snapshot: {type(e).__name__}: {e}"[
                :300
            ]
        return {e.id: e for e in exps}, f"{len(exps)} expectations from index"

    def _review(
        self,
        request: ReviewRequest,
        head: Workspace,
        base: Workspace | None,
        focus_statements: list[str],
    ) -> ReviewOutcome:
        ci = request.change_intent
        changed = list(ci.changed_paths) or changed_paths_between(
            self.source, ci.base_sha, ci.head_sha
        )
        diff = git_diff(self.source, ci.base_sha, ci.head_sha)
        injection = scan_injection(f"{ci.title}\n{ci.body}")
        expectations, intel_note = self._load_expectations(request)
        gw = self.host.llm()
        run_id = self.host.start_agent_run(
            AgentName.reviewer,
            "review",
            provider_mode=gw.provider_mode,
            model_id=gw.model_for(AgentName.reviewer.value),
            prompt_version=PROMPT_VERSION,
            input_payload={
                "request": request.model_dump(mode="json"),
                "changed_paths": changed,
                "injection_flags": injection,
                "intelligence": intel_note,
                "sandbox": {"driver": self.sandbox.name, "isolation": self.sandbox.isolation_level},
            },
        )
        self.host.progress(
            f"reviewer: reviewing {len(changed)} changed path(s) at {ci.head_sha[:12]}",
            agent=AgentName.reviewer,
            changed_paths=changed[:20],
        )
        try:
            if diff:
                self.host.store_text(diff, ArtifactKind.diff, media_type="text/x-diff")
            tb = ReviewerToolbox(
                host=self.host,
                head=head,
                base=base,
                sandbox=self.sandbox,
                budget=self.budget,
                change_diff=diff,
                intelligence=self.intelligence if expectations else None,
                snapshot_ref=request.snapshot_ref,
                expectations=expectations,
            )
            res = gw.run_tool_loop(
                agent=AgentName.reviewer.value,
                system=_prompt("reviewer_v1.md"),
                user_content=self._user_content(
                    request, changed, diff, injection, intel_note, focus_statements
                ),
                tools=tb.review_tools(),
                output_model=ReviewerReport,
                max_turns=self.budget.max_turns,
            )
            outcome = self._adjudicate(request, run_id, res.final, tb, head, injection)
            outcome.turns, outcome.provider_mode, outcome.model = (
                res.turns,
                res.provider_mode,
                res.model,
            )
            for f in outcome.result.findings:
                self.host.record_finding(f, actor=ACTOR)
            self.host.finish_agent_run(
                run_id,
                AgentRunStatus.succeeded,
                usage=res.usage,
                tool_calls=res.tool_calls,
                output={
                    "review_result": outcome.result.model_dump(mode="json"),
                    "model_report": res.final.model_dump(mode="json"),
                    "rejected_proposals": outcome.rejected,
                    "test_runs": tb.test_runs,
                },
                transcript=res.transcript,
            )
            return outcome
        except Exception as exc:
            code = getattr(exc, "code", ErrorCode.INTERNAL)
            self.host.finish_agent_run(
                run_id,
                AgentRunStatus.failed,
                error=ErrorBody(
                    code=code if isinstance(code, ErrorCode) else ErrorCode.INTERNAL,
                    message=f"{type(exc).__name__}: {exc}"[:500],
                ),
            )
            raise

    def _user_content(
        self,
        request: ReviewRequest,
        changed: list[str],
        diff: str,
        injection: list[str],
        intel_note: str,
        focus_statements: list[str] | None = None,
    ) -> str:
        ci = request.change_intent
        cap = 15_000
        shown = diff if len(diff) <= cap else diff[:cap] + "\n... (truncated; call get_change_diff)"
        return "\n".join(
            [
                "<review_request>",
                f"head_commit: {ci.head_sha}",
                f"base_commit: {ci.base_sha or 'none (full snapshot review)'}",
                f"project_root: {self.source.subdir or '.'}",
                f"changed_paths: {json.dumps(changed)}",
                f"focus_paths: {json.dumps(list(request.focus_paths))}",
                f"code_intelligence: {intel_note}",
                "</review_request>",
                "<untrusted_change_intent>",
                f"source: {ci.source.value}",
                f"title: {ci.title}",
                "body:",
                ci.body,
                "</untrusted_change_intent>",
                f"<injection_scan>{json.dumps(injection) if injection else 'none'}</injection_scan>",
                "<untrusted_diff>",
                shown or "(no diff)",
                "</untrusted_diff>",
                *(
                    [
                        "<test_generation_focus>",
                        *focus_statements,
                        "</test_generation_focus>",
                        "Write and run one behavioral test per focus statement.",
                    ]
                    if focus_statements
                    else []
                ),
                "Review this change for functional correctness against its intended behavior.",
            ]
        )

    def _adjudicate(
        self,
        request: ReviewRequest,
        run_id: str,
        report: ReviewerReport,
        tb: ReviewerToolbox,
        head: Workspace,
        injection: list[str],
    ) -> ReviewOutcome:
        ci = request.change_intent
        intent: IntentAdjudication = adjudicate_claims(
            report.claims, head, ci, tb.expectations, list(report.open_questions), injection
        )
        checker = CitationChecker(head, ci, tb.expectations)
        rejected = list(intent.rejected)
        questions = list(intent.evidence.open_questions)
        clarify = any(
            c.status in (IntentClaimStatus.ambiguous, IntentClaimStatus.conflicting)
            for c in intent.evidence.claims
        )
        now = utcnow()
        findings: list[Finding] = []

        def spans(cits: list[CitationIn]) -> list[EvidenceRef]:
            out = []
            for c in cits:
                ev, _, note = checker.check(c)
                if ev is not None and ev.kind is EvidenceKind.source_span:
                    out.append(ev)
                elif ev is None:
                    rejected.append(f"span rejected: {note}")
            return out

        for f in report.findings:
            decision = intent.by_key.get(f.claim_key)
            if decision is None:
                rejected.append(
                    f"finding '{f.title[:80]}': unknown or rejected claim {f.claim_key}"
                )
                continue
            evidence = spans(f.suspected_spans)
            if not evidence:
                rejected.append(f"finding '{f.title[:80]}': no verifiable source span")
                continue
            ex: TestExecution | None = tb.executions.get(f.test_id or "")
            reason: str
            if ex is None:
                status, reason = FindingStatus.hypothesis, "no executed test demonstrates it"
            elif ex.outcome_on_head == "failed" and ex.reproducible:
                if decision.claim.status is IntentClaimStatus.confirmed:
                    status, reason = (
                        FindingStatus.validated,
                        "generated test fails reproducibly on head",
                    )
                else:
                    status = FindingStatus.hypothesis
                    reason = f"test fails, but the rule is only {decision.claim.status.value}"
                    clarify = True
                    questions.append(
                        f"A generated test fails against an unconfirmed rule; confirm: "
                        f"{decision.claim.statement}"[:500]
                    )
            elif ex.outcome_on_head == "failed":
                status, reason = FindingStatus.inconclusive, "test failure did not reproduce"
            elif ex.outcome_on_head == "passed":
                status, reason = FindingStatus.refuted, "generated test passes on head"
            else:
                status, reason = FindingStatus.inconclusive, "test errored (harness/tooling)"
            if ex is not None and ex.test_id in tb.written:
                wt = tb.written[ex.test_id]
                bundle = self.host.store_json(
                    {
                        "kind": BUNDLE_KIND,
                        "tests": [
                            {
                                "test_id": wt.test_id,
                                "path": wt.path,
                                "content": wt.content,
                                "claim_key": wt.claim_key,
                                "artifact_id": wt.artifact.id,
                                "sha256": sha256_text(wt.content),
                            }
                        ],
                    },
                    ArtifactKind.other,
                )
                evidence.append(
                    EvidenceRef(
                        kind=EvidenceKind.artifact,
                        artifact_id=bundle.id,
                        sha256=bundle.sha256,
                        provenance=ACTOR,
                        note=f"{BUNDLE_KIND}: {wt.path} test_id={wt.test_id}"[:500],
                    )
                )
            if ex is not None:
                driver = ex.head_runs[-1].driver
                evidence.append(
                    _ev_for_run(ex.report, f"{ex.path} on head: {ex.outcome_on_head}", driver)
                )
                if ex.base_report is not None:
                    evidence.append(
                        _ev_for_run(
                            ex.base_report, f"{ex.path} on base: {ex.outcome_on_base}", driver
                        )
                    )
                    if ex.outcome_on_base == "passed" and ex.outcome_on_head == "failed":
                        reason += "; passes on base, so the change introduced it"
            evidence.extend(decision.claim.citations[:3])
            level = SeverityLevel(f.severity.value)
            findings.append(
                Finding(
                    id=new_id(IdPrefix.fnd),
                    assessment_id=request.assessment_id,
                    snapshot_id=request.snapshot_ref.snapshot_id,
                    commit_sha=ci.head_sha,
                    kind=FindingKind.functional,
                    title=f.title,
                    status=status,
                    severity=SeverityAssessment(
                        level=level,
                        factors=SeverityFactors(
                            reachability="changed code path"
                            if ci.base_sha
                            else "snapshot code path",
                            privileges_required="not assessed by reviewer",
                            data_sensitivity="not assessed by reviewer",
                            verified_path=status is FindingStatus.validated,
                        ),
                        rationale=f.rationale,
                    ),
                    subject_refs=sorted({e.path for e in evidence if e.path})[:10],
                    expectation_ids=[decision.claim.expectation_id]
                    if decision.claim.expectation_id
                    else [],
                    evidence=evidence,
                    confidence=_CONF[status],
                    produced_by_run_id=run_id,
                    history=[
                        StatusChange(
                            from_status=None,
                            to_status=status,
                            at=now,
                            actor=ACTOR,
                            reason=reason[:500],
                        )
                    ],
                    created_at=now,
                    updated_at=now,
                )
            )

        handoffs: list[Finding] = []
        for s in report.security_concerns:
            evidence = spans(s.spans)
            if not evidence:
                rejected.append(f"security concern '{s.title[:80]}': no verifiable span")
                continue
            handoffs.append(
                Finding(
                    id=new_id(IdPrefix.fnd),
                    assessment_id=request.assessment_id,
                    snapshot_id=request.snapshot_ref.snapshot_id,
                    commit_sha=ci.head_sha,
                    kind=FindingKind.security,
                    title=f"[{s.weakness_class}] {s.title}"[:500],
                    status=FindingStatus.hypothesis,
                    subject_refs=sorted({e.path for e in evidence if e.path})[:10],
                    evidence=evidence,
                    confidence=0.5,
                    produced_by_run_id=run_id,
                    history=[
                        StatusChange(
                            from_status=None,
                            to_status=FindingStatus.hypothesis,
                            at=now,
                            actor=ACTOR,
                            reason=f"handoff to scout: {s.rationale}"[:500],
                        )
                    ],
                    created_at=now,
                    updated_at=now,
                )
            )

        sources: dict[str, GeneratedTestSource] = {}
        generated: list[GeneratedTest] = []
        for tid, wt in tb.written.items():
            ex = tb.executions.get(tid)
            exp_id = (intent.by_key.get(wt.claim_key) or None) and intent.by_key[
                wt.claim_key
            ].claim.expectation_id
            generated.append(
                GeneratedTest(
                    id=tid,
                    path=wt.path,
                    expectation_ids=[exp_id] if exp_id else [],
                    artifact_id=wt.artifact.id,
                    outcome_on_head=ex.outcome_on_head if ex else "not_run",
                )
            )
            sources[tid] = GeneratedTestSource(
                tid, wt.path, wt.content, wt.claim_key, sha256_text(wt.content), wt.artifact.id
            )

        seen: set[str] = set()
        questions = [q for q in questions if not (q in seen or seen.add(q))]
        result = ReviewResult(
            assessment_id=request.assessment_id,
            agent_run_id=run_id,
            run_status=AgentRunStatus.succeeded,
            status=ReviewStatus.needs_clarification if clarify else ReviewStatus.completed,
            intent_evidence=intent.evidence.model_copy(update={"open_questions": questions[:20]}),
            findings=findings + handoffs,
            generated_tests=generated,
        )
        return ReviewOutcome(
            result=result, test_sources=sources, security_handoffs=handoffs, rejected=rejected
        )

    # ================================================================ repair
    def repair(
        self,
        finding: Finding,
        approval: Approval,
        tests: list[GeneratedTestSource],
        *,
        attempt: int = 1,
    ) -> RepairOutcome:
        check_repair_gate(finding, approval, tests)
        pristine = Workspace.export(self.source, finding.commit_sha)
        for t in tests:
            pristine.write(t.path, t.content)
            init = t.path.rsplit("/", 1)[0] + "/__init__.py"
            if pristine.exists(pristine.repo_rel("tests/__init__.py")) and not pristine.exists(
                init
            ):
                pristine.write(init, "")
        candidate = pristine.clone()
        try:
            return self._repair(finding, tests, pristine, candidate, attempt)
        finally:
            candidate.close()
            pristine.close()

    def _repair(
        self,
        finding: Finding,
        tests: list[GeneratedTestSource],
        pristine: Workspace,
        candidate: Workspace,
        attempt: int,
    ) -> RepairOutcome:
        gw = self.host.llm()
        run_id = self.host.start_agent_run(
            AgentName.reviewer,
            f"repair:{finding.id}",
            attempt=attempt,
            provider_mode=gw.provider_mode,
            model_id=gw.model_for(AgentName.reviewer.value),
            prompt_version=REPAIR_PROMPT_VERSION,
            input_payload={
                "finding": finding.model_dump(mode="json"),
                "tests": [t.path for t in tests],
            },
        )
        try:
            tb = ReviewerToolbox(
                host=self.host,
                head=candidate,
                sandbox=self.sandbox,
                budget=self.budget,
                pristine=pristine,
            )
            for t in tests:
                tb.written[t.test_id] = WrittenTest(
                    t.test_id,
                    t.path,
                    t.content,
                    t.claim_key,
                    "validated failing test",
                    ArtifactRef(
                        id=t.artifact_id,
                        kind=ArtifactKind.other,
                        sha256=t.sha256,
                        size_bytes=len(t.content.encode()),
                    ),
                )
            res = gw.run_tool_loop(
                agent=AgentName.reviewer.value,
                system=_prompt("repair_v1.md"),
                user_content=self._repair_content(finding, tests),
                tools=tb.repair_tools(),
                output_model=RepairReport,
                max_turns=self.budget.max_turns,
            )
            outcome = self._finalize_repair(
                finding, tests, pristine, candidate, run_id, res.final, attempt
            )
            outcome.turns = res.turns
            self.host.finish_agent_run(
                run_id,
                AgentRunStatus.succeeded,
                usage=res.usage,
                tool_calls=res.tool_calls,
                output={
                    "model_report": res.final.model_dump(mode="json"),
                    "accepted_locally": outcome.accepted_locally,
                    "reasons": outcome.reasons,
                    "patch_id": outcome.patch.id if outcome.patch else None,
                },
                transcript=res.transcript,
            )
            return outcome
        except Exception as exc:
            code = getattr(exc, "code", ErrorCode.INTERNAL)
            self.host.finish_agent_run(
                run_id,
                AgentRunStatus.failed,
                error=ErrorBody(
                    code=code if isinstance(code, ErrorCode) else ErrorCode.INTERNAL,
                    message=f"{type(exc).__name__}: {exc}"[:500],
                ),
            )
            raise

    def _repair_content(self, finding: Finding, tests: list[GeneratedTestSource]) -> str:
        spans = [
            f"{e.path}:{e.span.start_line}-{e.span.end_line} ({e.note or ''})"
            for e in finding.evidence
            if e.kind is EvidenceKind.source_span and e.span
        ]
        parts = [
            "<validated_finding>",
            f"id: {finding.id}",
            f"title: {finding.title}",
            f"commit: {finding.commit_sha}",
            "suspected spans:",
            *spans,
            "</validated_finding>",
            f"<project_root>{self.source.subdir or '.'}</project_root>",
        ]
        for t in tests:
            parts += [
                f"<failing_generated_test test_id='{t.test_id}' path='{t.path}'>",
                t.content,
                "</failing_generated_test>",
            ]
        parts.append("Make the minimal fix. The generated test(s) above are protected.")
        return "\n".join(parts)

    def _finalize_repair(
        self,
        finding: Finding,
        tests: list[GeneratedTestSource],
        pristine: Workspace,
        candidate: Workspace,
        run_id: str,
        report: RepairReport,
        attempt: int,
    ) -> RepairOutcome:
        diff, changed = unified_diff(pristine, candidate)
        reasons: list[str] = []
        if not changed:
            reasons.append("no implementation change was made")
        tampered = [p for p in changed if is_protected_path(p)]
        if tampered:
            reasons.append(f"protected test/config files changed: {tampered}")
        if pristine.digests([t.path for t in tests]) != candidate.digests([t.path for t in tests]):
            reasons.append("generated requirement tests were modified")
        replay_report: ArtifactRef | None = None
        if not reasons:
            ok, replay_reasons, replay_report = self._fresh_replay(finding, tests, pristine, diff)
            reasons.extend(replay_reasons)
        accepted = not reasons
        patch: PatchCandidate | None = None
        updated = finding
        if accepted:
            art = self.host.store_text(diff, ArtifactKind.diff, media_type="text/x-diff")
            patch = PatchCandidate(
                id=new_id(IdPrefix.pat),
                finding_id=finding.id,
                attempt=attempt,
                diff_artifact_id=art.id,
                diff_sha256=art.sha256,
                base_commit_sha=finding.commit_sha,
                worktree_ref=f"ephemeral-export:{finding.commit_sha[:12]}",
                files_changed=changed,
                tests_added=[t.path for t in tests],
                local_test_run_id=new_id(IdPrefix.tst),
                produced_by_run_id=run_id,
                rationale=f"{report.summary} Root cause: {report.root_cause}"[:500],
                created_at=utcnow(),
            )
            self.host.record_patch(patch)
            now = utcnow()
            updated = finding.model_copy(
                update={
                    "status": FindingStatus.patch_proposed,
                    "updated_at": now,
                    "evidence": [
                        *finding.evidence,
                        _ev_for_run(
                            replay_report,
                            "fresh replay of candidate: generated + existing tests pass",
                            self.sandbox.name,
                        ),  # type: ignore[arg-type]
                    ],
                    "history": [
                        *finding.history,
                        StatusChange(
                            from_status=finding.status,
                            to_status=FindingStatus.patch_proposed,
                            at=now,
                            actor=ACTOR,
                            reason="candidate passes fresh local replay; awaiting independent Verify",
                        ),
                    ],
                }
            )
            self.host.record_finding(updated, actor=ACTOR)
        return RepairOutcome(
            patch=patch,
            finding=updated,
            accepted_locally=accepted,
            reasons=reasons,
            diff_text=diff,
            agent_run_id=run_id,
            test_report_artifact_id=replay_report.id if replay_report else None,
        )

    def _fresh_replay(
        self, finding: Finding, tests: list[GeneratedTestSource], pristine: Workspace, diff: str
    ) -> tuple[bool, list[str], ArtifactRef]:
        """Re-run trusted tests on a NEW export + the diff, never the agent's workspace."""
        fresh = Workspace.export(self.source, finding.commit_sha)
        try:
            ok, msg = apply_unified_diff(fresh, diff)
            reasons = [] if ok else [f"diff does not apply to a fresh checkout: {msg}"]
            runs: list[tuple[str, ExecResult]] = []
            if ok:
                for t in tests:
                    fresh.write(t.path, t.content)
                    init = t.path.rsplit("/", 1)[0] + "/__init__.py"
                    if pristine.exists(init) and not fresh.exists(init):
                        fresh.write(init, "")
                timeout = self.budget.test_timeout_s
                for t in tests:
                    r = self.sandbox.run_pytest(
                        fresh.project_dir, [fresh.project_rel(t.path)], timeout_s=timeout
                    )
                    runs.append((f"generated:{t.test_id}", r))
                    if classify(r) != "passed":
                        reasons.append(f"generated test {t.path} is {classify(r)} on the candidate")
                existing = ReviewerToolbox(
                    host=self.host, head=fresh, sandbox=self.sandbox, budget=self.budget
                )._existing_targets(fresh)
                if existing:
                    before = self.sandbox.run_pytest(
                        pristine.project_dir, existing, timeout_s=timeout
                    )
                    after = self.sandbox.run_pytest(fresh.project_dir, existing, timeout_s=timeout)
                    runs += [("existing@pristine", before), ("existing@candidate", after)]
                    failing_before = {
                        c.nodeid for c in before.cases if c.outcome in ("failed", "error")
                    }
                    failing_after = {
                        c.nodeid for c in after.cases if c.outcome in ("failed", "error")
                    }
                    if classify(after) == "error" and classify(before) != "error":
                        reasons.append("existing suite errors on the candidate")
                    elif failing_after - failing_before:
                        reasons.append(
                            f"candidate breaks existing tests: {sorted(failing_after - failing_before)[:5]}"
                        )
            art = self.host.store_json(
                {
                    "label": f"fresh-replay:{finding.id}",
                    "commit_sha": finding.commit_sha,
                    "diff_applied": ok,
                    "runs": [
                        {"label": label, **r.to_json(), "classification": classify(r)}
                        for label, r in runs
                    ],
                    "reasons": reasons,
                },
                ArtifactKind.test_report,
            )
            return not reasons, reasons, art
        finally:
            fresh.close()


def check_repair_gate(
    finding: Finding, approval: Approval, tests: list[GeneratedTestSource]
) -> None:
    """Deterministic preconditions for a repair attempt (never delegated to the model)."""
    if (
        approval.subject_type is not ApprovalSubject.remediation
        or approval.subject_id != finding.id
        or approval.status is not ApprovalStatus.approved
    ):
        raise ReviewError(
            ErrorCode.APPROVAL_REQUIRED,
            f"repair of {finding.id} requires an approved remediation approval for that finding",
        )
    if finding.kind is not FindingKind.functional or finding.status is not FindingStatus.validated:
        raise ReviewError(
            ErrorCode.VALIDATION_FAILED,
            f"only validated functional findings can be repaired (got {finding.kind.value}/{finding.status.value})",
        )
    if not tests:
        raise ReviewError(ErrorCode.VALIDATION_FAILED, "repair needs the failing generated test(s)")


def report_json(outcome: ReviewOutcome) -> dict[str, Any]:
    return {
        "result": outcome.result.model_dump(mode="json"),
        "rejected": outcome.rejected,
        "turns": outcome.turns,
        "provider_mode": outcome.provider_mode,
        "model": outcome.model,
    }
