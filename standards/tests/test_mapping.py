"""Mapping rules: catalog validity, evidence, deprecation, legacy, rule tables, review."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.standards import (
    CatalogStatus,
    ControlStatus,
    MappedVia,
    Observation,
    ReviewStatus,
    StandardFramework,
)
from standards import catalog, mapping
from standards.catalog import load_json
from standards.mapping import MappingRejected

SPAN = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app/routes.py",
    commit_sha="a" * 40,
    span=SourceSpan(start_line=10, end_line=14),
    provenance="test",
)
RUN = EvidenceRef(
    kind=EvidenceKind.sandbox_run, artifact_id="art_12345678", sha256="b" * 64, provenance="test"
)
A = StandardFramework.attack


def attack(identifier: str, evidence: list[EvidenceRef] | None = None):  # type: ignore[no-untyped-def]
    return mapping.build_mapping(
        A,
        identifier,
        mapped_via=MappedVia.human,
        observation=Observation.hypothesis,
        rationale="test",
        confidence=0.5,
        evidence=[SPAN] if evidence is None else evidence,
    )


@pytest.mark.parametrize(
    ("framework", "identifier"),
    [
        (A, "T9999"),
        (A, "T1190 "),
        (StandardFramework.d3fend, "D3-MADEUP"),
        (StandardFramework.cwe, "CWE-0"),
        (StandardFramework.owasp_llm, "LLM01"),
    ],
)
def test_unknown_and_malformed_ids_are_rejected(
    framework: StandardFramework, identifier: str
) -> None:
    with pytest.raises(MappingRejected) as info:
        mapping.resolve(framework, identifier)
    assert info.value.code == "unknown_identifier"


def test_mapping_records_catalog_version_and_url() -> None:
    m = attack("T1190")
    assert (m.id, m.catalog_version, m.review_status) == ("T1190", "20.0", ReviewStatus.proposed)
    assert m.url == "https://attack.mitre.org/techniques/T1190"


def test_mapping_without_evidence_is_refused() -> None:
    with pytest.raises(MappingRejected) as info:
        attack("T1190", evidence=[])
    assert info.value.code == "insufficient_evidence"


def test_revoked_and_deprecated_ids_are_refused_with_replacement() -> None:
    with pytest.raises(MappingRejected) as info:
        attack("T1002")
    assert (info.value.code, info.value.replaced_by) == ("revoked_identifier", "T1560")
    with pytest.raises(MappingRejected) as info:
        attack("T1026")
    assert info.value.code == "deprecated_identifier"
    with pytest.raises(MappingRejected) as info:
        mapping.check_cwe("CWE-1")
    assert info.value.code == "deprecated_identifier"


def test_legacy_import_keeps_inactive_ids_flagged() -> None:
    m = mapping.import_legacy(
        A, "T1002", source_version="8.0", rationale="old report", evidence=[SPAN]
    )
    assert m.legacy and m.catalog_status is CatalogStatus.revoked
    assert "replaced by T1560" in m.rationale and m.confidence == 0.0
    with pytest.raises(ValidationError):
        type(m).model_validate({**m.model_dump(), "legacy": False})


@pytest.mark.parametrize(
    ("cwe", "code"),
    [("CWE-840", "not_a_weakness"), ("CWE-20", "mapping_discouraged")],
)
def test_cwe_mapping_guidance_is_enforced(cwe: str, code: str) -> None:
    with pytest.raises(MappingRejected) as info:
        mapping.check_cwe(cwe)
    assert info.value.code == code


def test_discouraged_cwe_is_allowed_only_for_humans() -> None:
    assert mapping.check_cwe("CWE-20", by_human=True).id == "CWE-20"
    c = mapping.classify_cwe(
        "CWE-639",
        observation=Observation.observed_in_sandbox,
        mapped_via=MappedVia.check_template_rule,
        rationale="ownership check reproduced",
        confidence=0.9,
        evidence=[SPAN, RUN],
    )
    assert (c.id, c.mapping_usage, c.catalog_version) == ("CWE-639", "Allowed", "4.20")


def test_observed_in_sandbox_needs_run_evidence() -> None:
    with pytest.raises(ValidationError):
        mapping.classify_cwe(
            "CWE-639",
            observation=Observation.observed_in_sandbox,
            mapped_via=MappedVia.human,
            rationale="claimed",
            confidence=0.9,
            evidence=[SPAN],
        )


def test_attack_rule_applies_only_when_conditions_hold() -> None:
    maps, unmapped = mapping.attack_for_check(
        "access_control.ownership",
        {"reachability": "authenticated"},
        observation=Observation.observed_in_sandbox,
        evidence=[SPAN, RUN],
    )
    assert [m.id for m in maps] == ["T1190"] and unmapped == []
    assert maps[0].rule_id == "check_attack.ownership.t1190"
    assert maps[0].review_status is ReviewStatus.proposed

    maps, unmapped = mapping.attack_for_check(
        "access_control.ownership", {}, observation=Observation.hypothesis, evidence=[SPAN]
    )
    assert maps == [] and unmapped


def test_no_forced_mapping_for_logic_flaws_or_unknown_categories() -> None:
    for category in ("input_validation.bounds", "something.new"):
        maps, unmapped = mapping.attack_for_check(
            category, {}, observation=Observation.hypothesis, evidence=[SPAN]
        )
        assert maps == [] and unmapped[0].framework == "attack" and unmapped[0].reason


def test_d3fend_hardening_is_proposed_and_rl_actions_are_simulation_only() -> None:
    maps, _ = mapping.d3fend_for_hardening(
        "centralize_check", "access_control.ownership", evidence=[SPAN]
    )
    assert [m.id for m in maps] == ["D3-AMED"]
    assert maps[0].control_status is ControlStatus.proposed and not maps[0].simulation_derived
    maps, unmapped = mapping.d3fend_for_hardening(
        "lint_rule", "access_control.ownership", evidence=[SPAN]
    )
    assert maps == [] and unmapped

    maps, _ = mapping.d3fend_for_rl_action("isolate", evidence=[SPAN])
    assert [m.id for m in maps] == ["D3-NI"]
    assert maps[0].simulation_derived and maps[0].observation is Observation.simulated
    with pytest.raises(ValidationError):
        type(maps[0]).model_validate({**maps[0].model_dump(), "control_status": "implemented"})
    for action in ("rate_limit", "noop", "escalate_to_human", "block_principal"):
        assert mapping.d3fend_for_rl_action(action, evidence=[SPAN]) == (
            [],
            [
                mapping.Unmapped(
                    "d3fend", f"{action}: " + mapping._rules("rl_d3fend")["unmapped"][action]
                )
            ],
        )


def test_tested_control_needs_test_evidence() -> None:
    with pytest.raises(ValidationError):
        mapping.d3fend_for_hardening(
            "centralize_check",
            "access_control.ownership",
            evidence=[SPAN],
            control_status=ControlStatus.tested,
        )


def test_rule_tables_reference_only_active_catalog_ids() -> None:
    for row in load_json("rules/check_attack.json")["rules"]:
        assert catalog.attack_technique(row["technique"]).status == "active"
    for name in ("fortify_d3fend", "rl_d3fend"):
        for row in load_json(f"rules/{name}.json")["rules"]:
            assert catalog.d3fend_technique(row["technique"]).status == "active"


def test_capec_chain_yields_review_candidates_not_mappings() -> None:
    candidates = mapping.attack_candidates_via_capec("CWE-284")
    assert candidates and all(isinstance(c, mapping.ChainCandidate) for c in candidates)
    assert mapping.attack_candidates_via_capec("CWE-639") == []


def test_only_humans_review_mappings() -> None:
    m = attack("T1190")
    with pytest.raises(MappingRejected):
        mapping.review(m, reviewer="agent:scout", accept=True)
    accepted = mapping.review(m, reviewer="user:usr_alan01", accept=True)
    assert (accepted.review_status, accepted.reviewed_by) == (
        ReviewStatus.accepted,
        "user:usr_alan01",
    )
    with pytest.raises(ValidationError):
        type(m).model_validate({**m.model_dump(), "review_status": "accepted"})


# ------------------------------------------------------------------ framework update


@pytest.fixture
def next_attack_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A simulated newer ATT&CK release that revokes T1190 in favour of T1133."""
    src = Path(catalog.__file__).parent / "data"
    root = tmp_path / "data"
    shutil.copytree(src, root)
    data = json.loads((root / "attack-enterprise.json").read_text())
    data["version"] = "21.0"
    data["techniques"]["T1190"] |= {"revoked": True, "revoked_by": "T1133"}
    raw = json.dumps(data).encode()
    (root / "attack-enterprise.json").write_bytes(raw)
    man = json.loads((root / "MANIFEST.json").read_text())
    man["files"]["attack-enterprise.json"] |= {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "version": "21.0",
    }
    (root / "MANIFEST.json").write_text(json.dumps(man))
    monkeypatch.setattr(catalog, "_data_root", lambda: root)
    for fn in (catalog.manifest, catalog.load_json, mapping._rules):
        fn.cache_clear()
    yield
    for fn in (catalog.manifest, catalog.load_json, mapping._rules):
        fn.cache_clear()


def test_after_update_old_id_is_refused_and_legacy_import_flags_it(
    next_attack_release: None,
) -> None:
    assert catalog.catalog_versions()["attack"] == "21.0"
    with pytest.raises(MappingRejected) as info:
        attack("T1190")
    assert (info.value.code, info.value.replaced_by) == ("revoked_identifier", "T1133")
    legacy = mapping.import_legacy(
        A, "T1190", source_version="20.0", rationale="pre-update", evidence=[SPAN]
    )
    assert legacy.legacy and legacy.catalog_version == "21.0"
    assert "replaced by T1133" in legacy.rationale
    with pytest.raises(MappingRejected):
        mapping.attack_for_check(
            "access_control.ownership",
            {"reachability": "authenticated"},
            observation=Observation.hypothesis,
            evidence=[SPAN],
        )
