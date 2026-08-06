"""Career Analytics use cases, durable refreshes, and freshness enforcement."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rezumi.modules.career_analytics.domain import (
    AnalyticsAuditAction,
    AnalyticsAuditEvent,
    AnalyticsJobStatus,
    AnalyticsOutboxMessage,
    AnalyticsOutboxStatus,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
    AnalyticsSnapshotStatus,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsNotFound,
    CareerAnalyticsQuotaExceeded,
    CareerAnalyticsSourceChanged,
    CareerAnalyticsSourceLimitExceeded,
    CareerAnalyticsUnavailable,
    CareerAnalyticsValidationError,
)

from .aggregation import aggregate
from .models import (
    APPLICATION_COHORT_DEFINITION,
    METRIC_DEFINITION_VERSION,
    TIMESTAMP_SEMANTICS,
    AnalyticsReconciliationOutcome,
    AnalyticsRefreshView,
    AnalyticsReport,
    AnalyticsSourceWatermark,
    ApplicationAnalyticsFact,
    ApplicationSourceCursor,
    ClaimedAnalyticsOutbox,
    RefreshAnalytics,
    RequestContext,
    metric_definitions_payload,
    suppression_policy_payload,
)
from .ports import (
    ApplicationAnalyticsSource,
    CareerAnalyticsUnitOfWork,
    CareerAnalyticsUnitOfWorkFactory,
    Clock,
    IdentifierFactory,
    SupplementalAnalyticsSource,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_RESTRICTED_PAYLOAD_KEYS = frozenset(
    {
        "applicationPack",
        "contact",
        "contactEmail",
        "contactName",
        "evidenceStatement",
        "message",
        "note",
        "offerSummary",
        "rawJobDescription",
        "rawResume",
        "rejectionReason",
        "templateBody",
    }
)


@dataclass(frozen=True, slots=True)
class CareerAnalyticsPolicy:
    source_page_size: int = 100
    max_source_page_size: int = 200
    max_window_days: int = 3_650
    max_attempts: int = 3
    lease_seconds: int = 300
    retry_seconds: int = 30
    max_outbox_batch: int = 100
    max_active_jobs_per_owner: int = 5
    max_job_history_per_owner: int = 1_000
    idempotency_replay_seconds: int = 7 * 24 * 60 * 60

    def __post_init__(self) -> None:
        if not 1 <= self.source_page_size <= self.max_source_page_size <= 500:
            raise ValueError("analytics source page policy is invalid")
        if not 1 <= self.max_window_days <= 3_650:
            raise ValueError("analytics window policy is invalid")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("analytics retry policy is invalid")
        if not 30 <= self.lease_seconds <= 3_600:
            raise ValueError("analytics lease policy is invalid")
        if not 1 <= self.retry_seconds <= 3_600:
            raise ValueError("analytics retry delay is invalid")
        if not 1 <= self.max_outbox_batch <= 500:
            raise ValueError("analytics outbox policy is invalid")
        if not 1 <= self.max_active_jobs_per_owner <= 100:
            raise ValueError("analytics active-job quota is invalid")
        if not self.max_active_jobs_per_owner <= self.max_job_history_per_owner <= 100_000:
            raise ValueError("analytics job-history quota is invalid")
        if not 300 <= self.idempotency_replay_seconds <= 30 * 24 * 60 * 60:
            raise ValueError("analytics idempotency replay horizon is invalid")


class CareerAnalyticsService:
    """Owner-private aggregate analytics with reproducible source watermarks."""

    def __init__(
        self,
        *,
        unit_of_work: CareerAnalyticsUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        applications: ApplicationAnalyticsSource,
        supplemental: SupplementalAnalyticsSource,
        policy: CareerAnalyticsPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._applications = applications
        self._supplemental = supplemental
        self._policy = policy or CareerAnalyticsPolicy()

    async def request_refresh(
        self,
        owner_user_id: UUID,
        command: RefreshAnalytics,
        *,
        idempotency_key: str,
        context: RequestContext,
    ) -> AnalyticsRefreshView:
        self._validate_request(owner_user_id, command, idempotency_key, context)
        fingerprint = _fingerprint(
            {
                "scope": command.scope.value,
                "timezone": command.timezone,
                "windowEnd": command.window_end.isoformat(),
                "windowStart": command.window_start.isoformat(),
            }
        )
        now = self._clock.now()
        async with self._uow() as uow:
            await uow.lock_owner(owner_user_id)
            existing = await uow.find_job_by_idempotency(
                owner_user_id,
                idempotency_key,
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise CareerAnalyticsIdempotencyConflict(
                        "idempotency key was already used for different analytics input"
                    )
                return _refresh_view(existing)
            replay_since = now - timedelta(seconds=self._policy.idempotency_replay_seconds)
            await uow.compact_terminal_job_history(
                owner_user_id,
                older_than=replay_since,
                limit=self._policy.max_job_history_per_owner,
            )
            active_jobs, replay_jobs = await uow.job_capacity(
                owner_user_id,
                since=replay_since,
            )
            if active_jobs >= self._policy.max_active_jobs_per_owner:
                raise CareerAnalyticsQuotaExceeded(
                    "analytics active refresh quota has been reached"
                )
            if replay_jobs >= self._policy.max_job_history_per_owner:
                raise CareerAnalyticsQuotaExceeded(
                    "analytics refresh replay-window quota has been reached"
                )
            job = AnalyticsRefreshJob(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                scope=command.scope,
                window_start=command.window_start,
                window_end=command.window_end,
                timezone=command.timezone,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                status=AnalyticsJobStatus.QUEUED,
                attempts=0,
                max_attempts=self._policy.max_attempts,
                trace_id=context.trace_id,
                source_watermark_before=None,
                source_watermark_after=None,
                lease_token=None,
                leased_until=None,
                next_attempt_at=now,
                safe_error_code=None,
                version=1,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            outbox = AnalyticsOutboxMessage(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                job_id=job.id,
                status=AnalyticsOutboxStatus.PENDING,
                attempts=0,
                max_attempts=self._policy.max_attempts,
                lease_token=None,
                leased_until=None,
                next_attempt_at=now,
                safe_error_code=None,
                created_at=now,
                updated_at=now,
                published_at=None,
            )
            await uow.add_job(job, outbox)
            await uow.add_audit(
                self._audit(
                    job,
                    AnalyticsAuditAction.REFRESH_REQUESTED,
                    context,
                    now,
                )
            )
            await uow.commit()
        return _refresh_view(job)

    async def get_refresh(
        self,
        owner_user_id: UUID,
        job_id: UUID,
    ) -> AnalyticsRefreshView:
        async with self._uow() as uow:
            job = await uow.get_job(owner_user_id, job_id)
        if job is None:
            raise CareerAnalyticsNotFound
        return _refresh_view(job)

    async def process_refresh(
        self,
        job_id: UUID,
        *,
        trace_id: str,
    ) -> AnalyticsRefreshView:
        if _TRACE_ID.fullmatch(trace_id) is None:
            raise CareerAnalyticsValidationError("trace id is invalid")
        token = self._ids.new()
        now = self._clock.now()
        async with self._uow() as uow:
            job = await uow.get_job_by_id(job_id, for_update=True)
            if job is None:
                raise CareerAnalyticsNotFound
            if trace_id != job.trace_id:
                raise CareerAnalyticsValidationError(
                    "analytics worker trace does not match durable state"
                )
            if job.status == AnalyticsJobStatus.COMPLETED:
                return _refresh_view(job)
            job.claim(
                token=token,
                now=now,
                leased_until=now + timedelta(seconds=self._policy.lease_seconds),
            )
            await uow.save_job(job)
            await uow.add_audit(
                AnalyticsAuditEvent(
                    id=self._ids.new(),
                    owner_user_id=job.owner_user_id,
                    action=AnalyticsAuditAction.REFRESH_STARTED,
                    target_type="analytics_refresh_job",
                    target_id=job.id,
                    actor_user_id=None,
                    request_id=None,
                    trace_id=trace_id,
                    metadata={"attempt": str(job.attempts), "scope": job.scope.value},
                    created_at=now,
                )
            )
            await uow.commit()

        try:
            before = await self._watermarks(
                job.owner_user_id,
                window_start=job.window_start,
                window_end=job.window_end,
            )
            applications = await self._read_applications(job.owner_user_id)
            supplemental_start, supplemental_end = _supplemental_window(
                job.window_start,
                job.window_end,
            )
            supplemental = await self._supplemental.snapshot(
                job.owner_user_id,
                window_start=supplemental_start,
                window_end=supplemental_end,
            )
            payload = aggregate(
                scope=job.scope,
                applications=applications,
                supplemental=supplemental,
                window_start=job.window_start,
                window_end=job.window_end,
                timezone=job.timezone,
            )
            serialized = payload.as_dict()
            _validate_private_payload(serialized)
        except CareerAnalyticsSourceChanged:
            return await self._record_failure(
                job_id,
                token=token,
                safe_error_code="source_changed",
                trace_id=trace_id,
            )
        except CareerAnalyticsSourceLimitExceeded:
            return await self._record_failure(
                job_id,
                token=token,
                safe_error_code="source_limit_exceeded",
                trace_id=trace_id,
            )
        except CareerAnalyticsUnavailable:
            return await self._record_failure(
                job_id,
                token=token,
                safe_error_code="source_unavailable",
                trace_id=trace_id,
            )
        except Exception as exc:
            await self._record_failure(
                job_id,
                token=token,
                safe_error_code="aggregation_failed",
                trace_id=trace_id,
            )
            raise CareerAnalyticsUnavailable("analytics aggregation failed safely") from exc

        try:
            after = await self._watermarks(
                job.owner_user_id,
                window_start=job.window_start,
                window_end=job.window_end,
            )
        except Exception as exc:
            safe_error_code = (
                "source_limit_exceeded"
                if isinstance(exc, CareerAnalyticsSourceLimitExceeded)
                else "source_unavailable"
                if isinstance(exc, CareerAnalyticsUnavailable)
                else "aggregation_failed"
            )
            failed = await self._record_failure(
                job_id,
                token=token,
                safe_error_code=safe_error_code,
                trace_id=trace_id,
            )
            if safe_error_code != "aggregation_failed":
                return failed
            raise CareerAnalyticsUnavailable(
                "analytics pre-commit watermark check failed safely"
            ) from exc
        if _watermark_tokens(before) != _watermark_tokens(after):
            return await self._record_failure(
                job_id,
                token=token,
                safe_error_code="source_changed",
                trace_id=trace_id,
            )
        async with self._uow() as uow:
            current = await uow.get_job_by_id(job_id, for_update=True)
            if current is None:
                raise CareerAnalyticsNotFound
            completed_at = self._clock.now()
            current.complete(
                token=token,
                before=_watermark_payload(before),
                after=_watermark_payload(after),
                now=completed_at,
            )
            snapshot = AnalyticsSnapshot(
                id=self._ids.new(),
                owner_user_id=current.owner_user_id,
                job_id=current.id,
                scope=current.scope,
                metric_definition_version=METRIC_DEFINITION_VERSION,
                window_start=current.window_start,
                window_end=current.window_end,
                timezone=current.timezone,
                source_watermark=_watermark_payload(before),
                payload=serialized,
                payload_sha256=payload.sha256(),
                status=AnalyticsSnapshotStatus.READY,
                created_at=completed_at,
                stale_at=None,
            )
            await uow.add_snapshot(snapshot)
            await uow.save_job(current)
            await uow.add_audit(
                AnalyticsAuditEvent(
                    id=self._ids.new(),
                    owner_user_id=current.owner_user_id,
                    action=AnalyticsAuditAction.SNAPSHOT_CREATED,
                    target_type="analytics_snapshot",
                    target_id=snapshot.id,
                    actor_user_id=None,
                    request_id=None,
                    trace_id=trace_id,
                    metadata={
                        "metric_version": METRIC_DEFINITION_VERSION,
                        "scope": current.scope.value,
                    },
                    created_at=completed_at,
                )
            )
            await uow.commit()
        return _refresh_view(current)

    async def get_report(
        self,
        owner_user_id: UUID,
        *,
        scope: AnalyticsScope,
        window_start: date,
        window_end: date,
        context: RequestContext,
        timezone: str = "UTC",
    ) -> AnalyticsReport:
        self._validate_context(owner_user_id, context)
        self._validate_window(window_start, window_end)
        self._validate_timezone(timezone)
        async with self._uow() as uow:
            snapshot = await uow.get_latest_snapshot(
                owner_user_id,
                scope,
                window_start,
                window_end,
                timezone,
            )
            refresh = await uow.find_latest_job(
                owner_user_id,
                scope,
                window_start,
                window_end,
                timezone,
            )
        refresh_view = _refresh_view(refresh) if refresh is not None else None
        if snapshot is None:
            freshness = (
                "refreshing"
                if refresh is not None
                and refresh.status
                in {
                    AnalyticsJobStatus.QUEUED,
                    AnalyticsJobStatus.RUNNING,
                    AnalyticsJobStatus.RETRY_WAIT,
                }
                else "failed"
                if refresh is not None and refresh.status == AnalyticsJobStatus.DEAD_LETTER
                else "empty"
            )
            return AnalyticsReport(
                scope=scope,
                status=None,
                freshness=freshness,
                metric_definition_version=METRIC_DEFINITION_VERSION,
                window_start=window_start,
                window_end=window_end,
                timezone=timezone,
                cohort_definition=APPLICATION_COHORT_DEFINITION,
                metric_definitions=metric_definitions_payload(),
                suppression_policy=suppression_policy_payload(),
                timestamp_semantics=dict(TIMESTAMP_SEMANTICS),
                source_watermarks={},
                payload=None,
                generated_at=None,
                refresh=refresh_view,
            )
        if not snapshot.verify_payload_hash():
            raise CareerAnalyticsUnavailable("analytics snapshot integrity check failed")
        current = await self._watermarks(
            owner_user_id,
            window_start=window_start,
            window_end=window_end,
        )
        stale = snapshot.status == AnalyticsSnapshotStatus.STALE or _stored_tokens(
            snapshot.source_watermark
        ) != _watermark_tokens(current)
        if stale and snapshot.status == AnalyticsSnapshotStatus.READY:
            stale_at = self._clock.now()
            async with self._uow() as uow:
                persisted = await uow.get_latest_snapshot(
                    owner_user_id,
                    scope,
                    window_start,
                    window_end,
                    timezone,
                    for_update=True,
                )
                if (
                    persisted is not None
                    and persisted.id == snapshot.id
                    and persisted.status == AnalyticsSnapshotStatus.READY
                ):
                    persisted.mark_stale(stale_at)
                    await uow.save_snapshot(persisted)
                    await uow.add_audit(
                        AnalyticsAuditEvent(
                            id=self._ids.new(),
                            owner_user_id=owner_user_id,
                            action=AnalyticsAuditAction.SNAPSHOT_MARKED_STALE,
                            target_type="analytics_snapshot",
                            target_id=persisted.id,
                            actor_user_id=context.actor_user_id,
                            request_id=context.request_id,
                            trace_id=context.trace_id,
                            metadata={
                                "scope": scope.value,
                                "timezone": timezone,
                            },
                            created_at=stale_at,
                        )
                    )
                    await uow.commit()
        return AnalyticsReport(
            scope=scope,
            status=(AnalyticsSnapshotStatus.STALE if stale else AnalyticsSnapshotStatus.READY),
            freshness="stale" if stale else "current",
            metric_definition_version=snapshot.metric_definition_version,
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            timezone=snapshot.timezone,
            cohort_definition=APPLICATION_COHORT_DEFINITION,
            metric_definitions=metric_definitions_payload(),
            suppression_policy=suppression_policy_payload(),
            timestamp_semantics=dict(TIMESTAMP_SEMANTICS),
            source_watermarks=snapshot.source_watermark,
            payload=None if stale else snapshot.payload,
            generated_at=snapshot.created_at,
            refresh=refresh_view,
        )

    async def claim_outbox(self, *, limit: int = 50) -> tuple[ClaimedAnalyticsOutbox, ...]:
        if not 1 <= limit <= self._policy.max_outbox_batch:
            raise CareerAnalyticsValidationError("outbox limit is invalid")
        now = self._clock.now()
        claimed: list[ClaimedAnalyticsOutbox] = []
        async with self._uow() as uow:
            deliveries = await uow.claim_outbox(now=now, limit=limit)
            for message, job in deliveries:
                if job.id != message.job_id or job.owner_user_id != message.owner_user_id:
                    raise CareerAnalyticsNotFound
                token = self._ids.new()
                message.claim(
                    token=token,
                    now=now,
                    leased_until=now + timedelta(seconds=self._policy.lease_seconds),
                )
                await uow.save_outbox(message)
                claimed.append(
                    ClaimedAnalyticsOutbox(
                        message_id=message.id,
                        job_id=message.job_id,
                        lease_token=token,
                        job_version_at_claim=job.version,
                    )
                )
            await uow.commit()
        return tuple(claimed)

    async def mark_outbox_published(
        self,
        message_id: UUID,
        *,
        lease_token: UUID,
        job_version_at_claim: int,
    ) -> None:
        if job_version_at_claim < 1:
            raise CareerAnalyticsValidationError("claimed analytics job version is invalid")
        now = self._clock.now()
        async with self._uow() as uow:
            message = await uow.get_outbox(message_id, for_update=True)
            if message is None:
                raise CareerAnalyticsNotFound
            job = await uow.get_job_by_id(message.job_id, for_update=True)
            if job is None or job.owner_user_id != message.owner_user_id:
                raise CareerAnalyticsNotFound
            message.published(
                token=lease_token,
                now=now,
                recovery_at=now + timedelta(seconds=self._policy.lease_seconds),
            )
            await uow.save_outbox(message)
            # A fast worker can transition this job before the publisher records
            # its broker acknowledgement. The version captured under the same
            # row locks as the outbox claim distinguishes that race from a
            # normal retry publication, which must remain PUBLISHED until the
            # worker gets its bounded opportunity.
            if job.status is AnalyticsJobStatus.RETRY_WAIT and job.version != job_version_at_claim:
                await self._prepare_retry_delivery(
                    uow,
                    message,
                    job,
                    now=now,
                )
            await uow.commit()

    async def mark_outbox_failed(
        self,
        message_id: UUID,
        *,
        lease_token: UUID,
        safe_error_code: str = "publish_failed",
    ) -> None:
        now = self._clock.now()
        async with self._uow() as uow:
            message = await uow.get_outbox(message_id, for_update=True)
            if message is None:
                raise CareerAnalyticsNotFound
            message.failed(
                token=lease_token,
                safe_error_code=safe_error_code,
                retry_at=now + timedelta(seconds=self._policy.retry_seconds),
                now=now,
            )
            await uow.save_outbox(message)
            if message.status is AnalyticsOutboxStatus.DEAD_LETTER:
                await self._dead_letter_undelivered_job(
                    uow,
                    message,
                    safe_error_code=safe_error_code,
                    now=now,
                )
            await uow.commit()

    async def reconcile_expired(
        self,
        *,
        limit: int = 100,
    ) -> AnalyticsReconciliationOutcome:
        if not 1 <= limit <= 500:
            raise CareerAnalyticsValidationError("reconciliation limit is invalid")
        now = self._clock.now()
        recovered_jobs = 0
        dead_lettered_jobs = 0
        recovered_outbox = 0
        dead_lettered_outbox = 0
        requeued_deliveries = 0
        async with self._uow() as uow:
            # Keep the same outbox-to-job lock order as explicit publish failure.
            expired_outbox = await uow.claim_expired_outbox(now=now, limit=limit)
            for message in expired_outbox:
                message.recover_expired(now=now)
                await uow.save_outbox(message)
                if message.status is AnalyticsOutboxStatus.DEAD_LETTER:
                    dead_lettered_outbox += 1
                    if await self._dead_letter_undelivered_job(
                        uow,
                        message,
                        safe_error_code="lease_expired",
                        now=now,
                    ):
                        dead_lettered_jobs += 1
                else:
                    recovered_outbox += 1
            expired_job_deliveries = await uow.claim_expired_job_deliveries(
                now=now,
                limit=limit,
            )
            for message, job in expired_job_deliveries:
                job.recover_expired(now=now)
                await uow.save_job(job)
                terminalized_by_delivery = False
                delivery_status_before = message.status
                if job.status is AnalyticsJobStatus.RETRY_WAIT:
                    terminalized_by_delivery = await self._prepare_retry_delivery(
                        uow,
                        message,
                        job,
                        now=now,
                    )
                if (
                    delivery_status_before is AnalyticsOutboxStatus.PUBLISHED
                    and message.status is AnalyticsOutboxStatus.PENDING
                ):
                    requeued_deliveries += 1
                elif (
                    delivery_status_before is not AnalyticsOutboxStatus.DEAD_LETTER
                    and message.status is AnalyticsOutboxStatus.DEAD_LETTER
                ):
                    dead_lettered_outbox += 1
                if terminalized_by_delivery:
                    dead_lettered_jobs += 1
                else:
                    if job.status is AnalyticsJobStatus.DEAD_LETTER:
                        dead_lettered_jobs += 1
                    else:
                        recovered_jobs += 1
                    await uow.add_audit(
                        self._worker_failure_audit(
                            job,
                            safe_error_code="lease_expired",
                            trace_id=job.trace_id,
                            now=now,
                            failure_stage="refresh_processing",
                        )
                    )
            due_deliveries = await uow.claim_due_deliveries(now=now, limit=limit)
            for message, _job in due_deliveries:
                message.recover_published(
                    safe_error_code="delivery_unconfirmed",
                    retry_at=now,
                    now=now,
                )
                await uow.save_outbox(message)
                if message.status is AnalyticsOutboxStatus.DEAD_LETTER:
                    dead_lettered_outbox += 1
                    if await self._dead_letter_undelivered_job(
                        uow,
                        message,
                        safe_error_code="delivery_attempts_exhausted",
                        now=now,
                    ):
                        dead_lettered_jobs += 1
                else:
                    requeued_deliveries += 1
            await uow.commit()
        return AnalyticsReconciliationOutcome(
            recovered_jobs=recovered_jobs,
            dead_lettered_jobs=dead_lettered_jobs,
            recovered_outbox=recovered_outbox,
            dead_lettered_outbox=dead_lettered_outbox,
            requeued_deliveries=requeued_deliveries,
        )

    async def _dead_letter_undelivered_job(
        self,
        uow: CareerAnalyticsUnitOfWork,
        message: AnalyticsOutboxMessage,
        *,
        safe_error_code: str,
        now: datetime,
    ) -> bool:
        job = await uow.get_job_by_id(message.job_id, for_update=True)
        if job is None or job.owner_user_id != message.owner_user_id:
            raise CareerAnalyticsNotFound
        # A broker handoff can succeed even when its acknowledgement fails.
        # Never overwrite a job that a worker currently owns or completed.
        if job.status not in {
            AnalyticsJobStatus.QUEUED,
            AnalyticsJobStatus.RETRY_WAIT,
        }:
            return False
        job.dead_letter_undelivered(safe_error_code=safe_error_code, now=now)
        await uow.save_job(job)
        await uow.add_audit(
            self._worker_failure_audit(
                job,
                safe_error_code=safe_error_code,
                trace_id=job.trace_id,
                now=now,
                failure_stage="outbox_publish",
            )
        )
        return True

    async def _prepare_retry_delivery(
        self,
        uow: CareerAnalyticsUnitOfWork,
        message: AnalyticsOutboxMessage,
        job: AnalyticsRefreshJob,
        *,
        now: datetime,
    ) -> bool:
        """Move a retry back behind the leased outbox or terminalize it."""

        if job.status is not AnalyticsJobStatus.RETRY_WAIT:
            return False
        if message.status is AnalyticsOutboxStatus.PUBLISHED:
            message.recover_published(
                safe_error_code=job.safe_error_code or "refresh_retry",
                retry_at=job.next_attempt_at,
                now=now,
            )
            await uow.save_outbox(message)
        if message.status is not AnalyticsOutboxStatus.DEAD_LETTER:
            return False
        return await self._dead_letter_undelivered_job(
            uow,
            message,
            safe_error_code="delivery_attempts_exhausted",
            now=now,
        )

    async def _record_failure(
        self,
        job_id: UUID,
        *,
        token: UUID,
        safe_error_code: str,
        trace_id: str,
    ) -> AnalyticsRefreshView:
        now = self._clock.now()
        async with self._uow() as uow:
            message = await uow.get_outbox_for_job(job_id, for_update=True)
            if message is None:
                raise CareerAnalyticsNotFound
            job = await uow.get_job_by_id(job_id, for_update=True)
            if job is None or job.owner_user_id != message.owner_user_id:
                raise CareerAnalyticsNotFound
            job.fail(
                token=token,
                safe_error_code=safe_error_code,
                retry_at=now + timedelta(seconds=self._policy.retry_seconds),
                now=now,
            )
            await uow.save_job(job)
            terminalized_by_delivery = await self._prepare_retry_delivery(
                uow,
                message,
                job,
                now=now,
            )
            if not terminalized_by_delivery:
                await uow.add_audit(
                    self._worker_failure_audit(
                        job,
                        safe_error_code=safe_error_code,
                        trace_id=trace_id,
                        now=now,
                    )
                )
            await uow.commit()
        return _refresh_view(job)

    async def _read_applications(
        self,
        owner_user_id: UUID,
    ) -> tuple[ApplicationAnalyticsFact, ...]:
        cursor: ApplicationSourceCursor | None = None
        facts: list[ApplicationAnalyticsFact] = []
        seen_ids: set[UUID] = set()
        seen_cursors: set[tuple[datetime, UUID]] = set()
        while True:
            page = await self._applications.page(
                owner_user_id,
                cursor=cursor,
                limit=self._policy.source_page_size,
            )
            for fact in page.data:
                if fact.application_id in seen_ids:
                    raise CareerAnalyticsUnavailable(
                        "analytics source returned a duplicate application"
                    )
                seen_ids.add(fact.application_id)
                facts.append(fact)
            if page.next_cursor is None:
                return tuple(facts)
            cursor_key = (
                page.next_cursor.created_at,
                page.next_cursor.application_id,
            )
            if cursor_key in seen_cursors or page.next_cursor == cursor:
                raise CareerAnalyticsUnavailable("analytics source cursor did not advance")
            seen_cursors.add(cursor_key)
            cursor = page.next_cursor

    async def _watermarks(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> tuple[AnalyticsSourceWatermark, AnalyticsSourceWatermark]:
        supplemental_start, supplemental_end = _supplemental_window(
            window_start,
            window_end,
        )
        application, supplemental = await asyncio.gather(
            self._applications.watermark(owner_user_id),
            self._supplemental.watermark(
                owner_user_id,
                window_start=supplemental_start,
                window_end=supplemental_end,
            ),
        )
        return application, supplemental

    def _validate_request(
        self,
        owner_user_id: UUID,
        command: RefreshAnalytics,
        idempotency_key: str,
        context: RequestContext,
    ) -> None:
        self._validate_context(owner_user_id, context)
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise CareerAnalyticsValidationError("idempotency key is invalid")
        self._validate_window(command.window_start, command.window_end)
        self._validate_timezone(command.timezone)

    def _validate_context(
        self,
        owner_user_id: UUID,
        context: RequestContext,
    ) -> None:
        if context.actor_user_id != owner_user_id:
            raise CareerAnalyticsValidationError("analytics actor does not match owner")
        if _TRACE_ID.fullmatch(context.trace_id) is None:
            raise CareerAnalyticsValidationError("trace id is invalid")
        if not 1 <= len(context.request_id) <= 128:
            raise CareerAnalyticsValidationError("request id is invalid")

    def _validate_window(self, window_start: date, window_end: date) -> None:
        if (
            window_end < window_start
            or (window_end - window_start).days > self._policy.max_window_days
        ):
            raise CareerAnalyticsValidationError(
                "analytics window must be ordered and no longer than ten years"
            )

    def _validate_timezone(self, timezone: str) -> None:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise CareerAnalyticsValidationError("timezone is invalid") from exc

    def _audit(
        self,
        job: AnalyticsRefreshJob,
        action: AnalyticsAuditAction,
        context: RequestContext,
        now: datetime,
    ) -> AnalyticsAuditEvent:
        return AnalyticsAuditEvent(
            id=self._ids.new(),
            owner_user_id=job.owner_user_id,
            action=action,
            target_type="analytics_refresh_job",
            target_id=job.id,
            actor_user_id=context.actor_user_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            metadata={"scope": job.scope.value},
            created_at=now,
        )

    def _worker_failure_audit(
        self,
        job: AnalyticsRefreshJob,
        *,
        safe_error_code: str,
        trace_id: str,
        now: datetime,
        failure_stage: str | None = None,
    ) -> AnalyticsAuditEvent:
        metadata = {
            "error_code": safe_error_code,
            "scope": job.scope.value,
        }
        if failure_stage is not None:
            metadata["failure_stage"] = failure_stage
        return AnalyticsAuditEvent(
            id=self._ids.new(),
            owner_user_id=job.owner_user_id,
            action=(
                AnalyticsAuditAction.REFRESH_DEAD_LETTERED
                if job.status == AnalyticsJobStatus.DEAD_LETTER
                else AnalyticsAuditAction.REFRESH_RETRY_SCHEDULED
            ),
            target_type="analytics_refresh_job",
            target_id=job.id,
            actor_user_id=None,
            request_id=None,
            trace_id=trace_id,
            metadata=metadata,
            created_at=now,
        )


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _supplemental_window(window_start: date, window_end: date) -> tuple[date, date]:
    """Guard UTC-date source queries for every supported IANA timezone offset."""

    return (
        window_start if window_start == date.min else window_start - timedelta(days=1),
        window_end if window_end == date.max else window_end + timedelta(days=1),
    )


def _refresh_view(job: AnalyticsRefreshJob) -> AnalyticsRefreshView:
    return AnalyticsRefreshView(
        id=job.id,
        scope=job.scope,
        window_start=job.window_start,
        window_end=job.window_end,
        timezone=job.timezone,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        safe_error_code=job.safe_error_code,
        version=job.version,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def _watermark_payload(
    values: tuple[AnalyticsSourceWatermark, ...],
) -> dict[str, object]:
    return {value.source: value.as_dict() for value in values}


def _watermark_tokens(
    values: tuple[AnalyticsSourceWatermark, ...],
) -> dict[str, str]:
    return {value.source: value.token for value in values}


def _stored_tokens(values: dict[str, object]) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for source, raw in values.items():
        if not isinstance(raw, dict) or not isinstance(raw.get("token"), str):
            raise CareerAnalyticsUnavailable("analytics watermark is malformed")
        tokens[source] = raw["token"]
    return tokens


def _validate_private_payload(value: object, *, key: str | None = None) -> None:
    if key in _RESTRICTED_PAYLOAD_KEYS:
        raise CareerAnalyticsValidationError(
            "analytics payload contains a restricted content field"
        )
    if isinstance(value, dict):
        if len(value) > 100:
            raise CareerAnalyticsValidationError("analytics payload object is too large")
        for child_key, child_value in value.items():
            if not isinstance(child_key, str) or len(child_key) > 120:
                raise CareerAnalyticsValidationError("analytics payload key is invalid")
            _validate_private_payload(child_value, key=child_key)
    elif isinstance(value, list):
        if len(value) > 500:
            raise CareerAnalyticsValidationError("analytics payload list is too large")
        for child in value:
            _validate_private_payload(child)
    elif isinstance(value, str) and len(value) > 500:
        raise CareerAnalyticsValidationError("analytics payload text is too long")
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise CareerAnalyticsValidationError("analytics payload value is invalid")
