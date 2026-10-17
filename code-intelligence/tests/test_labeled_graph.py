from pathlib import Path

from intel_test_helpers import repository as repository
from test_service import service


def test_labeled_exact_call_edges_have_no_false_positives_or_missing_edges(
    repository: tuple[Path, str],
    tmp_path: Path,
) -> None:
    root, sha = repository
    engine = service(root, tmp_path / "index.sqlite")
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    index = engine.store.get(ref)
    names = {symbol.id: symbol.qualified_name for symbol in index.symbols}
    expected = {
        ("app.payments.read_payment", "app.payments.refund"),
        ("app.payments.read_payment", "app.auth.current_user"),
        ("tests.test_payments.test_refund_bounds", "app.payments.refund"),
    }
    actual = {
        (names[edge.caller_id], names[edge.callee_id])
        for edge in index.calls
        if edge.resolution == "exact" and edge.callee_id is not None
    }
    true_positive = len(actual & expected)
    false_positive = len(actual - expected)
    false_negative = len(expected - actual)
    assert (true_positive, false_positive, false_negative) == (3, 0, 0)
    print(f"LABELED exact edges TP={true_positive} FP={false_positive} FN={false_negative}")
