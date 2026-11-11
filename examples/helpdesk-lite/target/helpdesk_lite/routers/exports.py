from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from helpdesk_lite.access import not_found
from helpdesk_lite.auth import current_agent
from helpdesk_lite.files import export_path
from helpdesk_lite.store import Agent

router = APIRouter(tags=["exports"])


@router.get("/exports/download", response_class=PlainTextResponse)
def download_export(
    file: str = Query(min_length=1, max_length=200), agent: Agent = Depends(current_agent)
) -> str:
    try:
        path = export_path(agent.org_id, file)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad export name") from None
    if not path.is_file():
        raise not_found()
    return path.read_text(errors="replace")
