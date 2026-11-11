from split.shares import split


def test_shares_follow_the_rule_for_many_bills():
    for total in range(0, 120):
        for people in range(1, 9):
            shares = split(total, people)
            extra = total % people
            assert shares == [total // people + 1] * extra + [total // people] * (people - extra)
            assert sum(shares) == total
