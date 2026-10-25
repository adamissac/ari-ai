from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RAILWAY_GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
GITHUB_API_URL = "https://api.github.com"
ALERT_TITLE = "[ops-alert] Production storage watchdog"
RAILWAY_USER_AGENT = "ari-storage-watch/1.0"


@dataclass
class VolumeReport:
    name: str
    used_mb: float
    size_mb: float
    pct: float | None
    level: int | None


@dataclass
class Report:
    volumes: list[VolumeReport]
    backup_line: str
    problems: list[str]


def evaluate(
    volumes: Sequence[Mapping[str, Any]],
    backups: Sequence[Mapping[str, Any]],
    now: datetime,
    thresholds: Sequence[int],
    backup_max_age_h: float,
) -> Report:
    if backup_max_age_h < 0:
        raise ValueError("backup_max_age_h must not be negative")
    threshold_levels = sorted(set(int(threshold) for threshold in thresholds))
    if any(threshold < 0 or threshold > 100 for threshold in threshold_levels):
        raise ValueError("thresholds must be between 0 and 100")

    current_time = _as_utc(now)
    results: list[VolumeReport] = []
    problems: list[str] = []

    for volume in volumes:
        name = str(volume["name"])
        used_mb = float(volume["currentSizeMB"])
        size_mb = float(volume["sizeMB"])
        if size_mb <= 0:
            results.append(VolumeReport(name, used_mb, size_mb, None, None))
            continue

        pct = round(100 * used_mb / size_mb, 1)
        level = max(
            (threshold for threshold in threshold_levels if pct >= threshold),
            default=None,
        )
        results.append(VolumeReport(name, used_mb, size_mb, pct, level))
        if level is not None:
            problems.append(f"{name} at {pct:.1f}% ({used_mb:g}/{size_mb:g} MB) — level {level}")

    if not results:
        problems.append("No Railway volumes found for the token's environment.")

    if not backups:
        backup_line = f"No backups found (maximum age {backup_max_age_h:g} hours)."
        problems.append(f"No backups found within the maximum age of {backup_max_age_h:g} hours.")
    else:
        newest = max(backups, key=lambda backup: _backup_created_at(backup))
        created_at = _backup_created_at(newest)
        age_hours = (current_time - created_at).total_seconds() / 3600
        backup_name = str(newest.get("name") or "unnamed")
        created_text = str(newest["createdAt"])
        backup_line = (
            f"Latest backup: `{backup_name}` created {created_text} "
            f"({age_hours:.1f} hours old; maximum {backup_max_age_h:g} hours)."
        )
        if age_hours > backup_max_age_h:
            problems.append(
                f"Latest backup {backup_name!r} is {age_hours:.1f} hours old "
                f"(maximum {backup_max_age_h:g} hours)."
            )

    return Report(results, backup_line, problems)


def render_markdown(report: Report) -> str:
    lines = [
        "# Production storage watchdog",
        "",
        "| Volume | Used MB | Size MB | Usage | Level |",
        "|---|---:|---:|---:|---:|",
    ]
    for volume in report.volumes:
        usage = f"{volume.pct:.1f}%" if volume.pct is not None else "unsized"
        level = str(volume.level) if volume.level is not None else "—"
        lines.append(
            f"| {_markdown_cell(volume.name)} | {volume.used_mb:g} | "
            f"{volume.size_mb:g} | {usage} | {level} |"
        )
    lines.extend(["", report.backup_line, "", "## Problems"])
    if report.problems:
        lines.extend(f"- {problem}" for problem in report.problems)
    else:
        lines.append("- None")
    return "\n".join(lines)


def marker(problems: Sequence[str]) -> str:
    digest = hashlib.sha256("\n".join(sorted(problems)).encode("utf-8")).hexdigest()
    return f"<!-- storage-watch:{digest[:16]} -->"


