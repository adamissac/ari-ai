from collections.abc import Callable
from typing import Any

Event = dict[str, Any]


class Consumer:
    def __init__(self, handler: Callable[[Event], None]) -> None:
        self.handler = handler
        self.handled = 0

    def handle_batch(self, events: list[Event]) -> int:
        count = 0
        for event in events:
            self.handler(event)
            count += 1
        self.handled += count
        return count
