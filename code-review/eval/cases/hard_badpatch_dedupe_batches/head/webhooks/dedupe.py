class SeenIds:
    """Event ids that have already been handled."""

    def __init__(self) -> None:
        self._ids: set[str] = set()

    def first_time(self, event_id: str) -> bool:
        if event_id in self._ids:
            return False
        self._ids.add(event_id)
        return True
