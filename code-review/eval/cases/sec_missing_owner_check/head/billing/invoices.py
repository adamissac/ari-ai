"""Invoices. A customer may only read invoices they own (tenant isolation)."""

from dataclasses import dataclass


class NotFound(Exception):
    pass


@dataclass
class Invoice:
    id: str
    customer_id: str
    total_cents: int


def require_owner(invoice: Invoice, customer_id: str) -> None:
    if invoice.customer_id != customer_id:
        raise NotFound(invoice.id)


def get_invoice(store: dict[str, Invoice], customer_id: str, invoice_id: str) -> Invoice:
    """Look up an invoice; returns a copy so callers cannot mutate the store."""
    invoice = store.get(invoice_id)
    if invoice is None:
        raise NotFound(invoice_id)
    return Invoice(invoice.id, invoice.customer_id, invoice.total_cents)
