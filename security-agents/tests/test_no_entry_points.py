"""A repository with no recognised HTTP entry points (e.g. a JavaScript app) still gets its
functional review; only the security agents, which need an attack surface, are skipped."""

import shutil

from security_agents.checks.library import default_library
from security_agents.contracts import Budget
from security_agents.intel import LocalIntel
from security_agents.llm import FakeLLM, ProviderGateway
from security_agents.sandbox.driver import LocalProcessDriver
from security_agents.sandbox.workspace import SnapshotHandle, copy_tree
from security_agents.workflow import Orchestrator, OrchestratorConfig
from security_agents.workflow.states import AssessmentState

from .conftest import BUILD_RECIPE, PAYMENTS_LITE
from .test_contracts import TARGET_ID, live_scope


class NoEntryPoints:
    """The real index, minus its HTTP routes."""

    def __init__(self, inner):
        self._inner = inner

    def entry_points(self, *args, **kwargs):
        return []

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_no_entry_points_completes_with_functional_review_only(tmp_path):
    staging = tmp_path / "staging"
    copy_tree(PAYMENTS_LITE, staging)
    shutil.copy2(BUILD_RECIPE, staging / "build_recipe.json")
    snapshot = SnapshotHandle.from_directory(
        staging, tmp_path / "snapshot", snapshot_id="snp_noentry", repo_id="rep_noentry"
    )
    llm = FakeLLM({})  # no agent may call the model
    result = Orchestrator(
        OrchestratorConfig(
            assessment_id="asm_noentry",
            project_id="prj_noentry",
            org_id="org_noentry",
            scope=live_scope(),
            target_id=TARGET_ID,
            requested_by="usr_requester",
            budget=Budget(max_tokens=100_000, max_usd=1.0, max_wall_clock_s=300.0),
        ),
        intel=NoEntryPoints(LocalIntel(snapshot)),
        gateway=ProviderGateway(llm),
        driver=LocalProcessDriver(allow=True),
        library=default_library(),
        workdir=tmp_path / "work",
    ).run()
    assert result.state is AssessmentState.COMPLETED, (result.error_code, result.error_detail)
    states = result.state_log.states()
    assert AssessmentState.FUNCTIONAL_REVIEW.value in states  # the reviewer is started here
    assert result.runs == [] and result.findings == []
    assert any("security agents skipped" in note for *_, note in result.state_log.entries)


class JsEntryPointsOnly(NoEntryPoints):
    """The real index, with its routes relabelled as JavaScript handlers."""

    def entry_points(self, *args, **kwargs):
        return [
            e.model_copy(update={"path": "api/" + e.path.rsplit("/", 1)[-1].replace(".py", ".js")})
            for e in self._inner.entry_points(*args, **kwargs)
        ]


def test_js_only_entry_points_skip_with_a_precise_label(tmp_path):
    staging = tmp_path / "staging"
    copy_tree(PAYMENTS_LITE, staging)
    shutil.copy2(BUILD_RECIPE, staging / "build_recipe.json")
    snapshot = SnapshotHandle.from_directory(
        staging, tmp_path / "snapshot", snapshot_id="snp_jsentry", repo_id="rep_jsentry"
    )
    intel = JsEntryPointsOnly(LocalIntel(snapshot))
    assert intel.entry_points()
    result = Orchestrator(
        OrchestratorConfig(
            assessment_id="asm_jsentry",
            project_id="prj_jsentry",
            org_id="org_jsentry",
            scope=live_scope(),
            target_id=TARGET_ID,
            requested_by="usr_requester",
            budget=Budget(max_tokens=100_000, max_usd=1.0, max_wall_clock_s=300.0),
        ),
        intel=intel,
        gateway=ProviderGateway(FakeLLM({})),
        driver=LocalProcessDriver(allow=True),
        library=default_library(),
        workdir=tmp_path / "work",
    ).run()
    assert result.state is AssessmentState.COMPLETED, (result.error_code, result.error_detail)
    assert result.runs == [] and result.findings == []
    notes = [note for *_, note in result.state_log.entries]
    assert any("JavaScript/TypeScript HTTP entry points" in n and "skipped" in n for n in notes)


def test_node_recipe_on_a_driver_without_node_support_skips_with_a_label(tmp_path):
    import json

    from .test_node_recipe import recipe

    staging = tmp_path / "staging"
    copy_tree(PAYMENTS_LITE, staging)
    (staging / "build_recipe.json").write_text(json.dumps(recipe()))
    snapshot = SnapshotHandle.from_directory(
        staging, tmp_path / "snapshot", snapshot_id="snp_nodedrv", repo_id="rep_nodedrv"
    )

    class OtherDriver(LocalProcessDriver):
        name = "vercel-sandbox"

    result = Orchestrator(
        OrchestratorConfig(
            assessment_id="asm_nodedrv",
            project_id="prj_nodedrv",
            org_id="org_nodedrv",
            scope=live_scope(),
            target_id=TARGET_ID,
            requested_by="usr_requester",
            budget=Budget(max_tokens=100_000, max_usd=1.0, max_wall_clock_s=300.0),
        ),
        intel=LocalIntel(snapshot),
        gateway=ProviderGateway(FakeLLM({})),
        driver=OtherDriver(allow=True),
        library=default_library(),
        workdir=tmp_path / "work",
    ).run()
    assert result.state is AssessmentState.COMPLETED, (result.error_code, result.error_detail)
    assert result.runs == []
    notes = [note for *_, note in result.state_log.entries]
    assert any("not supported on the vercel-sandbox sandbox yet" in n for n in notes), notes
