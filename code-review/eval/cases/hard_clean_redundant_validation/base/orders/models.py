from dataclasses import dataclass, field

MAX_QTY = 999


class InvalidQuantity(Exception):
    pass


@dataclass(frozen=True)
class Line:
    sku: str
    qty: int

    def __post_init__(self) -> None:
        if not 1 <= self.qty <= MAX_QTY:
            raise InvalidQuantity(self.qty)


@dataclass
class Order:
    lines: list[Line] = field(default_factory=list)
