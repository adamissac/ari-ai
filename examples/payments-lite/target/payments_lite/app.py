"""HTTP API for payments-lite.

Intended behavior (the platform should discover these from docstrings, tests and
conventions):

- A customer can only read their own profile, payments and refunds.
- Total refunds for a payment must never exceed the payment's original amount.
- Amounts are positive and use two decimal places.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from payments_lite.store import Customer, Payment, Refund, Store, seeded_store


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    description: str = Field(default="", max_length=200)


class PaymentOut(BaseModel):
    id: str
    customer_id: str
    amount: Decimal
    currency: str
    description: str
    refunded: Decimal


class RefundIn(BaseModel):
    payment_id: str
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reason: str = Field(default="", max_length=200)


class RefundOut(BaseModel):
    id: str
    payment_id: str
    amount: Decimal
    reason: str


class CustomerOut(BaseModel):
    id: str
    name: str
    email: str


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="payments-lite", version="0.1.0")
    app.state.store = store or seeded_store()

    def get_store() -> Store:
        return app.state.store

    def current_customer(
        authorization: Annotated[str | None, Header()] = None,
        store: Store = Depends(get_store),
    ) -> Customer:
        """Resolve the bearer token to a customer; 401 if missing or unknown."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        customer_id = store.tokens.get(authorization.removeprefix("Bearer "))
        if customer_id is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        return store.customers[customer_id]

    def require_owner(resource_customer_id: str, customer: Customer) -> None:
        """A customer may only access resources they own. 404 (not 403) avoids leaking existence."""
        if resource_customer_id != customer.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")

    def payment_out(store: Store, p: Payment) -> PaymentOut:
        refunded = sum((r.amount for r in store.refunds_for(p.id)), Decimal("0"))
        return PaymentOut(
            id=p.id,
            customer_id=p.customer_id,
            amount=p.amount,
            currency=p.currency,
            description=p.description,
            refunded=refunded,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me", response_model=CustomerOut)
    def me(customer: Customer = Depends(current_customer)) -> CustomerOut:
        return CustomerOut(id=customer.id, name=customer.name, email=customer.email)

    @app.get("/customers/{customer_id}", response_model=CustomerOut)
    def get_customer(
        customer_id: str,
        customer: Customer = Depends(current_customer),
        store: Store = Depends(get_store),
    ) -> CustomerOut:
        """A customer can only read their own profile."""
        target = store.customers.get(customer_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(target.id, customer)
        return CustomerOut(id=target.id, name=target.name, email=target.email)

    @app.get("/payments", response_model=list[PaymentOut])
    def list_payments(
        customer: Customer = Depends(current_customer), store: Store = Depends(get_store)
    ) -> list[PaymentOut]:
        """List the current customer's own payments."""
        return [
            payment_out(store, p) for p in store.payments.values() if p.customer_id == customer.id
        ]

    @app.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
    def create_payment(
        body: PaymentIn,
        customer: Customer = Depends(current_customer),
        store: Store = Depends(get_store),
    ) -> PaymentOut:
        p = Payment(store.next_id("pay"), customer.id, body.amount, body.currency, body.description)
        store.payments[p.id] = p
        return payment_out(store, p)

    @app.get("/payments/{payment_id}", response_model=PaymentOut)
    def get_payment(
        payment_id: str,
        customer: Customer = Depends(current_customer),
        store: Store = Depends(get_store),
    ) -> PaymentOut:
        """Return one payment by id."""
        p = store.payments.get(payment_id)
        if p is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return payment_out(store, p)

    @app.post("/refunds", response_model=RefundOut, status_code=status.HTTP_201_CREATED)
    def create_refund(
        body: RefundIn,
        customer: Customer = Depends(current_customer),
        store: Store = Depends(get_store),
    ) -> RefundOut:
        """Refund part or all of a payment the customer owns.

        Total refunds for a payment must never exceed the payment's original amount.
        """
        p = store.payments.get(body.payment_id)
        if p is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(p.customer_id, customer)
        if body.amount > p.amount:
            raise HTTPException(422, "refund exceeds payment amount")
        r = Refund(store.next_id("ref"), p.id, customer.id, body.amount, body.reason)
        store.refunds[r.id] = r
        return RefundOut(id=r.id, payment_id=r.payment_id, amount=r.amount, reason=r.reason)

    @app.get("/refunds/{refund_id}", response_model=RefundOut)
    def get_refund(
        refund_id: str,
        customer: Customer = Depends(current_customer),
        store: Store = Depends(get_store),
    ) -> RefundOut:
        r = store.refunds.get(refund_id)
        if r is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(r.customer_id, customer)
        return RefundOut(id=r.id, payment_id=r.payment_id, amount=r.amount, reason=r.reason)

    return app


app = create_app()
