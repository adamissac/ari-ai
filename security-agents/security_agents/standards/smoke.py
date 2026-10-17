from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..checks.library import default_library
from ..contracts import Approval, AuthorizedScope, Budget, ScopeStatus, ScopeTarget, new_id
from ..intel import LocalIntel, load_expectations
from ..llm import FakeLLM, ProviderGateway
from ..sandbox.driver import LocalProcessDriver
from ..sandbox.workspace import SnapshotHandle, copy_tree
from ..workflow import Orchestrator, OrchestratorConfig
from . import registry
from .roe import coverage_table
from .validators import validate_cwe

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parent
FIXTURE = REPO_ROOT / "examples" / "payments-lite"
DEFAULT_OUT = PACKAGE_ROOT / "standards-smoke-output"
TARGET_ID = "tgt_payments_lite"


def _scope(categories: list[str]) -> AuthorizedScope:
    now = datetime.now(UTC)
    return AuthorizedScope(
        id=new_id("scp"),
        project_id="prj_standards_smoke",
        name="payments-lite sandbox (standards smoke)",
        targets=[
            ScopeTarget(
                target_id=TARGET_ID,
                repo_id="rep_payments_lite",
                build_recipe_ref="build_recipe.json",
                exposed_ports=[8000],
            )
        ],
        allowed_check_categories=categories,
        status=ScopeStatus.ACTIVE,
        requested_by="usr_requester",
        approved_by="usr_approver",
        approved_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=2),
        notes="owned demo target; standards smoke run",
    )


def _tagged(result: Any, intel: LocalIntel) -> dict[str, Any]:
    finding = result.findings[0]
    hypothesis = finding.hypothesis
    cwe = validate_cwe(hypothesis.weakness_class)
    severity = finding.severity
    verification = finding.verifications[-1] if finding.verifications else None
    return {
        "provenance": {
            "run_mode": "replay: scripted model turns from tests/fake_agents.py; real tool authorization, sandboxes, diff and tests",
            "live_model_used": False,
            "commit_sha": intel.snapshot.commit_sha,
            "snapshot_pinned_by": intel.snapshot.pinned_by,
            "assessment_state": result.state.value,
            "standards_versions": {
                name: registry.version(name) for name in ("cwe", "attack_enterprise", "d3fend", "owasp_api", "cvss31")
            },
        },
        "finding": {
            "id": finding.finding_id,
            "title": hypothesis.title,
            "status": finding.status,
            "validation_outcome": finding.validation.outcome.value if finding.validation else None,
            "validated_by_sandbox_run": finding.validation.sandbox_run_id if finding.validation else None,
        },
        "cwe": {
            "id": cwe.identifier,
            "name": cwe.name,
            "mitre_mapping_usage": cwe.mapping_usage,
            "catalog_version": cwe.catalog_version,
            "source": "official MITRE CWE catalog; identifier proposed by the model and validated by code",
        },
        "owasp_api_security_top_10": {
            "category": hypothesis.owasp_api_category,
            "title": hypothesis.owasp_api_title,
            "edition": hypothesis.owasp_api_edition,
            "mapping_kind": hypothesis.owasp_mapping_kind,
            "source": "derived by code from the CWE; never supplied by the model",
        },
        "cvss": {
            "version": severity.cvss_version,
            "vector": severity.cvss_vector,
            "base_score": severity.cvss_base_score,
            "rating": severity.cvss_rating,
            "score_kind": severity.score_kind,
            "platform_severity_level": severity.level.value,
            "level_source": severity.level_source,
            "metrics": [m.model_dump(mode="json") for m in severity.metric_evidence],
            "source": "metrics proposed by the model with evidence; vector, score, rating and level computed by code",
        },
        "attack_path": [
            {
                "order": step.order,
                "description": step.description,
                "verified": step.verified,
                "attack_technique": step.attack_technique,
                "attack_technique_name": step.attack_technique_name,
                "attack_label": step.attack_label,
            }
            for step in finding.attack_path.steps
        ],
        "d3fend": {
            "remediation_plan": {
                "technique": finding.plan.d3fend_technique,
                "label": finding.plan.d3fend_label,
                "version": finding.plan.d3fend_version,
            },
            "hardening": [
                {
                    "category": r.category,
                    "technique": r.d3fend_technique,
                    "label": r.d3fend_label,
                }
                for r in finding.recommendations
            ],
            "mapping_kind": "model proposal validated against the pinned D3FEND index",
        },
        "verification": {
            "verdict": verification.verdict if verification else None,
            "checks": {c.name.value: c.passed for c in verification.checks} if verification else {},
        },
        "regression_tests": [t.test_path for t in finding.regression_tests],
    }


