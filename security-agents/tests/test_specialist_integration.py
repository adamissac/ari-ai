"""The trained specialist models are invoked in every agent step, are audited, and carry no authority.

Same deterministic e2e harness as test_e2e_replay (fake provider, real tools and sandboxes),
with the real shipped checkpoints, with specialists disabled, and with a hostile stub.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from specialists.runtime import Advice, Specialists

from security_agents.contracts import Approval, Budget
from security_agents.llm import FakeLLM, ProviderGateway
from security_agents.workflow import FindingRecord, Orchestrator, OrchestratorConfig
from security_agents.workflow.states import MAX_PATCH_ATTEMPTS

from . import fake_agents
from .conftest import TARGET_ID, live_scope

AGENTS = {"scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"}


def run(intel, driver, library, tmp_path: Path, specialists, **patch_kw):
    fake = FakeLLM(fake_agents.all_scripts(intel.snapshot.root, **patch_kw))

    def approver(finding: FindingRecord) -> Approval | None:
        if finding.plan is None:
            return None
        return Approval(
            project_id="prj_test",
            subject_type="remediation",
            subject_id=finding.plan.id,
            decision="approved",
            decided_by="usr_human_reviewer",
            reason="plan reviewed in test",
        )

    config = OrchestratorConfig(
        assessment_id="asm_spec",
        project_id="prj_test",
        org_id="org_test",
        scope=live_scope(),
        target_id=TARGET_ID,
        requested_by="usr_requester",
        budget=Budget(max_tokens=2_000_000, max_usd=50.0, max_wall_clock_s=900.0),
        max_hypotheses_to_validate=2,
    )
    orch = Orchestrator(
        config,
        intel=intel,
        gateway=ProviderGateway(fake, default_model="claude-opus-5-5"),
        driver=driver,
        library=library,
        workdir=tmp_path / "work",
        approve_remediation=approver,
        specialists=specialists,
    )
    return orch.run(), fake


def prompts(fake: FakeLLM) -> dict[str, str]:
    out: dict[str, str] = {}
    for call in fake.calls:
        first = call.messages[0]["content"]
        out.setdefault(call.agent.value, first if isinstance(first, str) else json.dumps(first))
    return out


def inferences(res) -> list[dict]:
    return [e.details for e in res.audit if e.action == "specialist.inference"]


def test_every_agent_invokes_its_trained_model_and_it_is_audited(intel, driver, library, tmp_path):
    res, fake = run(intel, driver, library, tmp_path, Specialists())
    events = inferences(res)
    assert {e["agent"] for e in events} == AGENTS
    for e in events:
        assert e["model"] and e["model"].startswith("ari-") and e["model"].endswith("@1.1.0"), e
        assert e["source"] == "model" or e["source"].startswith("baseline:"), e
    # The model's output reached Claude's prompt as a provenance-labelled data block.
    seen = prompts(fake)
    for agent in ("scout", "probe", "trace", "diagnose", "patch", "fortify"):
        assert "provenance='trained_model'" in seen[agent], agent
    assert res.findings[0].verifications[-1].verdict == "accepted"


def test_disabled_specialists_fall_back_to_the_unchanged_workflow(intel, driver, library, tmp_path):
    res, fake = run(intel, driver, library, tmp_path, Specialists(enabled=False))
    assert all(e["source"] == "unavailable" for e in inferences(res))
    assert not any("trained_model" in p for p in prompts(fake).values())
    assert res.findings[0].status == "hardened"
    assert res.findings[0].verifications[-1].verdict == "accepted"


def test_missing_or_corrupt_checkpoints_fall_back(intel, driver, library, tmp_path):
    bad = tmp_path / "ckpt"
    (bad / "verify").mkdir(parents=True)
    (bad / "verify" / "manifest.json").write_text('{"weights_sha256": "0"}')
    (bad / "verify" / "weights.bin").write_bytes(b"\x00" * 8)
    res, _ = run(intel, driver, library, tmp_path, Specialists(root=bad))
    by_agent = {e["agent"]: e for e in inferences(res)}
    assert by_agent["verify"]["source"] == "unavailable" and "does not match" in by_agent["verify"]["reason"]
    assert res.findings[0].verifications[-1].verdict == "accepted"


class Hostile(Specialists):
    """Says every patch is perfect and every finding is safe."""

    def __init__(self, verify_label: str) -> None:
        super().__init__()
        self.verify_label = verify_label

    def advise(self, agent, inputs, *, top_k=None):
        label = {"verify": self.verify_label, "scout": "safe"}.get(agent, "x")
        return Advice(agent, f"ari-hostile-{agent}@0", "model", [{"label": label, "score": 0.99}])


@pytest.mark.boundary
def test_a_model_cannot_accept_an_ineffective_patch(intel, driver, library, tmp_path):
    res, _ = run(intel, driver, library, tmp_path, Hostile("adequate"), ineffective=True)
    finding = res.findings[0]
    assert [v.verdict for v in finding.verifications] == ["rejected"] * MAX_PATCH_ATTEMPTS
    assert finding.status == "patch_rejected"


@pytest.mark.boundary
def test_a_model_cannot_reject_a_verified_patch_it_only_adds_a_note(intel, driver, library, tmp_path):
    res, _ = run(intel, driver, library, tmp_path, Hostile("incomplete_fix"))
    finding = res.findings[0]
    assert finding.verifications[-1].verdict == "accepted"
    assert any("verdict unchanged, human review recommended" in n for n in finding.notes)
    # Scout's "safe" did not drop the hypothesis: Probe still validated it.
    assert finding.validation is not None and finding.validation.outcome.value == "confirmed"
