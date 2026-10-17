"""Local PostgreSQL without Docker: an embedded real PostgreSQL 16 via `pgserver`.

    uv run python -m backend.devdb          # start (idempotent) and print DATABASE_URL
    uv run python -m backend.devdb --stop

Used by tests when DATABASE_URL is unset and by `make dev`. Docker Compose
(`docker compose up`) is the alternative where Docker is installed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[2] / ".dev" / "pgdata"


def start(data_dir: Path = DEFAULT_DIR, database: str = "hackatl") -> str:
    import pgserver  # dev-only dependency

    data_dir.mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(str(data_dir), cleanup_mode=None)
    exists = srv.psql(f"SELECT 1 FROM pg_database WHERE datname = '{database}';")
    if "1 row" not in exists:
        srv.psql(f'CREATE DATABASE "{database}";')
    uri = srv.get_uri(database)
    return uri.replace("postgresql://", "postgresql+psycopg://", 1)


def stop(data_dir: Path = DEFAULT_DIR) -> None:
    import pgserver

    pgserver.get_server(str(data_dir), cleanup_mode="stop").cleanup()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stop", action="store_true")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DIR)
    a = p.parse_args()
    if a.stop:
        stop(a.data_dir)
    else:
        print(start(a.data_dir))
