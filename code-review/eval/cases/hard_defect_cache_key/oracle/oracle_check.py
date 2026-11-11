from pricing.quotes import quote


def test_two_tiers_get_their_own_price_for_the_same_item():
    assert quote("gold", "widget", 3) == 2700
    assert quote("standard", "widget", 3) == 3000
