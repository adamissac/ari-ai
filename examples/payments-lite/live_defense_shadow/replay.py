"""Post the owned payments-lite shadow fixture to an Ari ingest token.

Does not attack third parties. Counters are local and labelled owned_staging.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

GROUND = Path(__file__).with_name("ground_truth.json")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", required=True, help="API origin including /api/v1")
    p.add_argument("--project", required=True)
    p.add_argument("--token", required=True)
    args = p.parse_args(argv)
    fixture = json.loads(GROUND.read_text())
    now = datetime.now(UTC)
    for window in fixture["windows"]:
        end = now + timedelta(seconds=int(window["offset_s"]))
        body = {
            "source": "owned_staging",
            "window_start": (end - timedelta(minutes=1)).isoformat(),
            "window_end": end.isoformat(),
            "routes": window["routes"],
        }
        req = Request(
            f"{args.api.rstrip('/')}/ingest/runtime/{args.project}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {args.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req) as resp:
                print(window["id"], resp.status, resp.read().decode()[:300])
        except HTTPError as exc:
            print(window["id"], exc.code, exc.read().decode()[:500], file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
