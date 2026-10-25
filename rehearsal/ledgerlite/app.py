"""ledgerlite — pilot rehearsal target: a two-tenant ledger API.

Planted defect (for the pilot rehearsal, documented in the repo README):
`GET /entries/{entry_id}` fetches the row but never checks that the
authenticated user's account owns it — a classic object-level authorization
miss (CWE-639). Every other route enforces ownership correctly so a good
reviewer should flag exactly this route and nothing else.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

DB = "ledgerlite.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    account_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    memo TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO users VALUES ('usr_alice','tok-alice','acct_a'),"
            " ('usr_bob','tok-bob','acct_b')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO entries VALUES "
            "('ent_a1','acct_a','invoice-1042',12500),"
            "('ent_a2','acct_a','invoice-1043',9900),"
            "('ent_b1','acct_b','invoice-2001',4400)"
        )


_init()


def current_user(authorization: str = Header(default="")) -> sqlite3.Row:
    token = authorization.removeprefix("Bearer ").strip()
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise HTTPException(401, "invalid token")
    return row


def _entry(entry_id: str) -> sqlite3.Row:
    with db() as conn:
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "entry not found")
    return row


def create_app() -> FastAPI:
    app = FastAPI(title="ledgerlite")

    @app.get("/entries")
    def list_entries(user: sqlite3.Row = Depends(current_user)):
        with db() as conn:
            rows = conn.execute(
                "SELECT id, memo, amount_cents FROM entries WHERE account_id = ?",
                (user["account_id"],),
            ).fetchall()
        return {"items": [dict(r) for r in rows]}

    @app.get("/entries/{entry_id}")
    def get_entry(entry_id: str, user: sqlite3.Row = Depends(current_user)):
        # PLANTED DEFECT: no account_id check — any authenticated user can read
        # any tenant's entry by guessing the id (CWE-639, missing BOLA/IDOR check).
        row = _entry(entry_id)
        return {"id": row["id"], "memo": row["memo"], "amount_cents": row["amount_cents"]}

    @app.get("/accounts/{account_id}/entries")
    def account_entries(account_id: str, user: sqlite3.Row = Depends(current_user)):
        if account_id != user["account_id"]:
            raise HTTPException(403, "not your account")
        with db() as conn:
            rows = conn.execute(
                "SELECT id, memo, amount_cents FROM entries WHERE account_id = ?",
                (account_id,),
            ).fetchall()
        return {"items": [dict(r) for r in rows]}

    @app.post("/entries")
    def create_entry(payload: dict, user: sqlite3.Row = Depends(current_user)):
        memo = str(payload.get("memo", ""))[:200]
        amount = int(payload.get("amount_cents", 0))
        if amount <= 0 or amount > 10_000_000:
            raise HTTPException(422, "amount out of bounds")
        entry_id = f"ent_{user['account_id']}_{abs(hash(memo)) % 10**6}"
        with db() as conn:
            conn.execute(
                "INSERT INTO entries VALUES (?, ?, ?, ?)",
                (entry_id, user["account_id"], memo, amount),
            )
        return {"id": entry_id}

    return app
