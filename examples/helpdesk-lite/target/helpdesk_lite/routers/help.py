from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from helpdesk_lite.access import not_found
from helpdesk_lite.files import ARTICLES, article_path

router = APIRouter(tags=["help"])


@router.get("/help/articles/index")
def list_articles() -> list[str]:
    return sorted(p.name for p in ARTICLES.glob("*.md"))


@router.get("/help/articles", response_class=PlainTextResponse)
def read_article(file: str = Query(min_length=1, max_length=200)) -> str:
    try:
        path = Path(article_path(file))
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad article name") from None
    if not path.is_file():
        raise not_found()
    return path.read_text(errors="replace")
