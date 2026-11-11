"""Where downloadable files live."""

import os
from pathlib import Path

DATA = Path(__file__).parent / "data"
ARTICLES = DATA / "articles"
EXPORTS = DATA / "exports"


def article_path(name: str) -> str:
    """Path of a help article. A name may not climb out of the article folder."""
    if ".." in Path(name).parts:
        raise ValueError(name)
    return os.path.join(ARTICLES, name)


def export_path(org_id: str, name: str) -> Path:
    """Path of one of the organization's exports."""
    folder = (EXPORTS / org_id).resolve()
    candidate = (folder / name).resolve()
    if not candidate.is_relative_to(folder):
        raise ValueError(name)
    return candidate
