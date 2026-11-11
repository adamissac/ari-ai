"""Visibility rules shared by the routers."""

from fastapi import HTTPException, status

from helpdesk_lite.store import Agent, Store, Ticket


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not found")


def require_org(agent: Agent, org_id: str) -> None:
    if agent.org_id != org_id:
        raise not_found()


def visible(agent: Agent, ticket: Ticket) -> bool:
    """Whether the agent may read the ticket. Closed tickets are read-only."""
    return ticket.org_id == agent.org_id or ticket.status == "closed"


def readable_ticket(store: Store, agent: Agent, ticket_id: str) -> Ticket:
    ticket = store.tickets.get(ticket_id)
    if ticket is None or not visible(agent, ticket):
        raise not_found()
    return ticket