def run(out_dir: Path) -> dict[str, Path]:
    sys.path.insert(0, str(PACKAGE_ROOT))
    from tests import fake_agents

    workdir = Path(tempfile.mkdtemp(prefix="standards-smoke-"))
    staging = workdir / "staging"
    copy_tree(FIXTURE / "target", staging)
    shutil.copy2(FIXTURE / "build_recipe.json", staging / "build_recipe.json")
    snapshot = SnapshotHandle.from_directory(
        staging, workdir / "snapshot", snapshot_id=new_id("snp"), repo_id="rep_payments_lite"
    )
    intel = LocalIntel(
        snapshot,
        expectations=load_expectations(
            FIXTURE / "labels.yaml",
            snapshot_id=snapshot.snapshot_id,
            commit_sha=snapshot.commit_sha,
            strip_prefix="target/",
        ),
    )
    library = default_library()
    scope = _scope(sorted(library.categories()))
    gateway = ProviderGateway(FakeLLM(fake_agents.all_scripts(snapshot.root)))
    config = OrchestratorConfig(
        assessment_id=new_id("asm"),
        project_id=scope.project_id,
        org_id="org_standards_smoke",
        scope=scope,
        target_id=TARGET_ID,
        requested_by=scope.requested_by,
        budget=Budget(max_tokens=2_000_000, max_usd=50.0, max_wall_clock_s=900.0),
        max_hypotheses_to_validate=1,
    )
    result = Orchestrator(
        config,
        intel=intel,
        gateway=gateway,
        driver=LocalProcessDriver(allow=True),
        library=library,
        workdir=workdir / "work",
        approve_remediation=lambda f: Approval(
            project_id=scope.project_id,
            subject_type="remediation",
            subject_id=f.plan.id,
            decision="approved",
            decided_by="usr_human_reviewer",
            reason="standards smoke run",
        ),
    ).run()
    if not result.findings or result.roe is None:
        raise SystemExit(f"smoke run did not produce a finding and rules of engagement (state {result.state.value})")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "tagged_finding": out_dir / "finding.tagged.json",
        "rules_of_engagement": out_dir / "rules_of_engagement.json",
        "sp_800_115_coverage": out_dir / "sp800115_coverage.json",
    }
    paths["tagged_finding"].write_text(json.dumps(_tagged(result, intel), indent=2) + "\n", encoding="utf-8")
    paths["rules_of_engagement"].write_text(
        json.dumps(result.roe.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    paths["sp_800_115_coverage"].write_text(json.dumps(coverage_table(), indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(workdir, ignore_errors=True)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="security_agents.standards.smoke")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    paths = run(args.out.resolve())
    finding = json.loads(paths["tagged_finding"].read_text(encoding="utf-8"))
    print("STANDARDS SMOKE RUN (replay fixture, no live model)")
    print(f"finding: {finding['finding']['title']} [{finding['finding']['status']}]")
    print(f"CWE: {finding['cwe']['id']} {finding['cwe']['name']} (MITRE usage {finding['cwe']['mitre_mapping_usage']})")
    owasp = finding["owasp_api_security_top_10"]
    print(f"OWASP API {owasp['edition']}: {owasp['category']} {owasp['title']} ({owasp['mapping_kind']})")
    cvss = finding["cvss"]
    print(f"CVSS: {cvss['vector']} base score {cvss['base_score']} rating {cvss['rating']} ({cvss['score_kind']})")
    print("ATT&CK: " + "; ".join(s["attack_technique"] or s["attack_label"] for s in finding["attack_path"]))
    print(f"D3FEND plan: {finding['d3fend']['remediation_plan']['technique']} {finding['d3fend']['remediation_plan']['label']}")
    print(f"verification: {finding['verification']['verdict']}")
    print("written:")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    print("  sarif: not produced yet (P1, after the M3 gate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
