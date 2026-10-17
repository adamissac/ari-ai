"""Worker job handlers: GitHub delivery -> monitoring event -> reassessment, assessment
runs (hosting the security-agents orchestrator), and RL recommendations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import sqlalchemy as sa

from backend import audit
from backend.artifacts import ArtifactStore
from backend.db import (
    defense_recommendations,
    findings,
    monitoring_events,
    reassessment_requests,
    repositories,
    transaction,
    webhook_deliveries,
)
from backend.host import AssessmentHost, HostError
from backend.integrations import load_factory
from backend.llm import LLMError
from backend.services import (
    active_scope_for_repo,
    create_assessment,
    monitoring_assessment_state,
    project_org,
    project_settings,
    verified_finding_paths,
)
from backend.settings import get_settings
from backend.worker import JobCancelled, JobContext, PermanentJobError, handler
from monitoring.api import Action, Ignored, correlate, decide, normalize_github
from shared.assessment import TERMINAL_STATES, AssessmentState, AssessmentTrigger
from shared.audit import ActorType
from shared.base import utcnow
from shared.errors import ErrorCode
from shared.findings import FindingKind
from shared.ids import IdPrefix, new_id
from shared.monitoring import (
    CommitRange,
    EventSource,
    EventStatus,
    EventType,
    MonitoringEvent,
    ReassessmentRequest,
    ReassessmentScope,
    ReassessmentStatus,
)
from shared.rl import DefenseRecommendation, PlatformFacts, RLExplanation

log = logging.getLogger("backend.pipeline")


# ----------------------------------------------------------- GitHub deliveries


def _impact_provider() -> tuple[Any | None, str | None]:
    loaded = load_factory(get_settings().code_intelligence_factory)
    if loaded.obj is None or not hasattr(loaded.obj, "affected_by_diff"):
        return None, loaded.reason or "code_intelligence service lacks affected_by_diff"
    return loaded.obj, None


@handler("process_github_delivery")
def process_github_delivery(ctx: JobContext) -> dict[str, Any]:
    delivery_id = ctx.job.payload["delivery_id"]
    store = ArtifactStore()
    with transaction() as conn:
        d = (
            conn.execute(
                sa.select(webhook_deliveries).where(webhook_deliveries.c.delivery_id == delivery_id)
            )
            .mappings()
            .first()
        )
        if d is None:
            raise PermanentJobError(ErrorCode.NOT_FOUND, f"delivery {delivery_id} not found")
        dedupe = f"github:delivery:{delivery_id}"
        done = conn.execute(
            sa.select(monitoring_events.c.id, monitoring_events.c.status).where(
                monitoring_events.c.dedupe_key == dedupe
            )
        ).first()
        if done is not None and done.status in (
            EventStatus.processed.value,
            EventStatus.ignored.value,
        ):
            return {"monitoring_event_id": done.id, "idempotent_replay": True}
        _, raw = store.get(conn, d["payload_artifact_id"])
    payload = json.loads(raw)
    change = normalize_github(d["event_name"], payload)
    if isinstance(change, Ignored):
        return {"ignored": change.reason}

    with transaction() as conn:
        repo = (
            conn.execute(
                sa.select(repositories).where(repositories.c.full_name == change.repo_full_name)
            )
            .mappings()
            .first()
        )
    if repo is None:
        return {"ignored": f"repository {change.repo_full_name} is not connected"}

    paths_complete = change.paths_complete
    changed_paths = list(change.changed_paths)
    notes = list(change.notes)
    if not paths_complete and change.base_sha and repo["installation_id"]:
        try:
            from backend.github import GitHubApp

            changed_paths, paths_complete = GitHubApp().compare_paths(
                repo["installation_id"], repo["full_name"], change.base_sha, change.head_sha
            )
            notes.append("changed paths fetched via GitHub compare API")
        except Exception as exc:  # degrade to full reassessment, never guess
            notes.append(
                f"compare API unavailable ({type(exc).__name__}); treating path list as incomplete"
            )
    if changed_paths != list(change.changed_paths):
        from dataclasses import replace

        change = replace(change, changed_paths=tuple(changed_paths), paths_complete=paths_complete)

    ctx.check_cancelled()
    provider, why = _impact_provider()
    impact, degraded = correlate(repo["id"], change, provider)
    for n in (why if provider is None else None, degraded):
        if n:
            notes.append(n)

    with transaction() as conn:
        project_id = repo["project_id"]
        policy = project_settings(conn, project_id).monitoring_policy
        scope = active_scope_for_repo(conn, project_id, repo["id"])
        open_, since = monitoring_assessment_state(conn, repo["id"])
        decision = decide(
            impact,
            policy=policy,
            paths_complete=paths_complete,
            has_active_scope=scope is not None,
            verified_finding_paths=verified_finding_paths(conn, project_id),
            seconds_since_last_monitoring_assessment=since,
            open_monitoring_assessment=open_,
        )
        now = utcnow()
        event = MonitoringEvent(
            id=new_id(IdPrefix.evt),
            project_id=project_id,
            repo_id=repo["id"],
            source=EventSource.github,
            type=EventType(change.event),
            occurred_at=change.occurred_at,
            received_at=d["received_at"],
            dedupe_key=dedupe,
            payload_artifact_id=d["payload_artifact_id"],
            commit_range=CommitRange(base_sha=change.base_sha, head_sha=change.head_sha),
            ref=change.ref,
            pr_number=change.pr_number,
            simulated=bool(ctx.job.payload.get("simulated", False)),
            status=EventStatus.processed
            if decision.action is not Action.record_only
            else EventStatus.ignored,
            status_reason=(decision.reason + ("; " + "; ".join(notes) if notes else ""))[:500],
            impact=impact,
        )
        inserted = conn.execute(
            sa.dialects.postgresql.insert(monitoring_events)
            .values(
                id=event.id,
                project_id=project_id,
                repo_id=repo["id"],
                dedupe_key=dedupe,
                status=event.status.value,
                doc=event.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=[monitoring_events.c.dedupe_key])
            .returning(monitoring_events.c.id)
        ).scalar()
        if inserted is None:
            return {"idempotent_replay": True}
        result: dict[str, Any] = {
            "monitoring_event_id": event.id,
            "decision": decision.action.value,
            "reason": decision.reason,
        }
        if decision.action is not Action.record_only:
            status = {
                Action.assess: ReassessmentStatus.started,
                Action.blocked_no_scope: ReassessmentStatus.blocked_no_scope,
                Action.coalesced: ReassessmentStatus.coalesced,
            }[decision.action]
            rrq = ReassessmentRequest(
                id=new_id(IdPrefix.rrq),
                project_id=project_id,
                repo_id=repo["id"],
                event_ids=[event.id],
                scope=decision.scope or ReassessmentScope.targeted,
                head_sha=change.head_sha,
                targets=list(decision.targets or decision.regression_finding_ids),
                status=status,
                reason=decision.reason,
                created_at=now,
            )
            if decision.action is Action.assess and scope is not None:
                asm, _ = create_assessment(
                    conn,
                    project_id=project_id,
                    repo_id=repo["id"],
                    scope_id=scope.id,
                    commit_sha=change.head_sha,
                    trigger=AssessmentTrigger.monitoring,
                    budget=None,
                    created_by=None,
                    reassessment_request_id=rrq.id,
                )
                rrq = rrq.model_copy(update={"assessment_id": asm.id})
                result["assessment_id"] = asm.id
            conn.execute(
                sa.insert(reassessment_requests).values(
                    id=rrq.id,
                    project_id=project_id,
                    repo_id=repo["id"],
                    status=rrq.status.value,
                    doc=rrq.model_dump(mode="json"),
                )
            )
            result["reassessment_request_id"] = rrq.id
        audit.record(
            conn,
            org_id=project_org(conn, project_id),
            project_id=project_id,
            actor_type=ActorType.github,
            actor_id=change.sender or "github",
            action="monitoring.event_processed",
            subject_type="monitoring_event",
            subject_id=event.id,
            details={
                "delivery_id": delivery_id,
                "decision": decision.action.value,
                "head_sha": change.head_sha,
                "impact_resolution": impact.resolution.value,
            },
        )
    return result


# ------------------------------------------------------------------ assessments


@handler("run_assessment")
def run_assessment(ctx: JobContext) -> dict[str, Any]:
    asm_id = ctx.job.payload["assessment_id"]
    host = AssessmentHost(asm_id, job_ctx=ctx)
    a = host.assessment
    if a.state in TERMINAL_STATES:
        return {"state": a.state.value, "noop": True}
    try:
        if a.state is AssessmentState.CREATED:
            host.transition(AssessmentState.SCOPE_CHECK, "checking authorized scope")
            host.require_active_scope()
        loaded = load_factory(get_settings().orchestrator_factory)
        if loaded.obj is None:
            host.terminate(
                AssessmentState.FAILED,
                ErrorCode.SUBSYSTEM_UNAVAILABLE,
                f"security-agents orchestrator unavailable: {loaded.reason}",
            )
            return {"state": "FAILED", "reason": loaded.reason}
        loaded.obj.run(host)
    except (HostError, LLMError) as exc:
        state = {
            ErrorCode.CANCELLED: AssessmentState.CANCELLED,
            ErrorCode.BUDGET_EXHAUSTED: AssessmentState.BUDGET_EXHAUSTED,
        }.get(exc.code, AssessmentState.FAILED)
        if host.assessment.state not in TERMINAL_STATES:
            host.terminate(state, exc.code, str(exc))
        return {"state": host.assessment.state.value, "error_code": exc.code.value}
    except JobCancelled:
        if host.assessment.state not in TERMINAL_STATES:
            host.terminate(AssessmentState.CANCELLED, ErrorCode.CANCELLED, "job cancelled")
        raise
    except Exception as exc:
        # Agent work is not blindly re-run (side effects already recorded); fail visibly.
        log.exception("orchestrator crashed for %s", asm_id)
        if host.assessment.state not in TERMINAL_STATES:
            host.terminate(
                AssessmentState.FAILED,
                ErrorCode.INTERNAL,
                f"orchestrator error: {type(exc).__name__}: {exc}",
            )
        raise PermanentJobError(ErrorCode.INTERNAL, str(exc)) from exc
    final = host.assessment.state
    if final not in TERMINAL_STATES and final is not AssessmentState.AWAITING_APPROVAL:
        host.terminate(
            AssessmentState.FAILED,
            ErrorCode.CONFLICT_STATE,
            f"orchestrator returned in non-terminal state {final.value}",
        )
    return {"state": host.assessment.state.value}


# --------------------------------------------------------------------------- RL

_ROUTE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) /\S*$")


def platform_facts(
    conn: sa.engine.Connection, project_id: str
) -> tuple[PlatformFacts, dict[str, Any]]:
    """Build PlatformFacts with rl_defense.platform_mapping (Adam) from persisted findings.

    Only route-shaped ``Finding.subject_refs`` ("METHOD /path") map onto simulator nodes;
    the route->node topology is the per-project config at RL_TOPOLOGY_PATH. Runtime
    signals are the latest scored windows from /ingest/runtime (labeled runtime_demo /
    replay / simulated; there is no production telemetry in MVP).
    """
    from rl_defense import platform_mapping as pm
    from shared.findings import Finding

    topo_path = get_settings().rl_topology_path
    if not topo_path or not topo_path.exists():
        raise PermanentJobError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "RL_TOPOLOGY_PATH not set or missing"
        )
    topology = pm.load_topology(topo_path)
    inputs = []
    for doc in conn.execute(
        sa.select(findings.c.doc).where(
            findings.c.project_id == project_id, findings.c.kind == FindingKind.security.value
        )
    ).scalars():
        f = Finding.model_validate(doc)
        routes = tuple(r for r in f.subject_refs if _ROUTE.match(r))
        if routes:
            inputs.append(
                pm.FindingInput(
                    id=f.id,
                    status=f.status.value,
                    severity=f.severity.level.value if f.severity else None,
                    routes=routes,
                )
            )
    from backend.api.runtime import latest_route_signals

    signals = [pm.RouteSignal(**sig) for sig in latest_route_signals(conn, project_id)]
    facts, provenance = pm.facts_from_platform(topology, inputs, [], signals, project_id=project_id)
    return PlatformFacts.model_validate(facts.model_dump(mode="json")), provenance


@handler("rl_recommend")
def rl_recommend(ctx: JobContext) -> dict[str, Any]:
    settings = get_settings()
    project_id = ctx.job.payload["project_id"]
    if not settings.rl_checkpoint_path or not settings.rl_checkpoint_path.exists():
        raise PermanentJobError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "RL_CHECKPOINT_PATH not set or missing"
        )
    try:
        from rl_defense import api as rl_api
    except ModuleNotFoundError as exc:
        raise PermanentJobError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "rl_defense not installed in this worker"
        ) from exc
    provenance: dict[str, Any] = {"source": "request"}
    with transaction() as conn:
        if ctx.job.payload.get("facts"):
            facts = PlatformFacts.model_validate(ctx.job.payload["facts"])
        else:
            facts, provenance = platform_facts(conn, project_id)
    local_facts = rl_api.PlatformFacts.model_validate(facts.model_dump(mode="json"))
    runner = rl_api.load_policy(settings.rl_checkpoint_path)
    rec = DefenseRecommendation.model_validate(
        runner.recommend(local_facts).model_dump(mode="json")
    )
    explanation = None
    if hasattr(runner, "explain"):
        try:
            raw = runner.explain(local_facts).model_dump(mode="json")
            explanation = RLExplanation.model_validate({**raw, "recommendation_id": rec.id})
        except Exception:  # an explanation is optional; never block the recommendation
            log.exception("rl explanation failed for %s", rec.id)
    with transaction() as conn:
        conn.execute(
            sa.insert(defense_recommendations).values(
                id=rec.id,
                project_id=project_id,
                doc=rec.model_dump(mode="json"),
                explanation=explanation.model_dump(mode="json") if explanation else None,
            )
        )
        audit.record(
            conn,
            org_id=project_org(conn, project_id),
            project_id=project_id,
            actor_type=ActorType.system,
            actor_id="rl_defense",
            action="rl.recommendation_created",
            subject_type="defense_recommendation",
            subject_id=rec.id,
            details={
                "policy_version": rec.policy_version,
                "action": rec.action,
                "node": rec.node,
                "facts_provenance": provenance,
            },
        )
    return {
        "recommendation_id": rec.id,
        "facts_provenance": provenance,
        "explained": explanation is not None,
    }


# ------------------------------------------------------------------- snapshots


@handler("index_snapshot")
def index_snapshot(ctx: JobContext) -> dict[str, Any]:
    """Delegate indexing to code_intelligence (Sarosh); persist its Snapshot verbatim.

    Expected interface: ``service.index_snapshot(snapshot: Snapshot, repo_full_name: str) -> Snapshot``.
    """
    from backend.db import snapshots
    from shared.intelligence import Snapshot, SnapshotStatus

    snap_id = ctx.job.payload["snapshot_id"]
    with transaction() as conn:
        row = conn.execute(sa.select(snapshots).where(snapshots.c.id == snap_id)).mappings().one()
        full_name = conn.execute(
            sa.select(repositories.c.full_name).where(repositories.c.id == row["repo_id"])
        ).scalar_one()
    snap = Snapshot.model_validate(row["doc"])
    loaded = load_factory(get_settings().code_intelligence_factory)
    if loaded.obj is None or not hasattr(loaded.obj, "index_snapshot"):
        reason = loaded.reason or "code_intelligence service lacks index_snapshot"
        failed = snap.model_copy(
            update={
                "status": SnapshotStatus.failed,
                "error_message": f"SUBSYSTEM_UNAVAILABLE: {reason}"[:500],
            }
        )
        with transaction() as conn:
            conn.execute(
                sa.update(snapshots)
                .where(snapshots.c.id == snap_id)
                .values(status=failed.status.value, doc=failed.model_dump(mode="json"))
            )
        return {"status": "failed", "reason": reason}
    result = Snapshot.model_validate(loaded.obj.index_snapshot(snap, full_name))
    if (
        result.id != snap.id
        or result.commit_sha != snap.commit_sha
        or result.repo_id != snap.repo_id
    ):
        raise PermanentJobError(
            ErrorCode.SCHEMA_INVALID, "indexer returned a snapshot for a different SHA/repo"
        )
    with transaction() as conn:
        conn.execute(
            sa.update(snapshots)
            .where(snapshots.c.id == snap_id)
            .values(
                status=result.status.value,
                index_version=result.index_version,
                doc=result.model_dump(mode="json"),
            )
        )
    return {"status": result.status.value}
