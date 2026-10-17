"""Send a correctly signed GitHub webhook to a running API (local demo / smoke testing).

    uv run python -m backend.replay_webhook --repo acme/payments-lite \
        --head <40-hex sha> --base <40-hex sha> --path app/payments.py

Deliveries sent this way are SIMULATED (a locally signed fixture), not real GitHub
traffic; they exercise the exact production verification path.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime

import httpx

from backend.github import sign
from backend.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=None, help="API base URL (default: API_BASE_URL)")
    p.add_argument("--repo", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--base", default=None)
    p.add_argument("--ref", default="refs/heads/main")
    p.add_argument("--path", action="append", default=[], help="changed path (repeatable)")
    a = p.parse_args(argv)
    s = get_settings()
    if not s.github_webhook_secret:
        raise SystemExit("GITHUB_WEBHOOK_SECRET is not set")
    payload = {
        "ref": a.ref,
        "before": a.base or "0" * 40,
        "after": a.head,
        "forced": False,
        "deleted": False,
        "repository": {"full_name": a.repo},
        "sender": {"login": "local-replay"},
        "head_commit": {"timestamp": datetime.now(UTC).isoformat()},
        "commits": [{"added": [], "modified": a.path, "removed": []}],
    }
    raw = json.dumps(payload).encode()
    r = httpx.post(
        f"{a.api or s.api_base_url}/api/v1/webhooks/github",
        content=raw,
        timeout=10,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "X-Hub-Signature-256": sign(s.github_webhook_secret.get_secret_value().encode(), raw),
        },
    )
    print(r.status_code, r.text)
    return 0 if r.status_code in (200, 202) else 1


if __name__ == "__main__":
    raise SystemExit(main())
