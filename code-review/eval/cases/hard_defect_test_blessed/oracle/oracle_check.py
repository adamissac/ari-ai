from shipping.fees import shipping_fee


def test_an_order_of_exactly_fifty_ships_free():
    assert shipping_fee(5000) == 0
