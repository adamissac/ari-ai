"""Pilot rehearsal, unfamiliar-repo leg: execute the reviewed ownership check
against examples/inventory-lite through the real Probe check path
(default_registry -> checks.run_template -> CheckRunner -> driver -> rendered
pytest in the check-runner sandbox).

inventory-lite was authored after the scripted fixtures were fixed, so nothing in
the check code is shaped around it: the planted CWE-639-class ownership defect on
GET /items/{item_id} must be *confirmed by execution*, and the guarded sibling
GET /warehouses/{workspace_id} must be refuted. Same code the orchestrator's
Probe invokes; only the agent's model turns are absent.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from security_agents.checks.library import default_library
from security_agents.contracts import AgentName, AuthorizedScope, ScopeStatus, ScopeTarget
from security_agents.intel import FindingsHistory, LocalIntel
from security_agents.sandbox.driver import LocalProcessDriver
from security_agents.sandbox.workspace import SnapshotHandle, copy_tree
from security_agents.scope_guard import Decision
from security_agents.standards.roe import build_roe
from security_agents.tools import CheckRunner, default_registry, recipe_from_snapshot, wire_name
from security_agents.tools.registry import ToolContext

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_LITE_DIR = REPO_ROOT / "examples" / "inventory-lite"
INVENTORY_LITE = INVENTORY_LITE_DIR / "target"  # the platform indexes target/ only
BUILD_RECIPE = INVENTORY_LITE_DIR / "build_recipe.json"
TARGET_ID = "tgt_inventory_lite"


@pytest.fixture
def inventory_snapshot(tmp_path: Path) -> SnapshotHandle:
    assert INVENTORY_LITE.is_dir(), f"missing rehearsal fixture target at {INVENTORY_LITE}"
    staging = tmp_path / "staging"
    copy_tree(INVENTORY_LITE, staging)
    shutil.copy2(BUILD_RECIPE, staging / "build_recipe.json")
    return SnapshotHandle.from_directory(
        staging, tmp_path / "snapshot", snapshot_id="snp_rehearsal", repo_id="rep_inventory_lite"
    )


@pytest.fixture
def inventory_ctx(inventory_snapshot: SnapshotHandle) -> ToolContext:
    library = default_library()
    intel = LocalIntel(inventory_snapshot, expectations=[])
    base = datetime.now(UTC)
    scope = AuthorizedScope(
        id="scp_rehearsal",
        project_id="prj_rehearsal",
        name="inventory-lite sandbox",
        targets=[
            ScopeTarget(
                target_id=TARGET_ID,
                repo_id="rep_inventory_lite",
                build_recipe_ref="build_recipe.json",
                exposed_ports=[8000],
            )
        ],
        allowed_check_categories=["access_control.ownership"],
        status=ScopeStatus.ACTIVE,
        requested_by="usr_rehearsal",
        approved_by="usr_owner",
        approved_at=base - timedelta(hours=1),
        expires_at=base + timedelta(hours=8),
        notes="rehearsal unfamiliar target",
    )
    runner = CheckRunner(
        driver=LocalProcessDriver(allow=True),
        library=library,
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    ctx = ToolContext(
        assessment_id="asm_rehearsal",
        agent=AgentName.PROBE,
        run_id="run_rehearsal",
        step_key="rehearsal",
        read_root=intel.snapshot.root,
        services={
            "intel": intel,
            "history": FindingsHistory(),
            "checks": library,
            "check_runner": runner,
        },
        scope=scope,
        org_member_count=1,
        kill_switch=lambda: False,
        now=lambda: datetime.now(UTC),
    )
    ctx.roe = build_roe(scope, library.list_public())
    ctx.artifacts["last_scope_decision"] = Decision(
        allowed=True, reason_code="OK", scope_id="scp_rehearsal", evaluated_at=datetime.now(UTC)
    )
    return ctx


def _run_ownership(ctx: ToolContext, route_id: str) -> dict:
    result = default_registry().invoke(
        ctx,
        wire_name("checks.run_template"),
        {
            "template_ref": "access_control.ownership@1",
            "target_id": TARGET_ID,
            "parameters": {
                "route_id": route_id,
                "owner_identity": "alice",
                "other_identity": "bob",
            },
        },
    )
    return result.payload if hasattr(result, "payload") else result


def test_planted_item_ownership_defect_is_confirmed_by_execution(inventory_ctx):
    """The check EXECUTES: bob really gets 200 on alice's item (expected 403/404)."""
    out = _run_ownership(inventory_ctx, "item_detail")
    assert out["errors"] == 0 and out["skipped"] == 0
    assert out["matches_expectation"] is False
    failing = {t.split("::")[-1] for t in out["failing_tests"]}
    assert "test_other_identity_is_denied" in failing


def test_guarded_warehouse_route_is_refuted(inventory_ctx):
    """The guarded sibling must not be falsely flagged (precision check)."""
    out = _run_ownership(inventory_ctx, "warehouse_detail")
    assert out["errors"] == 0
    assert out["matches_expectation"] is True
    assert out["passed"] == 2 and out["failed"] == 0


def test_results_are_evidence_not_model_claims(inventory_ctx):
    out = _run_ownership(inventory_ctx, "item_detail")
    assert out["driver"] == "local-process"
    assert out["transport"] == "inprocess"
    assert out["sandbox_run_id"].startswith("sbx_")
    assert json.dumps(out["parameters"])  # record is serializable evidence
