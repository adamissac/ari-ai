from dataclasses import dataclass


@dataclass(frozen=True)
class Doc:
    id: str
    tenant: str
    status: str
    title: str


@dataclass(frozen=True)
class User:
    id: str
    tenant: str
