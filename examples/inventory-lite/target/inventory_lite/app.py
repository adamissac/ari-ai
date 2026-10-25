"""HTTP API for inventory-lite.

Intended behavior (the platform should discover these from docstrings, tests and
conventions):

- A workspace can only read its own profile, items and transfers.
- A transfer quantity must never exceed the item's available stock.
- Quantities are positive integers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from inventory_lite.store import Item, Store, Transfer, Workspace, seeded_store


class ItemOut(BaseModel):
    id: str
    workspace_id: str
    sku: str
    quantity: int
    description: str
    transferred: int


class TransferIn(BaseModel):
    item_id: str
    quantity: int = Field(gt=0)
    destination: str = Field(default="", max_length=200)


class TransferOut(BaseModel):
    id: str
    item_id: str
    quantity: int
    destination: str


class WorkspaceOut(BaseModel):
    id: str
    name: str


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="inventory-lite", version="0.1.0")
    app.state.store = store or seeded_store()

    def get_store() -> Store:
        return app.state.store

    def current_workspace(
        authorization: Annotated[str | None, Header()] = None,
        store: Store = Depends(get_store),
    ) -> Workspace:
        """Resolve the bearer token to a workspace; 401 if missing or unknown."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        workspace_id = store.tokens.get(authorization.removeprefix("Bearer "))
        if workspace_id is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        return store.workspaces[workspace_id]

    def require_owner(resource_workspace_id: str, workspace: Workspace) -> None:
        """A workspace may only access resources it owns. 404 (not 403) avoids leaking existence."""
        if resource_workspace_id != workspace.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")

    def item_out(store: Store, it: Item) -> ItemOut:
        transferred = sum((t.quantity for t in store.transfers_for(it.id)), 0)
        return ItemOut(
            id=it.id,
            workspace_id=it.workspace_id,
            sku=it.sku,
            quantity=it.quantity,
            description=it.description,
            transferred=transferred,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me", response_model=WorkspaceOut)
    def me(workspace: Workspace = Depends(current_workspace)) -> WorkspaceOut:
        return WorkspaceOut(id=workspace.id, name=workspace.name)

    @app.get("/warehouses/{workspace_id}", response_model=WorkspaceOut)
    def get_warehouse(
        workspace_id: str,
        workspace: Workspace = Depends(current_workspace),
        store: Store = Depends(get_store),
    ) -> WorkspaceOut:
        """A workspace can only read its own warehouse profile."""
        target = store.workspaces.get(workspace_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(target.id, workspace)
        return WorkspaceOut(id=target.id, name=target.name)

    @app.get("/items", response_model=list[ItemOut])
    def list_items(
        workspace: Workspace = Depends(current_workspace), store: Store = Depends(get_store)
    ) -> list[ItemOut]:
        """List the current workspace's own items."""
        return [
            item_out(store, it) for it in store.items.values() if it.workspace_id == workspace.id
        ]

    @app.get("/items/{item_id}", response_model=ItemOut)
    def get_item(
        item_id: str,
        workspace: Workspace = Depends(current_workspace),
        store: Store = Depends(get_store),
    ) -> ItemOut:
        """Return one item by id."""
        it = store.items.get(item_id)
        if it is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return item_out(store, it)

    @app.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
    def create_transfer(
        body: TransferIn,
        workspace: Workspace = Depends(current_workspace),
        store: Store = Depends(get_store),
    ) -> TransferOut:
        """Move stock out of an item the workspace owns."""
        it = store.items.get(body.item_id)
        if it is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(it.workspace_id, workspace)
        transferred = sum((t.quantity for t in store.transfers_for(it.id)), 0)
        if transferred + body.quantity > it.quantity:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "insufficient stock")
        t = Transfer(store.next_id("xfr"), it.id, workspace.id, body.quantity, body.destination)
        store.transfers[t.id] = t
        return TransferOut(
            id=t.id, item_id=t.item_id, quantity=t.quantity, destination=t.destination
        )

    @app.get("/transfers/{transfer_id}", response_model=TransferOut)
    def get_transfer(
        transfer_id: str,
        workspace: Workspace = Depends(current_workspace),
        store: Store = Depends(get_store),
    ) -> TransferOut:
        """A workspace can only read its own transfers."""
        t = store.transfers.get(transfer_id)
        if t is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        require_owner(t.workspace_id, workspace)
        return TransferOut(
            id=t.id, item_id=t.item_id, quantity=t.quantity, destination=t.destination
        )

    return app


app = create_app()
