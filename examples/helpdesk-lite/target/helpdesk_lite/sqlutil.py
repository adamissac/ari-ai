"""Small helpers for building search queries."""


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def like_clause(column: str, term: str) -> str:
    """SQL fragment matching rows whose column contains the term literally."""
    return f"{column} LIKE '%{_escape_like(term)}%' ESCAPE '\\'"


def contains_param(term: str) -> str:
    """Bound-parameter value matching rows whose column contains the term literally."""
    return f"%{_escape_like(term)}%"


def any_column_like(columns: tuple[str, ...]) -> str:
    """SQL fragment with one bound LIKE per column, OR-ed together."""
    return " OR ".join(f"{column} LIKE ? ESCAPE '\\'" for column in columns)