def sync_issue(client: Any, repo: str, report: Report) -> str:
    issues = client.get(f"/repos/{repo}/issues?state=open&per_page=100")
    if not isinstance(issues, list):
        raise RuntimeError("GitHub returned an unexpected issue list")
    issue = next(
        (
            item
            for item in issues
            if item.get("title") == ALERT_TITLE and "pull_request" not in item
        ),
        None,
    )
    markdown = render_markdown(report)

    if report.problems:
        expected_marker = marker(report.problems)
        body = f"{markdown.rstrip()}\n\n{expected_marker}\n"
        if issue is None:
            client.post(
                f"/repos/{repo}/issues",
                {"title": ALERT_TITLE, "body": body},
            )
            return "created"
        current_marker = _extract_marker(str(issue.get("body") or ""))
        if current_marker == expected_marker:
            return "unchanged"
        number = issue.get("number")
        if number is None:
            raise RuntimeError("Open watchdog issue has no issue number")
        client.patch(
            f"/repos/{repo}/issues/{number}",
            {"body": body},
        )
        client.post(
            f"/repos/{repo}/issues/{number}/comments",
            {"body": markdown},
        )
        return "updated"

    if issue is None:
        return "no open issue"
    number = issue.get("number")
    if number is None:
        raise RuntimeError("Open watchdog issue has no issue number")
    client.post(
        f"/repos/{repo}/issues/{number}/comments",
        {"body": f"Recovered\n\n{markdown}"},
    )
    client.patch(
        f"/repos/{repo}/issues/{number}",
        {"state": "closed"},
    )
    return "closed"


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: Mapping[str, Any]) -> Any:
        return self._request("POST", path, payload)

    def patch(self, path: str, payload: Mapping[str, Any]) -> Any:
        return self._request("PATCH", path, payload)

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{GITHUB_API_URL}{path}",
            data=body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": RAILWAY_USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read()
        except HTTPError as error:
            raise RuntimeError(f"GitHub API returned HTTP {error.code}") from None
        except URLError:
            raise RuntimeError("GitHub API request failed") from None
        return json.loads(response_body) if response_body else None


def parse_thresholds(value: str) -> list[int]:
    try:
        thresholds = [int(part.strip()) for part in value.split(",")]
    except ValueError:
        raise ValueError("WATCH_THRESHOLDS must be comma-separated integers") from None
    if not thresholds or any(threshold < 0 or threshold > 100 for threshold in thresholds):
        raise ValueError("WATCH_THRESHOLDS values must be between 0 and 100")
    return sorted(set(thresholds))


