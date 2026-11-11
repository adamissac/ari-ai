from fastapi import APIRouter, Depends
from pydantic import BaseModel

from helpdesk_lite.access import not_found, readable_ticket
from helpdesk_lite.auth import current_agent, get_store
from helpdesk_lite.store import Agent, Store

router = APIRouter(tags=["attachments"])


class AttachmentOut(BaseModel):
    id: str
    ticket_id: str
    filename: str
    size: int


@router.get("/attachments/{attachment_id}", response_model=AttachmentOut)
def get_attachment(
    attachment_id: str, agent: Agent = Depends(current_agent), store: Store = Depends(get_store)
) -> AttachmentOut:
    attachment = store.attachments.get(attachment_id)
    if attachment is None:
        raise not_found()
    readable_ticket(store, agent, attachment.ticket_id)
    return AttachmentOut(
        id=attachment.id,
        ticket_id=attachment.ticket_id,
        filename=attachment.filename,
        size=attachment.size,
    )
