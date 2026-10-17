"""Graph expansion plus BM25 ranking; complete spans and conservative UTF-8 byte budget."""

from __future__ import annotations

import html
import math
import re
from collections import Counter, deque

from shared.base import utcnow
from shared.evidence import EvidenceRef
from shared.intelligence import ContextChunk, ContextPack, ContextPackRequest, Symbol

from code_intelligence.extract import citation
from code_intelligence.models import IntelligenceError, StoredIndex, stable_id
from code_intelligence.privacy import redact


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower())


def estimate(text: str) -> int:
    # A deliberately conservative upper bound for byte-based provider tokenizers.
    # Count the serialized pack envelope too, rather than assuming chars / 4 is safe.
    return len(text.encode("utf-8"))


def delimited(content: str, evidence: EvidenceRef) -> str:
    # XML escaping prevents repository text from terminating the data delimiter.
    return (
        '<untrusted_repository_data trust="untrusted">\n'
        + html.escape(evidence.model_dump_json(), quote=True)
        + "\n"
        + html.escape(redact(content), quote=True)
        + "\n</untrusted_repository_data>"
    )


def neighbors(index: StoredIndex, seeds: set[str], depth: int = 2) -> dict[str, int]:
    if not 0 <= depth <= 3:
        raise IntelligenceError("Graph depth must be between 0 and 3")
    adjacent: dict[str, set[str]] = {s.id: set() for s in index.symbols}
    for edge in index.calls:
        if edge.callee_id and edge.callee_id in adjacent and edge.caller_id in adjacent:
            adjacent[edge.caller_id].add(edge.callee_id)
            adjacent[edge.callee_id].add(edge.caller_id)
    distances = dict.fromkeys(seeds, 0)
    queue = deque(sorted(seeds))
    while queue:
        current = queue.popleft()
        if distances[current] >= depth:
            continue
        for target in sorted(adjacent.get(current, ())):
            if target not in distances:
                distances[target] = distances[current] + 1
                queue.append(target)
    return distances


