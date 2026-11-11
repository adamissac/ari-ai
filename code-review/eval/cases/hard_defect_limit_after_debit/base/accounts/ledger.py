from dataclasses import dataclass, field


@dataclass
class Ledger:
    balances: dict[str, int]
    sent_today: dict[str, int] = field(default_factory=dict)
