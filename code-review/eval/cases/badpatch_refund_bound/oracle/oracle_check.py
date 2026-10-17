import pytest
from payments.refunds import Payment, RefundTooLarge, refund


def test_cumulative_refunds_are_bounded():
    p = Payment(1000)
    refund(p, 600)
    with pytest.raises(RefundTooLarge):
        refund(p, 600)
