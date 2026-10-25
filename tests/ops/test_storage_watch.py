import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "storage_watch.py"
SPEC = importlib.util.spec_from_file_location("storage_watch", SCRIPT_PATH)
storage_watch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = storage_watch
SPEC.loader.exec_module(storage_watch)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def make_volume(current_mb: float, size_mb: float = 10_000) -> dict[str, object]:
    return {
        "name": "postgres-volume",
        "sizeMB": size_mb,
        "currentSizeMB": current_mb,
    }


def make_backup(age_hours: float, name: str = "Daily Schedule") -> dict[str, str]:
    created_at = NOW - timedelta(hours=age_hours)
    return {
        "name": name,
        "createdAt": created_at.isoformat().replace("+00:00", "Z"),
        "expiresAt": "2026-11-01T00:00:00Z",
        "referencedMB": "0",
    }


class FakeClient:
    def __init__(self, issues: list[dict[str, object]] | None = None) -> None:
        self.issues = list(issues or [])
        self.calls: list[tuple[str, str, object | None]] = []
        self.next_number = 42

    def get(self, path: str) -> list[dict[str, object]]:
        self.calls.append(("GET", path, None))
        return list(self.issues)

    def post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(("POST", path, payload))
        if path.endswith("/issues"):
            issue = {
                "number": self.next_number,
                "title": payload["title"],
                "body": payload["body"],
            }
            self.issues.append(issue)
            return issue
        return {}

    def patch(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(("PATCH", path, payload))
        if self.issues and path.endswith(f"/{self.issues[0].get('number')}"):
            self.issues[0].update(payload)
        return {}


def make_report(problems: list[str], alert_keys: list[str] | None = None) -> storage_watch.Report:
    return storage_watch.Report(
        volumes=[storage_watch.VolumeReport("postgres-volume", 8100, 10_000, 81.0, 80)],
        backup_line="Latest backup: `Daily Schedule` created 2026-10-25T10:00:00Z (2.0 hours old; maximum 36 hours).",
        problems=problems,
        alert_keys=alert_keys
        if alert_keys is not None
        else (["volume:postgres-volume:80"] if problems else []),
    )


class EvaluateTests(unittest.TestCase):
    def test_usage_below_70_has_no_problems(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(6900)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertEqual(report.volumes[0].pct, 69.0)
        self.assertIsNone(report.volumes[0].level)
        self.assertEqual(report.problems, [])

    def test_72_percent_crosses_level_70(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(7200)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertEqual(report.volumes[0].level, 70)
        self.assertEqual(
            report.problems,
            ["postgres-volume at 72.0% (7200/10000 MB) — level 70"],
        )
        self.assertEqual(report.alert_keys, ["volume:postgres-volume:70"])

    def test_91_percent_crosses_level_90(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(9100)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertEqual(report.volumes[0].level, 90)
        self.assertIn("level 90", report.problems[0])
        self.assertEqual(report.alert_keys, ["volume:postgres-volume:90"])

    def test_zero_size_is_reported_unsized_without_a_volume_problem(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(50, size_mb=0)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertIsNone(report.volumes[0].pct)
        self.assertIsNone(report.volumes[0].level)
        self.assertEqual(report.problems, [])
        self.assertEqual(report.alert_keys, [])
        self.assertIn("unsized", storage_watch.render_markdown(report))

    def test_newest_backup_older_than_limit_is_stale(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(1000)],
            [make_backup(48, "Older"), make_backup(40)],
            NOW,
            [70, 80, 90],
            36,
        )

        self.assertEqual(len(report.problems), 1)
        self.assertIn("Daily Schedule", report.problems[0])
        self.assertIn("40.0 hours old", report.problems[0])
        self.assertEqual(report.alert_keys, ["backup:stale"])

    def test_no_backups_is_a_problem(self) -> None:
        report = storage_watch.evaluate([make_volume(1000)], [], NOW, [70, 80, 90], 36)

        self.assertEqual(len(report.problems), 1)
        self.assertIn("No backups found", report.problems[0])
        self.assertEqual(report.alert_keys, ["backup:none"])

    def test_fresh_backup_has_no_problem(self) -> None:
        report = storage_watch.evaluate(
            [make_volume(1000)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertEqual(report.problems, [])
        self.assertIn("Daily Schedule", report.backup_line)
        self.assertEqual(report.alert_keys, [])

    def test_no_volumes_has_a_stable_alert_key(self) -> None:
        report = storage_watch.evaluate([], [make_backup(2)], NOW, [70, 80, 90], 36)

        self.assertEqual(report.alert_keys, ["volumes:none"])

    def test_marker_is_stable_regardless_of_problem_order(self) -> None:
        alert_keys = ["volume:postgres-volume:80", "backup:stale"]

        self.assertEqual(
            storage_watch.marker(alert_keys),
            storage_watch.marker(list(reversed(alert_keys))),
        )

    def test_marker_is_stable_within_a_volume_alert_level(self) -> None:
        report_81 = storage_watch.evaluate(
            [make_volume(8120)], [make_backup(2)], NOW, [70, 80, 90], 36
        )
        report_84 = storage_watch.evaluate(
            [make_volume(8490)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertNotEqual(report_81.problems, report_84.problems)
        self.assertEqual(report_81.alert_keys, ["volume:postgres-volume:80"])
        self.assertEqual(report_81.alert_keys, report_84.alert_keys)
        self.assertEqual(
            storage_watch.marker(report_81.alert_keys),
            storage_watch.marker(report_84.alert_keys),
        )

    def test_marker_is_stable_as_stale_backup_age_changes(self) -> None:
        report_40 = storage_watch.evaluate(
            [make_volume(1000)], [make_backup(40)], NOW, [70, 80, 90], 36
        )
        report_41 = storage_watch.evaluate(
            [make_volume(1000)], [make_backup(41)], NOW, [70, 80, 90], 36
        )

        self.assertNotEqual(report_40.problems, report_41.problems)
        self.assertEqual(report_40.alert_keys, ["backup:stale"])
        self.assertEqual(report_40.alert_keys, report_41.alert_keys)
        self.assertEqual(
            storage_watch.marker(report_40.alert_keys),
            storage_watch.marker(report_41.alert_keys),
        )

    def test_marker_changes_when_volume_alert_level_changes(self) -> None:
        report_80 = storage_watch.evaluate(
            [make_volume(8490)], [make_backup(2)], NOW, [70, 80, 90], 36
        )
        report_90 = storage_watch.evaluate(
            [make_volume(9100)], [make_backup(2)], NOW, [70, 80, 90], 36
        )

        self.assertEqual(report_80.alert_keys, ["volume:postgres-volume:80"])
        self.assertEqual(report_90.alert_keys, ["volume:postgres-volume:90"])
        self.assertNotEqual(
            storage_watch.marker(report_80.alert_keys),
            storage_watch.marker(report_90.alert_keys),
        )


class IssueSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = "adamissac/ari-ai"
        self.report = make_report(["postgres-volume at 81.0% — level 80"])

    def test_creates_issue_when_none_is_open(self) -> None:
        client = FakeClient()

        result = storage_watch.sync_issue(client, self.repo, self.report)

        self.assertEqual(result, "created")
        self.assertEqual([call[0] for call in client.calls], ["GET", "POST"])
        self.assertEqual(client.calls[1][1], f"/repos/{self.repo}/issues")
        payload = client.calls[1][2]
        self.assertEqual(payload["title"], storage_watch.ALERT_TITLE)
        self.assertIn(storage_watch.marker(self.report.alert_keys), payload["body"])

    def test_patches_and_comments_when_marker_changes(self) -> None:
        old_alert_key = "volume:postgres-volume:70"
        issue = {
            "number": 7,
            "title": storage_watch.ALERT_TITLE,
            "body": f"old report\n\n{storage_watch.marker([old_alert_key])}",
        }
        client = FakeClient([issue])

        result = storage_watch.sync_issue(client, self.repo, self.report)

        self.assertEqual(result, "updated")
        self.assertEqual([call[0] for call in client.calls], ["GET", "PATCH", "POST"])
        self.assertIn(storage_watch.marker(self.report.alert_keys), client.calls[1][2]["body"])
        self.assertEqual(
            client.calls[2][1],
            f"/repos/{self.repo}/issues/7/comments",
        )
        self.assertIn("# Production storage watchdog", client.calls[2][2]["body"])

    def test_same_marker_makes_no_mutating_calls(self) -> None:
        issue = {
            "number": 7,
            "title": storage_watch.ALERT_TITLE,
            "body": storage_watch.marker(self.report.alert_keys),
        }
        client = FakeClient([issue])

        result = storage_watch.sync_issue(client, self.repo, self.report)

        self.assertEqual(result, "unchanged")
        self.assertEqual([call[0] for call in client.calls], ["GET"])

    def test_same_volume_level_does_not_mutate_issue_as_usage_changes(self) -> None:
        report_81 = storage_watch.evaluate(
            [make_volume(8120)], [make_backup(2)], NOW, [70, 80, 90], 36
        )
        report_84 = storage_watch.evaluate(
            [make_volume(8490)], [make_backup(2)], NOW, [70, 80, 90], 36
        )
        issue = {
            "number": 7,
            "title": storage_watch.ALERT_TITLE,
            "body": storage_watch.marker(report_81.alert_keys),
        }
        client = FakeClient([issue])

        result = storage_watch.sync_issue(client, self.repo, report_84)

        self.assertEqual(result, "unchanged")
        self.assertEqual([call[0] for call in client.calls], ["GET"])

    def test_recovery_comments_and_closes_issue(self) -> None:
        issue = {
            "number": 7,
            "title": storage_watch.ALERT_TITLE,
            "body": "previous report",
        }
        client = FakeClient([issue])
        healthy_report = make_report([])

        result = storage_watch.sync_issue(client, self.repo, healthy_report)

        self.assertEqual(result, "closed")
        self.assertEqual([call[0] for call in client.calls], ["GET", "POST", "PATCH"])
        self.assertIn("Recovered", client.calls[1][2]["body"])
        self.assertIn("# Production storage watchdog", client.calls[1][2]["body"])
        self.assertEqual(client.calls[2][2], {"state": "closed"})

    def test_healthy_report_with_no_issue_has_no_mutations(self) -> None:
        client = FakeClient()

        result = storage_watch.sync_issue(client, self.repo, make_report([]))

        self.assertEqual(result, "no open issue")
        self.assertEqual([call[0] for call in client.calls], ["GET"])

    def test_pull_requests_are_ignored(self) -> None:
        pull_request = {
            "number": 7,
            "title": storage_watch.ALERT_TITLE,
            "body": "pull request body",
            "pull_request": {"url": "https://api.github.com/repos/adamissac/ari-ai/pulls/7"},
        }
        client = FakeClient([pull_request])

        result = storage_watch.sync_issue(client, self.repo, make_report([]))

        self.assertEqual(result, "no open issue")
        self.assertEqual([call[0] for call in client.calls], ["GET"])


if __name__ == "__main__":
    unittest.main()
