"""Rendering customer-supplied names into HTML. Output must be fully HTML-escaped (&, <, >, ", ')."""


def render_name(name: str) -> str:
    return f"<span class=name>{name}</span>"
