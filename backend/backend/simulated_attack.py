"""Simulated attack drill for continuous defense (labelled simulation, ADR-0013).

Live production telemetry does not exist in the MVP, so the 24/7 defense leg is exercised
with a drill: Claude plays an attacker *on paper* against the connected repository's real
routes (entry points from the latest ready snapshot, and routes of open findings), and the
drill turns that plan into synthetic per-route counters. Those counters go through the real
runtime ingest and scorer (``backend.api.runtime.ingest``) with ``source="drill"``, so
detection, ``log_anomaly`` events, finding links and incident correlation are the product's
own code paths. Claude never sends traffic, never runs code and never sees the repository's
contents beyond route names; nothing in the defense response is executed.

The defense response comes from the RL policy when a checkpoint is configured, otherwise
from a small labelled rule-based responder. Either way it is a recommendation only.
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import BaseModel, Field

from backend.db import findings, repositories, snapshots, transaction
from backend.llm import build_gateway, llm_mode
from backend.worker import JobContext, PermanentJobError, handler
from shared.errors import ErrorCode
from shared.findings import Finding, FindingKind
from shared.monitoring import RouteWindow, RuntimeSignalBatch

log = logging.getLogger(__name__)

Technique = Literal["enumeration", "credential_stuffing", "bounds_abuse"]
ROUTE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) /[^\s]{0,300}$")
WINDOW = timedelta(minutes=5)
BASELINE_WINDOWS = 12
FALLBACK_ROUTES = ["GET /api/items/{item_id}", "POST /login", "POST /api/orders"]

SYSTEM = (
    "You are the red-team narrator for Ari, a security product. This is an authorized, "
    "fully simulated tabletop drill on the customer's own repository: no traffic is sent "
    "and nothing you write is executed. Choose ONE route from the list and ONE technique "
    "(enumeration, credential_stuffing or bounds_abuse) an attacker would most plausibly "
    "use against it, and describe the attack at the level of an incident report. Do not "
    "write exploit code, payloads or commands. Reply with only a JSON object: "
    '{"route": str, "technique": str, "attacker": str, "objective": str, '
    '"narrative": str (<= 500 chars), "steps": [str, ...] (3-5 short steps)}.'
)


class AttackPlan(BaseModel):
    route: str = Field(pattern=ROUTE.pattern)
    technique: Technique
    attacker: str = Field(max_length=120)
    objective: str = Field(max_length=300)
    narrative: str = Field(max_length=600)
    steps: list[str] = Field(min_length=1, max_length=6)


def candidate_routes(conn: sa.Connection, project_id: str) -> list[str]:
    """Routes of open security findings first, then entry points of the latest snapshot."""
    routes: list[str] = []
    for doc in conn.execute(
        sa.select(findings.c.doc).where(
            findings.c.project_id == project_id, findings.c.kind == FindingKind.security.value
        )
    ).scalars():
        routes += [r for r in Finding.model_validate(doc).subject_refs if ROUTE.match(r)]
    snapshot_id = conn.execute(
        sa.select(snapshots.c.id)
        .join(repositories, repositories.c.id == snapshots.c.repo_id)
        .where(repositories.c.project_id == project_id, snapshots.c.status == "ready")
        .order_by(snapshots.c.created_at.desc())
        .limit(1)
    ).scalar()
    if snapshot_id:
        try:
            from backend.intelligence import build_service, snapshot_ref
            from backend.pipeline import _paged

            for ep in _paged(build_service().entry_points, snapshot_ref(snapshot_id)):
                if ep.method and ep.path_template:
                    routes.append(f"{ep.method} {ep.path_template}")
        except Exception as exc:  # intelligence is optional for the drill
            log.warning("drill: entry points unavailable for %s: %s", project_id, exc)
    routes = [r for r in dict.fromkeys(routes) if ROUTE.match(r)]
    return routes[:40] or list(FALLBACK_ROUTES)


def _technique_for(route: str) -> Technique:
    method, _, path = route.partition(" ")
    if any(w in path.lower() for w in ("login", "auth", "token", "session", "/me")):
        return "credential_stuffing"
    if method == "POST":
        return "bounds_abuse"
    return "enumeration"


def scripted_plan(routes: list[str], seed: str) -> AttackPlan:
    """Deterministic plan used when Claude is unavailable (no key, refusal, bad output)."""
    route = sorted(routes, key=lambda r: ("{" not in r, r))[0]
    technique = _technique_for(route)
    text = {
        "enumeration": (
            "Walks sequential IDs to read other customers' records",
            "A logged-in user of one tenant scripts requests across neighbouring IDs and "
            "reads records that belong to other tenants.",
        ),
        "credential_stuffing": (
            "Replays leaked passwords against the sign-in route",
            "A botnet replays a leaked email/password list against the authentication "
            "route, hoping some customers reused passwords.",
        ),
        "bounds_abuse": (
            "Submits amounts past the allowed limit",
            "A customer repeatedly submits values just past the allowed bound to see "
            "whether the server enforces the running total.",
        ),
    }[technique]
    return AttackPlan(
        route=route,
        technique=technique,
        attacker="Scripted drill attacker",
        objective=text[0],
        narrative=text[1],
        steps=["Pick a target route", "Automate requests", "Watch which ones succeed"],
    )


def plan_attack(routes: list[str], repo: str, seed: str) -> tuple[AttackPlan, str]:
    """Claude's plan when the LLM is live and its answer validates, else the scripted one."""
    if llm_mode() == "unavailable":
        return scripted_plan(routes, seed), "scripted"
    try:
        resp = build_gateway().create_message(
            agent="attack_drill",
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Repository: {repo}\nRoutes:\n" + "\n".join(routes),
                }
            ],
            max_tokens=4000,
        )
        text = "".join(b.get("text", "") for b in resp.content if b.get("type") == "text")
        match = re.search(r"\{.*\}", text, re.S)
        plan = AttackPlan.model_validate(json.loads(match.group(0) if match else text))
        if plan.route not in routes:
            raise ValueError("route not in the candidate list")
        return plan, "claude"
    except Exception as exc:  # any provider/parse failure falls back to the scripted drill
        log.warning("drill: Claude plan unusable, using scripted plan: %s", exc)
        return scripted_plan(routes, seed), "scripted"


