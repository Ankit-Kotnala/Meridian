"""Deterministic in-memory Career Analytics ports for service tests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from uuid import UUID

from rezumi.modules.career_analytics.application import (
    AchievementGrowthPoint,
    AnalyticsSourceWatermark,
    ApplicationAnalyticsFact,
    ApplicationAnalyticsSourcePage,
    ApplicationSourceCursor,
    ReadinessHistoryPoint,
    SupplementalAnalyticsSnapshot,
)
from rezumi.modules.career_analytics.domain import (
    AnalyticsAuditEvent,
    AnalyticsJobStatus,
    AnalyticsOutboxMessage,
    AnalyticsOutboxStatus,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
)

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


class MutableClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class SequenceIdentifiers:
    def __init__(self, start: int = 1) -> None:
        self.value = start

    def new(self) -> UUID:
        result = UUID(int=self.value)
        self.value += 1
        return result


class MemoryCareerAnalytics:
    def __init__(self) -> None:
        self.jobs: dict[UUID, AnalyticsRefreshJob] = {}
        self.outbox: dict[UUID, AnalyticsOutboxMessage] = {}
        self.snapshots: dict[UUID, AnalyticsSnapshot] = {}
        self.audits: list[AnalyticsAuditEvent] = []
        self.capacity_query_calls = 0
        self.compaction_query_calls = 0

    def __call__(self) -> MemoryCareerAnalytics:
        return self

    async def __aenter__(self) -> MemoryCareerAnalytics:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def lock_owner(self, owner_user_id: UUID) -> None:
        _ = owner_user_id

    async def get_job(
        self,
        owner_user_id: UUID,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None:
        _ = for_update
        value = self.jobs.get(job_id)
        return value if value is not None and value.owner_user_id == owner_user_id else None

    async def get_job_by_id(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsRefreshJob | None:
        _ = for_update
        return self.jobs.get(job_id)

    async def find_job_by_idempotency(
        self,
        owner_user_id: UUID,
        idempotency_key: str,
    ) -> AnalyticsRefreshJob | None:
        return next(
            (
                value
                for value in self.jobs.values()
                if value.owner_user_id == owner_user_id and value.idempotency_key == idempotency_key
            ),
            None,
        )

    async def find_latest_job(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
    ) -> AnalyticsRefreshJob | None:
        values = [
            value
            for value in self.jobs.values()
            if value.owner_user_id == owner_user_id
            and value.scope == scope
            and value.window_start == window_start
            and value.window_end == window_end
            and value.timezone == timezone
        ]
        return max(values, key=lambda value: (value.created_at, str(value.id)), default=None)

    async def job_capacity(
        self,
        owner_user_id: UUID,
        *,
        since: datetime,
    ) -> tuple[int, int]:
        self.capacity_query_calls += 1
        active = sum(
            value.owner_user_id == owner_user_id
            and value.status
            in {
                AnalyticsJobStatus.QUEUED,
                AnalyticsJobStatus.RUNNING,
                AnalyticsJobStatus.RETRY_WAIT,
            }
            for value in self.jobs.values()
        )
        replay = sum(
            value.owner_user_id == owner_user_id and value.created_at >= since
            for value in self.jobs.values()
        )
        return active, replay

    async def count_active_jobs(self, owner_user_id: UUID) -> int:
        return sum(
            value.owner_user_id == owner_user_id
            and value.status
            in {
                AnalyticsJobStatus.QUEUED,
                AnalyticsJobStatus.RUNNING,
                AnalyticsJobStatus.RETRY_WAIT,
            }
            for value in self.jobs.values()
        )

    async def compact_terminal_job_history(
        self,
        owner_user_id: UUID,
        *,
        older_than: datetime,
        limit: int,
    ) -> int:
        self.compaction_query_calls += 1
        latest_snapshot = max(
            (value for value in self.snapshots.values() if value.owner_user_id == owner_user_id),
            key=lambda value: (value.created_at, str(value.id)),
            default=None,
        )
        protected_job_id = latest_snapshot.job_id if latest_snapshot is not None else None
        candidates = sorted(
            (
                value
                for value in self.jobs.values()
                if value.owner_user_id == owner_user_id
                and value.status
                in {
                    AnalyticsJobStatus.COMPLETED,
                    AnalyticsJobStatus.DEAD_LETTER,
                }
                and value.updated_at < older_than
                and value.id != protected_job_id
            ),
            key=lambda value: (value.updated_at, str(value.id)),
        )[:limit]
        for job in candidates:
            self.jobs.pop(job.id, None)
            self.outbox = {
                key: value for key, value in self.outbox.items() if value.job_id != job.id
            }
            self.snapshots = {
                key: value for key, value in self.snapshots.items() if value.job_id != job.id
            }
        return len(candidates)

    async def add_job(
        self,
        job: AnalyticsRefreshJob,
        outbox: AnalyticsOutboxMessage,
    ) -> None:
        self.jobs[job.id] = job
        self.outbox[outbox.id] = outbox

    async def save_job(self, job: AnalyticsRefreshJob) -> None:
        self.jobs[job.id] = job

    async def get_outbox(
        self,
        message_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None:
        _ = for_update
        return self.outbox.get(message_id)

    async def get_outbox_for_job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> AnalyticsOutboxMessage | None:
        _ = for_update
        return next(
            (message for message in self.outbox.values() if message.job_id == job_id),
            None,
        )

    async def claim_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        return [
            (value, self.jobs[value.job_id])
            for value in sorted(
                self.outbox.values(),
                key=lambda item: (item.next_attempt_at, str(item.id)),
            )
            if value.status == AnalyticsOutboxStatus.PENDING and value.next_attempt_at <= now
        ][:limit]

    async def save_outbox(self, message: AnalyticsOutboxMessage) -> None:
        self.outbox[message.id] = message

    async def add_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        self.snapshots[snapshot.id] = snapshot

    async def get_latest_snapshot(
        self,
        owner_user_id: UUID,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        timezone: str,
        *,
        for_update: bool = False,
    ) -> AnalyticsSnapshot | None:
        _ = for_update
        values = [
            value
            for value in self.snapshots.values()
            if value.owner_user_id == owner_user_id
            and value.scope == scope
            and value.window_start == window_start
            and value.window_end == window_end
            and value.timezone == timezone
        ]
        return max(values, key=lambda value: (value.created_at, str(value.id)), default=None)

    async def save_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        self.snapshots[snapshot.id] = snapshot

    async def add_audit(self, event: AnalyticsAuditEvent) -> None:
        self.audits.append(event)

    async def claim_expired_job_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        jobs = [
            job
            for job in sorted(
                self.jobs.values(),
                key=lambda value: (value.leased_until or NOW, str(value.id)),
            )
            if job.status == AnalyticsJobStatus.RUNNING
            and job.leased_until is not None
            and job.leased_until < now
        ][:limit]
        return [
            (
                next(message for message in self.outbox.values() if message.job_id == job.id),
                job,
            )
            for job in jobs
        ]

    async def claim_expired_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[AnalyticsOutboxMessage]:
        return [
            message
            for message in sorted(
                self.outbox.values(),
                key=lambda value: (value.leased_until or NOW, str(value.id)),
            )
            if message.status == AnalyticsOutboxStatus.LEASED
            and message.leased_until is not None
            and message.leased_until < now
        ][:limit]

    async def claim_due_deliveries(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]]:
        result: list[tuple[AnalyticsOutboxMessage, AnalyticsRefreshJob]] = []
        for message in sorted(
            self.outbox.values(),
            key=lambda value: (value.next_attempt_at, str(value.id)),
        ):
            job = self.jobs[message.job_id]
            if (
                message.status is AnalyticsOutboxStatus.PUBLISHED
                and message.next_attempt_at <= now
                and job.status
                in {
                    AnalyticsJobStatus.QUEUED,
                    AnalyticsJobStatus.RETRY_WAIT,
                }
                and job.next_attempt_at <= now
            ):
                result.append((message, job))
        return result[:limit]

    async def commit(self) -> None:
        return None


class StaticApplicationSource:
    def __init__(self, facts: tuple[ApplicationAnalyticsFact, ...] = ()) -> None:
        self.facts = list(facts)
        self.generation = 1
        self.page_calls = 0
        self.change_on_first_page = False

    async def watermark(self, owner_user_id: UUID) -> AnalyticsSourceWatermark:
        _ = owner_user_id
        payload = {
            "generation": self.generation,
            "ids": [str(value.application_id) for value in self.facts],
        }
        token = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return AnalyticsSourceWatermark(
            source="applications",
            token=f"sha256:{token}",
            record_count=len(self.facts),
            max_updated_at=max(
                (value.updated_at for value in self.facts),
                default=None,
            ),
        )

    async def page(
        self,
        owner_user_id: UUID,
        *,
        cursor: ApplicationSourceCursor | None,
        limit: int,
    ) -> ApplicationAnalyticsSourcePage:
        _ = owner_user_id
        self.page_calls += 1
        values = sorted(
            self.facts,
            key=lambda value: (value.created_at, str(value.application_id)),
        )
        if cursor is not None:
            values = [
                value
                for value in values
                if (value.created_at, str(value.application_id))
                > (cursor.created_at, str(cursor.application_id))
            ]
        visible = values[:limit]
        next_cursor = None
        if len(values) > limit:
            anchor = visible[-1]
            next_cursor = ApplicationSourceCursor(
                created_at=anchor.created_at,
                application_id=anchor.application_id,
            )
        if self.change_on_first_page and self.page_calls == 1:
            self.generation += 1
        return ApplicationAnalyticsSourcePage(
            data=tuple(deepcopy(visible)),
            next_cursor=next_cursor,
        )


class StaticSupplementalSource:
    def __init__(
        self,
        *,
        readiness: tuple[ReadinessHistoryPoint, ...] = (),
        achievements: tuple[AchievementGrowthPoint, ...] = (),
    ) -> None:
        self.value = SupplementalAnalyticsSnapshot(
            readiness=readiness,
            achievements=achievements,
        )
        self.eligible_achievement_ids = {value.evidence_revision_id for value in achievements}
        self.generation = 1
        self.watermark_windows: list[tuple[date, date]] = []
        self.snapshot_windows: list[tuple[date, date]] = []

    def set_achievement_eligible(
        self,
        evidence_revision_id: UUID,
        *,
        eligible: bool,
    ) -> None:
        if eligible:
            self.eligible_achievement_ids.add(evidence_revision_id)
        else:
            self.eligible_achievement_ids.discard(evidence_revision_id)

    async def watermark(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> AnalyticsSourceWatermark:
        _ = owner_user_id
        self.watermark_windows.append((window_start, window_end))
        selected = self._selected(window_start, window_end)
        payload = {
            "achievements": [
                {
                    "id": str(value.evidence_revision_id),
                    "occurredAt": value.occurred_at.isoformat(),
                }
                for value in selected.achievements
            ],
            "readiness": [
                {
                    "id": str(value.analysis_id),
                    "createdAt": value.created_at.isoformat(),
                }
                for value in selected.readiness
            ],
            "windowEnd": window_end.isoformat(),
            "windowStart": window_start.isoformat(),
        }
        token = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        timestamps = [
            *(value.created_at for value in selected.readiness),
            *(value.occurred_at for value in selected.achievements),
        ]
        return AnalyticsSourceWatermark(
            source="career",
            token=f"sha256:{token}",
            record_count=len(selected.readiness) + len(selected.achievements),
            max_updated_at=max(timestamps, default=None),
        )

    async def snapshot(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> SupplementalAnalyticsSnapshot:
        _ = owner_user_id
        self.snapshot_windows.append((window_start, window_end))
        return deepcopy(self._selected(window_start, window_end))

    def _selected(
        self,
        window_start: date,
        window_end: date,
    ) -> SupplementalAnalyticsSnapshot:
        return SupplementalAnalyticsSnapshot(
            readiness=tuple(
                value
                for value in self.value.readiness
                if window_start <= value.created_at.date() <= window_end
            ),
            achievements=tuple(
                value
                for value in self.value.achievements
                if window_start <= value.occurred_at.date() <= window_end
                and value.evidence_revision_id in self.eligible_achievement_ids
            ),
        )
