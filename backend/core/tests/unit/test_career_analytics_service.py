"""Career Analytics grounding, privacy, completeness, and job safety tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from career_analytics_memory import (
    NOW,
    MemoryCareerAnalytics,
    MutableClock,
    SequenceIdentifiers,
    StaticApplicationSource,
    StaticSupplementalSource,
)
from rezumi.modules.career_analytics.application import (
    ANALYTICS_INTERPRETATION,
    AchievementGrowthPoint,
    AnalyticsReconciliationOutcome,
    AnalyticsSourceWatermark,
    ApplicationAnalyticsFact,
    CareerAnalyticsPolicy,
    CareerAnalyticsService,
    ReadinessHistoryPoint,
    RefreshAnalytics,
    RequestContext,
    SupplementalAnalyticsSnapshot,
    aggregate,
)
from rezumi.modules.career_analytics.domain import (
    AnalyticsAuditAction,
    AnalyticsAuditEvent,
    AnalyticsJobStatus,
    AnalyticsOutboxStatus,
    AnalyticsScope,
    AnalyticsSnapshotStatus,
    CareerAnalyticsConflict,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsNotFound,
    CareerAnalyticsQuotaExceeded,
    CareerAnalyticsSourceLimitExceeded,
    CareerAnalyticsUnavailable,
    CareerAnalyticsValidationError,
)

OWNER_ID = UUID("00000000-0000-4000-8000-000000000901")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000902")
TRACE_ID = "9" * 32
WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2026, 12, 31)


def _fact(index: int) -> ApplicationAnalyticsFact:
    created_at = datetime(2026, 2, 1, tzinfo=UTC)
    return ApplicationAnalyticsFact(
        application_id=UUID(int=10_000 + index),
        stage="interview" if index % 3 == 0 else "applied",
        outcome="offer" if index % 11 == 0 else "none",
        role_title=f"Fictional role {index % 25}",
        source=f"source-{index % 7}",
        industry=f"industry-{index % 4}",
        resume_version_id=UUID(int=20_000 + index % 8),
        resume_version_number=(index % 8) + 1,
        requirement_coverage_basis_points=(index * 97) % 10_001,
        first_applied_at=created_at,
        first_response_at=created_at if index % 2 == 0 else None,
        first_interview_at=created_at if index % 3 == 0 else None,
        first_offer_at=created_at if index % 11 == 0 else None,
        outcome_at=created_at if index % 11 == 0 else None,
        created_at=created_at,
        updated_at=created_at,
    )


def _service(
    *,
    source: StaticApplicationSource | None = None,
    supplemental: StaticSupplementalSource | None = None,
    memory: MemoryCareerAnalytics | None = None,
    clock: MutableClock | None = None,
    policy: CareerAnalyticsPolicy | None = None,
) -> tuple[
    CareerAnalyticsService,
    MemoryCareerAnalytics,
    StaticApplicationSource,
    StaticSupplementalSource,
    MutableClock,
]:
    selected_memory = memory or MemoryCareerAnalytics()
    selected_source = source or StaticApplicationSource()
    selected_supplemental = supplemental or StaticSupplementalSource()
    selected_clock = clock or MutableClock()
    return (
        CareerAnalyticsService(
            unit_of_work=selected_memory,
            clock=selected_clock,
            identifiers=SequenceIdentifiers(),
            applications=selected_source,
            supplemental=selected_supplemental,
            policy=policy or CareerAnalyticsPolicy(source_page_size=100),
        ),
        selected_memory,
        selected_source,
        selected_supplemental,
        selected_clock,
    )


def _command(scope: AnalyticsScope = AnalyticsScope.APPLICATIONS) -> RefreshAnalytics:
    return RefreshAnalytics(
        scope=scope,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        timezone="UTC",
    )


def _context(owner_id: UUID = OWNER_ID) -> RequestContext:
    return RequestContext(
        actor_user_id=owner_id,
        request_id="analytics-request",
        trace_id=TRACE_ID,
    )


def test_small_cohort_rates_are_suppressed_and_copy_is_noncausal() -> None:
    payload = aggregate(
        scope=AnalyticsScope.OVERVIEW,
        applications=tuple(_fact(index) for index in range(4)),
        supplemental=SupplementalAnalyticsSnapshot(readiness=(), achievements=()),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        timezone="UTC",
    )

    assert payload.interpretation == ANALYTICS_INTERPRETATION
    assert payload.counts["applications"] == 4
    assert all(value.suppressed for value in payload.rates.values())
    assert all(value.numerator is None for value in payload.rates.values())
    assert all(value.denominator is None for value in payload.rates.values())
    normalized = str(payload.as_dict()).casefold()
    for banned in (
        "caused",
        "improved your chances",
        "predicts",
        "guarantee",
    ):
        assert banned not in normalized


def test_audit_actor_cannot_be_attributed_to_another_owner() -> None:
    with pytest.raises(CareerAnalyticsValidationError, match="actor must match owner"):
        AnalyticsAuditEvent(
            id=UUID(int=9901),
            owner_user_id=OWNER_ID,
            action=AnalyticsAuditAction.REFRESH_REQUESTED,
            target_type="analytics_refresh_job",
            target_id=UUID(int=9902),
            actor_user_id=OTHER_ID,
            request_id="cross-owner-audit",
            trace_id=TRACE_ID,
            metadata={"scope": AnalyticsScope.APPLICATIONS.value},
            created_at=NOW,
        )


@pytest.mark.asyncio
async def test_refresh_is_idempotent_owner_scoped_and_rejects_fingerprint_reuse() -> None:
    service, memory, _source, _supplemental, _clock = _service()

    created = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-key-001",
        context=_context(),
    )
    replay = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-key-001",
        context=_context(),
    )

    assert replay.id == created.id
    assert memory.compaction_query_calls == 1
    assert memory.capacity_query_calls == 1
    with pytest.raises(CareerAnalyticsIdempotencyConflict):
        await service.request_refresh(
            OWNER_ID,
            _command(AnalyticsScope.READINESS),
            idempotency_key="analytics-key-001",
            context=_context(),
        )
    with pytest.raises(CareerAnalyticsNotFound):
        await service.get_refresh(OTHER_ID, created.id)


@pytest.mark.asyncio
async def test_complete_keyset_refresh_exceeds_legacy_cap_and_stale_data_fails_closed() -> None:
    facts = tuple(_fact(index) for index in range(1_005))
    source = StaticApplicationSource(facts)
    supplemental = StaticSupplementalSource(
        readiness=(
            ReadinessHistoryPoint(
                analysis_id=UUID(int=30_001),
                role_label="Fictional role",
                raw_score_basis_points=7_500,
                label="developing",
                engine_version="role-readiness/1.0.0",
                created_at=NOW,
            ),
        ),
        achievements=(
            AchievementGrowthPoint(
                evidence_revision_id=UUID(int=30_002),
                category="achievement",
                occurred_at=NOW,
            ),
        ),
    )
    service, memory, _source, _supplemental, _clock = _service(
        source=source,
        supplemental=supplemental,
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-key-complete",
        context=_context(),
    )

    completed = await service.process_refresh(refresh.id, trace_id=TRACE_ID)
    report = await service.get_report(
        OWNER_ID,
        scope=AnalyticsScope.APPLICATIONS,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        context=_context(),
    )

    assert completed.status == AnalyticsJobStatus.COMPLETED
    assert source.page_calls == 11
    assert report.status == AnalyticsSnapshotStatus.READY
    assert report.freshness == "current"
    assert report.payload is not None

    assert report.payload["counts"]["applications"] == 1_005  # type: ignore[index]
    assert len(report.payload["timeBuckets"]) <= 24  # type: ignore[arg-type]
    assert len(report.payload["breakdowns"]["role"]) == 21  # type: ignore[index,arg-type]
    assert len(memory.snapshots) == 1
    worker_audits = [
        event
        for event in memory.audits
        if event.action
        in {
            AnalyticsAuditAction.REFRESH_STARTED,
            AnalyticsAuditAction.SNAPSHOT_CREATED,
        }
    ]
    assert worker_audits
    assert all(event.actor_user_id is None for event in worker_audits)
    assert all(event.request_id is None for event in worker_audits)
    assert all(event.trace_id == TRACE_ID for event in worker_audits)
    serialized = str(report.payload)
    for restricted in (
        "offerSummary",
        "rejectionReason",
        "evidenceStatement",
        "contactEmail",
        "rawResume",
    ):
        assert restricted not in serialized

    source.generation += 1
    stale = await service.get_report(
        OWNER_ID,
        scope=AnalyticsScope.APPLICATIONS,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        context=_context(),
    )
    assert stale.status == AnalyticsSnapshotStatus.STALE
    assert stale.freshness == "stale"
    assert stale.payload is None
    assert next(iter(memory.snapshots.values())).status == AnalyticsSnapshotStatus.STALE
    assert memory.audits[-1].action == AnalyticsAuditAction.SNAPSHOT_MARKED_STALE
    assert memory.audits[-1].actor_user_id == OWNER_ID
    assert memory.audits[-1].request_id == "analytics-request"
    assert memory.audits[-1].trace_id == TRACE_ID


@pytest.mark.asyncio
async def test_completion_uses_post_watermark_time_and_rejects_an_expired_lease() -> None:
    clock = MutableClock()

    class LeaseExpiringSupplementalSource(StaticSupplementalSource):
        async def watermark(
            self,
            owner_user_id: UUID,
            *,
            window_start: date,
            window_end: date,
        ) -> AnalyticsSourceWatermark:
            result = await super().watermark(
                owner_user_id,
                window_start=window_start,
                window_end=window_end,
            )
            if len(self.watermark_windows) == 2:
                clock.value = NOW + timedelta(seconds=301)
            return result

    supplemental = LeaseExpiringSupplementalSource()
    service, memory, _source, _supplemental, _clock = _service(
        supplemental=supplemental,
        clock=clock,
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-post-watermark-lease-fence",
        context=_context(),
    )

    with pytest.raises(CareerAnalyticsConflict, match="lease is invalid or expired"):
        await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert memory.snapshots == {}
    assert memory.jobs[refresh.id].status is AnalyticsJobStatus.RUNNING

    recovery = await service.reconcile_expired()
    assert recovery.recovered_jobs == 1
    assert memory.jobs[refresh.id].status is AnalyticsJobStatus.RETRY_WAIT


@pytest.mark.asyncio
async def test_eligibility_only_flip_changes_windowed_watermark_and_stales_report() -> None:
    achievement = AchievementGrowthPoint(
        evidence_revision_id=UUID(int=30_101),
        category="achievement",
        occurred_at=NOW,
    )
    supplemental = StaticSupplementalSource(achievements=(achievement,))
    service, memory, _source, _supplemental, _clock = _service(
        supplemental=supplemental,
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-eligibility-flip",
        context=_context(),
    )
    await service.process_refresh(refresh.id, trace_id=TRACE_ID)
    snapshot = next(iter(memory.snapshots.values()))
    guarded_window = (
        WINDOW_START - timedelta(days=1),
        WINDOW_END + timedelta(days=1),
    )
    assert supplemental.watermark_windows == [guarded_window, guarded_window]
    assert supplemental.snapshot_windows == [guarded_window]
    stored_career = snapshot.source_watermark["career"]
    assert isinstance(stored_career, dict)
    stored_token = stored_career["token"]

    supplemental.set_achievement_eligible(
        achievement.evidence_revision_id,
        eligible=False,
    )
    assert supplemental.generation == 1
    current = await supplemental.watermark(
        OWNER_ID,
        window_start=WINDOW_START - timedelta(days=1),
        window_end=WINDOW_END + timedelta(days=1),
    )
    assert current.token != stored_token

    report = await service.get_report(
        OWNER_ID,
        scope=AnalyticsScope.APPLICATIONS,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        context=_context(),
    )
    assert report.status == AnalyticsSnapshotStatus.STALE
    assert report.freshness == "stale"
    assert report.payload is None
    assert snapshot.status == AnalyticsSnapshotStatus.STALE
    assert supplemental.watermark_windows == [guarded_window] * 4


@pytest.mark.asyncio
async def test_concurrent_source_change_schedules_bounded_retry_without_snapshot() -> None:
    source = StaticApplicationSource(tuple(_fact(index) for index in range(8)))
    source.change_on_first_page = True
    service, memory, _source, _supplemental, _clock = _service(source=source)
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-key-change",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.RETRY_WAIT
    assert result.safe_error_code == "source_changed"
    assert result.attempts == 1
    assert memory.snapshots == {}
    assert memory.audits[-1].action == AnalyticsAuditAction.REFRESH_RETRY_SCHEDULED


@pytest.mark.asyncio
async def test_supplemental_source_limit_records_stable_bounded_retry() -> None:
    class OversizedSupplementalSource(StaticSupplementalSource):
        async def snapshot(
            self,
            owner_user_id: UUID,
            *,
            window_start: date,
            window_end: date,
        ) -> SupplementalAnalyticsSnapshot:
            _ = owner_user_id, window_start, window_end
            raise CareerAnalyticsSourceLimitExceeded("bounded source exceeded")

    service, memory, _source, _supplemental, _clock = _service(
        supplemental=OversizedSupplementalSource()
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-source-limit",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.RETRY_WAIT
    assert result.safe_error_code == "source_limit_exceeded"
    assert memory.snapshots == {}


@pytest.mark.asyncio
async def test_supplemental_unavailability_records_distinct_safe_retry() -> None:
    class UnavailableSupplementalSource(StaticSupplementalSource):
        async def watermark(
            self,
            owner_user_id: UUID,
            *,
            window_start: date,
            window_end: date,
        ):
            _ = owner_user_id, window_start, window_end
            raise CareerAnalyticsUnavailable("provider details")

    service, memory, _source, _supplemental, _clock = _service(
        supplemental=UnavailableSupplementalSource()
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-source-unavailable",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.RETRY_WAIT
    assert result.safe_error_code == "source_unavailable"
    assert memory.snapshots == {}


@pytest.mark.asyncio
async def test_precommit_source_unavailability_uses_the_same_safe_retry_code() -> None:
    class BecomesUnavailableSupplementalSource(StaticSupplementalSource):
        calls = 0

        async def watermark(
            self,
            owner_user_id: UUID,
            *,
            window_start: date,
            window_end: date,
        ):
            self.calls += 1
            if self.calls == 2:
                raise CareerAnalyticsUnavailable("provider details")
            return await super().watermark(
                owner_user_id,
                window_start=window_start,
                window_end=window_end,
            )

    service, memory, _source, _supplemental, _clock = _service(
        supplemental=BecomesUnavailableSupplementalSource()
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-source-precommit",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.RETRY_WAIT
    assert result.safe_error_code == "source_unavailable"
    assert memory.snapshots == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("public_delta", [3_648, 3_649, 3_650])
async def test_public_window_boundary_fits_the_internal_timezone_guard(
    public_delta: int,
) -> None:
    start = date(2010, 1, 2)
    end = start + timedelta(days=public_delta)
    supplemental = StaticSupplementalSource()
    service, _memory, _source, _supplemental, _clock = _service(supplemental=supplemental)
    refresh = await service.request_refresh(
        OWNER_ID,
        RefreshAnalytics(
            scope=AnalyticsScope.OVERVIEW,
            window_start=start,
            window_end=end,
            timezone="Pacific/Kiritimati",
        ),
        idempotency_key=f"analytics-window-{public_delta}",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.COMPLETED
    guarded = (start - timedelta(days=1), end + timedelta(days=1))
    assert supplemental.watermark_windows == [guarded, guarded]
    assert supplemental.snapshot_windows == [guarded]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end", "guarded"),
    [
        (
            date.min,
            date.min + timedelta(days=3_650),
            (date.min, date.min + timedelta(days=3_651)),
        ),
        (
            date.max - timedelta(days=3_650),
            date.max,
            (date.max - timedelta(days=3_651), date.max),
        ),
    ],
)
async def test_public_window_guard_clamps_at_date_boundaries(
    start: date,
    end: date,
    guarded: tuple[date, date],
) -> None:
    supplemental = StaticSupplementalSource()
    service, _memory, _source, _supplemental, _clock = _service(supplemental=supplemental)
    refresh = await service.request_refresh(
        OWNER_ID,
        RefreshAnalytics(
            scope=AnalyticsScope.OVERVIEW,
            window_start=start,
            window_end=end,
            timezone="UTC",
        ),
        idempotency_key=f"analytics-boundary-{start.isoformat()}",
        context=_context(),
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    assert result.status == AnalyticsJobStatus.COMPLETED
    assert supplemental.watermark_windows == [guarded, guarded]
    assert supplemental.snapshot_windows == [guarded]


@pytest.mark.asyncio
async def test_outbox_delivery_and_expired_lease_reconciliation_are_idempotent() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(clock=clock)
    await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-key-outbox",
        context=_context(),
    )

    claimed = await service.claim_outbox()
    assert len(claimed) == 1
    message = memory.outbox[claimed[0].message_id]
    assert message.status == AnalyticsOutboxStatus.LEASED

    clock.value = NOW + timedelta(seconds=301)
    outcome = await service.reconcile_expired()
    assert outcome == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=0,
        recovered_outbox=1,
        dead_lettered_outbox=0,
        requeued_deliveries=0,
    )
    assert message.status == AnalyticsOutboxStatus.PENDING

    claimed_again = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed_again[0].message_id,
        lease_token=claimed_again[0].lease_token,
        job_version_at_claim=claimed_again[0].job_version_at_claim,
    )
    assert message.status == AnalyticsOutboxStatus.PUBLISHED
    assert await service.claim_outbox() == ()


@pytest.mark.asyncio
async def test_retry_delivery_is_rearmed_once_behind_the_leased_outbox() -> None:
    clock = MutableClock()
    source = StaticApplicationSource(tuple(_fact(index) for index in range(8)))
    source.change_on_first_page = True
    service, memory, _source, _supplemental, _clock = _service(
        source=source,
        clock=clock,
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-durable-retry-delivery",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    message = memory.outbox[claimed[0].message_id]
    assert result.status is AnalyticsJobStatus.RETRY_WAIT
    assert message.status is AnalyticsOutboxStatus.PENDING
    assert message.next_attempt_at == NOW + timedelta(seconds=30)
    assert await service.claim_outbox() == ()
    assert (await service.reconcile_expired()).requeued_deliveries == 0

    clock.value = NOW + timedelta(seconds=30)
    retry_claim = await service.claim_outbox()
    assert len(retry_claim) == 1
    assert await service.claim_outbox() == ()

    await service.mark_outbox_published(
        retry_claim[0].message_id,
        lease_token=retry_claim[0].lease_token,
        job_version_at_claim=retry_claim[0].job_version_at_claim,
    )
    published_retry = memory.outbox[retry_claim[0].message_id]
    assert published_retry.status is AnalyticsOutboxStatus.PUBLISHED
    assert published_retry.attempts == 2
    assert await service.claim_outbox() == ()


@pytest.mark.asyncio
async def test_worker_failure_before_publish_ack_rearms_the_consumed_delivery() -> None:
    source = StaticApplicationSource(tuple(_fact(index) for index in range(8)))
    source.change_on_first_page = True
    service, memory, _source, _supplemental, _clock = _service(source=source)
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-pre-ack-worker-failure",
        context=_context(),
    )
    claimed = await service.claim_outbox()

    result = await service.process_refresh(refresh.id, trace_id=TRACE_ID)

    message = memory.outbox[claimed[0].message_id]
    assert result.status is AnalyticsJobStatus.RETRY_WAIT
    assert message.status is AnalyticsOutboxStatus.LEASED
    assert result.attempts == message.attempts == 1

    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )
    rearmed = memory.outbox[claimed[0].message_id]
    assert rearmed.status is AnalyticsOutboxStatus.PENDING
    assert rearmed.next_attempt_at == NOW + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_unconfirmed_delivery_is_requeued_once_then_dispatch_claim_is_fenced() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(clock=clock)
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-unconfirmed-delivery",
        context=_context(),
    )
    first_claim = await service.claim_outbox()
    await service.mark_outbox_published(
        first_claim[0].message_id,
        lease_token=first_claim[0].lease_token,
        job_version_at_claim=first_claim[0].job_version_at_claim,
    )
    clock.value = NOW + timedelta(seconds=301)

    first_recovery = await service.reconcile_expired(limit=1)
    second_recovery = await service.reconcile_expired(limit=1)

    assert first_recovery.requeued_deliveries == 1
    assert second_recovery == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=0,
        recovered_outbox=0,
        dead_lettered_outbox=0,
        requeued_deliveries=0,
    )
    assert memory.jobs[refresh.id].status is AnalyticsJobStatus.QUEUED
    assert memory.outbox[first_claim[0].message_id].status is AnalyticsOutboxStatus.PENDING
    assert len(await service.claim_outbox()) == 1
    assert await service.claim_outbox() == ()


@pytest.mark.asyncio
async def test_unconfirmed_delivery_exhaustion_is_terminal_and_reported() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(max_attempts=1, lease_seconds=30),
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-unconfirmed-terminal",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )
    clock.value = NOW + timedelta(seconds=31)

    outcome = await service.reconcile_expired()

    assert outcome == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=1,
        recovered_outbox=0,
        dead_lettered_outbox=1,
        requeued_deliveries=0,
    )
    assert memory.jobs[refresh.id].status is AnalyticsJobStatus.DEAD_LETTER
    assert memory.outbox[claimed[0].message_id].status is AnalyticsOutboxStatus.DEAD_LETTER
    assert memory.audits[-1].actor_user_id is None
    assert memory.audits[-1].request_id is None


@pytest.mark.asyncio
async def test_exhausted_outbox_publish_failure_dead_letters_job_and_audits() -> None:
    service, memory, _source, _supplemental, _clock = _service(
        policy=CareerAnalyticsPolicy(max_attempts=1)
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-outbox-terminal-failure",
        context=_context(),
    )
    claimed = await service.claim_outbox()

    await service.mark_outbox_failed(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
    )

    message = memory.outbox[claimed[0].message_id]
    job = memory.jobs[refresh.id]
    assert message.status is AnalyticsOutboxStatus.DEAD_LETTER
    assert message.safe_error_code == "publish_failed"
    assert job.status is AnalyticsJobStatus.DEAD_LETTER
    assert job.safe_error_code == "publish_failed"
    assert await memory.count_active_jobs(OWNER_ID) == 0
    terminal_audits = [
        event
        for event in memory.audits
        if event.action is AnalyticsAuditAction.REFRESH_DEAD_LETTERED
    ]
    assert len(terminal_audits) == 1
    assert terminal_audits[0].target_id == refresh.id
    assert terminal_audits[0].trace_id == TRACE_ID
    assert terminal_audits[0].metadata == {
        "error_code": "publish_failed",
        "failure_stage": "outbox_publish",
        "scope": AnalyticsScope.APPLICATIONS.value,
    }


@pytest.mark.asyncio
async def test_exhausted_outbox_lease_dead_letters_job_once_and_releases_quota() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(max_attempts=1),
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-outbox-terminal-lease",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    clock.value = NOW + timedelta(seconds=301)

    assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=1,
        recovered_outbox=0,
        dead_lettered_outbox=1,
        requeued_deliveries=0,
    )
    assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=0,
        recovered_outbox=0,
        dead_lettered_outbox=0,
        requeued_deliveries=0,
    )

    message = memory.outbox[claimed[0].message_id]
    job = memory.jobs[refresh.id]
    assert message.status is AnalyticsOutboxStatus.DEAD_LETTER
    assert message.safe_error_code == "lease_expired"
    assert job.status is AnalyticsJobStatus.DEAD_LETTER
    assert job.safe_error_code == "lease_expired"
    assert await memory.count_active_jobs(OWNER_ID) == 0
    terminal_audits = [
        event
        for event in memory.audits
        if event.action is AnalyticsAuditAction.REFRESH_DEAD_LETTERED
    ]
    assert len(terminal_audits) == 1
    assert terminal_audits[0].target_id == refresh.id
    assert terminal_audits[0].metadata["failure_stage"] == "outbox_publish"
    assert terminal_audits[0].metadata["error_code"] == "lease_expired"


@pytest.mark.asyncio
async def test_exhausted_refresh_lease_dead_letters_and_audits_once() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(max_attempts=1, lease_seconds=30),
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-refresh-terminal-lease",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )
    job = memory.jobs[refresh.id]
    job.claim(
        token=UUID(int=999),
        now=NOW,
        leased_until=NOW + timedelta(seconds=30),
    )
    clock.value = NOW + timedelta(seconds=31)

    assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=1,
        recovered_outbox=0,
        dead_lettered_outbox=0,
        requeued_deliveries=0,
    )
    assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=0,
        recovered_outbox=0,
        dead_lettered_outbox=0,
        requeued_deliveries=0,
    )

    assert job.status is AnalyticsJobStatus.DEAD_LETTER
    assert job.safe_error_code == "lease_expired"
    assert await memory.count_active_jobs(OWNER_ID) == 0
    terminal_audits = [
        event
        for event in memory.audits
        if event.action is AnalyticsAuditAction.REFRESH_DEAD_LETTERED
    ]
    assert len(terminal_audits) == 1
    assert terminal_audits[0].target_id == refresh.id
    assert terminal_audits[0].metadata == {
        "error_code": "lease_expired",
        "failure_stage": "refresh_processing",
        "scope": AnalyticsScope.APPLICATIONS.value,
    }


@pytest.mark.asyncio
async def test_expired_refresh_lease_requeues_its_published_delivery_once() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(max_attempts=3, lease_seconds=30),
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-refresh-recovery-delivery",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )
    job = memory.jobs[refresh.id]
    job.claim(
        token=UUID(int=997),
        now=NOW,
        leased_until=NOW + timedelta(seconds=30),
    )
    clock.value = NOW + timedelta(seconds=31)

    outcome = await service.reconcile_expired()

    assert outcome == AnalyticsReconciliationOutcome(
        recovered_jobs=1,
        dead_lettered_jobs=0,
        recovered_outbox=0,
        dead_lettered_outbox=0,
        requeued_deliveries=1,
    )
    assert job.status is AnalyticsJobStatus.RETRY_WAIT
    assert memory.outbox[claimed[0].message_id].status is AnalyticsOutboxStatus.PENDING


@pytest.mark.asyncio
async def test_expired_refresh_with_exhausted_delivery_reports_both_dead_letters() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(max_attempts=3, lease_seconds=30),
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-refresh-exhausted-delivery",
        context=_context(),
    )
    claimed = await service.claim_outbox()
    await service.mark_outbox_published(
        claimed[0].message_id,
        lease_token=claimed[0].lease_token,
        job_version_at_claim=claimed[0].job_version_at_claim,
    )
    message = memory.outbox[claimed[0].message_id]
    message.attempts = message.max_attempts
    job = memory.jobs[refresh.id]
    job.claim(
        token=UUID(int=998),
        now=NOW,
        leased_until=NOW + timedelta(seconds=30),
    )
    clock.value = NOW + timedelta(seconds=31)

    outcome = await service.reconcile_expired()

    assert outcome == AnalyticsReconciliationOutcome(
        recovered_jobs=0,
        dead_lettered_jobs=1,
        recovered_outbox=0,
        dead_lettered_outbox=1,
        requeued_deliveries=0,
    )
    assert job.status is AnalyticsJobStatus.DEAD_LETTER
    assert message.status is AnalyticsOutboxStatus.DEAD_LETTER


def test_iana_timezone_controls_midnight_cohorts_and_event_buckets() -> None:
    kolkata_boundary = replace(
        _fact(1),
        created_at=datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
        first_applied_at=datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
        first_interview_at=datetime(2026, 1, 1, 20, 30, tzinfo=UTC),
    )
    negative_offset_boundary = replace(
        _fact(2),
        created_at=datetime(2026, 1, 2, 3, 0, tzinfo=UTC),
        first_applied_at=datetime(2026, 1, 2, 3, 0, tzinfo=UTC),
        first_offer_at=datetime(2026, 1, 2, 3, 30, tzinfo=UTC),
    )
    outside_kolkata_cohort = replace(
        _fact(3),
        created_at=datetime(2026, 1, 1, 18, 0, tzinfo=UTC),
        first_applied_at=datetime(2026, 1, 1, 18, 0, tzinfo=UTC),
        first_response_at=datetime(2026, 1, 1, 19, 0, tzinfo=UTC),
        first_interview_at=datetime(2026, 1, 1, 19, 30, tzinfo=UTC),
        first_offer_at=datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
    )
    outside_los_angeles_cohort = replace(
        _fact(4),
        created_at=datetime(2026, 1, 1, 7, 30, tzinfo=UTC),
        first_applied_at=datetime(2026, 1, 1, 7, 30, tzinfo=UTC),
        first_response_at=datetime(2026, 1, 1, 8, 15, tzinfo=UTC),
        first_interview_at=datetime(2026, 1, 1, 8, 30, tzinfo=UTC),
        first_offer_at=datetime(2026, 1, 1, 8, 45, tzinfo=UTC),
    )

    kolkata = aggregate(
        scope=AnalyticsScope.APPLICATIONS,
        applications=(
            kolkata_boundary,
            negative_offset_boundary,
            outside_kolkata_cohort,
        ),
        supplemental=SupplementalAnalyticsSnapshot(readiness=(), achievements=()),
        window_start=date(2026, 1, 2),
        window_end=date(2026, 1, 2),
        timezone="Asia/Kolkata",
    )
    los_angeles = aggregate(
        scope=AnalyticsScope.APPLICATIONS,
        applications=(
            kolkata_boundary,
            negative_offset_boundary,
            outside_los_angeles_cohort,
        ),
        supplemental=SupplementalAnalyticsSnapshot(readiness=(), achievements=()),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 1),
        timezone="America/Los_Angeles",
    )

    assert kolkata.counts["applications"] == 2
    assert kolkata.counts["responses"] == 1
    assert kolkata.time_buckets[0].interviews == 1
    assert kolkata.time_buckets[0].offers == 1
    assert los_angeles.counts["applications"] == 2
    assert los_angeles.counts["responses"] == 1
    assert los_angeles.time_buckets[0].interviews == 1
    assert los_angeles.time_buckets[0].offers == 1


@pytest.mark.asyncio
async def test_same_window_keeps_timezone_specific_snapshots_distinct() -> None:
    source = StaticApplicationSource((_fact(1),))
    service, memory, _source, _supplemental, _clock = _service(source=source)
    utc = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-timezone-utc",
        context=_context(),
    )
    kolkata = await service.request_refresh(
        OWNER_ID,
        replace(_command(), timezone="Asia/Kolkata"),
        idempotency_key="analytics-timezone-kolkata",
        context=_context(),
    )

    await service.process_refresh(utc.id, trace_id=TRACE_ID)
    await service.process_refresh(kolkata.id, trace_id=TRACE_ID)
    utc_report = await service.get_report(
        OWNER_ID,
        scope=AnalyticsScope.APPLICATIONS,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        context=_context(),
        timezone="UTC",
    )
    kolkata_report = await service.get_report(
        OWNER_ID,
        scope=AnalyticsScope.APPLICATIONS,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        context=_context(),
        timezone="Asia/Kolkata",
    )

    assert utc_report.timezone == "UTC"
    assert kolkata_report.timezone == "Asia/Kolkata"
    assert {value.timezone for value in memory.snapshots.values()} == {
        "UTC",
        "Asia/Kolkata",
    }


@pytest.mark.asyncio
async def test_snapshot_tamper_fails_closed_before_payload_is_returned() -> None:
    service, memory, _source, _supplemental, _clock = _service(
        source=StaticApplicationSource(tuple(_fact(index) for index in range(5)))
    )
    refresh = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-tamper-check",
        context=_context(),
    )
    await service.process_refresh(refresh.id, trace_id=TRACE_ID)
    snapshot = next(iter(memory.snapshots.values()))
    snapshot.payload["counts"] = {"applications": 999}

    with pytest.raises(CareerAnalyticsUnavailable):
        await service.get_report(
            OWNER_ID,
            scope=AnalyticsScope.APPLICATIONS,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            context=_context(),
        )


@pytest.mark.asyncio
async def test_owner_active_and_history_quotas_follow_idempotency_replay() -> None:
    policy = CareerAnalyticsPolicy(
        source_page_size=100,
        max_active_jobs_per_owner=1,
        max_job_history_per_owner=2,
    )
    service, _memory, _source, _supplemental, _clock = _service(policy=policy)
    created = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-quota-first",
        context=_context(),
    )
    replay = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-quota-first",
        context=_context(),
    )

    assert replay.id == created.id
    with pytest.raises(CareerAnalyticsQuotaExceeded):
        await service.request_refresh(
            OWNER_ID,
            _command(),
            idempotency_key="analytics-quota-second",
            context=_context(),
        )

    history_service, _memory, _source, _supplemental, _clock = _service(
        policy=CareerAnalyticsPolicy(
            source_page_size=100,
            max_active_jobs_per_owner=1,
            max_job_history_per_owner=1,
            idempotency_replay_seconds=300,
        )
    )
    terminal = await history_service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-history-first",
        context=_context(),
    )
    await history_service.process_refresh(terminal.id, trace_id=TRACE_ID)
    with pytest.raises(CareerAnalyticsQuotaExceeded):
        await history_service.request_refresh(
            OWNER_ID,
            _command(),
            idempotency_key="analytics-history-second",
            context=_context(),
        )


@pytest.mark.asyncio
async def test_old_terminal_history_is_compacted_without_lifetime_exhaustion() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(
            source_page_size=100,
            max_active_jobs_per_owner=1,
            max_job_history_per_owner=1,
            idempotency_replay_seconds=300,
        ),
    )
    first = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-retention-first",
        context=_context(),
    )
    await service.process_refresh(first.id, trace_id=TRACE_ID)
    first_snapshot = next(value for value in memory.snapshots.values() if value.job_id == first.id)

    clock.value += timedelta(seconds=301)
    second = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-retention-second",
        context=_context(),
    )

    assert first.id in memory.jobs
    assert first_snapshot.id in memory.snapshots
    await service.process_refresh(second.id, trace_id=TRACE_ID)
    second_snapshot = next(
        value for value in memory.snapshots.values() if value.job_id == second.id
    )
    clock.value += timedelta(seconds=301)
    third = await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-retention-third",
        context=_context(),
    )

    assert third.id in memory.jobs
    assert first.id not in memory.jobs
    assert first_snapshot.id not in memory.snapshots
    assert second.id in memory.jobs
    assert second_snapshot.id in memory.snapshots


@pytest.mark.asyncio
async def test_terminal_compaction_is_tenant_scoped() -> None:
    clock = MutableClock()
    service, memory, _source, _supplemental, _clock = _service(
        clock=clock,
        policy=CareerAnalyticsPolicy(
            source_page_size=100,
            max_active_jobs_per_owner=1,
            max_job_history_per_owner=1,
            idempotency_replay_seconds=300,
        ),
    )
    other = await service.request_refresh(
        OTHER_ID,
        _command(),
        idempotency_key="analytics-retention-other",
        context=_context(OTHER_ID),
    )
    await service.process_refresh(other.id, trace_id=TRACE_ID)
    clock.value += timedelta(seconds=301)

    await service.request_refresh(
        OWNER_ID,
        _command(),
        idempotency_key="analytics-retention-owner",
        context=_context(),
    )

    assert other.id in memory.jobs
    assert any(value.job_id == other.id for value in memory.snapshots.values())


def test_coverage_trends_and_resume_version_outcomes_are_suppressed_per_cohort() -> None:
    facts = tuple(_fact(index) for index in range(6))
    payload = aggregate(
        scope=AnalyticsScope.APPLICATIONS,
        applications=facts,
        supplemental=SupplementalAnalyticsSnapshot(readiness=(), achievements=()),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        timezone="UTC",
    ).as_dict()

    trend = payload["requirementCoverageTrend"]
    outcomes = payload["outcomesByResumeVersion"]
    assert isinstance(trend, list)
    assert any(
        point["valueBasisPoints"] is not None  # type: ignore[index]
        for point in trend
    )
    assert isinstance(outcomes, list)
    assert all(
        version["offerRate"]["suppressed"]  # type: ignore[index]
        for version in outcomes
    )
    assert all(
        version["offerRate"]["denominator"] is None  # type: ignore[index]
        for version in outcomes
    )