def traffic(plan: AttackPlan, now: datetime, seed: str) -> list[RuntimeSignalBatch]:
    """Twelve quiet five-minute windows, then the attack window, all ending by ``now``."""
    rng = random.Random(seed)
    batches = []
    for i in range(BASELINE_WINDOWS, 0, -1):
        end = now - WINDOW * i
        requests = rng.randint(54, 66)
        errors = rng.randint(0, 2)
        batches.append(
            RuntimeSignalBatch(
                source="drill",
                window_start=end - WINDOW,
                window_end=end,
                routes=[
                    RouteWindow(
                        route=plan.route,
                        requests=requests,
                        status_4xx=errors,
                        auth_failures=min(errors, rng.randint(0, 1)),
                    )
                ],
            )
        )
    spike = {
        "enumeration": dict(requests=900, status_4xx=430, auth_failures=260),
        "credential_stuffing": dict(requests=700, status_4xx=650, auth_failures=630),
        "bounds_abuse": dict(requests=420, status_4xx=150, auth_failures=0),
    }[plan.technique]
    batches.append(
        RuntimeSignalBatch(
            source="drill",
            window_start=now - WINDOW,
            window_end=now,
            routes=[RouteWindow(route=plan.route, **spike)],
        )
    )
    return batches


def rule_based_response(plan: AttackPlan, linked: list[str]) -> list[dict[str, str]]:
    route = plan.route
    actions = {
        "enumeration": [
            ("Rate-limit", f"Throttle {route} per client (e.g. 30 requests/minute)"),
            ("Enforce ownership", f"Require the caller's tenant on {route} before returning data"),
        ],
        "credential_stuffing": [
            ("Lock out", "Temporarily lock accounts after repeated failed sign-ins"),
            ("Challenge", f"Require MFA or a CAPTCHA on {route} for suspicious clients"),
        ],
        "bounds_abuse": [
            ("Validate", f"Reject requests on {route} that exceed the remaining allowed total"),
            ("Review", "Flag the accounts involved for manual review"),
        ],
    }[plan.technique]
    out = [{"action": a, "detail": d} for a, d in actions]
    if linked:
        out.append(
            {"action": "Fix the root cause", "detail": f"Ship the patch for {', '.join(linked)}"}
        )
    out.append({"action": "Alert", "detail": "Page the on-call owner with the incident"})
    return out


@handler("attack_drill")
def attack_drill(ctx: JobContext) -> dict[str, Any]:
    from backend.api.runtime import _open_findings_on, ingest

    project_id = ctx.job.payload["project_id"]
    with transaction() as conn:
        repo = conn.execute(
            sa.select(repositories.c.id, repositories.c.full_name)
            .where(repositories.c.project_id == project_id)
            .order_by(repositories.c.created_at)
            .limit(1)
        ).first()
        if repo is None:
            raise PermanentJobError(ErrorCode.VALIDATION_FAILED, "connect a repository first")
        routes = candidate_routes(conn, project_id)
    plan, author = plan_attack(routes, repo.full_name, ctx.job.id)
    now = datetime.now(UTC).replace(microsecond=0)
    detection = None
    event_ids: list[str] = []
    for batch in traffic(plan, now, ctx.job.id):
        batch = batch.model_copy(update={"repo_id": repo.id})
        ack = ingest(project_id, f"drill:{ctx.job.id}", batch)
        event_ids += ack.monitoring_event_ids
        detection = ack.scores[0]
    with transaction() as conn:
        linked = _open_findings_on(conn, project_id, plan.route)
    assert detection is not None
    detected = detection.anomaly_score >= 0.5
    return {
        "simulated": True,
        "repo": repo.full_name,
        "plan": plan.model_dump(),
        "plan_author": author,
        "detection": {
            "detected": detected,
            "anomaly_score": detection.anomaly_score,
            "reasons": detection.reasons,
            "monitoring_event_ids": event_ids,
            "linked_findings": linked,
        },
        "response": {
            "responder": "rule-based (RL policy not deployed)",
            "executed": False,
            "actions": rule_based_response(plan, linked) if detected else [],
        },
    }
