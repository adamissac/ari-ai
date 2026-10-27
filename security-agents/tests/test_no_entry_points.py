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
