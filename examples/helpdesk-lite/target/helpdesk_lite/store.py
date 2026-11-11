"""Seeded in-memory data. Objects live in dicts; tickets and customers are also indexed in
SQLite for search."""

import sqlite3
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Agent:
    id: str
    org_id: str
    name: str
    role: str  # "admin" or "agent"


@dataclass
class Ticket:
    id: str
    org_id: str
    customer_id: str
    subject: str
    status: str  # "open" or "closed"


@dataclass(frozen=True)
class Customer:
    id: str
    org_id: str
    name: str
    email: str


@dataclass(frozen=True)
class Attachment:
    id: str
    ticket_id: str
    filename: str
    size: int


@dataclass
class Store:
    db: sqlite3.Connection
    agents: dict[str, Agent] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    customers: dict[str, Customer] = field(default_factory=dict)
    attachments: dict[str, Attachment] = field(default_factory=dict)

    def add_ticket(self, ticket: Ticket) -> None:
        self.tickets[ticket.id] = ticket
        self.db.execute(
            "INSERT INTO tickets (id, org_id, subject, status) VALUES (?, ?, ?, ?)",
            (ticket.id, ticket.org_id, ticket.subject, ticket.status),
        )

    def add_customer(self, customer: Customer) -> None:
        self.customers[customer.id] = customer
        self.db.execute(
            "INSERT INTO customers (id, org_id, name, email) VALUES (?, ?, ?, ?)",
            (customer.id, customer.org_id, customer.name, customer.email),
        )

    def close_ticket(self, ticket: Ticket) -> None:
        ticket.status = "closed"
        self.db.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket.id,))


def seeded_store() -> Store:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE tickets (id TEXT PRIMARY KEY, org_id TEXT, subject TEXT, status TEXT)")
    db.execute("CREATE TABLE customers (id TEXT PRIMARY KEY, org_id TEXT, name TEXT, email TEXT)")
    store = Store(db=db)
    for agent, token in (
        (Agent("agt_alice", "org_alice", "Alice", "admin"), "fixture-token-alice"),
        (Agent("agt_bob", "org_bob", "Bob", "admin"), "fixture-token-bob"),
        (Agent("agt_carol", "org_alice", "Carol", "agent"), "fixture-token-carol"),
    ):
        store.agents[agent.id] = agent
        store.tokens[token] = agent.id
    store.add_customer(Customer("cus_a1", "org_alice", "Ada Park", "ada@example.test"))
    store.add_customer(Customer("cus_b1", "org_bob", "Ben Ortiz", "ben@example.test"))
    store.add_ticket(Ticket("tkt_a1", "org_alice", "cus_a1", "Refund not received", "closed"))
    store.add_ticket(Ticket("tkt_a2", "org_alice", "cus_a1", "Login loop on mobile", "open"))
    store.add_ticket(
        Ticket("tkt_b1", "org_bob", "cus_b1", "Invoice shows the wrong address", "closed")
    )
    store.add_ticket(Ticket("tkt_b2", "org_bob", "cus_b1", "Cannot add a teammate", "open"))
    store.attachments["att_a1"] = Attachment("att_a1", "tkt_a1", "bank-statement.pdf", 48213)
    store.attachments["att_b1"] = Attachment("att_b1", "tkt_b1", "invoice-0042.pdf", 30127)
    return store
