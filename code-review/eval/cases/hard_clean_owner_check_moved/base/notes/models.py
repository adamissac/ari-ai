from dataclasses import dataclass


class NotFound(Exception):
    pass


@dataclass
class Note:
    id: str
    owner: str
    text: str
