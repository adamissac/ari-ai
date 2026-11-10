from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventory.reserve import Item


def available(item: Item) -> int:
    """Units that can still be promised to customers."""
    return max(item.on_hand - item.reserved, 0)
