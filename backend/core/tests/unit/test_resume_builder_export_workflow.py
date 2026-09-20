"""Durability and fencing tests for asynchronous resume exports."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from resume_builder_memory import (
    OWNER_ID,
    FixedClock,
    MemoryResumeBuilder,
    MemoryStorage,
    PlainTextExtractor,
    StaticResumeSourceProvider,
    TextOnlyRenderer,
    UuidFactory,
)
from rezumi.modules.resume_builder.application import (
    CreateResume,
    ExportResume,
    RenderedResume,
    RequestContext,
    ResumeBuilderService,
    ResumeExportCleanupProcessor,
    ResumeExportObjectCleanupProcessor,
    ResumeExportOutboxDispatcher,
    ResumeExportProcessor,
    ResumeExportReconciler,
    ResumeExportRecord,
    ResumeExportWorkerPolicy,
    ResumeRecord,
)
from rezumi.modules.resume_builder.domain import (
    ResumeAuditAction,
    ResumeEntityFact,
    ResumeExportOperation,
    ResumeExportStatus,
    ResumeFormat,
    ResumeLayout,
    ResumeTemplate,
    ResumeVersion,
    build_fidelity_manifest,
)
from rezumi.modules.resume_builder.infrastructure import (
    DeterministicResumeRenderer,
    ResumeBuilderDocumentExtractor,
    ResumeExportExtractionLimits,
)


class MutableClock:
    def __init__(self) -> None:
        self.current: datetime = FixedClock().now()

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class RecordingPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[UUID, str, ResumeExportOperation]] = []

    async def publish(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None:
        self.published.append((export_id, trace_id, operation))


class FailingRenderer:
    def render(self, *_args: object, **_kwargs: object) -> object:
        raise RuntimeError("private renderer detail")


class FailingPublisher:
    async def publish(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None:
        _ = (export_id, trace_id, operation)
        raise RuntimeError("private broker detail")


class ManifestMutationRenderer:
    def __init__(self, behavior: str) -> None:
        self._behavior = behavior

    def render(self, version: ResumeVersion, *, fmt: str) -> RenderedResume:
        _ = fmt
        lines = [entry.text for entry in build_fidelity_manifest(version).entries]
        if self._behavior == "omit":
            output = lines[:-1]
        elif self._behavior == "duplicate":
            output = [*lines, lines[0]]
        elif self._behavior == "reverse":
            output = list(reversed(lines))
        elif self._behavior == "unsearchable":
            output = []
        else:
            raise AssertionError(f"unknown test renderer behavior: {self._behavior}")
        return RenderedResume(
            media_type="text/plain; charset=utf-8",
            filename="resume.txt",
            content=(("\n".join(output) + "\n") if output else "").encode("utf-8"),
            expected_lines=tuple(lines),
            renderer_version=f"manifest-mutation-{self._behavior}",
        )


class LeaseStealingPublisher:
    def __init__(self, state: MemoryResumeBuilder) -> None:
        self._state = state

    async def publish(
        self,
        export_id: UUID,
        trace_id: str,
        operation: ResumeExportOperation,
    ) -> None:
        _ = (export_id, trace_id, operation)
        message = next(iter(self._state.export_outbox.values()))
        self._state.export_outbox[message.id] = replace(
            message,
            lease_token=UUID("00000000-0000-4000-8000-00000000ffff"),
        )


class FailingDeleteStorage(MemoryStorage):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self._failures = failures

    async def delete(self, object_key: str) -> None:
        if self._failures:
            self._failures -= 1
            raise RuntimeError("private storage detail")
        await super().delete(object_key)


class CoordinatedStorage(MemoryStorage):
    def __init__(self) -> None:
        super().__init__()
        self.first_put = asyncio.Event()
        self.release_first_put = asyncio.Event()
        self.put_calls = 0

    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        await super().put_bytes(object_key, value, media_type)
        self.put_calls += 1
        if self.put_calls == 1:
            self.first_put.set()
            await self.release_first_put.wait()


class UncertainPutStorage(MemoryStorage):
    async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
        await super().put_bytes(object_key, value, media_type)
        raise RuntimeError("private uncertain storage result")


async def _request_export(
    state: MemoryResumeBuilder,
    storage: MemoryStorage,
    clock: MutableClock,
) -> tuple[ResumeRecord, ResumeExportRecord]:
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )
    resume = await service.create_resume(
        OWNER_ID,
        CreateResume(
            title="Durable export",
            target_role="Product Lead",
            template=ResumeTemplate.STANDARD_PROFESSIONAL,
        ),
        idempotency_key="durable-resume",
        context=RequestContext(OWNER_ID, "request-export", "a" * 32),
    )
    export = await service.export_version(
        OWNER_ID,
        resume.current_version.id,
        ExportResume(format=ResumeFormat.TEXT),
        idempotency_key="durable-export",
        context=RequestContext(OWNER_ID, "request-export", "a" * 32),
    )
    return resume, export


async def _export_current_version(
    state: MemoryResumeBuilder,
    storage: MemoryStorage,
    clock: MutableClock,
    version_id: UUID,
    *,
    fmt: ResumeFormat,
    idempotency_key: str,
) -> ResumeExportRecord:
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )
    return await service.export_version(
        OWNER_ID,
        version_id,
        ExportResume(format=fmt),
        idempotency_key=idempotency_key,
        context=RequestContext(OWNER_ID, idempotency_key, "b" * 32),
    )


def _document_limits(tmp_path: Path) -> ResumeExportExtractionLimits:
    del tmp_path
    return ResumeExportExtractionLimits(
        max_bytes=8 * 1024 * 1024,
        max_pdf_pages=100,
        max_archive_entries=256,
        max_archive_uncompressed_bytes=52_428_800,
        max_archive_ratio=100,
        processing_timeout_seconds=30,
    )


@pytest.mark.asyncio
async def test_duplicate_delivery_is_terminal_and_does_not_render_twice() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    first = await processor.process(requested.export.id, "delivery-one")
    second = await processor.process(requested.export.id, "delivery-two")

    assert first.status is ResumeExportStatus.VERIFIED
    assert second.status is ResumeExportStatus.VERIFIED
    assert len(storage.objects) == 1
    assert state.exports[requested.export.id].attempts == 1


@pytest.mark.asyncio
async def test_expired_attempt_cleanup_cannot_delete_the_winning_fenced_object() -> None:
    state = MemoryResumeBuilder()
    storage = CoordinatedStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.export_outbox.clear()
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    stale_task = asyncio.create_task(processor.process(requested.export.id, "stale-delivery"))
    await storage.first_put.wait()

    clock.advance(331)
    reconciler = ResumeExportReconciler(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
    )
    assert (await reconciler.reconcile(10)).requeued == 1
    winner = await processor.process(requested.export.id, "winning-delivery")
    winning_key = state.exports[requested.export.id].object_key
    assert winner.status is ResumeExportStatus.VERIFIED
    assert winning_key is not None
    assert "/attempt-2/" in winning_key

    storage.release_first_put.set()
    stale = await stale_task

    assert stale.safe_error_code == "execution_lease_lost"
    assert winning_key in storage.objects
    assert state.exports[requested.export.id].object_key == winning_key
    assert all("/attempt-1/" not in key for key in storage.objects)


@pytest.mark.asyncio
async def test_crash_after_object_write_is_recovered_by_durable_cleanup() -> None:
    state = MemoryResumeBuilder()
    storage = CoordinatedStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.export_outbox.clear()
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    crashed = asyncio.create_task(processor.process(requested.export.id, "crashed-delivery"))
    await storage.first_put.wait()
    crashed.cancel()
    with pytest.raises(asyncio.CancelledError):
        await crashed

    cleanup = next(iter(state.export_object_cleanups.values()))
    assert cleanup.completed_at is None
    assert cleanup.cancelled_at is None
    assert cleanup.object_key in storage.objects

    clock.advance(631)
    cleaner = ResumeExportObjectCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=storage,
    )
    result = await cleaner.cleanup_due(10)

    assert result.completed == 1
    assert cleanup.object_key not in storage.objects
    persisted = state.export_object_cleanups[cleanup.id]
    assert persisted.completed_at == clock.now()
    assert persisted.attempts == 1
    assert state.audits[-1].action is ResumeAuditAction.EXPORT_ORPHAN_CLEANUP_COMPLETED


@pytest.mark.asyncio
async def test_orphan_object_cleanup_retries_then_dead_letters_truthfully() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.export_outbox.clear()
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    assert (
        await processor.process(requested.export.id, "winning-delivery")
    ).status is ResumeExportStatus.VERIFIED
    cleanup = next(iter(state.export_object_cleanups.values()))
    state.export_object_cleanups[cleanup.id] = replace(
        cleanup,
        object_key=f"{cleanup.object_key}.orphan",
        not_before=clock.now(),
        max_attempts=2,
        cancelled_at=None,
    )
    failing_storage = FailingDeleteStorage(failures=2)
    cleaner = ResumeExportObjectCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=failing_storage,
        policy=ResumeExportWorkerPolicy(retry_delay_seconds=1),
    )

    first = await cleaner.cleanup_due(10)
    clock.advance(1)
    terminal = await cleaner.cleanup_due(10)

    assert first.failed == 1
    assert terminal.dead_lettered == 1
    persisted = state.export_object_cleanups[cleanup.id]
    assert persisted.attempts == 2
    assert persisted.completed_at is None
    assert persisted.dead_lettered_at == clock.now()
    assert persisted.last_error == "orphan_object_cleanup_failed"
    assert state.audits[-1].action is ResumeAuditAction.EXPORT_ORPHAN_CLEANUP_DEAD_LETTERED


@pytest.mark.asyncio
async def test_failed_verification_stays_blocked_when_immediate_object_cleanup_fails() -> None:
    state = MemoryResumeBuilder()
    storage = FailingDeleteStorage(failures=1)
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.export_outbox.clear()
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=ManifestMutationRenderer("omit"),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    outcome = await processor.process(requested.export.id, "blocked-delivery")
    cleanup = next(iter(state.export_object_cleanups.values()))

    assert outcome.status is ResumeExportStatus.BLOCKED
    assert state.exports[requested.export.id].object_key is None
    assert cleanup.object_key in storage.objects
    assert not cleanup.terminal

    clock.advance(631)
    cleaner = ResumeExportObjectCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=storage,
    )
    result = await cleaner.cleanup_due(10)

    assert result.completed == 1
    assert cleanup.object_key not in storage.objects
    assert state.export_object_cleanups[cleanup.id].completed_at == clock.now()


@pytest.mark.asyncio
async def test_uncertain_object_write_is_compensated_before_retry() -> None:
    state = MemoryResumeBuilder()
    storage = UncertainPutStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
        policy=ResumeExportWorkerPolicy(retry_delay_seconds=1),
    )

    outcome = await processor.process(requested.export.id, "uncertain-write")

    assert outcome.status is ResumeExportStatus.RETRY_WAIT
    assert outcome.retryable
    assert storage.objects == {}
    assert len(storage.deleted) == 1
    assert "/attempt-1/" in storage.deleted[0]
    assert state.exports[requested.export.id].last_error == "export_processing_failed"


@pytest.mark.asyncio
async def test_export_deletion_is_outbox_backed_fenced_and_truthful() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    renderer = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    assert (
        await renderer.process(requested.export.id, "render-before-delete")
    ).status is ResumeExportStatus.VERIFIED
    state.export_outbox.clear()
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )

    accepted = await service.delete_export(
        OWNER_ID,
        requested.export.id,
        idempotency_key="durable-delete",
        context=RequestContext(OWNER_ID, "delete-request", "c" * 32),
    )

    assert accepted.export.status is ResumeExportStatus.DELETION_PENDING
    assert accepted.export.deleted_at is None
    assert len(storage.objects) == 1
    message = next(iter(state.export_outbox.values()))
    assert message.operation is ResumeExportOperation.DELETE
    cleanup = ResumeExportCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=storage,
    )

    first = await cleanup.process(requested.export.id, "cleanup-delivery")
    duplicate = await cleanup.process(requested.export.id, "cleanup-duplicate")

    assert first.status is ResumeExportStatus.DELETED
    assert duplicate.status is ResumeExportStatus.DELETED
    assert state.exports[requested.export.id].object_key is None
    assert state.exports[requested.export.id].deleted_at == clock.now()
    assert storage.objects == {}
    assert len(storage.deleted) == 1
    actions = tuple(event.action for event in state.audits)
    assert ResumeAuditAction.EXPORT_DELETION_REQUESTED in actions
    assert ResumeAuditAction.EXPORT_DELETED in actions


@pytest.mark.asyncio
async def test_export_cleanup_retries_without_losing_the_private_object() -> None:
    state = MemoryResumeBuilder()
    storage = FailingDeleteStorage(failures=1)
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    renderer = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    assert (
        await renderer.process(requested.export.id, "render-before-retry")
    ).status is ResumeExportStatus.VERIFIED
    state.export_outbox.clear()
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )
    await service.delete_export(
        OWNER_ID,
        requested.export.id,
        idempotency_key="retrying-delete",
        context=RequestContext(OWNER_ID, "retry-delete", "d" * 32),
    )
    cleanup = ResumeExportCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=storage,
        policy=ResumeExportWorkerPolicy(retry_delay_seconds=1),
    )

    retry = await cleanup.process(requested.export.id, "cleanup-failure")

    assert retry.status is ResumeExportStatus.DELETION_RETRY_WAIT
    assert retry.retryable
    assert len(storage.objects) == 1
    assert state.exports[requested.export.id].last_error == "object_cleanup_failed"
    assert state.audits[-1].action is ResumeAuditAction.EXPORT_DELETION_RETRY_SCHEDULED
    assert "private storage detail" not in str(state.audits[-1].metadata)

    clock.advance(1)
    completed = await cleanup.process(requested.export.id, "cleanup-retry")

    assert completed.status is ResumeExportStatus.DELETED
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_export_cleanup_dead_letters_without_claiming_the_object_is_deleted() -> None:
    state = MemoryResumeBuilder()
    storage = FailingDeleteStorage(failures=2)
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    renderer = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )
    assert (
        await renderer.process(requested.export.id, "render-before-dead-letter")
    ).status is ResumeExportStatus.VERIFIED
    state.export_outbox.clear()
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )
    await service.delete_export(
        OWNER_ID,
        requested.export.id,
        idempotency_key="dead-letter-delete",
        context=RequestContext(OWNER_ID, "dead-letter-delete", "e" * 32),
    )
    state.exports[requested.export.id] = replace(
        state.exports[requested.export.id],
        cleanup_max_attempts=2,
    )
    cleanup = ResumeExportCleanupProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        storage=storage,
        policy=ResumeExportWorkerPolicy(retry_delay_seconds=1),
    )

    first = await cleanup.process(requested.export.id, "cleanup-dead-one")
    clock.advance(1)
    terminal = await cleanup.process(requested.export.id, "cleanup-dead-two")

    assert first.status is ResumeExportStatus.DELETION_RETRY_WAIT
    assert terminal.status is ResumeExportStatus.DELETION_DEAD_LETTERED
    export = state.exports[requested.export.id]
    assert export.deleted_at is None
    assert export.object_key is not None
    assert len(storage.objects) == 1
    assert state.audits[-1].action is ResumeAuditAction.EXPORT_DELETION_DEAD_LETTERED


@pytest.mark.asyncio
async def test_transient_failure_retries_from_durable_outbox_then_dead_letters() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.exports[requested.export.id] = replace(requested.export, max_attempts=2)
    dispatcher = ResumeExportOutboxDispatcher(
        unit_of_work=state,
        publisher=RecordingPublisher(),
        clock=clock,
        identifiers=UuidFactory(),
    )
    assert (await dispatcher.dispatch_pending(10)).published == 1
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=FailingRenderer(),  # type: ignore[arg-type]
        extractor=PlainTextExtractor(),
        storage=storage,
        policy=ResumeExportWorkerPolicy(retry_delay_seconds=1),
    )

    retry = await processor.process(requested.export.id, "delivery-one")
    assert retry.status is ResumeExportStatus.RETRY_WAIT
    assert retry.retryable
    clock.advance(1)
    assert (await dispatcher.dispatch_pending(10)).published == 1
    dead = await processor.process(requested.export.id, "delivery-two")

    assert dead.status is ResumeExportStatus.DEAD_LETTERED
    assert not dead.retryable
    assert state.exports[requested.export.id].dead_lettered_at == clock.now()
    assert state.exports[requested.export.id].last_error == "export_processing_failed"
    actions = tuple(event.action for event in state.audits)
    assert ResumeAuditAction.EXPORT_DISPATCHED in actions
    assert ResumeAuditAction.EXPORT_RETRY_SCHEDULED in actions
    assert ResumeAuditAction.EXPORT_DEAD_LETTERED in actions


@pytest.mark.asyncio
async def test_outbox_publish_dead_letter_is_durable_redacted_and_audited() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    message = next(iter(state.export_outbox.values()))
    state.export_outbox[message.id] = replace(message, max_attempts=1)
    dispatcher = ResumeExportOutboxDispatcher(
        unit_of_work=state,
        publisher=FailingPublisher(),
        clock=clock,
        identifiers=UuidFactory(),
    )

    result = await dispatcher.dispatch_pending(10)

    assert result.dead_lettered == 1
    export = state.exports[requested.export.id]
    assert export.status is ResumeExportStatus.DEAD_LETTERED
    assert export.last_error == "publish_dead_lettered"
    audit = state.audits[-1]
    assert audit.action is ResumeAuditAction.EXPORT_DISPATCH_DEAD_LETTERED
    assert audit.metadata["stage"] == "outbox_dispatch"
    assert "private broker detail" not in str(audit.metadata)


@pytest.mark.asyncio
async def test_invalid_pinned_content_is_blocked_without_retry_or_object() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, requested = await _request_export(state, storage, clock)
    section = resume.current_version.sections[0]
    state.versions[resume.current_version.id] = replace(
        resume.current_version,
        sections=(
            replace(
                section,
                items=(replace(section.items[0], evidence_references=()),),
            ),
        ),
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    outcome = await processor.process(requested.export.id, "invalid-content")

    assert outcome.status is ResumeExportStatus.BLOCKED
    assert not outcome.retryable
    assert storage.objects == {}
    report = state.verifications[requested.export.id]
    assert report.critical_failures == ("unsupported_version_content",)


@pytest.mark.asyncio
async def test_outbox_acknowledgement_is_fenced_by_the_claimed_lease() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, _requested = await _request_export(state, storage, clock)
    dispatcher = ResumeExportOutboxDispatcher(
        unit_of_work=state,
        publisher=LeaseStealingPublisher(state),
        clock=clock,
        identifiers=UuidFactory(),
    )

    result = await dispatcher.dispatch_pending(10)

    assert result.published == 0
    message = next(iter(state.export_outbox.values()))
    assert message.published_at is None


@pytest.mark.asyncio
async def test_reconciler_rearms_a_lost_pending_delivery_once() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.export_outbox.clear()
    clock.advance(301)
    reconciler = ResumeExportReconciler(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
    )

    first = await reconciler.reconcile(10)
    second = await reconciler.reconcile(10)

    assert first.requeued == 1
    assert second.requeued == 0
    assert len(state.export_outbox) == 1
    assert state.exports[requested.export.id].status is ResumeExportStatus.PENDING
    assert state.audits[-1].action is ResumeAuditAction.EXPORT_RECOVERY_SCHEDULED
    assert state.audits[-1].metadata["stage"] == "reconciliation"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("behavior", "expected_failure_prefix"),
    [
        ("omit", "occurrence:"),
        ("duplicate", "occurrence:"),
        ("reverse", "reading_order:"),
        ("unsearchable", "searchability_failed"),
    ],
)
async def test_verifier_blocks_manifest_omissions_duplicates_order_and_searchability(
    behavior: str,
    expected_failure_prefix: str,
) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=ManifestMutationRenderer(behavior),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    outcome = await processor.process(requested.export.id, f"worker-{behavior}")

    assert outcome.status is ResumeExportStatus.BLOCKED
    report = state.verifications[requested.export.id]
    assert any(
        failure == expected_failure_prefix or failure.startswith(expected_failure_prefix)
        for failure in report.critical_failures
    )
    if behavior == "omit":
        assert report.missing_lines
    if behavior == "duplicate":
        assert report.duplicate_lines
    if behavior == "reverse":
        assert report.reading_order_failures
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_verifier_blocks_a_tampered_version_content_hash() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    _resume, requested = await _request_export(state, storage, clock)
    state.exports[requested.export.id] = replace(
        requested.export,
        version_content_sha256="0" * 64,
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    outcome = await processor.process(requested.export.id, "tampered-version-pin")

    assert outcome.status is ResumeExportStatus.BLOCKED
    report = state.verifications[requested.export.id]
    assert "version_content_hash_mismatch" in report.critical_failures
    assert "manifest_version_mismatch" in report.grounding_codes
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_verifier_blocks_unsupported_numeric_entity_facts() -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, requested = await _request_export(state, storage, clock)
    entity_id = UUID("00000000-0000-4000-8000-000000000999")
    section = resume.current_version.sections[0]
    numeric_version = replace(
        resume.current_version,
        sections=(
            replace(
                section,
                items=(replace(section.items[0], entity_id=entity_id),),
            ),
            *resume.current_version.sections[1:],
        ),
        entities=(
            ResumeEntityFact(
                id=entity_id,
                kind="experience",
                title="Led 42 portfolio launches",
                organization=None,
                official_title=None,
                display_title=None,
                location=None,
                start_date=None,
                end_date=None,
                is_current=False,
                evidence_ids=(),
            ),
        ),
    )
    state.versions[numeric_version.id] = numeric_version
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=storage,
    )

    outcome = await processor.process(requested.export.id, "unsupported-numeric-worker")

    assert outcome.status is ResumeExportStatus.BLOCKED
    report = state.verifications[requested.export.id]
    assert any(
        failure.startswith("unsupported_manifest_entry:entity:")
        for failure in report.critical_failures
    )
    assert any(
        failure.startswith("numeric_grounding_missing:entity:")
        for failure in report.critical_failures
    )
    assert "numeric_grounding_failed" in report.grounding_codes
    assert storage.objects == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", [ResumeFormat.PDF, ResumeFormat.DOCX])
async def test_unicode_pdf_and_docx_pass_exact_manifest_verification(
    tmp_path: Path,
    fmt: ResumeFormat,
) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, _unused = await _request_export(state, storage, clock)
    state.exports.clear()
    state.export_outbox.clear()
    unicode_text = "Improved café onboarding for customers in München."
    section = resume.current_version.sections[0]
    item = section.items[0]
    reference = item.evidence_references[0]
    unicode_version = replace(
        resume.current_version,
        personal_facts=(replace(resume.current_version.personal_facts[0], value="José Núñez"),),
        sections=(
            replace(
                section,
                items=(
                    replace(
                        item,
                        text=unicode_text,
                        evidence_references=(
                            replace(
                                reference,
                                claim_sha256=hashlib.sha256(
                                    unicode_text.encode("utf-8")
                                ).hexdigest(),
                            ),
                        ),
                    ),
                ),
            ),
            *resume.current_version.sections[1:],
        ),
    )
    state.versions[unicode_version.id] = unicode_version
    requested = await _export_current_version(
        state,
        storage,
        clock,
        unicode_version.id,
        fmt=fmt,
        idempotency_key=f"unicode-{fmt.value}-export",
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=DeterministicResumeRenderer(),
        extractor=ResumeBuilderDocumentExtractor(_document_limits(tmp_path)),
        storage=storage,
        policy=ResumeExportWorkerPolicy(temp_root=tmp_path),
    )

    outcome = await processor.process(requested.export.id, f"unicode-{fmt.value}-worker")

    assert outcome.status is ResumeExportStatus.VERIFIED
    report = state.verifications[requested.export.id]
    assert report.critical_failures == ()
    assert report.occurrence_mismatches == ()
    assert "José Núñez" in report.detected_lines
    assert unicode_text in report.detected_lines
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_pdf_export_verifies_smart_apostrophe_bullets(tmp_path: Path) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, _unused = await _request_export(state, storage, clock)
    state.exports.clear()
    state.export_outbox.clear()
    smart_quote_text = (
        "Xmem is a India\u2019s First multi-modal, multi-agentic long-term memory layer for AI agents."
    )
    section = resume.current_version.sections[0]
    item = section.items[0]
    reference = item.evidence_references[0]
    smart_version = replace(
        resume.current_version,
        sections=(
            replace(
                section,
                items=(
                    replace(
                        item,
                        text=smart_quote_text,
                        evidence_references=(
                            replace(
                                reference,
                                claim_sha256=hashlib.sha256(
                                    smart_quote_text.encode("utf-8")
                                ).hexdigest(),
                            ),
                        ),
                    ),
                ),
            ),
            *resume.current_version.sections[1:],
        ),
    )
    state.versions[smart_version.id] = smart_version
    requested = await _export_current_version(
        state,
        storage,
        clock,
        smart_version.id,
        fmt=ResumeFormat.PDF,
        idempotency_key="smart-apostrophe-pdf-export",
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=DeterministicResumeRenderer(),
        extractor=ResumeBuilderDocumentExtractor(_document_limits(tmp_path)),
        storage=storage,
        policy=ResumeExportWorkerPolicy(temp_root=tmp_path),
    )

    outcome = await processor.process(requested.export.id, "smart-apostrophe-pdf-worker")

    report = state.verifications[requested.export.id]
    assert outcome.status is ResumeExportStatus.VERIFIED, report.critical_failures
    assert report.critical_failures == ()
    assert report.occurrence_mismatches == ()


@pytest.mark.asyncio
async def test_executive_pdf_export_verifies_glued_section_headings(tmp_path: Path) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, _unused = await _request_export(state, storage, clock)
    state.exports.clear()
    state.export_outbox.clear()
    section = resume.current_version.sections[0]
    item = section.items[0]
    reference = item.evidence_references[0]
    bullet_text = (
        "Xmem is a India's First multi-modal, multi-agentic long-term memory "
        "layer for AI agents. Primary language: Python."
    )
    executive_version = replace(
        resume.current_version,
        target_role="Software Engineer",
        template=ResumeTemplate.EXECUTIVE,
        source_evidence_ids=item.evidence_ids,
        sections=(
            replace(
                section,
                title="Experience",
                items=(
                    replace(
                        item,
                        text=bullet_text,
                        evidence_references=(
                            replace(
                                reference,
                                claim_sha256=hashlib.sha256(
                                    bullet_text.encode("utf-8")
                                ).hexdigest(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    state.versions[executive_version.id] = executive_version
    requested = await _export_current_version(
        state,
        storage,
        clock,
        executive_version.id,
        fmt=ResumeFormat.PDF,
        idempotency_key="executive-glued-heading-pdf-export",
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=DeterministicResumeRenderer(),
        extractor=ResumeBuilderDocumentExtractor(_document_limits(tmp_path)),
        storage=storage,
        policy=ResumeExportWorkerPolicy(temp_root=tmp_path),
    )

    outcome = await processor.process(requested.export.id, "executive-glued-heading-pdf-worker")

    assert outcome.status is ResumeExportStatus.VERIFIED
    report = state.verifications[requested.export.id]
    assert report.critical_failures == ()
    assert report.occurrence_mismatches == ()


@pytest.mark.asyncio
async def test_executive_pdf_export_verifies_github_style_multi_bullet_resume(
    tmp_path: Path,
) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, _unused = await _request_export(state, storage, clock)
    state.exports.clear()
    state.export_outbox.clear()
    section = resume.current_version.sections[0]
    item = section.items[0]
    reference = item.evidence_references[0]
    bullets = (
        "Primary language: Jupyter Notebook.",
        "Public repository xmem-landing.",
        (
            "Xmem is a India's First multi-modal, multi-agentic long-term memory "
            "layer for AI agents. Primary language: Python."
        ),
        "Software Engineer | Footballer",
    )
    executive_version = replace(
        resume.current_version,
        target_role="Software Engineer",
        template=ResumeTemplate.EXECUTIVE,
        source_evidence_ids=item.evidence_ids,
        sections=(
            replace(
                section,
                title="Experience",
                items=tuple(
                    replace(
                        item,
                        id=UUID(f"00000000-0000-4000-8000-00000000072{index}"),
                        text=text,
                        evidence_references=(
                            replace(
                                reference,
                                claim_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            ),
                        ),
                    )
                    for index, text in enumerate(bullets)
                ),
            ),
        ),
    )
    state.versions[executive_version.id] = executive_version
    requested = await _export_current_version(
        state,
        storage,
        clock,
        executive_version.id,
        fmt=ResumeFormat.PDF,
        idempotency_key="executive-github-bullets-pdf-export",
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=DeterministicResumeRenderer(),
        extractor=ResumeBuilderDocumentExtractor(_document_limits(tmp_path)),
        storage=storage,
        policy=ResumeExportWorkerPolicy(temp_root=tmp_path),
    )

    outcome = await processor.process(requested.export.id, "executive-github-bullets-pdf-worker")

    assert outcome.status is ResumeExportStatus.VERIFIED
    report = state.verifications[requested.export.id]
    assert report.critical_failures == ()
    assert report.occurrence_mismatches == ()


@pytest.mark.asyncio
async def test_real_pdf_round_trip_blocks_a_page_limit_overflow(tmp_path: Path) -> None:
    state = MemoryResumeBuilder()
    storage = MemoryStorage()
    clock = MutableClock()
    resume, _unused = await _request_export(state, storage, clock)
    state.exports.clear()
    state.export_outbox.clear()
    source_section = resume.current_version.sections[0]
    source_item = source_section.items[0]
    sections = tuple(
        replace(
            source_section,
            id=UUID(f"00000000-0000-4000-8000-{0x900 + section_index:012x}"),
            title=f"Experience {section_index + 1}",
            items=tuple(
                replace(
                    source_item,
                    id=UUID(
                        f"00000000-0000-4000-8000-{0xA00 + section_index * 24 + item_index:012x}"
                    ),
                )
                for item_index in range(24)
            ),
        )
        for section_index in range(12)
    )
    oversized = replace(
        resume.current_version,
        sections=sections,
        source_evidence_ids=source_item.evidence_ids,
        layout=ResumeLayout(page_limit=1),
    )
    state.versions[oversized.id] = oversized
    service = ResumeBuilderService(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
    )
    requested = await service.export_version(
        OWNER_ID,
        oversized.id,
        ExportResume(format=ResumeFormat.PDF),
        idempotency_key="oversized-pdf-export",
        context=RequestContext(OWNER_ID, "oversized-export", "b" * 32),
    )
    processor = ResumeExportProcessor(
        unit_of_work=state,
        clock=clock,
        identifiers=UuidFactory(),
        renderer=DeterministicResumeRenderer(),
        extractor=ResumeBuilderDocumentExtractor(_document_limits(tmp_path)),
        storage=storage,
        policy=ResumeExportWorkerPolicy(temp_root=tmp_path),
    )

    outcome = await processor.process(requested.export.id, "oversized-worker")

    assert outcome.status is ResumeExportStatus.BLOCKED
    report = state.verifications[requested.export.id]
    assert report.page_count > 1
    assert any(value.startswith("page_limit_exceeded:") for value in report.critical_failures)
    assert storage.objects == {}
