# pricing

Prices are integer cents.

## Rules

- A quote is the customer's unit price times the quantity.
- The unit price is the list price minus the customer's tier discount.
- Tiers: standard pays list price, silver gets 5% off, gold gets 10% off.
- Quotes are cached in-process; a cached quote is always the same number a
  fresh computation would give.
