from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from helpdesk_lite.access import not_found, require_org
from helpdesk_lite.auth import current_agent, get_store
from helpdesk_lite.sqlutil import any_column_like, contains_param
from helpdesk_lite.store import Agent, Store

router = APIRouter(tags=["customers"])
SEARCHED = ("name", "email")


class CustomerOut(BaseModel):
    id: str
    name: str
    email: str


@router.get("/customers/search", response_model=list[CustomerOut])
def search_customers(
    q: str = Query(min_length=1, max_length=80),
    agent: Agent = Depends(current_agent),
    store: Store = Depends(get_store),
) -> list[CustomerOut]:
    sql = (
        "SELECT id, name, email FROM customers "
        f"WHERE org_id = ? AND ({any_column_like(SEARCHED)}) ORDER BY id"
    )
    params = (agent.org_id, *[contains_param(q)] * len(SEARCHED))
    rows = store.db.execute(sql, params).fetchall()
    return [CustomerOut(id=r[0], name=r[1], email=r[2]) for r in rows]


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str, agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> CustomerOut:
    customer = store.customers.get(customer_id)
    if customer is None:
        raise not_found()
    require_org(agent, customer.org_id)
    return CustomerOut(id=customer.id, name=customer.name, email=customer.email)
