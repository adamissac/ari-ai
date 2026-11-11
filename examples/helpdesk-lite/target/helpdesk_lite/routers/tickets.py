from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from helpdesk_lite.access import readable_ticket, require_org
from helpdesk_lite.auth import current_agent, get_store
from helpdesk_lite.sqlutil import like_clause
from helpdesk_lite.store import Agent, Store, Ticket

router = APIRouter(tags=["tickets"])


class TicketOut(BaseModel):
    id: str
    customer_id: str
    subject: str
    status: str


class TicketHit(BaseModel):
    id: str
    subject: str
    status: str


def _out(ticket: Ticket) -> TicketOut:
    return TicketOut(
        id=ticket.id, customer_id=ticket.customer_id, subject=ticket.subject, status=ticket.status
    )


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> list[TicketOut]:
    return [_out(t) for t in store.tickets.values() if t.org_id == agent.org_id]


@router.get("/tickets/search", response_model=list[TicketHit])
def search_tickets(
    q: str = Query(min_length=1, max_length=80),
    agent: Agent = Depends(current_agent),
    store: Store = Depends(get_store),
) -> list[TicketHit]:
    sql = (
        "SELECT id, subject, status FROM tickets "
        f"WHERE org_id = ? AND {like_clause('subject', q)} ORDER BY id"
    )
    rows = store.db.execute(sql, (agent.org_id,)).fetchall()
    return [TicketHit(id=r[0], subject=r[1], status=r[2]) for r in rows]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: str, agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> TicketOut:
    return _out(readable_ticket(store, agent, ticket_id))


@router.post("/tickets/{ticket_id}/close", response_model=TicketOut)
def close_ticket(
    ticket_id: str, agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> TicketOut:
    ticket = store.tickets.get(ticket_id)
    require_org(agent, ticket.org_id if ticket else "")
    store.close_ticket(ticket)
    return _out(ticket)
