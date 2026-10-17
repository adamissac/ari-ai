from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import Field
from standards.catalog import load_json

from ..contracts import AgentName, AuthorizedScope, ScopeStatus, StrictModel

ALIGNMENT = "aligned with NIST SP 800-115 Appendix B (project mapping)"

PERMITTED_AGENTS: tuple[AgentName, ...] = (AgentName.PROBE, AgentName.VERIFY)

PROHIBITED_ACTIONS: tuple[str, ...] = (
    "Any target that is not listed in this document, including external hosts, URLs and IP addresses",
    "Free-form payloads, scripts or commands authored by a model",
    "Check templates that are not listed in this document or are not marked reviewed",
    "Destructive or state-changing actions outside the ephemeral sandbox target",
    "Denial-of-service, load or resource-exhaustion testing",
    "Social engineering, phishing or any test aimed at people",
    "Use of real credentials, customer data or production secrets",
    "Persistence, lateral movement or privilege escalation beyond the documented check",
    "Opening pull requests, merging or deploying changes",
)

STOP_CONDITIONS: tuple[str, ...] = (
    "The authorized scope is revoked, expires or changes after this document was issued",
    "The global kill switch pauses assessments",
    "Any tool call is denied by the scope guard or by this document",
    "A sandbox exceeds its time, memory, process or output limits",
    "The assessment budget is exhausted",
    "A human cancels the assessment",
)

DATA_HANDLING: tuple[str, ...] = (
    "Targets run only inside an isolated sandbox built from the owned repository",
    "Only synthetic fixture identities and seeded data are used",
    "Secrets are never placed in prompts, sandboxes or stored transcripts; stored output is redacted",
    "Check evidence records status codes and counts, not response bodies",
    "Sandboxes are removed after results are collected",
)

ASSUMPTIONS: tuple[str, ...] = (
    "The target is a sandbox build of a repository the requesting organization owns",
    "The sandbox driver enforces network isolation independently of this document",
    "Check templates run in the check-runner profile with the target attached only through the sandbox",
)

RISKS: tuple[str, ...] = (
    "A check could change state in the ephemeral target; mitigated by a fresh target per run",
    "A model could request an unlisted target or template; mitigated by deterministic guards before execution",
    "The local development sandbox driver is not a security boundary; mitigated by restricting it to owned fixtures",
)


class RoeTarget(StrictModel):
    target_id: str
    kind: str
    build_recipe_ref: str


class RulesOfEngagement(StrictModel):
    id: str
    scope_id: str
    scope_digest: str
    project_id: str
    purpose: str
    targets: list[RoeTarget] = Field(min_length=1)
    requested_by: str
    approved_by: str
    approved_at: datetime
    valid_from: datetime
    valid_until: datetime
    permitted_agents: list[AgentName]
    permitted_check_templates: list[str]
    permitted_check_categories: list[str]
    test_site: str
    test_equipment: str
    prohibited_actions: list[str]
    stop_conditions: list[str]
    data_handling: list[str]
    assumptions: list[str]
    risks: list[str]
    audit_event_ids: list[str]
    alignment: str = ALIGNMENT
    reference: dict[str, str]
    digest: str = ""


RoeReason = Literal[
    "OK",
    "MISSING_ROE",
    "ROE_SCOPE_MISMATCH",
    "ROE_STALE",
    "ROE_NOT_YET_VALID",
    "ROE_EXPIRED",
    "ROE_TARGET_NOT_LISTED",
    "ROE_TEMPLATE_NOT_PERMITTED",
    "ROE_AGENT_NOT_PERMITTED",
    "ROE_SCOPE_NOT_ACTIVE",
    "ROE_DIGEST_MISMATCH",
]


class RoeDecision(StrictModel):
    allowed: bool
    reason: RoeReason
    roe_id: str | None
    detail: str = ""


class RoeError(ValueError):
    pass


