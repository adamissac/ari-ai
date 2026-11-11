from shipping.fees import shipping_fee


def test_small_orders_pay_the_flat_fee():
    assert shipping_fee(1200) == 599


def test_free_at_the_threshold():
    assert shipping_fee(5000) == 0
