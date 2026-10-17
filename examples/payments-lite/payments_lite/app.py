"""payments-lite: a small, deliberately flawed payments API we own (DEMO-001).

Never deploy this anywhere. It runs only inside the platform's sandbox, with
synthetic fixture customers and in-memory data. Planted defects are documented
at the class level in README.md and labels.yaml.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .store import Customer, PaymentStore, Refund, seed_store


class RefundRequest(BaseModel):
    amount_cents: int = Field(gt=0)
    reason: str = Field(default="", max_length=200)


def create_app(store: PaymentStore | None = None) -> FastAPI:
    """App factory. Each call gets a fresh in-memory store seeded with fixtures."""
    app = FastAPI(title="payments-lite")
    app.state.store = store if store is not None else seed_store()

    def get_store() -> PaymentStore:
        return app.state.store

    def current_customer(
        authorization: str | None = Header(default=None),
        store: PaymentStore = Depends(get_store),
    ) -> Customer:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        customer = store.customer_for_token(authorization.removeprefix("Bearer ").strip())
        if customer is None:
            raise HTTPException(status_code=401, detail="invalid token")
        return customer

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/payments")
    def list_payments(
        customer: Customer = Depends(current_customer),
        store: PaymentStore = Depends(get_store),
    ) -> list[dict[str, object]]:
        return [p.public() for p in store.payments_for_customer(customer.id)]

    @app.get("/payments/{payment_id}")
    def get_payment(
        payment_id: str,
        customer: Customer = Depends(current_customer),
        store: PaymentStore = Depends(get_store),
    ) -> dict[str, object]:
        payment = store.get_payment(payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="payment not found")
        return payment.public()

    @app.get("/payments/{payment_id}/refunds")
    def list_refunds(
        payment_id: str,
        customer: Customer = Depends(current_customer),
        store: PaymentStore = Depends(get_store),
    ) -> list[dict[str, object]]:
        payment = store.get_payment_for_customer(payment_id, customer.id)
        if payment is None:
            raise HTTPException(status_code=404, detail="payment not found")
        return [r.public() for r in store.refunds_for_payment(payment.id)]

    @app.post("/payments/{payment_id}/refunds", status_code=201)
    def create_refund(
        payment_id: str,
        body: RefundRequest,
        customer: Customer = Depends(current_customer),
        store: PaymentStore = Depends(get_store),
    ) -> dict[str, object]:
        payment = store.get_payment_for_customer(payment_id, customer.id)
        if payment is None:
            raise HTTPException(status_code=404, detail="payment not found")
        refund: Refund = store.add_refund(payment.id, body.amount_cents, body.reason)
        return refund.public()

    return app


app = create_app()
