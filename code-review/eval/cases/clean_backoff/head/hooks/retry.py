"""Webhook retries: delays start at 1s, double each attempt, and are capped at 60s."""

CAP_S = 60


def backoff(attempt: int) -> int:
    """Delay in seconds before retry ``attempt`` (0-based)."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return min(CAP_S, 2**attempt)
