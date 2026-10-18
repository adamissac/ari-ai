import pytest
from payments.refunds import Payment, refund


def test_refund_recorded():
    p = Payment(1000)
    refund(p, 300)
    assert p.refunds == [300]


def test_rejects_zero():
    with pytest.raises(ValueError):
        refund(Payment(10), 0)
