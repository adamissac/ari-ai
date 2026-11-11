from fastapi import APIRouter, Depends
from pydantic import BaseModel

from helpdesk_lite.auth import current_agent, get_store, require_admin
from helpdesk_lite.store import Agent, Store

router = APIRouter(tags=["admin"])


class AgentOut(BaseModel):
    id: str
    name: str
    role: str


@router.get("/admin/agents", response_model=list[AgentOut])
def list_agents(
    agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> list[AgentOut]:
    require_admin(agent)
    return [
        AgentOut(id=a.id, name=a.name, role=a.role)
        for a in store.agents.values()
        if a.org_id == agent.org_id
    ]
