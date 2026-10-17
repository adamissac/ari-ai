#!/usr/bin/env python3
"""
Shared Test Result Schema

Provides a common result structure for all QA tests to ensure
consistent PASS/FAIL/SKIP outcomes with proper evidence.

Usage:
    from scripts.devin_qa.shared_test_schema import TestResult, TestSuite
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class TestStatus(Enum):
    """Test execution status."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    BLOCKED = "BLOCKED"


@dataclass
class TestResult:
    """Individual test result with full evidence."""
    name: str
    status: TestStatus
    expected: str
    actual: str
    elapsed_ms: float
    prerequisites: List[str] = field(default_factory=list)
    evidence: str = ""
    error_message: str = ""
    file_location: str = ""
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "expected": self.expected,
            "actual": self.actual,
            "elapsed_ms": self.elapsed_ms,
            "prerequisites": self.prerequisites,
            "evidence": self.evidence,
            "error_message": self.error_message,
            "file_location": self.file_location,
            "line_number": self.line_number,
        }


@dataclass
class TestSuite:
    """Collection of test results with summary."""
    name: str
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None

    def add_result(self, result: TestResult) -> None:
        """Add a test result to the suite."""
        self.results.append(result)

    def finish(self) -> None:
        """Mark the suite as finished."""
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration_ms(self) -> float:
        """Calculate total duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    @property
    def passed_count(self) -> int:
        """Count of passed tests."""
        return sum(1 for r in self.results if r.status == TestStatus.PASS)

    @property
    def failed_count(self) -> int:
        """Count of failed tests."""
        return sum(1 for r in self.results if r.status == TestStatus.FAIL)

    @property
    def skipped_count(self) -> int:
        """Count of skipped tests."""
        return sum(1 for r in self.results if r.status in (TestStatus.SKIP, TestStatus.BLOCKED))

    @property
    def total_count(self) -> int:
        """Total count of tests."""
        return len(self.results)

    @property
    def is_fully_verified(self) -> bool:
        """Return True only if all tests passed and none were skipped."""
        return self.failed_count == 0 and self.skipped_count == 0 and self.passed_count > 0

    @property
    def is_ready_for_demo(self) -> bool:
        """Return True if no tests failed (skips are acceptable for demo prep)."""
        return self.failed_count == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "total_count": self.total_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "is_fully_verified": self.is_fully_verified,
            "is_ready_for_demo": self.is_ready_for_demo,
            "results": [r.to_dict() for r in self.results],
        }

    def print_summary(self) -> None:
        """Print a human-readable summary."""
        print(f"\n{self.name}:")
        print(f"  Total: {self.total_count}")
        print(f"  Passed: {self.passed_count}")
        print(f"  Failed: {self.failed_count}")
        print(f"  Skipped: {self.skipped_count}")
        print(f"  Duration: {self.duration_ms:.0f}ms")
        print(f"  Fully Verified: {self.is_fully_verified}")
        print(f"  Ready for Demo: {self.is_ready_for_demo}")

        if self.failed_count > 0:
            print("\n  Failed tests:")
            for r in self.results:
                if r.status == TestStatus.FAIL:
                    print(f"    - {r.name}: {r.error_message or r.actual}")

        if self.skipped_count > 0:
            print("\n  Skipped tests:")
            for r in self.results:
                if r.status in (TestStatus.SKIP, TestStatus.BLOCKED):
                    print(f"    - {r.name}: {r.actual or 'Prerequisite missing'}")