def scope_digest(scope: AuthorizedScope) -> str:
    material = {
        "id": scope.id,
        "project_id": scope.project_id,
        "status": scope.status.value,
        "targets": [target.model_dump(mode="json") for target in scope.targets],
        "allowed_check_categories": sorted(scope.allowed_check_categories),
        "requested_by": scope.requested_by,
        "approved_by": scope.approved_by,
        "approved_at": scope.approved_at.isoformat() if scope.approved_at else None,
        "expires_at": scope.expires_at.isoformat(),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _document_digest(roe: RulesOfEngagement) -> str:
    body = roe.model_dump(mode="json", exclude={"digest"})
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def build_roe(
    scope: AuthorizedScope,
    templates: list[dict[str, Any]],
    *,
    audit_event_ids: list[str] | None = None,
    test_equipment: str = "security_agents sandbox driver, check-runner profile",
) -> RulesOfEngagement:
    if scope.status is not ScopeStatus.ACTIVE:
        raise RoeError(f"cannot issue rules of engagement for a {scope.status.value} scope")
    if not scope.approved_by or scope.approved_at is None:
        raise RoeError("cannot issue rules of engagement for an unapproved scope")
    permitted = sorted(
        template["ref"]
        for template in templates
        if template.get("runnable")
        and template.get("category") in scope.allowed_check_categories
        and template.get("side_effect_class") in ("read_only", "ephemeral_target_only")
    )
    reference = load_json("nist-sp800-115.json")
    roe = RulesOfEngagement(
        id=f"roe_{scope_digest(scope)[:24]}",
        scope_id=scope.id,
        scope_digest=scope_digest(scope),
        project_id=scope.project_id,
        purpose=(
            "Validate hypotheses about weaknesses in an owned application with reviewed, "
            "non-destructive checks against a sandbox build, and verify candidate fixes."
        ),
        targets=[
            RoeTarget(
                target_id=target.target_id,
                kind=target.kind,
                build_recipe_ref=target.build_recipe_ref,
            )
            for target in scope.targets
        ],
        requested_by=scope.requested_by,
        approved_by=scope.approved_by,
        approved_at=scope.approved_at,
        valid_from=scope.approved_at,
        valid_until=scope.expires_at,
        permitted_agents=list(PERMITTED_AGENTS),
        permitted_check_templates=permitted,
        permitted_check_categories=sorted(scope.allowed_check_categories),
        test_site="Isolated sandbox network containing only the scoped target; no egress",
        test_equipment=test_equipment,
        prohibited_actions=list(PROHIBITED_ACTIONS),
        stop_conditions=list(STOP_CONDITIONS),
        data_handling=list(DATA_HANDLING),
        assumptions=list(ASSUMPTIONS),
        risks=list(RISKS),
        audit_event_ids=sorted(audit_event_ids or []),
        reference={
            "standard": "NIST SP 800-115",
            "title": reference.get("title", ""),
            "status_on_csrc": reference.get("status_on_csrc", ""),
            "date_published": reference.get("date_published", ""),
            "section": "Appendix B, Rules of Engagement Template",
        },
    )
    return roe.model_copy(update={"digest": _document_digest(roe)})


def check_roe(
    roe: RulesOfEngagement | None,
    scope: AuthorizedScope | None,
    now: datetime,
    *,
    agent: AgentName,
    target_id: str | None,
    template_ref: str | None,
) -> RoeDecision:
    def deny(reason: RoeReason, detail: str = "") -> RoeDecision:
        return RoeDecision(allowed=False, reason=reason, roe_id=roe.id if roe else None, detail=detail[:300])

    if roe is None:
        return deny("MISSING_ROE", "no rules of engagement issued for this assessment")
    if roe.digest != _document_digest(roe):
        return deny("ROE_DIGEST_MISMATCH", "the rules of engagement document was altered after issue")
    if scope is None or roe.scope_id != scope.id:
        return deny("ROE_SCOPE_MISMATCH", "rules of engagement are not tied to the active scope")
    if scope.status is not ScopeStatus.ACTIVE:
        return deny("ROE_SCOPE_NOT_ACTIVE", f"scope is {scope.status.value}")
    if roe.scope_digest != scope_digest(scope):
        return deny("ROE_STALE", "the scope changed after these rules of engagement were issued")
    if now < roe.valid_from:
        return deny("ROE_NOT_YET_VALID")
    if now >= roe.valid_until:
        return deny("ROE_EXPIRED")
    if agent not in roe.permitted_agents:
        return deny("ROE_AGENT_NOT_PERMITTED", f"agent={agent.value}")
    if target_id is None or target_id not in {target.target_id for target in roe.targets}:
        return deny("ROE_TARGET_NOT_LISTED", f"target={str(target_id)[:80]}")
    if template_ref is not None and template_ref not in roe.permitted_check_templates:
        return deny("ROE_TEMPLATE_NOT_PERMITTED", f"template={template_ref[:80]}")
    return RoeDecision(allowed=True, reason="OK", roe_id=roe.id)


Coverage = Literal["covered", "partial", "not covered", "not applicable"]

APPENDIX_B_COVERAGE: dict[str, tuple[Coverage, str]] = {
    "1": ("covered", "document sections below"),
    "1.1": ("covered", "purpose"),
    "1.2": ("covered", "targets, permitted_check_templates, permitted_check_categories"),
    "1.3": ("covered", "assumptions"),
    "1.4": ("partial", "risks lists fixed platform risks; no per-engagement risk analysis"),
    "1.5": ("partial", "the artifact is a fixed schema rather than a described document structure"),
    "2": ("covered", "logistics fields below"),
    "2.1": ("partial", "requested_by and approved_by; no named test team or incident response contacts"),
    "2.2": ("covered", "valid_from and valid_until, taken from the approved scope window"),
    "2.3": ("covered", "test_site"),
    "2.4": ("covered", "test_equipment"),
    "3": ("partial", "communication is through audit events and progress events only"),
    "3.1": ("not covered", "no communication plan or escalation contacts are recorded"),
    "3.2": ("partial", "stop_conditions halt testing; no incident response procedure is defined"),
    "4": ("covered", "targets with build recipe references"),
    "5": ("covered", "permitted agents and templates"),
    "5.1": ("not applicable", "nontechnical testing is prohibited by prohibited_actions"),
    "5.2": ("covered", "permitted_check_templates (reviewed, non-destructive)"),
    "5.3": ("covered", "data_handling"),
    "6": ("partial", "audit_event_ids and the assessment report; no separate test report template"),
    "7": ("partial", "approved_by and approved_at record a digital approval, not a signature"),
}

PLANNING_COVERAGE: dict[str, tuple[Coverage, str]] = {
    "6.1": ("not covered", "no organizational security assessment policy is modeled"),
    "6.2": ("partial", "hypotheses are ranked and capped per assessment; no assessment calendar"),
    "6.3": ("covered", "techniques are a reviewed, versioned check-template library selected per hypothesis"),
    "6.4": ("partial", "test site and equipment are recorded; assessor selection is not modeled"),
    "6.5": ("partial", "the rules of engagement artifact and the assessment state machine form the plan"),
    "6.6": ("partial", "human scope approval is required; no legal review step is modeled"),
    "6.7": ("not applicable", "summary section"),
}


def coverage_table() -> list[dict[str, str]]:
    reference = load_json("nist-sp800-115.json")
    rows: list[dict[str, str]] = []
    for group, entries, coverage in (
        ("Section 6 planning", reference.get("planning_sections", []), PLANNING_COVERAGE),
        ("Appendix B rules of engagement", reference.get("roe_template_sections", []), APPENDIX_B_COVERAGE),
    ):
        for entry in entries:
            status, where = coverage.get(entry["section"], ("not covered", "not assessed"))
            rows.append(
                {
                    "group": group,
                    "section": entry["section"],
                    "title": entry["title"],
                    "status": status,
                    "where": where,
                }
            )
    return rows