def fetch_railway_data(
    token: str, backup_volume: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    token_data = _railway_graphql(token, "{projectToken{projectId environmentId}}")
    project_token = token_data.get("projectToken")
    if not isinstance(project_token, dict):
        raise RuntimeError("Railway project token did not return project/environment IDs")
    project_id = project_token.get("projectId")
    environment_id = project_token.get("environmentId")
    if not project_id or not environment_id:
        raise RuntimeError("Railway project token did not return project/environment IDs")

    project_query = (
        f"{{project(id:{json.dumps(project_id)})"
        "{volumes{edges{node{name volumeInstances{edges{"
        "node{id sizeMB currentSizeMB environmentId}"
        "}}}}}}}"
    )
    project_data = _railway_graphql(token, project_query).get("project")
    if not isinstance(project_data, dict):
        raise RuntimeError("Railway project query returned no project")

    volumes: list[dict[str, Any]] = []
    backup_instance_id: str | None = None
    volume_edges = project_data.get("volumes", {}).get("edges", [])
    for edge in volume_edges:
        node = edge.get("node") or {}
        name = node.get("name")
        instances = node.get("volumeInstances", {}).get("edges", [])
        for instance_edge in instances:
            instance = instance_edge.get("node") or {}
            if instance.get("environmentId") != environment_id:
                continue
            volume = {
                "name": name,
                "sizeMB": instance.get("sizeMB"),
                "currentSizeMB": instance.get("currentSizeMB"),
            }
            volumes.append(volume)
            if name == backup_volume and backup_instance_id is None:
                backup_instance_id = instance.get("id")

    if backup_instance_id is None:
        return volumes, []

    backup_query = (
        "{volumeInstanceBackupList("
        f"volumeInstanceId:{json.dumps(backup_instance_id)}"
        "){name createdAt expiresAt referencedMB}}"
    )
    backups = _railway_graphql(token, backup_query).get("volumeInstanceBackupList")
    if not isinstance(backups, list):
        raise RuntimeError("Railway backup query returned an unexpected result")
    return volumes, backups


def main() -> int:
    try:
        token = os.environ.get("RAILWAY_TOKEN")
        if not token:
            raise RuntimeError("RAILWAY_TOKEN is required")
        thresholds = parse_thresholds(os.getenv("WATCH_THRESHOLDS", "70,80,90"))
        backup_max_age_h = float(os.getenv("BACKUP_MAX_AGE_HOURS", "36"))
        if not math.isfinite(backup_max_age_h) or backup_max_age_h < 0:
            raise ValueError("BACKUP_MAX_AGE_HOURS must be a finite nonnegative number")
        backup_volume = os.getenv("BACKUP_VOLUME", "postgres-volume")

        volumes, backups = fetch_railway_data(token, backup_volume)
        report = evaluate(
            volumes,
            backups,
            datetime.now(UTC),
            thresholds,
            backup_max_age_h,
        )
        markdown = render_markdown(report)
        print(markdown)

        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as summary:
                summary.write(f"{markdown}\n")

        github_token = os.getenv("GITHUB_TOKEN")
        repository = os.getenv("GITHUB_REPOSITORY")
        if github_token and repository:
            result = sync_issue(GitHubClient(github_token), repository, report)
            print(f"Issue sync: {result}")
        else:
            print("GitHub issue sync skipped: GITHUB_TOKEN or GITHUB_REPOSITORY is unset.")

        return 1 if report.problems else 0
    except (HTTPError, URLError) as error:
        status = error.code if isinstance(error, HTTPError) else "network error"
        print(f"Storage watchdog failed: {status}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Storage watchdog failed: {error}", file=sys.stderr)
        return 1


def _railway_graphql(token: str, query: str) -> dict[str, Any]:
    body = json.dumps({"query": query}).encode("utf-8")
    request = Request(
        RAILWAY_GRAPHQL_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Project-Access-Token": token,
            "User-Agent": RAILWAY_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read()
    except HTTPError as error:
        if error.code == 403:
            response_body = _railway_curl_fallback(body, token)
        else:
            raise RuntimeError(f"Railway GraphQL returned HTTP {error.code}") from None
    except URLError:
        raise RuntimeError("Railway GraphQL request failed") from None

    try:
        payload = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError("Railway GraphQL returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Railway GraphQL returned an unexpected response")
    if "errors" in payload:
        raise RuntimeError("Railway GraphQL returned errors")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Railway GraphQL response has no data")
    return data


def _railway_curl_fallback(body: bytes, token: str) -> bytes:
    # Cloudflare can reject urllib's client fingerprint, so retry 403 with curl's user agent.
    config = "\n".join(
        [
            f"url = {_curl_config_value(RAILWAY_GRAPHQL_URL)}",
            'request = "POST"',
            f"header = {_curl_config_value('Project-Access-Token: ' + token)}",
            'header = "Content-Type: application/json"',
            'user-agent = "curl/8.7.1"',
            f"data-binary = {_curl_config_value(body.decode('utf-8'))}",
            "silent = true",
            "show-error = true",
            "fail-with-body = true",
            'write-out = "\\n%{http_code}"',
        ]
    )
    try:
        response = subprocess.run(
            ["curl", "--config", "-"],
            input=config.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise RuntimeError("Railway GraphQL curl fallback failed") from None
    output = response.stdout.decode("utf-8", errors="replace")
    if "\n" not in output:
        raise RuntimeError("Railway GraphQL curl fallback failed")
    response_body, status_text = output.rsplit("\n", 1)
    try:
        status = int(status_text)
    except ValueError:
        raise RuntimeError("Railway GraphQL curl fallback returned no HTTP status") from None
    if response.returncode != 0 or status >= 400:
        raise RuntimeError(f"Railway GraphQL returned HTTP {status}")
    return response_body.encode("utf-8")


def _curl_config_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r", "\\r").replace("\n", "\\n")
    return f'"{escaped}"'


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _backup_created_at(backup: Mapping[str, Any]) -> datetime:
    value = backup.get("createdAt")
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str):
        try:
            return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            pass
    raise ValueError("backup has an invalid createdAt timestamp")


def _extract_marker(body: str) -> str | None:
    match = re.search(r"<!-- storage-watch:[0-9a-f]{16} -->", body)
    return match.group(0) if match else None


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
