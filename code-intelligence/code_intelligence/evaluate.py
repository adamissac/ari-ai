"""Read-only M1 evidence export for an explicitly registered, owned local Git target."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import tempfile
import time
from collections import Counter
from pathlib import Path

from shared.intelligence import ContextPackRequest, ContextPurpose

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.models import INDEX_VERSION
from code_intelligence.store import SQLiteIndexStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--focus", default="/payments/{payment_id}")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="intel-evaluation-") as workspace:
        store = SQLiteIndexStore(Path(workspace) / "index.sqlite")
        binding = RepositoryBinding(
            "prj_evaluation00", "rep_evaluation00", "owned/evaluation", args.repository, args.prefix
        )
        service = IntelligenceService(store, [binding])
        started = time.perf_counter()
        ref = service.index_repository(binding.project_id, binding.repo_id, args.sha)
        elapsed = time.perf_counter() - started
        index = store.get(ref)
        pack = service.build_context_pack(
            ContextPackRequest(
                snapshot_ref=ref,
                purpose=ContextPurpose.scout,
                focus=[args.focus],
                token_budget=24_000,
            )
        )
        # Compare facts without wall-clock metadata; repeated indexing must not change IDs/edges.
        facts = json.dumps(
            dict(
                symbols=[s.model_dump(mode="json") for s in index.symbols],
                calls=[c.model_dump(mode="json") for c in index.calls],
            ),
            sort_keys=True,
        )
        result = dict(
            index_version=INDEX_VERSION,
            target_sha=args.sha,
            tree_sha=index.tree_sha,
            include_prefix=args.prefix,
            python=platform.python_version(),
            stats=index.snapshot.stats.model_dump(mode="json"),
            source_paths=[f.path for f in index.files],
            call_resolution_counts=dict(Counter(c.resolution.value for c in index.calls)),
            extracted_expectation_statuses=dict(
                Counter(e.status.value for e in index.expectations)
            ),
            declared_routes=[e.model_dump(mode="json") for e in index.entry_points],
            issues=[issue.model_dump() for issue in index.issues],
            facts_sha256=hashlib.sha256(facts.encode()).hexdigest(),
            index_seconds=elapsed,
            context=dict(
                id=pack.id,
                chunks=len(pack.chunks),
                token_count=pack.token_count,
                budget=pack.token_budget,
                focus=args.focus,
                paths=sorted({p.path for p in pack.provenance if p.path is not None}),
            ),
            caveats=[
                "No target code or target tests executed.",
                "Static route declarations are not proof of runtime reachability.",
                "Extracted expectations are unverified intent, not security verdicts.",
                "Single local timing is not a throughput benchmark.",
            ],
        )
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.pack.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2) + "\n")
        args.pack.write_text(pack.model_dump_json(indent=2) + "\n")
        print(
            json.dumps(
                dict(
                    stats=result["stats"],
                    context=result["context"],
                    target_sha=args.sha,
                    facts_sha256=result["facts_sha256"],
                )
            )
        )


if __name__ == "__main__":
    main()
