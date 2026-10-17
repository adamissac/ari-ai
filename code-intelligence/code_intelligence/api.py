"""Public, scoped intelligence API for review, security agents and monitoring.

Construct one service per worker with an injected durable store and explicit local
repository registrations. Missing repositories/snapshots fail rather than fabricate facts.
"""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from shared.base import utcnow
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import (
    PatchCandidate,
    VerificationCheckName,
    VerificationResult,
    VerificationVerdict,
)
from shared.intelligence import (
    BehavioralExpectation,
    ContextChunk,
    ContextPack,
    ContextPackRequest,
    ContextPurpose,
    EntryPoint,
    ImpactResolution,
    ImpactSet,
    Snapshot,
    SnapshotRef,
    SnapshotStats,
    SnapshotStatus,
    Symbol,
)
from shared.intelligence_memory import (
    ExpectationDecision,
    ExpectationDecisionRequest,
    VerifiedRegression,
)

from code_intelligence.extract import PythonExtractor, dependencies
from code_intelligence.inference import ExpectationProvider, validate_proposals
from code_intelligence.ingest import GitReader, Limits
from code_intelligence.memory import MemoryStore, SQLiteMemoryStore, apply_decisions
from code_intelligence.models import INDEX_VERSION, IntelligenceError, StoredIndex, stable_id
from code_intelligence.persistence import PayloadIndexStore, PayloadStore
from code_intelligence.retrieval import build_pack, delimited, estimate, neighbors
from code_intelligence.store import IndexStore, SQLiteIndexStore


@dataclass(frozen=True)
class RepositoryBinding:
    project_id: str
    repo_id: str
    full_name: str
    local_path: Path
    include_prefix: str = ""


