from rl_defense.standards import defensive_refs


def test_simulated_isolation_keeps_rule_provenance():
    refs = defensive_refs("isolate")
    assert refs
    assert all(
        ref.framework == "d3fend"
        and ref.simulation_derived
        and ref.mapped_via == "reviewed_rule_table"
        for ref in refs
    )


def test_noop_has_no_invented_control():
    assert defensive_refs("noop") == []
