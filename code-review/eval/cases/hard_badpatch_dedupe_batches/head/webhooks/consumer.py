from collections.abc import Callable
from typing import Any

from webhooks.dedupe import SeenIds

Event = dict[str, Any]


class Consumer:
    def __init__(self, handler: Callable[[Event], None]) -> None:
        self.handler = handler
        self.handled = 0

    def handle_batch(self, events: list[Event]) -> int:
        seen = SeenIds()
        count = 0
        for event in events:
            if not seen.first_time(event["id"]):
                continue
            self.handler(event)
            count += 1
        self.handled += count
        return count
