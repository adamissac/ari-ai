# accounts

Balances are integer cents.

## Transfers

- transfer() moves `amount` from the source balance to the destination balance.
- An account may send at most 1,000.00 per day.
- A transfer that fails for any reason changes nothing: no balance moves and the
  daily total is unchanged.