class IntelligenceService:
    def __init__(
        self,
        store: IndexStore,
        repositories: Sequence[RepositoryBinding] = (),
        limits: Limits | None = None,
        expectation_provider: ExpectationProvider | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.store = store
        self.memory = memory
        if self.memory is None and isinstance(store, SQLiteIndexStore):
            self.memory = SQLiteMemoryStore(store.path)
        if self.memory is None and isinstance(store, PayloadIndexStore):
            companion = getattr(store.payloads, "memory_store", None)
            if callable(companion):
                self.memory = cast(MemoryStore, companion())
        self.limits = limits or Limits()
        self.expectation_provider = expectation_provider
        self.repositories = {r.repo_id: r for r in repositories}
        if len(self.repositories) != len(repositories):
            raise IntelligenceError("Duplicate repository registration")

    def _binding(self, repo_id: str) -> RepositoryBinding:
        try:
            return self.repositories[repo_id]
        except KeyError as exc:
            raise IntelligenceError(
                "Repository is not registered for intelligence ingestion"
            ) from exc

    def index_repository(
        self,
        project_id: str,
        repo_id: str,
        commit_sha: str,
        *,
        base_snapshot: SnapshotRef | None = None,
    ) -> SnapshotRef:
        binding = self._binding(repo_id)
        if binding.project_id != project_id:
            raise IntelligenceError("Repository does not belong to requested project")
        if base_snapshot:
            self._validate_base(base_snapshot, project_id, repo_id)
        try:
            return self.store.find(project_id, repo_id, commit_sha, INDEX_VERSION).ref
        except IntelligenceError as exc:
            if "SNAPSHOT_NOT_READY" not in str(exc):
                raise
        snapshot = Snapshot(
            id=stable_id("snp", project_id, repo_id, commit_sha, INDEX_VERSION),
            repo_id=repo_id,
            commit_sha=commit_sha,
            status=SnapshotStatus.pending,
            index_version=INDEX_VERSION,
            base_snapshot_id=base_snapshot.snapshot_id if base_snapshot else None,
            created_at=utcnow(),
        )
        return self._index(binding, snapshot, base_snapshot).ref

    def _validate_base(self, ref: SnapshotRef, project_id: str, repo_id: str) -> StoredIndex:
        if ref.project_id != project_id or ref.repo_id != repo_id:
            raise IntelligenceError("Base snapshot belongs to another project/repository")
        return self.store.get(ref)

    def _index(
        self, binding: RepositoryBinding, snapshot: Snapshot, base: SnapshotRef | None = None
    ) -> StoredIndex:
        ref = SnapshotRef(
            project_id=binding.project_id,
            repo_id=binding.repo_id,
            snapshot_id=snapshot.id,
            commit_sha=snapshot.commit_sha,
            index_version=INDEX_VERSION,
        )
        reader = GitReader(binding.local_path, self.limits, binding.include_prefix)
        tree, files, issues = reader.read(ref.commit_sha)
        parser = PythonExtractor(ref, files)
        parser.extract()
        issues.extend(parser.issues)
        finished = Snapshot(
            id=snapshot.id,
            repo_id=snapshot.repo_id,
            commit_sha=snapshot.commit_sha,
            status=SnapshotStatus.ready,
            index_version=INDEX_VERSION,
            created_at=snapshot.created_at,
            completed_at=utcnow(),
            base_snapshot_id=base.snapshot_id if base else None,
            stats=SnapshotStats(
                files=len(files),
                symbols=len(parser.symbols),
                call_edges=len(parser.calls),
                entry_points=len(parser.entries),
                expectations=len(parser.expectations),
            ),
        )
        index = StoredIndex(
            ref=ref,
            snapshot=finished,
            tree_sha=tree,
            tree_files=reader.manifest,
            files=files,
            symbols=parser.symbols,
            calls=parser.calls,
            imports=parser.imports,
            entry_points=parser.entries,
            expectations=parser.expectations,
            dependencies=dependencies(files),
            issues=issues,
            base_snapshot_id=base.snapshot_id if base else None,
        )
        # Full re-derivation is the safe MVP incremental strategy. No artifact is carried
        # without proving its neighborhood and citations unchanged (so carried_from is empty).
        if self.expectation_provider is not None and index.entry_points:
            request = ContextPackRequest(
                snapshot_ref=ref, purpose=ContextPurpose.review, token_budget=24_000
            )
            pack = build_pack(index, request)
            inferred = self.expectation_provider.propose(pack)
            index.expectations.extend(validate_proposals(index, pack, inferred.proposals))
            index.inference_trace = inferred.trace
            index.snapshot.stats.expectations = len(index.expectations)
        self.store.put(index)
        return index

    def index_snapshot(self, snapshot: Snapshot, repo_full_name: str) -> Snapshot:
        """Srihith worker adapter; local paths come from administrator registration only."""
        binding = self._binding(snapshot.repo_id)
        if binding.full_name != repo_full_name:
            raise IntelligenceError("Backend repository name does not match registration")
        try:
            existing = self.store.find(
                binding.project_id, snapshot.repo_id, snapshot.commit_sha, INDEX_VERSION
            )
        except IntelligenceError as exc:
            if "SNAPSHOT_NOT_READY" not in str(exc):
                raise
        else:
            if str(existing.snapshot.id) != str(snapshot.id):
                raise IntelligenceError("Version already indexed with another snapshot id")
            return existing.snapshot
        base = None
        if snapshot.base_snapshot_id:
            raise IntelligenceError("Backend base snapshot requires an exact SnapshotRef")
        try:
            return self._index(binding, snapshot, base).snapshot
        except (IntelligenceError, OSError) as exc:
            # The worker persists this terminal result; do not leave an invalid SHA/path pending.
            return Snapshot(
                id=snapshot.id,
                repo_id=snapshot.repo_id,
                commit_sha=snapshot.commit_sha,
                status=SnapshotStatus.failed,
                index_version=INDEX_VERSION,
                created_at=snapshot.created_at,
                completed_at=utcnow(),
                error_message=f"INDEX_FAILED: {type(exc).__name__}: {exc}"[:500],
            )

    @staticmethod
    def _page(
        items: Sequence[Symbol] | Sequence[EntryPoint] | Sequence[BehavioralExpectation],
        offset: int,
        limit: int,
    ) -> Sequence[object]:
        if offset < 0 or not 1 <= limit <= 500:
            raise IntelligenceError("Pagination requires offset >= 0 and 1 <= limit <= 500")
        return items[offset : offset + limit]

    def get_symbol(self, ref: SnapshotRef, qualified_name: str) -> Symbol:
        matches = [
            s for s in self.store.get(ref).symbols if qualified_name in {s.id, s.qualified_name}
        ]
        if len(matches) != 1:
            raise IntelligenceError("Symbol missing or ambiguous; use exact symbol id")
        return matches[0]

    def symbols(self, ref: SnapshotRef, *, offset: int = 0, limit: int = 100) -> list[Symbol]:
        index = self.store.get(ref)
        self._page(index.symbols, offset, limit)
        return index.symbols[offset : offset + limit]

    def entry_points(
        self, ref: SnapshotRef, *, offset: int = 0, limit: int = 100
    ) -> list[EntryPoint]:
        index = self.store.get(ref)
        self._page(index.entry_points, offset, limit)
        return index.entry_points[offset : offset + limit]

    def expectations(
        self, ref: SnapshotRef, subject: str | None = None, *, offset: int = 0, limit: int = 100
    ) -> list[BehavioralExpectation]:
        index = self._effective_index(ref)
        aliases = {subject} if subject is not None else set()
        aliases.update(s.id for s in index.symbols if subject in {s.id, s.qualified_name})
        for entry in index.entry_points:
            if (
                entry.handler_symbol_id in aliases
                or entry.id == subject
                or entry.path_template == subject
            ):
                aliases.update({entry.id, entry.handler_symbol_id})
        result = [e for e in index.expectations if subject is None or e.subject_ref in aliases]
        self._page(result, offset, limit)
        return result[offset : offset + limit]

    def build_context_pack(self, request: ContextPackRequest) -> ContextPack:
        index = self._effective_index(request.snapshot_ref)
        supplements: list[tuple[set[str], str, EvidenceRef]] = []
        if self.memory is not None:
            by_id = {e.id: e for e in index.expectations}
            for decision in self.memory.decisions(request.snapshot_ref):
                expectation = by_id.get(decision.expectation_id)
                if expectation is not None:
                    supplements.append(
                        (
                            {
                                expectation.id,
                                expectation.subject_ref,
                                *(e.path for e in expectation.sources if e.path),
                            },
                            f"Authenticated intended-behavior decision {decision.expectation_id} "
                            f"revision {decision.revision}: {decision.status}. "
                            f"Reason: {decision.reason}. "
                            "This confirms intended behavior, not observed implementation "
                            "correctness.",
                            expectation.sources[-1],
                        )
                    )
            for record in self.memory.regressions(request.snapshot_ref):
                supplements.append(
                    (
                        {
                            record.finding_id,
                            record.patch_id,
                            *record.affected_paths,
                            *record.test_paths,
                        },
                        f"Independently verified CANDIDATE patch {record.patch_id} "
                        f"for {record.finding_id} "
                        f"at base {record.snapshot_ref.commit_sha}; "
                        f"verification {record.verification_id}. "
                        f"Regression test paths: {', '.join(record.test_paths)}. "
                        "Candidate evidence only: not proof of merge, deployment, or passing "
                        "tests on this "
                        "unpatched base or any other commit. Re-execute before claiming "
                        "current correctness.",
                        record.evidence[0],
                    )
                )
        return build_pack(index, request, supplements=supplements)

    def _effective_index(self, ref: SnapshotRef) -> StoredIndex:
        index = self.store.get(ref)
        if self.memory is None:
            return index
        return index.model_copy(
            update={"expectations": apply_decisions(index.expectations, self.memory.decisions(ref))}
        )

    def decide_expectation(
        self,
        ref: SnapshotRef,
        expectation_id: str,
        request: ExpectationDecisionRequest,
        *,
        actor_id: str,
    ) -> ExpectationDecision:
        """Backend supplies authenticated actor; this method is never an agent tool."""
        index = self.store.get(ref)
        if not any(e.id == expectation_id for e in index.expectations):
            raise IntelligenceError("NOT_FOUND: expectation not in exact snapshot")
        if self.memory is None:
            raise IntelligenceError("SUBSYSTEM_UNAVAILABLE: intelligence memory is not configured")
        decision = ExpectationDecision(
            **request.model_dump(),
            snapshot_ref=ref,
            expectation_id=expectation_id,
            revision=request.expected_revision + 1,
            decided_by=actor_id,
            decided_at=utcnow(),
        )
        return self.memory.put_decision(decision)

    def decision_history(
        self,
        ref: SnapshotRef,
        expectation_id: str,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> list[ExpectationDecision]:
        index = self.store.get(ref)
        if not any(e.id == expectation_id for e in index.expectations):
            raise IntelligenceError("NOT_FOUND: expectation not in exact snapshot")
        if self.memory is None:
            raise IntelligenceError("SUBSYSTEM_UNAVAILABLE: intelligence memory is not configured")
        return self.memory.history(ref, expectation_id, after=after, limit=limit)

    def verified_regressions(self, ref: SnapshotRef) -> list[VerifiedRegression]:
        self.store.get(ref)
        return self.memory.regressions(ref) if self.memory is not None else []

    def register_verified_regression(
        self,
        ref: SnapshotRef,
        patch: PatchCandidate,
        verification: VerificationResult,
    ) -> VerifiedRegression:
        self.store.get(ref)
        names = [c.name for c in verification.checks]
        if (
            verification.verdict is not VerificationVerdict.accepted
            or verification.patch_id != patch.id
            or patch.base_commit_sha != ref.commit_sha
            or verification.produced_by_run_id == patch.produced_by_run_id
            or len(names) != len(VerificationCheckName)
            or set(names) != set(VerificationCheckName)
            or not all(c.passed for c in verification.checks)
        ):
            raise IntelligenceError(
                "SCHEMA_INVALID: regression requires all independent Verify checks"
            )
        if self.memory is None:
            raise IntelligenceError("SUBSYSTEM_UNAVAILABLE: intelligence memory is not configured")
        executed = [
            e
            for c in verification.checks
            for e in c.evidence
            if e.kind in {EvidenceKind.test_run, EvidenceKind.sandbox_run}
        ]
        record = VerifiedRegression(
            snapshot_ref=ref,
            finding_id=patch.finding_id,
            patch_id=patch.id,
            verification_id=verification.id,
            affected_paths=sorted(set(patch.files_changed)),
            test_paths=sorted({p.split("::", 1)[0] for p in patch.tests_added}),
            evidence=executed,
            created_at=verification.created_at,
        )
        self.memory.put_regression(record)
        return record

    def graph_neighbors(self, ref: SnapshotRef, symbol_id: str, *, depth: int = 1) -> list[Symbol]:
        index = self.store.get(ref)
        if symbol_id not in {s.id for s in index.symbols}:
            raise IntelligenceError("Symbol is not in requested snapshot")
        found = neighbors(index, {symbol_id}, depth)
        return [s for s in index.symbols if s.id in found]

    def read_span(
        self,
        ref: SnapshotRef,
        path: str,
        start_line: int,
        end_line: int,
        *,
        max_bytes: int = 20_000,
    ) -> str:
        index = self.store.get(ref)
        files = [f for f in index.files if f.path == path]
        if not files or start_line < 1 or end_line < start_line:
            raise IntelligenceError("Invalid source span")
        lines = files[0].content.splitlines()
        if end_line > len(lines):
            raise IntelligenceError("Source span outside pinned file")
        content = "\n".join(lines[start_line - 1 : end_line])
        if len(content.encode()) > max_bytes:
            raise IntelligenceError("Source span exceeds budget")
        return content

    def read_chunk(
        self, ref: SnapshotRef, path: str, start_line: int, end_line: int
    ) -> ContextChunk:
        content = self.read_span(ref, path, start_line, end_line, max_bytes=15_000)
        evidence = EvidenceRef(
            kind=EvidenceKind.source_span,
            path=path,
            commit_sha=ref.commit_sha,
            span=SourceSpan(start_line=start_line, end_line=end_line),
            provenance=f"code_intelligence@{INDEX_VERSION}",
        )
        wrapped = delimited(content, evidence)
        if len(wrapped) > 20_000:
            raise IntelligenceError("Delimited source span exceeds budget")
        return ContextChunk(provenance=evidence, content=wrapped, token_estimate=estimate(wrapped))

    def search(
        self, ref: SnapshotRef, query: str, *, limit: int = 20, max_bytes: int = 20_000
    ) -> list[ContextChunk]:
        if (
            not query.strip()
            or len(query) > 500
            or not 1 <= limit <= 50
            or not 1 <= max_bytes <= 100_000
        ):
            raise IntelligenceError("Search requires bounded nonempty query and limit 1..50")
        index = self.store.get(ref)
        chunks: list[ContextChunk] = []
        used = 0
        for file in index.files:
            for number, line in enumerate(file.content.splitlines(), 1):
                if query.casefold() not in line.casefold():
                    continue
                chunk = self.read_chunk(ref, file.path, number, number)
                cost = len(chunk.model_dump_json().encode())
                if used + cost > max_bytes:
                    return chunks
                chunks.append(chunk)
                used += cost
                if len(chunks) == limit:
                    return chunks
        return chunks

    def affected_by_diff(
        self,
        repo_id: str,
        base_sha: str | None,
        head_sha: str,
        changed_paths: list[str] | None = None,
    ) -> ImpactSet:
        """Monitoring signature. Verified indexes take precedence over webhook path hints."""
        binding = self._binding(repo_id)
        head = self.store.find(binding.project_id, repo_id, head_sha, INDEX_VERSION)
        base = (
            self.store.find(binding.project_id, repo_id, base_sha, INDEX_VERSION)
            if base_sha
            else None
        )
        old_files = base.tree_files if base else {}
        new_files = head.tree_files
        paths = sorted(
            p for p in old_files.keys() | new_files.keys() if old_files.get(p) != new_files.get(p)
        )

        # Compare complete symbol spans rather than invalidating every symbol in a changed file.
        # Both graphs participate so removed edges and unchanged callers of changed code survive.
        def key(symbol: Symbol) -> tuple[str, str, str]:
            return symbol.path, symbol.qualified_name, symbol.kind.value

        def fingerprints(index: StoredIndex) -> dict[tuple[str, str, str], tuple[int, int, str]]:
            files = {f.path: f.content.splitlines() for f in index.files}
            return {
                key(s): (
                    s.start_line,
                    s.end_line,
                    "\n".join(files[s.path][s.start_line - 1 : s.end_line]),
                )
                for s in index.symbols
            }

        old_symbols = fingerprints(base) if base else {}
        new_symbols = fingerprints(head)
        changed_symbols = {
            k
            for k in old_symbols.keys() | new_symbols.keys()
            if old_symbols.get(k) != new_symbols.get(k)
        }
        affected: set[str] = set()
        expectations: set[str] = set()
        tests: set[str] = set()
        indexes = [base, head] if base else [head]
        logical_impact: set[tuple[str, str, str]] = set()
        for index in indexes:
            seeds = {s.id for s in index.symbols if key(s) in changed_symbols}
            expanded = neighbors(index, seeds, 1)
            logical_impact.update(key(s) for s in index.symbols if s.id in expanded)
        for index in indexes:
            impacted = {s.id for s in index.symbols if key(s) in logical_impact}
            affected.update(impacted)
            subjects = impacted | {
                e.id for e in index.entry_points if e.handler_symbol_id in impacted
            }
            for exp in index.expectations:
                if exp.subject_ref in subjects or any(e.path in paths for e in exp.sources):
                    expectations.add(exp.id)
            test_paths = {f.path for f in index.files if f.is_test}
            tests.update(s.path for s in index.symbols if s.id in impacted and s.path in test_paths)
        return ImpactSet(
            repo_id=repo_id,
            base_sha=base_sha,
            head_sha=head_sha,
            base_snapshot_id=base.ref.snapshot_id if base else None,
            head_snapshot_id=head.ref.snapshot_id,
            resolution=ImpactResolution.symbol,
            changed_paths=paths,
            symbols=sorted(affected),
            expectations=sorted(expectations),
            regression_tests=sorted(tests),
        )


def build_service() -> IntelligenceService:
    """Backend factory. Configuration contains trusted registration metadata, never target commands.

    INTELLIGENCE_REPOSITORIES_FILE: JSON list of project_id, repo_id, full_name, local_path.
    INTELLIGENCE_DB_PATH: durable local SQLite path. No implicit temporary/in-memory fallback.
    """
    config = os.environ.get("INTELLIGENCE_REPOSITORIES_FILE")
    database = os.environ.get("INTELLIGENCE_DB_PATH")
    payload_factory = os.environ.get("INTELLIGENCE_PAYLOAD_STORE_FACTORY")
    if not config or not (database or payload_factory):
        raise IntelligenceError(
            "Set INTELLIGENCE_REPOSITORIES_FILE and either "
            "INTELLIGENCE_DB_PATH or INTELLIGENCE_PAYLOAD_STORE_FACTORY"
        )
    if database and payload_factory:
        raise IntelligenceError("Choose exactly one intelligence persistence adapter")
    raw = json.loads(Path(config).read_text())
    registrations = [
        RepositoryBinding(
            project_id=item["project_id"],
            repo_id=item["repo_id"],
            full_name=item["full_name"],
            local_path=Path(item["local_path"]),
            include_prefix=item.get("include_prefix", ""),
        )
        for item in raw
    ]
    store: IndexStore
    if payload_factory:
        module_name, separator, factory_name = payload_factory.partition(":")
        if not separator or not module_name or not factory_name:
            raise IntelligenceError("Payload store factory must use module:callable syntax")
        factory = getattr(importlib.import_module(module_name), factory_name)
        store = PayloadIndexStore(cast(PayloadStore, factory()))
    else:
        assert database is not None
        store = SQLiteIndexStore(Path(database))
    return IntelligenceService(store, registrations)


def create_service(
    *,
    payload_store: PayloadStore,
    repositories: Sequence[RepositoryBinding],
    memory: MemoryStore | None = None,
) -> IntelligenceService:
    """Public host adapter: one backend-owned persistent index and annotation store."""
    return IntelligenceService(PayloadIndexStore(payload_store), repositories, memory=memory)
