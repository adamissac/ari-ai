# payments-lite

A small payments service: customers, payments and partial refunds, with bearer-token
authentication. Data is in memory and seeded with two synthetic customers.

## Behavior

- A customer can only read their own profile, payments and refunds.
- Total refunds for a payment must never exceed the payment's original amount.
- Amounts are positive with two decimal places.

## Run

```bash
pip install -e ".[dev]"
pytest -q
uvicorn payments_lite.app:app --port 8080
```

Fixture tokens: `fixture-token-alice`, `fixture-token-bob` (synthetic, not secrets).
