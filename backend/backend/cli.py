"""Console entry points: hackatl-api, hackatl-worker, hackatl-migrate."""

from __future__ import annotations


def serve() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, proxy_headers=True)


def worker() -> None:
    from backend.worker import main

    raise SystemExit(main())


def migrate() -> None:
    from backend.migrate import upgrade

    upgrade()
    print("database migrated to head")
