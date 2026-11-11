from shipping.fees import shipping_fee


def test_small_orders_pay_the_flat_fee():
    assert shipping_fee(1200) == 599


def test_large_orders_ship_free():
    assert shipping_fee(5001) == 0


def test_express_is_never_free():
    assert shipping_fee(1200, express=True) == 1499
    assert shipping_fee(9000, express=True) == 1499
