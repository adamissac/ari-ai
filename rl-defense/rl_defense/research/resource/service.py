"""Finite FIFO service on a virtual clock. Units are modeled worker-ticks, not CPU."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SOURCES = 4
ROUTES = 2


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    version: Literal["resource-queue/0.1"] = "resource-queue/0.1"
    workers: int = Field(default=2, ge=1, le=8)
    queue_capacity: int = Field(default=12, ge=1, le=64)
    window_ticks: int = Field(default=8, ge=2, le=32)
    deadline_ticks: int = Field(default=24, ge=1, le=128)
    horizon: int = Field(default=30, ge=1, le=64)
    application_budget: int = Field(default=4, ge=0, le=16)
    duration: int = Field(default=2, ge=1, le=8)
    delay: int = Field(default=1, ge=1, le=4)
    cooldown: int = Field(default=2, ge=0, le=8)
    route_quota: int = Field(default=8, ge=1, le=32)
    source_quota: int = Field(default=3, ge=1, le=32)
    apply_overhead: int = Field(default=1, ge=0, le=1)


@dataclass(frozen=True)
class Arrival:
    tick: int
    source: int
    route: int
    work: int
    adversarial: bool  # METRICS ONLY; never a policy observation/target input

    def __post_init__(self) -> None:
        if any(type(x) is not int for x in (self.tick, self.source, self.route, self.work)):
            raise ValueError("integer arrival fields required")
        if not (
            self.tick >= 0
            and 0 <= self.source < SOURCES
            and 0 <= self.route < ROUTES
            and 1 <= self.work <= 16
        ):
            raise ValueError("arrival outside fixture bounds")
        if type(self.adversarial) is not bool:
            raise ValueError("explicit fixture label required")


@dataclass
class Job:
    arrival: Arrival
    identifier: int
    remaining: int
    started: int | None = None
    outcome: str = "pending"
    finished: int | None = None
    consumed: int = 0


@dataclass
class Window:
    offered: int = 0
    accepted: int = 0
    completed: int = 0
    timeouts: int = 0
    limit_denials: int = 0
    capacity_denials: int = 0
    work: int = 0
    overhead: int = 0
    exhausted_ticks: int = 0
    queue_max: int = 0
    latency_sum: int = 0
    source_arrivals: list[int] = field(default_factory=lambda: [0] * SOURCES)
    source_work: list[int] = field(default_factory=lambda: [0] * SOURCES)
    route_arrivals: list[int] = field(default_factory=lambda: [0] * ROUTES)
    route_work: list[int] = field(default_factory=lambda: [0] * ROUTES)


class Service:
    """Nonpreemptive FIFO, finite in-service+waiting capacity, exact accounting.

    Running jobs retain FIFO order; admission sees workers plus waiting capacity.
    Deadline expiry precedes admission/service each tick. A completion at its exact
    deadline is timely. Each worker supplies at most one work unit per tick.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.now = 0
        self.sequence = 0
        self.jobs: list[Job] = []
        self.pending: list[Job] = []
        self.events: list[dict[str, int | str]] = []
        self.pressure_start: int | None = None
        self.recoveries: list[int] = []

    def event(self, kind: str, job: Job) -> None:
        self.sequence += 1
        self.events.append(
            {
                "kind": kind,
                "job": job.identifier,
                "tick": job.finished
                if kind == "completed" and job.finished is not None
                else self.now,
                "available_seq": self.sequence,
            }
        )

    def advance(
        self,
        arrivals: tuple[Arrival, ...],
        *,
        limit_kind: str | None = None,
        target: int | None = None,
        quota: int = 0,
        overhead: int = 0,
    ) -> Window:
        c = self.config
        if len(arrivals) > 64 or any(
            not self.now <= a.tick < self.now + c.window_ticks for a in arrivals
        ):
            raise ValueError("bounded current-window arrivals required")
        if limit_kind not in (None, "route", "source") or overhead not in (0, 1):
            raise ValueError("unsupported control or overhead")
        if limit_kind is not None and (
            target is None
            or quota < 1
            or not 0 <= target < (ROUTES if limit_kind == "route" else SOURCES)
        ):
            raise ValueError("invalid scoped limit")
        by_tick: dict[int, list[Arrival]] = {}
        for a in arrivals:
            by_tick.setdefault(a.tick, []).append(a)
        result = Window()
        tokens = quota
        for offset in range(c.window_ticks):
            # Old running and waiting jobs expire alike; partial work is retained.
            for j in tuple(self.pending):
                if self.now >= j.arrival.tick + c.deadline_ticks:
                    self.pending.remove(j)
                    j.outcome, j.finished = "timeout", self.now
                    result.timeouts += 1
                    self.event("timeout", j)
            for a in by_tick.get(self.now, ()):
                j = Job(a, len(self.jobs), a.work)
                self.jobs.append(j)
                result.offered += 1
                result.source_arrivals[a.source] += 1
                result.route_arrivals[a.route] += 1
                self.event("offered", j)
                matched = (limit_kind == "source" and a.source == target) or (
                    limit_kind == "route" and a.route == target
                )
                if matched and tokens == 0:
                    j.outcome, j.finished = "rate_limited", self.now
                    result.limit_denials += 1
                else:
                    if matched:
                        tokens -= 1
                    if len(self.pending) >= c.workers + c.queue_capacity:
                        j.outcome, j.finished = "capacity_rejected", self.now
                        result.capacity_denials += 1
                    else:
                        self.pending.append(j)
                        result.accepted += 1
                self.event(j.outcome, j)
            result.queue_max = max(result.queue_max, max(0, len(self.pending) - c.workers))
            full = len(self.pending) >= c.workers + c.queue_capacity
            result.exhausted_ticks += int(full)
            if full and self.pressure_start is None:
                self.pressure_start = self.now
            reserved = overhead if offset == 0 else 0
            result.overhead += reserved
            running = self.pending[: c.workers]
            # Application overhead consumes a worker slot, even when no work arrives.
            for j in running[: c.workers - reserved]:
                if j.started is None:
                    j.started = self.now
                j.remaining -= 1
                j.consumed += 1
                result.work += 1
                result.source_work[j.arrival.source] += 1
                result.route_work[j.arrival.route] += 1
                if j.remaining == 0:
                    self.pending.remove(j)
                    j.outcome, j.finished = "completed", self.now + 1
                    result.completed += 1
                    result.latency_sum += j.finished - j.arrival.tick
                    self.event("completed", j)
            self.now += 1
            if self.pressure_start is not None and len(self.pending) <= c.workers:
                self.recoveries.append(self.now - self.pressure_start)
                self.pressure_start = None
        # Finalize deadline outcomes available at this boundary before observation.
        for j in tuple(self.pending):
            if self.now >= j.arrival.tick + c.deadline_ticks:
                self.pending.remove(j)
                j.outcome, j.finished = "timeout", self.now
                result.timeouts += 1
                self.event("timeout", j)
        self.assert_accounting()
        if result.work + result.overhead > c.workers * c.window_ticks:
            raise AssertionError("resource capacity exceeded")
        return result

    def assert_accounting(self) -> None:
        if len(self.pending) > self.config.workers + self.config.queue_capacity:
            raise AssertionError("queue capacity exceeded")
        for j in self.jobs:
            if j.consumed + j.remaining != j.arrival.work or j.consumed < 0:
                raise AssertionError("work conservation failed")
            if (j in self.pending) != (j.outcome == "pending"):
                raise AssertionError("request outcome accounting failed")

    def metrics(self) -> dict[str, int | float | None]:
        """Generator labels are read ONLY here, after action execution."""
        legitimate = [j for j in self.jobs if not j.arrival.adversarial]
        completed = [j for j in legitimate if j.outcome == "completed"]
        return {
            "offered": len(self.jobs),
            "accepted": sum(
                j.outcome not in ("capacity_rejected", "rate_limited") for j in self.jobs
            ),
            "pending": len(self.pending),
            "adversarial_work": sum(j.consumed for j in self.jobs if j.arrival.adversarial),
            "legitimate_offered": len(legitimate),
            "legitimate_completed": len(completed),
            "legitimate_rate_denied": sum(j.outcome == "rate_limited" for j in legitimate),
            "legitimate_capacity_denied": sum(j.outcome == "capacity_rejected" for j in legitimate),
            "legitimate_timeouts": sum(j.outcome == "timeout" for j in legitimate),
            "legitimate_pending": sum(j.outcome == "pending" for j in legitimate),
            "legitimate_latency_sum": sum((j.finished or 0) - j.arrival.tick for j in completed),
            "legitimate_wait_sum": sum(
                (j.started if j.started is not None else j.arrival.tick) - j.arrival.tick
                for j in completed
            ),
            "legitimate_service_elapsed_sum": sum(
                (j.finished or 0) - (j.started if j.started is not None else j.arrival.tick)
                for j in completed
            ),
            "recovery_count": len(self.recoveries),
            "recovery_ticks_sum": sum(self.recoveries),
            "recovery_pending": int(self.pressure_start is not None),
            "legitimate_completion_fraction": len(completed) / len(legitimate)
            if legitimate
            else None,
        }
