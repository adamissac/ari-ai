# accounts

Balances are integer cents.

## Transfers

- transfer() moves `amount` from the source balance to the destination balance.
- A transfer that fails for any reason changes nothing: no balance moves.
