from __future__ import annotations

from typing import Any

from standards.catalog import catalog_versions, load_json

SCHEMA_URI = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
TOOL_NAME = "hackatl-security-agents"
LEVEL_FROM_SEVERITY = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}
LEVEL_MAPPING_KIND = "project mapping: platform severity level to SARIF result level"


def schema() -> dict[str, Any]:
    return dict(load_json("sarif-2.1.0.json")["schema"])


def _cwe_url(cwe_id: str) -> str:
    return f"https://cwe.mitre.org/data/definitions/{cwe_id.split('-', 1)[1]}.html"


def _rule(finding: Any) -> dict[str, Any]:
    hypothesis = finding.hypothesis
    tags = ["security", hypothesis.weakness_class]
    if hypothesis.owasp_api_category:
        tags.append(f"OWASP-API-{hypothesis.owasp_api_category}")
    properties: dict[str, Any] = {
        "tags": tags,
        "cwe": {
            "id": hypothesis.weakness_class,
            "name": hypothesis.cwe_name,
            "catalog_version": hypothesis.cwe_catalog_version,
            "mitre_mapping_usage": hypothesis.cwe_mapping_usage,
        },
        "owasp_api_security_top_10": {
            "category": hypothesis.owasp_api_category,
            "title": hypothesis.owasp_api_title,
            "edition": hypothesis.owasp_api_edition,
            "mapping_kind": hypothesis.owasp_mapping_kind,
        },
    }
    severity = finding.severity
    if severity is not None and severity.cvss_base_score is not None:
        properties["security-severity"] = f"{severity.cvss_base_score:.1f}"
    return {
        "id": hypothesis.weakness_class,
        "name": (hypothesis.cwe_name or hypothesis.weakness_class)[:200],
        "shortDescription": {"text": hypothesis.cwe_name or hypothesis.weakness_class},
        "helpUri": _cwe_url(hypothesis.weakness_class),
        "properties": properties,
    }


def _locations(finding: Any) -> list[dict[str, Any]]:
    locations = []
    for ref in finding.hypothesis.cited_spans:
        if not ref.path:
            continue
        physical: dict[str, Any] = {"artifactLocation": {"uri": ref.path, "uriBaseId": "SRCROOT"}}
        if ref.span is not None:
            physical["region"] = {"startLine": ref.span.start_line, "endLine": ref.span.end_line}
        locations.append({"physicalLocation": physical})
    return locations


def _result(finding: Any, rule_index: int) -> dict[str, Any]:
    hypothesis = finding.hypothesis
    severity = finding.severity
    level = LEVEL_FROM_SEVERITY.get(severity.level.value, "warning") if severity else "warning"
    verification = finding.verifications[-1] if finding.verifications else None
    properties: dict[str, Any] = {
        "finding_id": finding.finding_id,
        "status": finding.status,
        "validation_outcome": finding.validation.outcome.value if finding.validation else None,
        "validated_by_sandbox_run": finding.validation.sandbox_run_id if finding.validation else None,
        "verification_verdict": verification.verdict if verification else None,
        "level_mapping": LEVEL_MAPPING_KIND,
    }
    if severity is not None:
        properties["severity"] = {
            "platform_level": severity.level.value,
            "level_source": severity.level_source,
            "cvss_v31": {
                "vector": severity.cvss_vector,
                "base_score": severity.cvss_base_score,
                "rating": severity.cvss_rating,
                "score_kind": severity.score_kind,
                "unverified_metrics": [
                    m.metric for m in severity.metric_evidence if m.status == "unverified"
                ],
            },
            "cvss_v40": severity.cvss.model_dump(mode="json") if severity.cvss else None,
        }
    if finding.attack_path is not None:
        properties["attack"] = [
            {
                "step": step.order,
                "technique": step.attack_technique,
                "label": step.attack_label,
            }
            for step in finding.attack_path.steps
        ]
    if finding.plan is not None:
        properties["d3fend"] = {
            "technique": finding.plan.d3fend_technique,
            "label": finding.plan.d3fend_label,
            "version": finding.plan.d3fend_version,
        }
    result: dict[str, Any] = {
        "ruleId": hypothesis.weakness_class,
        "ruleIndex": rule_index,
        "kind": "fail",
        "level": level,
        "message": {"text": hypothesis.title},
        "properties": properties,
    }
    locations = _locations(finding)
    if locations:
        result["locations"] = locations
    return result


def to_sarif(result: Any, *, commit_sha: str | None = None, run_mode: str = "replay") -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    results: list[dict[str, Any]] = []
    for finding in result.findings:
        rule_id = finding.hypothesis.weakness_class
        if rule_id not in index:
            index[rule_id] = len(rules)
            rules.append(_rule(finding))
        results.append(_result(finding, index[rule_id]))
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": TOOL_NAME,
                "semanticVersion": "0.1.0",
                "rules": rules,
            }
        },
        "results": results,
        "columnKind": "unicodeCodePoints",
        "properties": {
            "assessment_id": result.assessment_id,
            "assessment_state": result.state.value,
            "run_mode": run_mode,
            "commit_sha": commit_sha,
            "standards_versions": catalog_versions(),
            "labels": "mapped to / aligned with; no certification is claimed; CVSS is base score only (severity, not risk)",
        },
    }
    return {"$schema": SCHEMA_URI, "version": "2.1.0", "runs": [run]}


def validate(log: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft4Validator(schema()).validate(log)
