"""helpdesk-lite: a small support desk API.

Agents work the tickets and customers of their own organization. See the README for the
intended behavior.
"""

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from helpdesk_lite.auth import current_agent
from helpdesk_lite.routers import admin, attachments, customers, exports, help, reports, tickets
from helpdesk_lite.store import Agent, Store, seeded_store


class MeOut(BaseModel):
    id: str
    org_id: str
    role: str


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="helpdesk-lite", version="0.1.0")
    app.state.store = store or seeded_store()
    signed_in = [Depends(current_agent)]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me", response_model=MeOut)
    def me(agent: Agent = Depends(current_agent)) -> MeOut:
        return MeOut(id=agent.id, org_id=agent.org_id, role=agent.role)

    app.include_router(tickets.router, dependencies=signed_in)
    app.include_router(customers.router, dependencies=signed_in)
    app.include_router(attachments.router, dependencies=signed_in)
    app.include_router(help.router, dependencies=signed_in)
    app.include_router(exports.router, dependencies=signed_in)
    app.include_router(reports.router)
    app.include_router(admin.router, dependencies=signed_in)
    return app
