"""Synthetic receipt fixtures only; no first-responder study or agent execution."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from shared.assessment import AgentName, AgentRun, AgentRunStatus, AgentStepResult
from shared.evidence import EvidenceRef
from shared.intelligence import SnapshotRef
from shared.scope import AuthorizedScope, ScopeStatus, ScopeTarget

from rl_defense.research.first_responder import (
    ACTIONS,
    FEATURES,
    Action,
    Capability,
    Decision,
    Fact,
    Frame,
    ResultReceipt,
    ScopeReceipt,
    Stamp,
    observation_digest,
    observe,
    validate_proposal,
)

T = datetime(2026, 10, 24, tzinfo=UTC)
PROJECT, REPO, ASSESSMENT, INCIDENT = (
    prefix + "0" * 26 for prefix in ("prj_", "rep_", "asm_", "inc_")
)
USER, RUN, ART = (prefix + "0" * 26 for prefix in ("usr_", "run_", "art_"))
SNAPSHOT = SnapshotRef(
    project_id=PROJECT,
    repo_id=REPO,
    commit_sha="a" * 40,
    snapshot_id="snp_" + "0" * 26,
    index_version="fixture",
)
EVIDENCE = EvidenceRef(
    kind="artifact", artifact_id=ART, sha256="b" * 64, provenance="unit-fixture/0.1"
)


def stamp(identity, **changes):
    return Stamp(
        receipt_id=identity,
        clock_id="fixture-journal",
        project_id=PROJECT,
        repo_id=REPO,
        assessment_id=ASSESSMENT,
        incident_id=INCIDENT,
        snapshot=SNAPSHOT,
        observed_at=T + timedelta(seconds=1),
        available_at=T + timedelta(seconds=2),
        available_seq=changes.pop("available_seq", 2),
        valid_until=T + timedelta(seconds=600),
        evidence=(EVIDENCE,),
        **changes,
    )


def frame(**changes):
    return Frame(
        clock_id="fixture-journal",
        project_id=PROJECT,
        repo_id=REPO,
        assessment_id=ASSESSMENT,
        incident_id=INCIDENT,
        snapshot=changes.pop("snapshot", SNAPSHOT),
        cutoff_at=T + timedelta(seconds=60),
        cutoff_seq=20,
        **changes,
    )


def scope(status=ScopeStatus.active):
    return ScopeReceipt(
        stamp=stamp("scope"),
        scope=AuthorizedScope(
            id="scp_" + "0" * 26,
            project_id=PROJECT,
            name="owned fixture",
            targets=[ScopeTarget(repo_id=REPO, build_recipe_ref="fixture")],
            status=status,
            requested_by=USER,
            approved_by=USER,
            approved_at=T,
            expires_at=T + timedelta(seconds=500),
        ),
    )


def capability(action=Action.scout):
    return Capability(
        stamp=stamp("cap"),
        action=action,
        enabled=True,
        input_ready=True,
        budget_ready=True,
        host_gate_ready=True,
    )


def enabled(**changes):
    data = dict(
        integration_agreed=True,
        deployment_binding=stamp("deploy"),
        scopes=(scope(),),
        capabilities=(capability(),),
    )
    data.update(changes)
    return frame(**data)


def result(status=AgentRunStatus.succeeded, attested=False):
    run = AgentRun(
        id=RUN,
        assessment_id=ASSESSMENT,
        agent=AgentName.scout,
        step_key="fixture",
        attempt=1,
        status=status,
        provider_mode="fake",
        started_at=T,
        ended_at=T + timedelta(seconds=1),
        output_artifact_id=ART,
    )
    return ResultReceipt(
        stamp=stamp("result"),
        run=run,
        result=AgentStepResult(agent_run_id=RUN, agent=AgentName.scout, status=status),
        usage_attested=attested,
    )


def test_missing_context_is_unknown_and_default_masks_are_inert():
    obs = observe(frame())
    assert not any(obs.known)
    assert obs.mask == tuple(a in (Action.abstain, Action.monitor) for a in ACTIONS)
    assert not frame().integration_agreed


def test_future_and_same_cutoff_data_do_not_backfill_observations():
    old = Fact(stamp=stamp("old"), name="suspicious_count", value=3.0)
    later = old.model_copy(
        update={
            "stamp": stamp("future").model_copy(
                update={"available_at": T + timedelta(seconds=60), "available_seq": 20}
            ),
            "value": 999.0,
        }
    )
    assert observe(frame(facts=(old,))) == observe(frame(facts=(old, later)))
    seq_only = later.model_copy(update={"stamp": stamp("seq-only", available_seq=20)})
    assert observe(frame(facts=(old,))) == observe(frame(facts=(old, seq_only)))


def test_observation_snapshot_is_immutable_after_input_mutation():
    receipt = result(attested=True)
    obs = observe(frame(results=(receipt,)))
    receipt.result.output["claim"] = "stopped all attacks"
    assert observe(frame(results=(receipt,))) == obs
    assert "useful_evidence" not in FEATURES


@pytest.mark.parametrize("field,value", [("clock_id", "other"), ("incident_id", "inc_" + "1" * 26)])
def test_mixed_context_or_clock_fails_closed(field, value):
    fact = Fact(
        stamp=stamp("foreign").model_copy(update={field: value}), name="suspicious_count", value=1.0
    )
    with pytest.raises(ValueError):
        observe(frame(facts=(fact,)))


def test_snapshot_mismatch_and_unknown_deployment_do_not_enable_agents():
    assert not observe(enabled(deployment_binding=None)).mask[ACTIONS.index(Action.scout)]
    assert not observe(frame(snapshot=None)).mask[ACTIONS.index(Action.scout)]
    other = SNAPSHOT.model_copy(update={"commit_sha": "c" * 40})
    fact = Fact(
        stamp=stamp("wrong-sha").model_copy(update={"snapshot": other}),
        name="verified_findings",
        value=1.0,
    )
    with pytest.raises(ValueError, match="snapshot"):
        observe(frame(facts=(fact,)))


@pytest.mark.parametrize("status", [ScopeStatus.revoked, ScopeStatus.expired, ScopeStatus.pending])
def test_scope_state_cannot_be_overridden_by_capability(status):
    assert not observe(enabled(scopes=(scope(status),))).mask[ACTIONS.index(Action.scout)]


def test_latest_expired_capability_does_not_revive_older_permission():
    old = capability()
    stale = old.model_copy(
        update={
            "stamp": stamp("expired", available_seq=3).model_copy(
                update={"valid_until": T + timedelta(seconds=30)}
            )
        }
    )
    assert not observe(enabled(capabilities=(old, stale))).mask[ACTIONS.index(Action.scout)]
    fact = Fact(stamp=stamp("old-fact"), name="pending_tasks", value=1.0)
    expired = fact.model_copy(
        update={
            "stamp": stale.stamp.model_copy(update={"receipt_id": "expired-fact"}),
            "value": 3.0,
        }
    )
    obs = observe(frame(facts=(fact, expired)))
    assert not obs.known[FEATURES.index("pending_tasks")]


def test_notifications_require_allowlisted_destination():
    cap = capability(Action.notify)
    assert not observe(enabled(capabilities=(cap,))).mask[ACTIONS.index(Action.notify)]
    assert observe(
        enabled(capabilities=(cap.model_copy(update={"destination_allowlisted": True}),))
    ).mask[ACTIONS.index(Action.notify)]


def test_recommendation_is_never_execution_or_a_grant():
    obs = observe(enabled(capabilities=(capability(Action.containment),)))
    decision = Decision(
        action=Action.containment,
        behavior_policy="fixture",
        observation_sha256=observation_digest(obs),
        issued_seq=21,
        issued_at=T + timedelta(seconds=60),
    )
    validate_proposal(obs, decision)
    assert decision.executed is False and decision.training_eligible is False
    with pytest.raises(ValidationError):
        Decision.model_validate({**decision.model_dump(), "executed": True})
    with pytest.raises(ValidationError):
        Decision.model_validate({**decision.model_dump(), "grant": "self-approved"})
    with pytest.raises(ValidationError):
        Decision.model_validate({**decision.model_dump(), "action": "execute_containment"})


def test_invalid_proposal_is_rejected_without_noop_replacement():
    obs = observe(frame())
    d = Decision(
        action=Action.scout,
        behavior_policy="fixture",
        observation_sha256=observation_digest(obs),
        issued_seq=21,
        issued_at=T + timedelta(seconds=60),
    )
    with pytest.raises(ValueError, match="infeasible"):
        validate_proposal(obs, d)
    with pytest.raises(ValueError, match="binding"):
        validate_proposal(obs, d.model_copy(update={"observation_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="cutoff"):
        validate_proposal(obs, d.model_copy(update={"issued_seq": 20}))


def test_result_schema_and_usage_unknown_are_not_security_outcomes():
    receipt = result()
    obs = observe(frame(results=(receipt,)))
    assert obs.values[FEATURES.index("completed_agent_runs")] == 1
    assert not obs.known[FEATURES.index("terminal_run_cost_usd")]
    assert observe(frame(results=(result(attested=True),))).known[
        FEATURES.index("terminal_run_cost_usd")
    ]
    with pytest.raises(ValidationError, match="mismatch"):
        ResultReceipt(
            stamp=receipt.stamp,
            run=receipt.run,
            result=receipt.result.model_copy(update={"agent": AgentName.trace}),
        )
    with pytest.raises(ValidationError):
        Fact(stamp=stamp("attack-label"), name="hidden_attack_type", value=1.0)
    with pytest.raises(ValidationError):
        Fact(stamp=stamp("nan"), name="suspicious_count", value=float("nan"))


def test_duplicate_result_receipts_are_not_double_counted():
    first = result()
    second = first.model_copy(update={"stamp": stamp("duplicate-run", available_seq=3)})
    with pytest.raises(ValueError, match="duplicate terminal"):
        observe(frame(results=(first, second)))
