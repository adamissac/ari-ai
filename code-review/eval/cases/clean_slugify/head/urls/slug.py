"""Slugs for product URLs."""

import re


def slugify(name: str) -> str:
    """Lowercase ``name``; runs of non-alphanumerics become one hyphen; no leading/trailing hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