def build_pack(
    index: StoredIndex,
    request: ContextPackRequest,
    *,
    supplements: list[tuple[set[str], str, EvidenceRef]] | None = None,
) -> ContextPack:
    if request.snapshot_ref != index.ref:
        raise IntelligenceError("Stale or mismatched context request")
    files = {f.path: f for f in index.files}
    focus = set(request.focus)
    for keys, _, _ in supplements or []:
        if focus & keys:
            focus.update(keys)
    entry_subjects = {e.id: e.handler_symbol_id for e in index.entry_points}
    seeds = {
        s.id for s in index.symbols if s.id in focus or s.qualified_name in focus or s.path in focus
    }
    for entry in index.entry_points:
        if entry.id in focus or entry.path_template in focus:
            seeds.add(entry.handler_symbol_id)
    for expectation in index.expectations:
        if expectation.id in focus:
            seeds.add(entry_subjects.get(expectation.subject_ref, expectation.subject_ref))
    distances = neighbors(index, seeds)
    query = tokens(" ".join(request.focus))
    docs = {s.id: tokens(s.qualified_name + " " + (s.docstring or "")) for s in index.symbols}
    frequency = Counter(word for terms in docs.values() for word in set(terms))
    mean_length = sum(map(len, docs.values())) / max(1, len(docs))

    def rank(symbol: Symbol) -> tuple[float, str, int]:
        terms = Counter(docs[symbol.id])
        lexical = 0.0
        for word in query:
            tf = terms[word]
            idf = math.log(1 + (len(docs) - frequency[word] + 0.5) / (frequency[word] + 0.5))
            lexical += (
                idf
                * tf
                * 2.5
                / (tf + 1.5 * (0.25 + 0.75 * len(docs[symbol.id]) / max(1, mean_length)))
            )
        graph = 20 / (1 + distances[symbol.id]) if symbol.id in distances else 0
        return (-(graph + lexical), symbol.path, symbol.start_line)

    ranked = sorted(index.symbols, key=rank)
    relevant = [s for s in ranked if s.id in distances or (query and rank(s)[0] < 0)]
    if not focus:
        entry_ids = {e.handler_symbol_id for e in index.entry_points}
        relevant = [s for s in ranked if s.id in entry_ids]
    pack = ContextPack(
        id=stable_id(
            "ctx",
            index.ref.snapshot_id,
            request.model_dump_json(),
            "\n".join(
                content + evidence.model_dump_json() for _, content, evidence in supplements or []
            ),
        ),
        snapshot_ref=index.ref,
        request=request,
        chunks=[],
        token_budget=request.token_budget,
        token_count=0,
        provenance=[],
        created_at=utcnow(),
    )
    # Tiny budgets can fail even with no chunks because the full typed envelope has a cost.
    if estimate(pack.model_dump_json()) > request.token_budget:
        raise IntelligenceError("BUDGET_EXHAUSTED: context envelope exceeds token budget")
    spans: set[tuple[str, ...]] = set()

    def append(content: str, evidence: EvidenceRef) -> bool:
        key: tuple[str, ...]
        if evidence.span is not None and evidence.path is not None:
            key = (evidence.path, str(evidence.span.start_line), str(evidence.span.end_line))
        else:
            key = (
                evidence.kind.value,
                evidence.provenance,
                evidence.artifact_id or "",
                evidence.sha256 or "",
            )
        if key in spans:
            return True
        wrapped = delimited(content, evidence)
        if len(wrapped) > 20_000:  # canonical ContextChunk.LongText
            return False
        chunk = ContextChunk(provenance=evidence, content=wrapped, token_estimate=estimate(wrapped))
        pack.chunks.append(chunk)
        pack.provenance.append(evidence)
        # Reserve bytes for the token_count integer itself.
        cost = estimate(pack.model_dump_json()) + 12
        if cost > request.token_budget:
            pack.chunks.pop()
            pack.provenance.pop()
            return False
        spans.add(key)
        pack.token_count = cost
        return True

    relevant_keys = {
        key for symbol in relevant for key in (symbol.id, symbol.qualified_name, symbol.path)
    }
    relevant_keys.update(
        entry.id for entry in index.entry_points if entry.handler_symbol_id in relevant_keys
    )
    for keys, content, evidence in supplements or []:
        if not request.focus or keys & relevant_keys or keys & set(request.focus):
            append(content, evidence)

    for symbol in relevant:
        # Modules can span an entire repository file. Include them only as explicit focus.
        if symbol.kind.value == "module" and symbol.id not in seeds:
            continue
        source = files[symbol.path].content.splitlines()
        metadata = [f"Symbol {symbol.id}: {symbol.qualified_name}"]
        for exp in index.expectations:
            if entry_subjects.get(exp.subject_ref, exp.subject_ref) == symbol.id:
                metadata.append(
                    f"Expectation {exp.id} [{exp.status.value}; {exp.origin.value}; "
                    f"confidence={exp.confidence}]: {exp.statement}"
                )
        append(
            "\n".join(metadata) + "\n" + "\n".join(source[symbol.start_line - 1 : symbol.end_line]),
            citation(index.ref, symbol),
        )
        for expectation in index.expectations:
            if entry_subjects.get(expectation.subject_ref, expectation.subject_ref) != symbol.id:
                continue
            for evidence in expectation.sources:
                if evidence.path not in files or evidence.span is None:
                    continue
                content = (
                    "Expected behavior ("
                    + expectation.status.value
                    + "; "
                    + str(expectation.confidence)
                    + "): "
                    + expectation.statement
                    + "\n"
                )
                content += "\n".join(
                    files[evidence.path].content.splitlines()[
                        evidence.span.start_line - 1 : evidence.span.end_line
                    ]
                )
                append(content, evidence)
        # Ensure statically linked tests are candidates even if their names differ from query.
        # They appear in distances via call edges and retain their whole symbol spans.
    if relevant and not any(c.provenance.path and c.provenance.span for c in pack.chunks):
        raise IntelligenceError("BUDGET_EXHAUSTED: no complete relevant span fits")
    pack.token_count = estimate(pack.model_dump_json()) + 12
    if pack.token_count > request.token_budget:
        raise IntelligenceError("BUDGET_EXHAUSTED")
    return pack
