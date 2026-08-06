"""Security and durability tests for private Career Record evidence attachments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

import pytest

from career_record_attachment_memory import (
    FakeAttachmentStorage,
    FakeClock,
    FakeExtractor,
    FakePublisher,
    FakeScanner,
    InMemoryAttachmentUnitOfWorkFactory,
    SequentialIds,
    SequentialTokens,
    pending_cleanups,
)
from rezumi.modules.career_record.application.attachment_workflow import (
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    AdmitAttachment,
    AttachmentCleanupProcessor,
    AttachmentConflict,
    AttachmentDownloadPurpose,
    AttachmentFailureRecorder,
    AttachmentIdempotencyConflict,
    AttachmentJobReconciler,
    AttachmentJobStatus,
    AttachmentLimits,
    AttachmentMediaType,
    AttachmentNotFound,
    AttachmentOutboxDispatcher,
    AttachmentPolicy,
    AttachmentProcessor,
    AttachmentRejected,
    AttachmentRequestContext,
    AttachmentStatus,
    AttachmentWorkflowService,
    CleanupPurpose,
    CleanupStatus,
    SafeAttachmentError,
    ScanVerdict,
)

OWNER = UUID(int=1)
OTHER_OWNER = UUID(int=2)
EVIDENCE = UUID(int=3)
OTHER_EVIDENCE = UUID(int=4)
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"
DOCX_BYTES = b"PK\x03\x04" + (b"docx-entry" * 8)


@dataclass(slots=True)
class Runtime:
    factory: InMemoryAttachmentUnitOfWorkFactory
    clock: FakeClock
    ids: SequentialIds
    storage: FakeAttachmentStorage
    scanner: FakeScanner
    extractor: FakeExtractor
    publisher: FakePublisher
    workflow: AttachmentWorkflowService
    processor: AttachmentProcessor
    cleanup: AttachmentCleanupProcessor
    dispatcher: AttachmentOutboxDispatcher
    policy: AttachmentPolicy


def make_runtime(tmp_path: Path, *, policy: AttachmentPolicy | None = None) -> Runtime:
    selected_policy = policy or AttachmentPolicy()
    factory = InMemoryAttachmentUnitOfWorkFactory()
    clock = FakeClock()
    ids = SequentialIds()
    storage = FakeAttachmentStorage()
    scanner = FakeScanner()
    extractor = FakeExtractor()
    publisher = FakePublisher()
    limits = AttachmentLimits(temp_root=tmp_path.resolve())
    workflow = AttachmentWorkflowService(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        limits=limits,
        policy=selected_policy,
        ids=ids,
        tokens=SequentialTokens(),
    )
    processor = AttachmentProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=scanner,
        extractor=extractor,
        limits=limits,
        policy=selected_policy,
        ids=ids,
    )
    return Runtime(
        factory=factory,
        clock=clock,
        ids=ids,
        storage=storage,
        scanner=scanner,
        extractor=extractor,
        publisher=publisher,
        workflow=workflow,
        processor=processor,
        cleanup=AttachmentCleanupProcessor(
            unit_of_work=factory, storage=storage, clock=clock, ids=ids
        ),
        dispatcher=AttachmentOutboxDispatcher(
            unit_of_work=factory,
            publisher=publisher,
            clock=clock,
            ids=ids,
            policy=selected_policy,
        ),
        policy=selected_policy,
    )


def context(owner_user_id: UUID = OWNER) -> AttachmentRequestContext:
    return AttachmentRequestContext(owner_user_id, "request-attachment", "trace-attachment")


async def admit(
    runtime: Runtime,
    *,
    owner_user_id: UUID = OWNER,
    evidence_id: UUID = EVIDENCE,
    value: bytes = PDF_BYTES,
    media_type: AttachmentMediaType = AttachmentMediaType.PDF,
    stored_media_type: str | None = None,
) -> UUID:
    runtime.factory.add_evidence(owner_user_id, evidence_id)
    suffix = "pdf" if media_type is AttachmentMediaType.PDF else "docx"
    view = await runtime.workflow.admit(
        owner_user_id,
        AdmitAttachment(evidence_id, f"evidence.{suffix}", media_type.value, len(value)),
        context(owner_user_id),
    )
    runtime.storage.upload_latest(value, stored_media_type)
    return view.attachment_id


async def finalize_and_process(
    runtime: Runtime, attachment_id: UUID, *, key: str = "finalize-key-001"
) -> UUID:
    finalized = await runtime.workflow.finalize(OWNER, attachment_id, key, context())
    outcome = await runtime.processor.process_job(finalized.job_id, "worker-token-001")
    assert outcome.status is AttachmentJobStatus.SUCCEEDED
    return finalized.job_id


@pytest.mark.asyncio
async def test_admission_is_owner_scoped_private_and_size_type_bound(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    runtime.factory.add_evidence(OWNER, EVIDENCE)

    view = await runtime.workflow.admit(
        OWNER,
        AdmitAttachment(EVIDENCE, "supporting-proof.pdf", "application/pdf", len(PDF_BYTES)),
        context(),
    )

    assert view.upload.method == "PUT"
    assert dict(view.upload.required_headers) == {
        "content-type": "application/pdf",
        "content-length": str(len(PDF_BYTES)),
    }
    staging_key, _, expected_size, _ = runtime.storage.put_requests[0]
    record = runtime.factory.state.attachments[view.attachment_id]
    assert expected_size == len(PDF_BYTES)
    assert OWNER.hex not in staging_key
    assert "supporting-proof" not in staging_key
    assert record.quarantine_object_key is not None
    assert record.quarantine_object_key != staging_key
    assert "object_key" not in view.__dataclass_fields__

    with pytest.raises(AttachmentNotFound):
        await runtime.workflow.get(OTHER_OWNER, view.attachment_id, context(OTHER_OWNER))
    with pytest.raises(AttachmentNotFound):
        await runtime.workflow.get(OWNER, view.attachment_id, context(OTHER_OWNER))
    with pytest.raises(AttachmentNotFound):
        await runtime.workflow.finalize(
            OTHER_OWNER, view.attachment_id, "other-finalize-1", context(OTHER_OWNER)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "stored_media_type", "expected_code"),
    [
        (PDF_BYTES + b"extra", None, SafeAttachmentError.UPLOAD_SIZE_MISMATCH),
        (
            PDF_BYTES,
            AttachmentMediaType.DOCX.value,
            SafeAttachmentError.UPLOAD_MEDIA_TYPE_MISMATCH,
        ),
        (
            b"X" * len(PDF_BYTES),
            None,
            SafeAttachmentError.UPLOAD_SIGNATURE_MISMATCH,
        ),
    ],
)
async def test_finalize_rejects_wrong_size_type_and_magic_bytes(
    tmp_path: Path,
    value: bytes,
    stored_media_type: str | None,
    expected_code: SafeAttachmentError,
) -> None:
    runtime = make_runtime(tmp_path)
    runtime.factory.add_evidence(OWNER, EVIDENCE)
    view = await runtime.workflow.admit(
        OWNER,
        AdmitAttachment(EVIDENCE, "proof.pdf", AttachmentMediaType.PDF.value, len(PDF_BYTES)),
        context(),
    )
    runtime.storage.upload_latest(value, stored_media_type)

    with pytest.raises(AttachmentRejected) as raised:
        await runtime.workflow.finalize(OWNER, view.attachment_id, "finalize-invalid-1", context())

    assert raised.value.code is expected_code
    record = runtime.factory.state.attachments[view.attachment_id]
    assert record.status is AttachmentStatus.REJECTED
    assert record.safe_error_code is expected_code
    assert not runtime.factory.state.jobs
    cleanups = pending_cleanups(runtime.factory, view.attachment_id)
    assert len(cleanups) == 1
    assert cleanups[0].purpose is CleanupPurpose.REJECTED_STAGING


@pytest.mark.asyncio
async def test_finalize_is_durably_idempotent_and_rejects_key_reuse(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    first_id = await admit(runtime)

    first = await runtime.workflow.finalize(OWNER, first_id, "finalize-replay-1", context())
    replay = await runtime.workflow.finalize(OWNER, first_id, "finalize-replay-1", context())

    assert replay == first
    assert len(runtime.storage.promotions) == 1
    assert len(runtime.factory.state.jobs) == 1
    assert len(runtime.factory.state.receipts) == 1
    assert len(runtime.factory.state.outbox) == 1

    second_id = await admit(runtime, evidence_id=OTHER_EVIDENCE)
    with pytest.raises(AttachmentIdempotencyConflict):
        await runtime.workflow.finalize(OWNER, second_id, "finalize-replay-1", context())


@pytest.mark.asyncio
async def test_scanner_outage_retries_fail_closed_without_extraction(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-scanner-1", context()
    )
    runtime.scanner.error = RuntimeError("scanner socket closed")

    outcome = await runtime.processor.process_job(finalized.job_id, "scanner-outage-token")

    assert outcome.status is AttachmentJobStatus.RETRY_WAIT
    assert outcome.safe_error_code is SafeAttachmentError.MALWARE_SCANNER_UNAVAILABLE
    assert outcome.retryable
    assert runtime.extractor.calls == 0
    record = runtime.factory.state.attachments[attachment_id]
    assert record.status is AttachmentStatus.QUARANTINED
    assert record.safe_error_code is SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY
    assert len(runtime.factory.state.outbox) == 2


@pytest.mark.asyncio
async def test_infected_attachment_is_rejected_and_quarantine_cleanup_is_durable(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-infected-1", context()
    )
    runtime.scanner.verdict = ScanVerdict.INFECTED

    outcome = await runtime.processor.process_job(finalized.job_id, "infected-token-001")

    assert outcome.status is AttachmentJobStatus.REJECTED
    assert outcome.safe_error_code is SafeAttachmentError.MALWARE_DETECTED
    assert not outcome.retryable
    assert runtime.extractor.calls == 0
    record = runtime.factory.state.attachments[attachment_id]
    assert record.status is AttachmentStatus.REJECTED
    assert any(
        item.purpose is CleanupPurpose.REJECTED_QUARANTINE
        for item in pending_cleanups(runtime.factory, attachment_id)
    )


@pytest.mark.asyncio
async def test_retry_attempts_are_bounded_and_dead_letter_visible(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-dead-letter-1", context()
    )
    runtime.scanner.verdict = ScanVerdict.UNAVAILABLE

    for attempt in range(runtime.policy.max_processing_attempts):
        outcome = await runtime.processor.process_job(
            finalized.job_id, f"retry-token-{attempt:03d}"
        )
        if attempt + 1 < runtime.policy.max_processing_attempts:
            assert outcome.status is AttachmentJobStatus.RETRY_WAIT
            runtime.clock.advance(seconds=5 * (2**attempt))

    assert outcome.status is AttachmentJobStatus.DEAD_LETTERED
    assert outcome.safe_error_code is SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
    record = runtime.factory.state.attachments[attachment_id]
    assert record.status is AttachmentStatus.REJECTED
    assert record.safe_error_code is SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED


@pytest.mark.asyncio
async def test_worker_runtime_failure_is_recorded_without_provider_composition(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-runtime-failure-1", context()
    )
    recorder = AttachmentFailureRecorder(
        unit_of_work=runtime.factory,
        clock=runtime.clock,
        ids=runtime.ids,
        policy=runtime.policy,
    )

    retrying = await recorder.record_failure(
        finalized.job_id,
        "runtime-failure-token",
        SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
        exhausted=False,
    )

    assert retrying.status is AttachmentJobStatus.RETRY_WAIT
    assert retrying.retryable
    assert runtime.factory.state.attachments[attachment_id].status is AttachmentStatus.QUARANTINED
    assert len(runtime.factory.state.outbox) == 2
    retry_message = max(
        runtime.factory.state.outbox.values(), key=lambda message: message.generation
    )
    assert retry_message.generation == 1
    assert retry_message.next_attempt_at > runtime.clock.now()

    exhausted = await recorder.record_failure(
        finalized.job_id,
        "runtime-failure-token",
        SafeAttachmentError.ATTACHMENT_PROCESSING_RETRY,
        exhausted=True,
    )

    assert exhausted.status is AttachmentJobStatus.DEAD_LETTERED
    assert exhausted.safe_error_code is SafeAttachmentError.ATTACHMENT_PROCESSING_DEAD_LETTERED
    attachment = runtime.factory.state.attachments[attachment_id]
    assert attachment.status is AttachmentStatus.REJECTED
    assert any(
        item.purpose is CleanupPurpose.REJECTED_QUARANTINE
        for item in pending_cleanups(runtime.factory, attachment_id)
    )


@pytest.mark.asyncio
async def test_expired_worker_is_fenced_before_clean_commit(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(OWNER, attachment_id, "finalize-fence-1", context())
    old_lease = await runtime.processor.claim_job(finalized.job_id, "old-worker-token")
    assert old_lease is not None
    runtime.clock.advance(seconds=runtime.policy.execution_lease_seconds + 1)
    new_lease = await runtime.processor.claim_job(finalized.job_id, "new-worker-token")
    assert new_lease is not None
    assert new_lease.fence == old_lease.fence + 1

    stale = await runtime.processor.process_claimed_job(old_lease)

    assert stale.safe_error_code is SafeAttachmentError.EXECUTION_FENCED
    assert runtime.factory.state.attachments[attachment_id].status is AttachmentStatus.PROCESSING

    current = await runtime.processor.process_claimed_job(new_lease)
    assert current.status is AttachmentJobStatus.SUCCEEDED
    assert runtime.factory.state.attachments[attachment_id].status is AttachmentStatus.CLEAN


@pytest.mark.asyncio
async def test_reconciler_recovers_a_lost_delivery_after_lease_expiry(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-reconcile-1", context()
    )
    assert (await runtime.dispatcher.dispatch_pending()).published == 1
    lost_lease = await runtime.processor.claim_job(finalized.job_id, "lost-worker-token")
    assert lost_lease is not None
    runtime.clock.advance(seconds=runtime.policy.execution_lease_seconds + 1)
    reconciler = AttachmentJobReconciler(
        unit_of_work=runtime.factory,
        clock=runtime.clock,
        stale_after_seconds=60,
        ids=runtime.ids,
        policy=runtime.policy,
    )

    recovered = await reconciler.reconcile_stale()

    assert recovered.requeued == 1
    assert recovered.dead_lettered == 0
    job = runtime.factory.state.jobs[finalized.job_id]
    assert job.status is AttachmentJobStatus.QUEUED
    assert job.execution_token_hash is None
    assert job.lease_expires_at is None
    assert max(message.generation for message in runtime.factory.state.outbox.values()) == 1
    stale = await runtime.processor.process_claimed_job(lost_lease)
    assert stale.safe_error_code is SafeAttachmentError.EXECUTION_FENCED
    assert (await runtime.dispatcher.dispatch_pending()).published == 1
    completed = await runtime.processor.process_job(finalized.job_id, "replacement-token")
    assert completed.status is AttachmentJobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_extractor_output_is_revalidated_against_resource_limits(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-extraction-1", context()
    )
    runtime.extractor.summary = replace(runtime.extractor.summary, page_count=21)

    outcome = await runtime.processor.process_job(finalized.job_id, "extract-limit-token")

    assert outcome.status is AttachmentJobStatus.REJECTED
    assert outcome.safe_error_code is SafeAttachmentError.INVALID_DOCUMENT_STRUCTURE
    assert runtime.factory.state.attachments[attachment_id].status is AttachmentStatus.REJECTED


@pytest.mark.asyncio
async def test_download_is_owner_scoped_clean_only_and_operation_specific(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-download-1", context()
    )

    with pytest.raises(AttachmentConflict):
        await runtime.workflow.download(
            OWNER,
            attachment_id,
            AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
            context(),
        )

    outcome = await runtime.processor.process_job(finalized.job_id, "download-clean-token")
    assert outcome.status is AttachmentJobStatus.SUCCEEDED
    grant = await runtime.workflow.download(
        OWNER,
        attachment_id,
        AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
        context(),
    )

    assert grant.operation.method == "GET"
    assert grant.purpose is AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW
    assert "career-record/attachments" not in grant.operation.url
    assert runtime.storage.get_requests[-1][2] is grant.purpose
    with pytest.raises(AttachmentNotFound):
        await runtime.workflow.download(
            OTHER_OWNER,
            attachment_id,
            AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
            context(OTHER_OWNER),
        )


@pytest.mark.asyncio
async def test_outbox_publishes_identifier_only_payload_and_dead_letters_broker_failure(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-outbox-1", context()
    )

    dispatched = await runtime.dispatcher.dispatch_pending()

    assert dispatched.published == 1
    assert runtime.publisher.calls == [
        (PROCESS_EVIDENCE_ATTACHMENT_TASK, finalized.job_id, "trace-attachment")
    ]
    published_payload = repr(runtime.publisher.calls)
    record = runtime.factory.state.attachments[attachment_id]
    assert record.display_filename not in published_payload
    assert record.staging_object_key not in published_payload
    assert record.quarantine_object_key not in published_payload

    failing = make_runtime(tmp_path / "broker", policy=AttachmentPolicy(max_outbox_attempts=1))
    failing_id = await admit(failing)
    failed_finalization = await failing.workflow.finalize(
        OWNER, failing_id, "finalize-outbox-fail", context()
    )
    failing.publisher.fail = True
    failed = await failing.dispatcher.dispatch_pending()
    assert failed.dead_lettered == 1
    assert (
        failing.factory.state.jobs[failed_finalization.job_id].status
        is AttachmentJobStatus.DEAD_LETTERED
    )
    assert failing.factory.state.attachments[failing_id].status is AttachmentStatus.REJECTED


@pytest.mark.asyncio
async def test_deletion_is_durable_redacts_content_and_cleans_every_private_object(
    tmp_path: Path,
) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    await finalize_and_process(runtime, attachment_id, key="finalize-delete-1")
    before = runtime.factory.state.attachments[attachment_id]
    filename = before.display_filename
    object_keys = {
        key for key in (before.staging_object_key, before.quarantine_object_key) if key is not None
    }

    deleting = await runtime.workflow.delete(OWNER, attachment_id, context())

    assert deleting.status is AttachmentStatus.DELETING
    with pytest.raises(AttachmentConflict):
        await runtime.workflow.download(
            OWNER,
            attachment_id,
            AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
            context(),
        )
    for cleanup in list(pending_cleanups(runtime.factory, attachment_id)):
        outcome = await runtime.cleanup.process(cleanup.id)
        assert outcome.status is CleanupStatus.COMPLETED

    deleted = runtime.factory.state.attachments[attachment_id]
    assert deleted.status is AttachmentStatus.DELETED
    assert deleted.display_filename is None
    assert deleted.media_type is None
    assert deleted.expected_size is None
    assert deleted.content_sha256 is None
    assert deleted.extraction is None
    assert deleted.staging_object_key is None
    assert deleted.quarantine_object_key is None
    assert object_keys.isdisjoint(runtime.storage.objects)

    audit_projection = repr(
        [
            (event.action.value, event.safe_details, event.request_id, event.trace_id)
            for event in runtime.factory.state.audits
        ]
    )
    assert filename is not None and filename not in audit_projection
    assert all(key not in audit_projection for key in object_keys)

    replay = await runtime.workflow.delete(OWNER, attachment_id, context())
    assert replay.status is AttachmentStatus.DELETED


@pytest.mark.asyncio
async def test_deletion_redacts_immediately_after_prior_rejection_cleanup(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    attachment_id = await admit(runtime)
    finalized = await runtime.workflow.finalize(
        OWNER, attachment_id, "finalize-rejected-delete-1", context()
    )
    runtime.scanner.verdict = ScanVerdict.INFECTED
    await runtime.processor.process_job(finalized.job_id, "rejected-delete-token")
    for cleanup in list(pending_cleanups(runtime.factory, attachment_id)):
        await runtime.cleanup.process(cleanup.id)

    deleted = await runtime.workflow.delete(OWNER, attachment_id, context())

    assert deleted.status is AttachmentStatus.DELETED
    assert deleted.display_filename is None
    assert deleted.media_type is None
    assert deleted.expected_size is None
