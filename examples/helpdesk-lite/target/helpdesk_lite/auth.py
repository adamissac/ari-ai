"""Who is calling."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from helpdesk_lite.store import Agent, Store


def get_store(request: Request) -> Store:
    return request.app.state.store


def current_agent(
    authorization: Annotated[str | None, Header()] = None,
    store: Store = Depends(get_store),
) -> Agent:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    agent_id = store.tokens.get(authorization.removeprefix("Bearer "))
    if agent_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return store.agents[agent_id]


def require_admin(agent: Agent) -> None:
    if agent.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admins only")
