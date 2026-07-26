"""Memory-backed vertical workflow, ownership, idempotency, and outbox tests."""

import asyncio
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from careeros.modules.resume_health.application import (
    ClaimGuestDocument,
    CorrectionOperation,
    CorrectSemanticField,
    CreateUploadIntent,
    DocumentLimits,
    ResumeRequestContext,
)
from careeros.modules.resume_health.application.models import (
    ExtractedBlock,
    ExtractionResult,
    FinalizedUpload,
    MalwareScanResult,
    SourceSpanView,
    StorageUploadTarget,
)
from careeros.modules.resume_health.application.service import (
    OutboxDispatcher,
    ResumeHealthPolicy,
    ResumeHealthProcessor,
    ResumeHealthService,
    ResumeJobFailureRecorder,
    ResumeJobReconciler,
    ResumeMaintenance,
)
from careeros.modules.resume_health.domain import (
    AnalysisStatus,
    DocumentStatus,
    JobKind,
    JobStatus,
    MalwareStatus,
    ObjectCleanupPurpose,
    OwnerScope,
    ResumeMediaType,
    SourceDocument,
    UploadStatus,
)
from careeros.modules.resume_health.domain.errors import (
    GuestCapabilityRejected,
    IdempotencyConflict,
    ResumeResourceNotFound,
    ResumeStateConflict,
    RetryableProcessingFailure,
    UploadExpired,
    UploadRejected,
)
from careeros.modules.resume_health.infrastructure.fakes import (
    FakeDocumentExtractor,
    FakeJobPublisher,
    FakeMalwareScanner,
    FixedClock,
    InMemoryObjectStorage,
    InMemoryResumeUnitOfWork,
    InMemoryResumeUnitOfWorkFactory,
)
from careeros.modules.resume_health.infrastructure.security import HmacGuestCapabilityManager
from careeros.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)


@pytest.fixture(autouse=True)
def _isolated_default_document_temp_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep default-root tests independent from host and parallel-worker ACLs."""

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


def _extraction() -> ExtractionResult:
    lines = (
        ("heading", "Experience"),
        ("bullet", "Built a fictional platform and improved delivery quality in 2025."),
        ("bullet", "Led a fictional project that reduced review time."),
        ("heading", "Education"),
        ("paragraph", "Fictional University, 2024"),
        ("heading", "Skills"),
        ("paragraph", "Python, PostgreSQL, accessibility"),
    )
    offset = 0
    blocks = []
    for kind, text in lines:
        blocks.append(
            ExtractedBlock(
                kind=kind,
                text=text,
                confidence_basis_points=9_000,
                spans=(SourceSpanView(1, offset, offset + len(text)),),
            )
        )
        offset += len(text) + 1
    return ExtractionResult(
        plain_text="\n".join(text for _, text in lines),
        reading_order=tuple(blocks),
        page_count=1,
        image_only=False,
        warnings=(),
        parser_version="fake/1",
    )


def _invocation_token() -> str:
    return uuid4().hex


def _runtime(
    *,
    storage: InMemoryObjectStorage | None = None,
    scanner: FakeMalwareScanner | None = None,
    extractor: FakeDocumentExtractor | None = None,
    policy: ResumeHealthPolicy | None = None,
    limits: DocumentLimits | None = None,
    semantic_parser: bool = True,
) -> tuple[
    InMemoryResumeUnitOfWorkFactory,
    InMemoryObjectStorage,
    FixedClock,
    ResumeHealthService,
    ResumeHealthProcessor,
]:
    factory = InMemoryResumeUnitOfWorkFactory()
    object_storage = storage or InMemoryObjectStorage()
    clock = FixedClock()
    resolved_limits = limits or DocumentLimits()
    resolved_semantic_parser = LocalResumeParserProvider() if semantic_parser else None
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("h" * 32),
        storage=object_storage,
        limits=resolved_limits,
        policy=policy,
        semantic_parser=resolved_semantic_parser,
    )
    processor = ResumeHealthProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=object_storage,
        scanner=scanner or FakeMalwareScanner(),
        extractor=extractor or FakeDocumentExtractor(_extraction()),
        limits=resolved_limits,
        semantic_parser=resolved_semantic_parser,
    )
    return factory, object_storage, clock, service, processor


async def _finalize_pdf(
    factory: InMemoryResumeUnitOfWorkFactory,
    storage: InMemoryObjectStorage,
    service: ResumeHealthService,
    owner: OwnerScope,
) -> FinalizedUpload:
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
    )
    storage.objects[factory.state.uploads[intent.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    return await service.finalize_upload(
        owner,
        intent.id,
        f"finalize-{uuid4().hex}",
        ResumeRequestContext("request", "0123456789abcdef0123456789abcdef"),
    )


async def _ready_pdf(
    factory: InMemoryResumeUnitOfWorkFactory,
    storage: InMemoryObjectStorage,
    service: ResumeHealthService,
    processor: ResumeHealthProcessor,
    owner: OwnerScope,
) -> FinalizedUpload:
    finalized = await _finalize_pdf(factory, storage, service, owner)
    outcome = await processor.process_job(
        finalized.job_id, "trace", execution_token=f"parse-{uuid4().hex}"
    )
    assert outcome.status == JobStatus.SUCCEEDED
    return finalized


@pytest.mark.asyncio
async def test_unwritable_configured_temp_root_fails_closed_without_path_disclosure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_root = (tmp_path / "configured-document-root").resolve()
    limits = DocumentLimits(temp_root=configured_root)
    factory, storage, _, service, processor = _runtime(limits=limits)
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    sensitive_path = r"C:\private\resume-source"

    def deny_temporary_directory(*args: object, **kwargs: object) -> None:
        del args
        assert kwargs["dir"] == configured_root
        raise PermissionError(f"access denied: {sensitive_path}")

    monkeypatch.setattr(tempfile, "TemporaryDirectory", deny_temporary_directory)

    outcome = await processor.process_job(
        finalized.job_id,
        "trace",
        execution_token=_invocation_token(),
    )

    assert outcome.status is JobStatus.FAILED
    assert outcome.retryable
    assert outcome.safe_error_code == "processing_failed"
    assert factory.state.documents[finalized.document_id].status is DocumentStatus.QUARANTINED
    assert sensitive_path not in repr((factory.state.jobs[finalized.job_id], factory.state.audit))


@pytest.mark.asyncio
async def test_registered_upload_parse_correct_analyze_delete_and_cross_user_denial() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    limits = DocumentLimits()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("p" * 32),
        storage=storage,
        limits=limits,
    )
    processor = ResumeHealthProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeMalwareScanner(),
        extractor=FakeDocumentExtractor(_extraction()),
        limits=limits,
    )
    owner = OwnerScope(user_id=uuid4())
    other = OwnerScope(user_id=uuid4())
    context = ResumeRequestContext("request", "trace")
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
        context,
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (source, ResumeMediaType.PDF.value)
    finalized = await service.finalize_upload(owner, intent.id, f"finalize-{uuid4().hex}", context)

    publisher = FakeJobPublisher()
    dispatch = await OutboxDispatcher(
        unit_of_work=factory, publisher=publisher, clock=clock
    ).dispatch_pending()
    assert dispatch.published == 1
    assert dispatch.failed == 0
    assert publisher.messages[0][1] == finalized.job_id

    with pytest.raises(ResumeResourceNotFound):
        await service.get_document(other, finalized.document_id)
    parse_outcome = await processor.process_job(finalized.job_id, "trace")
    assert parse_outcome.status == JobStatus.SUCCEEDED
    late_failure = await processor.record_task_failure(
        finalized.job_id,
        "trace",
        "late_worker_failure",
        retryable=False,
    )
    assert late_failure.status == JobStatus.SUCCEEDED
    document = await service.get_document(owner, finalized.document_id)
    assert document.status == DocumentStatus.READY
    assert document.current_snapshot_id is not None

    canonical = await service.get_canonical_resume(owner, document.id)
    block = canonical.resume.sections[0].blocks[0]
    corrected = await service.correct_canonical_resume(
        owner,
        document.id,
        canonical.revision,
        (CorrectionOperation(block.id, block.text + " (reviewed)"),),
        context,
    )
    assert corrected.revision == 2
    assert corrected.original_resume.sections[0].blocks[0].text == block.text

    analysis_job = await service.start_analysis(owner, document.id, "analysis-key-0001", context)
    with pytest.raises(ResumeStateConflict):
        await service.start_analysis(owner, document.id, "analysis-key-0002", context)
    analysis_outcome = await processor.process_job(analysis_job.id, "trace")
    assert analysis_outcome.status == JobStatus.SUCCEEDED
    analysis_id = factory.state.jobs[analysis_job.id].result_id
    assert analysis_id is not None
    report = await service.get_analysis(owner, analysis_id)
    assert report.status in {AnalysisStatus.SUCCEEDED, AnalysisStatus.INSUFFICIENT_DATA}
    assert report.feature_set_hash
    completed_replay = await service.start_analysis(
        owner, document.id, "analysis-key-0003", context
    )
    assert completed_replay.id == analysis_job.id

    latest_document = await service.get_document(owner, document.id)
    assert latest_document.latest_analysis_id == report.id
    deletion_job = await service.request_delete(
        owner,
        document.id,
        latest_document.version,
        "delete-key-0000001",
        context,
    )
    deletion_replay = await service.request_delete(
        owner,
        document.id,
        latest_document.version,
        "delete-key-0000001",
        context,
    )
    assert deletion_replay.id == deletion_job.id
    with pytest.raises(ResumeStateConflict):
        await service.request_delete(
            owner,
            document.id,
            latest_document.version + 1,
            "delete-key-0000002",
            context,
        )
    deletion_outcome = await processor.process_job(deletion_job.id, "trace")
    assert deletion_outcome.status == JobStatus.SUCCEEDED
    with pytest.raises(ResumeResourceNotFound):
        await service.get_document(owner, document.id)
    assert upload.status == UploadStatus.DELETED
    assert upload.display_filename == "deleted"

    audit_actions = {event.action for event in factory.state.audit}
    assert audit_actions >= {
        "upload.intent_created",
        "upload.finalized",
        "document.parsed",
        "canonical_resume.corrected",
        "resume_health.requested",
        "resume_health.completed",
        "document.deletion_requested",
        "document.deleted",
    }


@pytest.mark.asyncio
async def test_guest_capability_expiry_claim_and_outbox_dispatch() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("g" * 32),
        storage=storage,
        limits=DocumentLimits(),
    )
    guest = await service.begin_guest_session()
    guest_scope = await service.authenticate_guest(guest.capability_token)
    assert guest_scope.guest_session_id == guest.session_id

    clock.value += timedelta(days=2)
    with pytest.raises(GuestCapabilityRejected):
        await service.authenticate_guest(guest.capability_token)

    publisher = FakeJobPublisher()
    dispatcher = OutboxDispatcher(unit_of_work=factory, publisher=publisher, clock=clock)
    result = await dispatcher.dispatch_pending()
    assert result.published == 0

    assert ClaimGuestDocument(policy_version="v1", consent=True).consent


@pytest.mark.asyncio
async def test_document_admission_enforces_guest_and_registered_quotas() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("q" * 32),
        storage=storage,
        limits=DocumentLimits(),
        policy=ResumeHealthPolicy(max_registered_documents=1),
    )
    command = CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, 100)
    guest_session = await service.begin_guest_session()
    guest = await service.authenticate_guest(guest_session.capability_token)
    await service.create_upload_intent(guest, command)
    with pytest.raises(ResumeStateConflict):
        await service.create_upload_intent(guest, command)

    user = OwnerScope(user_id=uuid4())
    await service.create_upload_intent(user, command)
    with pytest.raises(ResumeStateConflict):
        await service.create_upload_intent(user, command)

    clock.value += timedelta(minutes=31)
    assert (await service.create_upload_intent(guest, command)).expected_size == 100
    assert (await service.create_upload_intent(user, command)).expected_size == 100


@pytest.mark.asyncio
async def test_guest_document_claim_requires_consent_and_transfers_ownership() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    limits = DocumentLimits()
    capability_manager = HmacGuestCapabilityManager("c" * 32)
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=capability_manager,
        storage=storage,
        limits=limits,
    )
    processor = ResumeHealthProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeMalwareScanner(),
        extractor=FakeDocumentExtractor(_extraction()),
        limits=limits,
    )
    guest_session = await service.begin_guest_session()
    guest = await service.authenticate_guest(guest_session.capability_token)
    context = ResumeRequestContext("request", "trace")
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        guest,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
        context,
    )
    storage.objects[factory.state.uploads[intent.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    finalized = await service.finalize_upload(guest, intent.id, f"finalize-{uuid4().hex}", context)
    await processor.process_job(finalized.job_id, context.trace_id)
    analysis_job = await service.start_analysis(
        guest, finalized.document_id, "guest-analysis-0001", context
    )
    await processor.process_job(analysis_job.id, context.trace_id)

    with pytest.raises(ResumeStateConflict):
        await service.claim_guest_document(
            uuid4(),
            guest_session.capability_token,
            finalized.document_id,
            ClaimGuestDocument(policy_version="v1", consent=False),
            context,
        )

    user_id = uuid4()
    claimed = await service.claim_guest_document(
        user_id,
        guest_session.capability_token,
        finalized.document_id,
        ClaimGuestDocument(policy_version="v1", consent=True),
        context,
    )
    assert claimed.retention_expires_at is None
    assert factory.state.documents[finalized.document_id].owner == OwnerScope(user_id=user_id)
    assert (await service.get_document(OwnerScope(user_id=user_id), claimed.id)).id == claimed.id
    with pytest.raises(GuestCapabilityRejected):
        await service.authenticate_guest(guest_session.capability_token)


@pytest.mark.asyncio
async def test_expired_guest_retention_queues_and_completes_durable_deletion() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    limits = DocumentLimits()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("r" * 32),
        storage=storage,
        limits=limits,
    )
    processor = ResumeHealthProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeMalwareScanner(),
        extractor=FakeDocumentExtractor(_extraction()),
        limits=limits,
    )
    guest_session = await service.begin_guest_session()
    guest = await service.authenticate_guest(guest_session.capability_token)
    context = ResumeRequestContext("request", "trace")
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        guest,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
        context,
    )
    storage.objects[factory.state.uploads[intent.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    finalized = await service.finalize_upload(guest, intent.id, f"finalize-{uuid4().hex}", context)
    await processor.process_job(finalized.job_id, context.trace_id)

    clock.value += timedelta(days=2)
    cleanup = await ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage
    ).purge_expired_guest_sessions()
    assert cleanup.queued_guest_deletions == 1
    assert cleanup.revoked_guest_sessions == 1
    deletion_job = next(
        job
        for job in factory.state.jobs.values()
        if job.kind == JobKind.DELETE and job.document_id == finalized.document_id
    )
    assert re.fullmatch(r"[0-9a-f]{32}", deletion_job.trace_id)
    retention_outbox = next(
        message for message in factory.state.outbox.values() if message.job_id == deletion_job.id
    )
    assert retention_outbox.trace_id == deletion_job.trace_id
    outcome = await processor.process_job(deletion_job.id, deletion_job.trace_id)
    assert outcome.status == JobStatus.SUCCEEDED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.DELETED
    with pytest.raises(GuestCapabilityRejected):
        await service.authenticate_guest(guest_session.capability_token)


@pytest.mark.asyncio
async def test_infected_unavailable_dead_letter_and_cancel_paths_fail_closed() -> None:
    async def finalized_runtime(
        scanner: FakeMalwareScanner,
    ) -> tuple[
        InMemoryResumeUnitOfWorkFactory,
        InMemoryObjectStorage,
        ResumeHealthService,
        ResumeHealthProcessor,
        OwnerScope,
        FinalizedUpload,
    ]:
        factory = InMemoryResumeUnitOfWorkFactory()
        storage = InMemoryObjectStorage()
        clock = FixedClock()
        limits = DocumentLimits()
        service = ResumeHealthService(
            unit_of_work=factory,
            clock=clock,
            capabilities=HmacGuestCapabilityManager("s" * 32),
            storage=storage,
            limits=limits,
        )
        processor = ResumeHealthProcessor(
            unit_of_work=factory,
            clock=clock,
            storage=storage,
            scanner=scanner,
            extractor=FakeDocumentExtractor(_extraction()),
            limits=limits,
        )
        owner = OwnerScope(user_id=uuid4())
        source = b"%PDF-1.7\nfictional\n%%EOF"
        intent = await service.create_upload_intent(
            owner,
            CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
        )
        storage.objects[factory.state.uploads[intent.id].staging_object_key] = (
            source,
            ResumeMediaType.PDF.value,
        )
        finalized = await service.finalize_upload(
            owner,
            intent.id,
            f"finalize-{uuid4().hex}",
            ResumeRequestContext("request", "trace"),
        )
        return factory, storage, service, processor, owner, finalized

    infected = MalwareScanResult(clean=False, infected=True, signature="test-signature")
    factory, _, _, processor, _, finalized = await finalized_runtime(FakeMalwareScanner(infected))
    infected_outcome = await processor.process_job(finalized.job_id, "trace")
    infected_document = factory.state.documents[finalized.document_id]
    assert infected_outcome.status == JobStatus.FAILED
    assert infected_document.status == DocumentStatus.REJECTED
    assert infected_document.malware_status == MalwareStatus.INFECTED

    class UnavailableScanner(FakeMalwareScanner):
        async def scan(self, path: Path) -> MalwareScanResult:
            del path
            raise RetryableProcessingFailure("malware_scanner_unavailable")

    factory, _, _, processor, _, finalized = await finalized_runtime(UnavailableScanner())
    outcomes = [await processor.process_job(finalized.job_id, "trace") for _ in range(3)]
    assert [outcome.status for outcome in outcomes] == [
        JobStatus.FAILED,
        JobStatus.FAILED,
        JobStatus.DEAD_LETTERED,
    ]
    dead_lettered = factory.state.documents[finalized.document_id]
    assert dead_lettered.malware_status == MalwareStatus.UNAVAILABLE
    assert dead_lettered.status == DocumentStatus.REJECTED

    factory, _, service, processor, owner, finalized = await finalized_runtime(FakeMalwareScanner())
    cancelled = await service.cancel_job(
        owner,
        finalized.job_id,
        ResumeRequestContext("request", "trace"),
    )
    assert cancelled.status == JobStatus.CANCELLED
    outcome = await processor.process_job(finalized.job_id, "trace")
    assert outcome.status == JobStatus.CANCELLED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.QUARANTINED


@pytest.mark.asyncio
async def test_partial_derivative_write_is_compensated_before_job_failure() -> None:
    class PartialPutStorage(InMemoryObjectStorage):
        async def put_bytes(self, object_key: str, value: bytes, media_type: str) -> None:
            if media_type == "application/json":
                raise RetryableProcessingFailure("object_storage_unavailable")
            await super().put_bytes(object_key, value, media_type)

    factory = InMemoryResumeUnitOfWorkFactory()
    storage = PartialPutStorage()
    clock = FixedClock()
    limits = DocumentLimits()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("w" * 32),
        storage=storage,
        limits=limits,
    )
    processor = ResumeHealthProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeMalwareScanner(),
        extractor=FakeDocumentExtractor(_extraction()),
        limits=limits,
    )
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
    )
    storage.objects[factory.state.uploads[intent.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    finalized = await service.finalize_upload(
        owner,
        intent.id,
        f"finalize-{uuid4().hex}",
        ResumeRequestContext("request", "trace"),
    )

    outcome = await processor.process_job(finalized.job_id, "trace")

    assert outcome.status == JobStatus.FAILED
    assert outcome.retryable
    assert not any(key.startswith("derivatives/") for key in storage.objects)
    assert len([key for key in storage.deleted if key.startswith("derivatives/")]) == 2


@pytest.mark.asyncio
async def test_expired_finalize_is_deleted_once_by_retention_cleanup() -> None:
    factory = InMemoryResumeUnitOfWorkFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("e" * 32),
        storage=storage,
        limits=DocumentLimits(),
    )
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (source, ResumeMediaType.PDF.value)
    clock.value += timedelta(minutes=31)

    with pytest.raises(UploadExpired):
        await service.finalize_upload(
            owner,
            intent.id,
            f"finalize-{uuid4().hex}",
            ResumeRequestContext("request", "trace"),
        )
    assert upload.status == UploadStatus.EXPIRED

    maintenance = ResumeMaintenance(unit_of_work=factory, clock=clock, storage=storage)
    first = await maintenance.cleanup_expired()
    deleted_after_first = tuple(storage.deleted)
    second = await maintenance.cleanup_expired()

    assert first.expired_uploads == 1
    assert second.expired_uploads == 0
    assert upload.status == UploadStatus.DELETED
    assert upload.staging_object_key not in storage.objects
    assert tuple(storage.deleted) == deleted_after_first


@pytest.mark.asyncio
async def test_finalize_restores_staging_when_database_write_fails_after_promotion() -> None:
    class FailingDocumentUnitOfWork(InMemoryResumeUnitOfWork):
        async def add_document(self, document: SourceDocument) -> None:
            del document
            raise ResumeStateConflict

    class FailingDocumentFactory(InMemoryResumeUnitOfWorkFactory):
        def __call__(self) -> InMemoryResumeUnitOfWork:
            return FailingDocumentUnitOfWork(self.state)

    factory = FailingDocumentFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("f" * 32),
        storage=storage,
        limits=DocumentLimits(),
    )
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, len(source)),
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (source, ResumeMediaType.PDF.value)

    with pytest.raises(ResumeStateConflict):
        await service.finalize_upload(
            owner,
            intent.id,
            f"finalize-{uuid4().hex}",
            ResumeRequestContext("request", "trace"),
        )

    assert storage.objects[upload.staging_object_key][0] == source
    assert not any(key.startswith("quarantine/") for key in storage.objects)


@pytest.mark.asyncio
async def test_live_execution_lease_is_busy_without_mutating_or_overlapping_work() -> None:
    class BlockingScanner(FakeMalwareScanner):
        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def scan(self, path: Path) -> MalwareScanResult:
            del path
            self.entered.set()
            await self.release.wait()
            return self.result

    scanner = BlockingScanner()
    factory, storage, _, service, processor = _runtime(scanner=scanner)
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)

    active = asyncio.create_task(
        processor.process_job(finalized.job_id, "trace", execution_token=_invocation_token())
    )
    await asyncio.wait_for(scanner.entered.wait(), timeout=1)
    leased = factory.state.jobs[finalized.job_id]
    version = leased.version
    attempts = leased.attempts

    duplicate = await processor.process_job(
        finalized.job_id, "trace", execution_token=_invocation_token()
    )

    assert duplicate.status == JobStatus.RUNNING
    assert duplicate.retryable
    assert duplicate.safe_error_code == "execution_lease_active"
    assert leased.version == version
    assert leased.attempts == attempts == 1
    unfenced = await processor.record_task_failure(
        finalized.job_id, "trace", "worker_runtime_unavailable", retryable=True
    )
    wrong_fence = await processor.record_task_failure(
        finalized.job_id,
        "trace",
        "worker_runtime_unavailable",
        retryable=True,
        execution_token=_invocation_token(),
    )
    assert unfenced.status == wrong_fence.status == JobStatus.RUNNING

    scanner.release.set()
    assert (await active).status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_expired_execution_lease_is_recovered_and_stale_worker_is_fenced() -> None:
    class FirstCallBlockingScanner(FakeMalwareScanner):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0
            self.first_entered = asyncio.Event()
            self.release_first = asyncio.Event()

        async def scan(self, path: Path) -> MalwareScanResult:
            del path
            self.calls += 1
            if self.calls == 1:
                self.first_entered.set()
                await self.release_first.wait()
            return self.result

    scanner = FirstCallBlockingScanner()
    factory, storage, clock, service, processor = _runtime(scanner=scanner)
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    stale = asyncio.create_task(
        processor.process_job(finalized.job_id, "trace", execution_token=_invocation_token())
    )
    await asyncio.wait_for(scanner.first_entered.wait(), timeout=1)

    clock.value += timedelta(seconds=331)
    recovered = await processor.process_job(
        finalized.job_id, "trace", execution_token=_invocation_token()
    )
    assert recovered.status == JobStatus.SUCCEEDED
    assert factory.state.jobs[finalized.job_id].attempts == 2

    scanner.release_first.set()
    assert (await stale).status == JobStatus.SUCCEEDED
    assert len(factory.state.snapshots) == 1
    assert len(factory.state.artifacts) == 2


@pytest.mark.asyncio
async def test_unexpected_provider_errors_retry_then_dead_letter_with_safe_code() -> None:
    class CrashingExtractor(FakeDocumentExtractor):
        async def extract(
            self, path: Path, media_type: str, limits: DocumentLimits
        ) -> ExtractionResult:
            del path, media_type, limits
            raise RuntimeError("sensitive provider detail must not escape")

    factory, storage, _, service, processor = _runtime(extractor=CrashingExtractor(_extraction()))
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)

    outcomes = [
        await processor.process_job(finalized.job_id, "trace", execution_token=f"crash-{index}")
        for index in range(3)
    ]

    assert [item.status for item in outcomes] == [
        JobStatus.FAILED,
        JobStatus.FAILED,
        JobStatus.DEAD_LETTERED,
    ]
    assert {item.safe_error_code for item in outcomes} == {"processing_failed"}
    document = factory.state.documents[finalized.document_id]
    assert document.status == DocumentStatus.REJECTED
    assert "sensitive" not in repr(factory.state.audit)


@pytest.mark.asyncio
async def test_preclaim_runtime_failures_claim_attempts_and_cannot_strand_queued_job() -> None:
    factory, storage, _, service, processor = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)

    outcomes = [
        await processor.record_task_failure(
            finalized.job_id,
            "trace",
            "worker_runtime_unavailable",
            retryable=True,
            execution_token=f"assembly-failure-{index}",
        )
        for index in range(3)
    ]

    assert [item.status for item in outcomes] == [
        JobStatus.FAILED,
        JobStatus.FAILED,
        JobStatus.DEAD_LETTERED,
    ]
    job = factory.state.jobs[finalized.job_id]
    assert job.attempts == job.max_attempts == 3
    assert job.execution_token_hash is None
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.REJECTED


@pytest.mark.asyncio
async def test_presign_failure_does_not_consume_quota_and_can_retry_immediately() -> None:
    class FailOncePresignStorage(InMemoryObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        async def presign_upload(
            self, object_key: str, media_type: str, expected_size: int, expires_at: datetime
        ) -> StorageUploadTarget:
            if self.fail:
                self.fail = False
                raise OSError("signer unavailable")
            return await super().presign_upload(object_key, media_type, expected_size, expires_at)

    storage = FailOncePresignStorage()
    factory, _, _, service, _ = _runtime(storage=storage)
    owner = OwnerScope(user_id=uuid4())
    command = CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, 100)

    with pytest.raises(OSError, match="signer unavailable"):
        await service.create_upload_intent(owner, command)
    assert factory.state.uploads == {}
    assert (await service.create_upload_intent(owner, command)).expected_size == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "stored_media_type", "expected_code"),
    [
        (b"not-a-pdf", ResumeMediaType.PDF.value, "document_signature_mismatch"),
        (b"%PDF-short", ResumeMediaType.PDF.value, "upload_size_mismatch"),
        (b"%PDF-valid", "text/plain", "upload_media_type_mismatch"),
    ],
)
async def test_permanent_upload_rejections_are_durable_cleaned_and_release_quota(
    value: bytes, stored_media_type: str, expected_code: str
) -> None:
    factory, storage, _, service, _ = _runtime(
        policy=ResumeHealthPolicy(max_registered_documents=1)
    )
    owner = OwnerScope(user_id=uuid4())
    expected_size = len(value) + 1 if expected_code == "upload_size_mismatch" else len(value)
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("fictional-resume.pdf", ResumeMediaType.PDF, expected_size),
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (value, stored_media_type)

    with pytest.raises(UploadRejected) as caught:
        await service.finalize_upload(
            owner,
            intent.id,
            f"finalize-{uuid4().hex}",
            ResumeRequestContext("request", "trace"),
        )

    assert caught.value.code == expected_code
    assert upload.status == UploadStatus.REJECTED
    assert upload.safe_error_code == expected_code
    assert upload.staging_cleaned_at is not None
    assert upload.display_filename == "deleted"
    assert upload.staging_object_key not in storage.objects
    replacement = await service.create_upload_intent(
        owner,
        CreateUploadIntent("replacement-resume.pdf", ResumeMediaType.PDF, 100),
    )
    assert replacement.display_filename == "replacement-resume.pdf"


@pytest.mark.asyncio
async def test_finalized_staging_cleanup_preserves_document_and_replay() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    upload = next(
        item
        for item in factory.state.uploads.values()
        if item.finalized_document_id == finalized.document_id
    )
    quarantine_key = factory.state.documents[finalized.document_id].quarantine_object_key
    storage.objects[upload.staging_object_key] = (b"stale-multipart", ResumeMediaType.PDF.value)
    clock.value = upload.expires_at + timedelta(minutes=15)

    first = await ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage
    ).cleanup_expired()
    replay = await service.finalize_upload(
        owner,
        upload.id,
        factory.state.jobs[finalized.job_id].idempotency_key,
        ResumeRequestContext("request", "trace"),
    )
    second = await ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage
    ).cleanup_expired()

    assert first.expired_uploads == 1
    assert second.expired_uploads == 0
    assert upload.status == UploadStatus.FINALIZED
    assert upload.staging_cleaned_at is not None
    assert replay.document_id == finalized.document_id
    assert quarantine_key in storage.objects


@pytest.mark.asyncio
async def test_upload_cleanup_grace_and_durable_backstop_remove_late_puts() -> None:
    policy = ResumeHealthPolicy(upload_cleanup_grace_seconds=60)
    factory, storage, clock, service, _ = _runtime(policy=policy)
    owner = OwnerScope(user_id=uuid4())
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("late-resume.pdf", ResumeMediaType.PDF, 10),
    )
    upload = factory.state.uploads[intent.id]
    maintenance = ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage, policy=policy
    )
    clock.value = upload.expires_at

    at_expiry = await maintenance.cleanup_expired()
    storage.objects[upload.staging_object_key] = (b"late-write", ResumeMediaType.PDF.value)
    assert at_expiry.expired_uploads == 0
    assert upload.staging_cleaned_at is None

    clock.value += timedelta(seconds=60)
    after_grace = await maintenance.cleanup_expired()
    assert after_grace.expired_uploads == 1
    assert upload.staging_object_key not in storage.objects
    backstop = next(
        item
        for item in factory.state.object_cleanups.values()
        if item.purpose == ObjectCleanupPurpose.UPLOAD_STAGING_BACKSTOP and not item.terminal
    )
    storage.objects[upload.staging_object_key] = (b"very-late-write", ResumeMediaType.PDF.value)

    clock.value = backstop.not_before
    await maintenance.cleanup_expired()
    assert upload.staging_object_key not in storage.objects
    assert backstop.completed_at is not None


@pytest.mark.asyncio
async def test_guest_claim_requires_ready_completed_idle_state_and_is_replay_safe() -> None:
    class OldObjectDeleteFailureStorage(InMemoryObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self.fail_keys: set[str] = set()

        async def delete(self, object_key: str) -> None:
            if object_key in self.fail_keys:
                raise OSError("old object cleanup unavailable")
            await super().delete(object_key)

    storage = OldObjectDeleteFailureStorage()
    factory, _, clock, service, processor = _runtime(storage=storage)
    guest_session = await service.begin_guest_session()
    guest = await service.authenticate_guest(guest_session.capability_token)
    finalized = await _finalize_pdf(factory, storage, service, guest)
    context = ResumeRequestContext("request", "trace")
    user_id = uuid4()
    claim = ClaimGuestDocument(policy_version="privacy-v1", consent=True)

    with pytest.raises(ResumeStateConflict):
        await service.claim_guest_document(
            user_id, guest_session.capability_token, finalized.document_id, claim, context
        )
    await processor.process_job(finalized.job_id, "trace", execution_token=_invocation_token())
    with pytest.raises(ResumeStateConflict):
        await service.claim_guest_document(
            user_id, guest_session.capability_token, finalized.document_id, claim, context
        )
    analysis_job = await service.start_analysis(
        guest, finalized.document_id, "guest-analysis-ready", context
    )
    with pytest.raises(ResumeStateConflict):
        await service.claim_guest_document(
            user_id, guest_session.capability_token, finalized.document_id, claim, context
        )
    await processor.process_job(analysis_job.id, "trace", execution_token=_invocation_token())

    original_document_key = factory.state.documents[finalized.document_id].quarantine_object_key
    original_artifact_keys = {
        item.object_key
        for item in factory.state.artifacts.values()
        if item.document_id == finalized.document_id
    }
    storage.fail_keys = {original_document_key, *original_artifact_keys}
    claimed = await service.claim_guest_document(
        user_id, guest_session.capability_token, finalized.document_id, claim, context
    )
    replay = await service.claim_guest_document(
        user_id, guest_session.capability_token, finalized.document_id, claim, context
    )

    assert claimed == replay
    assert claimed.retention_expires_at is None
    assert claimed.status == DocumentStatus.READY
    assert original_document_key in storage.objects
    assert original_artifact_keys <= storage.objects.keys()
    assert factory.state.guests[guest_session.session_id].claimed_document_id == claimed.id
    source_cleanups = [
        item
        for item in factory.state.object_cleanups.values()
        if item.purpose == ObjectCleanupPurpose.CLAIM_SOURCE
    ]
    compensation_cleanups = [
        item
        for item in factory.state.object_cleanups.values()
        if item.purpose == ObjectCleanupPurpose.CLAIM_COMPENSATION
    ]
    assert source_cleanups and all(not item.terminal for item in source_cleanups)
    assert compensation_cleanups and all(
        item.cancelled_at is not None for item in compensation_cleanups
    )
    storage.fail_keys.clear()
    clock.value += timedelta(minutes=2)
    await ResumeMaintenance(unit_of_work=factory, clock=clock, storage=storage).cleanup_expired()
    assert all(item.completed_at is not None for item in source_cleanups)
    assert original_document_key not in storage.objects
    assert not (original_artifact_keys & storage.objects.keys())
    with pytest.raises(GuestCapabilityRejected):
        await service.claim_guest_document(
            uuid4(), guest_session.capability_token, claimed.id, claim, context
        )
    with pytest.raises(GuestCapabilityRejected):
        await service.claim_guest_document(
            user_id, guest_session.capability_token, uuid4(), claim, context
        )


@pytest.mark.asyncio
async def test_failed_claim_copy_is_compensated_by_precommitted_cleanup_tasks() -> None:
    class FailAfterCopyStorage(InMemoryObjectStorage):
        copy_calls = 0

        async def copy(self, source_key: str, destination_key: str) -> None:
            await super().copy(source_key, destination_key)
            self.copy_calls += 1
            if self.copy_calls == 2:
                raise OSError("copy unavailable")

    storage = FailAfterCopyStorage()
    factory, _, _, service, processor = _runtime(storage=storage)
    session = await service.begin_guest_session()
    guest = await service.authenticate_guest(session.capability_token)
    finalized = await _ready_pdf(factory, storage, service, processor, guest)
    context = ResumeRequestContext("request", "trace")
    analysis = await service.start_analysis(
        guest, finalized.document_id, "copy-failure-analysis", context
    )
    await processor.process_job(analysis.id, "trace", execution_token=_invocation_token())

    with pytest.raises(OSError, match="copy unavailable"):
        await service.claim_guest_document(
            uuid4(),
            session.capability_token,
            finalized.document_id,
            ClaimGuestDocument(policy_version="privacy-v1", consent=True),
            context,
        )

    cleanups = tuple(factory.state.object_cleanups.values())
    assert cleanups
    assert all(item.purpose == ObjectCleanupPurpose.CLAIM_COMPENSATION for item in cleanups)
    assert all(item.completed_at is not None for item in cleanups)
    assert not any(key.startswith("quarantine/user/") for key in storage.objects)
    assert factory.state.documents[finalized.document_id].owner == guest


@pytest.mark.asyncio
async def test_retention_skips_active_work_and_recovers_after_dead_letter() -> None:
    class ToggleDeleteFailureStorage(InMemoryObjectStorage):
        fail_quarantine = True

        async def delete(self, object_key: str) -> None:
            if self.fail_quarantine and object_key.startswith("quarantine/"):
                raise RetryableProcessingFailure("object_storage_unavailable")
            await super().delete(object_key)

    storage = ToggleDeleteFailureStorage()
    factory, _, clock, service, processor = _runtime(storage=storage)
    session = await service.begin_guest_session()
    guest = await service.authenticate_guest(session.capability_token)
    finalized = await _finalize_pdf(factory, storage, service, guest)
    clock.value += timedelta(days=2)
    maintenance = ResumeMaintenance(unit_of_work=factory, clock=clock, storage=storage)

    active_cleanup = await maintenance.cleanup_expired()
    assert active_cleanup.queued_guest_deletions == 0
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.QUARANTINED
    await processor.process_job(finalized.job_id, "trace", execution_token=_invocation_token())
    queued = await maintenance.cleanup_expired()
    assert queued.queued_guest_deletions == 1
    first_delete = next(
        item
        for item in factory.state.jobs.values()
        if item.kind == JobKind.DELETE and item.document_id == finalized.document_id
    )
    first_key = first_delete.idempotency_key
    outcomes = [
        await processor.process_job(
            first_delete.id, "trace", execution_token=f"retention-failure-{index}"
        )
        for index in range(3)
    ]
    assert outcomes[-1].status == JobStatus.DEAD_LETTERED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.FAILED

    storage.fail_quarantine = False
    replacement_cleanup = await maintenance.cleanup_expired()
    assert replacement_cleanup.queued_guest_deletions == 1
    replacement = next(
        item
        for item in factory.state.jobs.values()
        if item.kind == JobKind.DELETE and item.id != first_delete.id
    )
    assert replacement.idempotency_key != first_key
    assert (
        await processor.process_job(replacement.id, "trace", execution_token=_invocation_token())
    ).status == JobStatus.SUCCEEDED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.DELETED


@pytest.mark.asyncio
async def test_delete_jobs_cannot_be_cancelled_while_queued_or_running() -> None:
    class BlockingDeleteStorage(InMemoryObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self.block = False
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def delete(self, object_key: str) -> None:
            if self.block and not self.entered.is_set():
                self.entered.set()
                await self.release.wait()
            await super().delete(object_key)

    storage = BlockingDeleteStorage()
    factory, _, _, service, processor = _runtime(storage=storage)
    owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    document = await service.get_document(owner, finalized.document_id)
    context = ResumeRequestContext("request", "trace")
    deletion = await service.request_delete(
        owner, document.id, document.version, "delete-cannot-cancel", context
    )

    with pytest.raises(ResumeStateConflict):
        await service.cancel_job(owner, deletion.id, context)
    storage.block = True
    active = asyncio.create_task(
        processor.process_job(deletion.id, "trace", execution_token=_invocation_token())
    )
    await asyncio.wait_for(storage.entered.wait(), timeout=1)
    with pytest.raises(ResumeStateConflict):
        await service.cancel_job(owner, deletion.id, context)
    storage.release.set()
    assert (await active).status == JobStatus.SUCCEEDED
    assert factory.state.documents[document.id].status == DocumentStatus.DELETED


@pytest.mark.asyncio
async def test_analysis_pins_snapshot_exposes_audit_features_and_allows_cancelled_retry() -> None:
    factory, storage, _, service, processor = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    context = ResumeRequestContext("request", "trace")
    original = await service.get_canonical_resume(owner, finalized.document_id)
    analysis_job = await service.start_analysis(
        owner, finalized.document_id, "pinned-analysis-0001", context
    )
    assert original.resume.semantics is not None
    semantic_field = original.resume.semantics.entities[0].fields[0]
    corrected = await service.review_canonical_semantics(
        owner,
        finalized.document_id,
        original.revision,
        (CorrectSemanticField(semantic_field.id, semantic_field.value + " reviewed"),),
        context,
    )

    assert (
        await processor.process_job(analysis_job.id, "trace", execution_token=_invocation_token())
    ).status == JobStatus.SUCCEEDED
    analysis_id = factory.state.jobs[analysis_job.id].result_id
    assert analysis_id is not None
    report = await service.get_analysis(owner, analysis_id)
    assert report.snapshot_id == original.id
    assert report.snapshot_id != corrected.id
    assert report.feature_schema_version == "resume-health-features/2"
    assert report.feature_values["block_count"] >= 3
    for component in report.components:
        allocated = sum(
            item.contribution_basis_points
            for item in report.feature_contributions
            if item.component_code == component.code
        )
        assert allocated == component.score_basis_points

    corrected_job = await service.start_analysis(
        owner, finalized.document_id, "pinned-analysis-0002", context
    )
    cancelled = await service.cancel_job(owner, corrected_job.id, context)
    assert cancelled.status == JobStatus.CANCELLED
    assert (await service.get_document(owner, finalized.document_id)).status == DocumentStatus.READY
    replacement = await service.start_analysis(
        owner, finalized.document_id, "pinned-analysis-0003", context
    )
    assert replacement.id != corrected_job.id


@pytest.mark.asyncio
async def test_retryable_analysis_failure_keeps_document_ready_until_explicit_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, storage, _, service, processor = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    context = ResumeRequestContext("request", "trace")
    analysis_job = await service.start_analysis(
        owner, finalized.document_id, "failing-analysis-0001", context
    )

    def crash_scoring(_: object) -> object:
        raise RuntimeError("internal scoring detail")

    monkeypatch.setattr(
        "careeros.modules.resume_health.application.service.score_resume_health",
        crash_scoring,
    )
    failed = await processor.process_job(
        analysis_job.id, "trace", execution_token=_invocation_token()
    )

    assert failed.status == JobStatus.FAILED
    assert failed.retryable
    assert failed.safe_error_code == "processing_failed"
    document = await service.get_document(owner, finalized.document_id)
    assert document.status == DocumentStatus.READY
    assert document.safe_error_code is None
    with pytest.raises(ResumeStateConflict):
        await service.start_analysis(owner, finalized.document_id, "failing-analysis-0002", context)
    assert (await service.cancel_job(owner, analysis_job.id, context)).status == JobStatus.CANCELLED
    assert (
        await service.start_analysis(owner, finalized.document_id, "failing-analysis-0003", context)
    ).id != analysis_job.id


@pytest.mark.asyncio
async def test_canonical_correction_accepts_more_than_fifty_bounded_operations() -> None:
    lines = (
        ("heading", "Experience"),
        *(("bullet", f"Built fictional project {index} in 2025.") for index in range(60)),
    )
    offset = 0
    blocks: list[ExtractedBlock] = []
    for kind, text in lines:
        blocks.append(
            ExtractedBlock(
                kind=kind,
                text=text,
                confidence_basis_points=9_000,
                spans=(SourceSpanView(1, offset, offset + len(text)),),
            )
        )
        offset += len(text) + 1
    extraction = ExtractionResult(
        plain_text="\n".join(text for _, text in lines),
        reading_order=tuple(blocks),
        page_count=1,
        image_only=False,
        warnings=(),
        parser_version="fake/large",
    )
    factory, storage, _, service, processor = _runtime(
        extractor=FakeDocumentExtractor(extraction),
        semantic_parser=False,
    )
    owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    canonical = await service.get_canonical_resume(owner, finalized.document_id)
    canonical_blocks = tuple(
        block for section in canonical.resume.sections for block in section.blocks
    )
    assert len(canonical_blocks) == 60

    corrected = await service.correct_canonical_resume(
        owner,
        finalized.document_id,
        canonical.revision,
        tuple(
            CorrectionOperation(block.id, block.text + " reviewed") for block in canonical_blocks
        ),
        ResumeRequestContext("request", "trace"),
    )

    assert corrected.revision == 2
    assert all(
        block.text.endswith(" reviewed")
        for section in corrected.resume.sections
        for block in section.blocks
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("guest_owner", [False, True])
async def test_revision_and_analysis_history_caps_hold_for_account_and_guest(
    guest_owner: bool,
) -> None:
    policy = ResumeHealthPolicy(
        max_canonical_revisions=2,
        max_analysis_jobs_per_document=2,
    )
    factory, storage, _, service, processor = _runtime(
        policy=policy,
        semantic_parser=False,
    )
    if guest_owner:
        session = await service.begin_guest_session()
        owner = await service.authenticate_guest(session.capability_token)
    else:
        owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    canonical = await service.get_canonical_resume(owner, finalized.document_id)
    block = canonical.resume.sections[0].blocks[0]
    context = ResumeRequestContext("request", "trace")

    with pytest.raises(ResumeStateConflict):
        await service.correct_canonical_resume(
            owner,
            finalized.document_id,
            canonical.revision,
            (CorrectionOperation(block.id, block.text),),
            context,
        )
    revised = await service.correct_canonical_resume(
        owner,
        finalized.document_id,
        canonical.revision,
        (CorrectionOperation(block.id, block.text + " reviewed"),),
        context,
    )
    with pytest.raises(ResumeStateConflict):
        await service.correct_canonical_resume(
            owner,
            finalized.document_id,
            revised.revision,
            (CorrectionOperation(block.id, block.text + " changed again"),),
            context,
        )

    first = await service.start_analysis(
        owner, finalized.document_id, "bounded-analysis-0001", context
    )
    await service.cancel_job(owner, first.id, context)
    second = await service.start_analysis(
        owner, finalized.document_id, "bounded-analysis-0002", context
    )
    await service.cancel_job(owner, second.id, context)
    with pytest.raises(ResumeStateConflict):
        await service.start_analysis(owner, finalized.document_id, "bounded-analysis-0003", context)


@pytest.mark.asyncio
async def test_finalize_uses_public_idempotency_key_across_uploads_before_storage() -> None:
    factory, storage, _, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    first = await service.create_upload_intent(
        owner, CreateUploadIntent("first.pdf", ResumeMediaType.PDF, len(source))
    )
    second = await service.create_upload_intent(
        owner, CreateUploadIntent("second.pdf", ResumeMediaType.PDF, len(source))
    )
    storage.objects[factory.state.uploads[first.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    storage.objects[factory.state.uploads[second.id].staging_object_key] = (
        source,
        ResumeMediaType.PDF.value,
    )
    key = f"public-finalize-{uuid4().hex}"
    context = ResumeRequestContext("request", "trace")
    finalized = await service.finalize_upload(owner, first.id, key, context)
    replay = await service.finalize_upload(owner, first.id, key, context)

    assert replay == finalized
    with pytest.raises(IdempotencyConflict):
        await service.finalize_upload(owner, second.id, key, context)
    assert factory.state.uploads[second.id].status == UploadStatus.ISSUED
    assert factory.state.uploads[second.id].staging_object_key in storage.objects


@pytest.mark.asyncio
async def test_finalize_commit_ack_loss_reloads_committed_result_without_compensation() -> None:
    class AckLossFactory(InMemoryResumeUnitOfWorkFactory):
        armed = False

        def __call__(self) -> InMemoryResumeUnitOfWork:
            factory = self

            class AckLossUnitOfWork(InMemoryResumeUnitOfWork):
                async def commit(self) -> None:
                    await super().commit()
                    if factory.armed:
                        factory.armed = False
                        raise OSError("commit acknowledgement lost")

            return AckLossUnitOfWork(self.state)

    factory = AckLossFactory()
    storage = InMemoryObjectStorage()
    clock = FixedClock()
    service = ResumeHealthService(
        unit_of_work=factory,
        clock=clock,
        capabilities=HmacGuestCapabilityManager("a" * 32),
        storage=storage,
        limits=DocumentLimits(),
    )
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner, CreateUploadIntent("ack-loss.pdf", ResumeMediaType.PDF, len(source))
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (source, ResumeMediaType.PDF.value)
    factory.armed = True

    finalized = await service.finalize_upload(
        owner,
        intent.id,
        f"ack-loss-{uuid4().hex}",
        ResumeRequestContext("request", "trace"),
    )

    document = factory.state.documents[finalized.document_id]
    assert document.quarantine_object_key in storage.objects
    assert upload.staging_object_key in storage.objects
    assert len(factory.state.jobs) == 1
    assert len(factory.state.outbox) == 1


@pytest.mark.asyncio
async def test_copy_only_promotion_error_preserves_staging_for_safe_retry() -> None:
    class CopyAckLossStorage(InMemoryObjectStorage):
        fail = True

        async def promote(self, staging_key: str, quarantine_key: str) -> None:
            await super().promote(staging_key, quarantine_key)
            if self.fail:
                self.fail = False
                raise OSError("copy acknowledgement lost")

    storage = CopyAckLossStorage()
    factory, _, _, service, _ = _runtime(storage=storage)
    owner = OwnerScope(user_id=uuid4())
    source = b"%PDF-1.7\nfictional\n%%EOF"
    intent = await service.create_upload_intent(
        owner,
        CreateUploadIntent("copy-ack-loss.pdf", ResumeMediaType.PDF, len(source)),
    )
    upload = factory.state.uploads[intent.id]
    storage.objects[upload.staging_object_key] = (source, ResumeMediaType.PDF.value)
    key = f"copy-ack-loss-{uuid4().hex}"
    context = ResumeRequestContext("request", "trace")

    with pytest.raises(OSError, match="copy acknowledgement lost"):
        await service.finalize_upload(owner, intent.id, key, context)
    assert upload.staging_object_key in storage.objects
    assert not factory.state.documents
    assert not any(value.startswith("quarantine/") for value in storage.objects)

    retried = await service.finalize_upload(owner, intent.id, key, context)
    assert retried.document_id in factory.state.documents


@pytest.mark.asyncio
async def test_outbox_backoff_dead_letters_job_and_document_at_bound() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    message = next(
        item for item in factory.state.outbox.values() if item.job_id == finalized.job_id
    )
    message.max_attempts = 2
    publisher = FakeJobPublisher()
    publisher.fail = True
    dispatcher = OutboxDispatcher(unit_of_work=factory, publisher=publisher, clock=clock)

    first = await dispatcher.dispatch_pending()
    deferred = await dispatcher.dispatch_pending()
    clock.value = message.next_attempt_at
    terminal = await dispatcher.dispatch_pending()

    assert (first.failed, first.dead_lettered) == (1, 0)
    assert (deferred.failed, deferred.dead_lettered) == (0, 0)
    assert (terminal.failed, terminal.dead_lettered) == (1, 1)
    assert message.dead_lettered_at is not None
    assert factory.state.jobs[finalized.job_id].status == JobStatus.DEAD_LETTERED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.REJECTED
    assert any(
        getattr(item, "action", "") == "processing_job.publish_dead_lettered"
        for item in factory.state.audit
    )


@pytest.mark.asyncio
async def test_cleanup_poison_is_isolated_and_reported_while_other_owners_progress() -> None:
    class PoisonStorage(InMemoryObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self.poison: set[str] = set()

        async def delete(self, object_key: str) -> None:
            if object_key in self.poison:
                raise OSError("poison object")
            await super().delete(object_key)

    storage = PoisonStorage()
    factory, _, clock, service, _ = _runtime(storage=storage)
    first_session = await service.begin_guest_session()
    second_session = await service.begin_guest_session()
    first_owner = await service.authenticate_guest(first_session.capability_token)
    second_owner = await service.authenticate_guest(second_session.capability_token)
    command = CreateUploadIntent("fictional.pdf", ResumeMediaType.PDF, 10)
    first = await service.create_upload_intent(first_owner, command)
    second = await service.create_upload_intent(second_owner, command)
    first_upload = factory.state.uploads[first.id]
    second_upload = factory.state.uploads[second.id]
    storage.objects[first_upload.staging_object_key] = (b"first-data", ResumeMediaType.PDF.value)
    storage.objects[second_upload.staging_object_key] = (
        b"second-dat",
        ResumeMediaType.PDF.value,
    )
    storage.poison.add(first_upload.staging_object_key)
    clock.value += timedelta(days=2)

    result = await ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage
    ).cleanup_expired()

    assert result.expired_uploads == 2
    assert result.revoked_guest_sessions == 2
    assert result.object_cleanup_failures == 1
    assert result.object_cleanup_dead_letters == 0
    assert second_upload.staging_object_key not in storage.objects
    assert first_upload.staging_object_key in storage.objects
    storage.poison.clear()
    pending = next(
        item
        for item in factory.state.object_cleanups.values()
        if item.object_key == first_upload.staging_object_key and not item.terminal
    )
    clock.value = pending.not_before
    recovered = await ResumeMaintenance(
        unit_of_work=factory, clock=clock, storage=storage
    ).cleanup_expired()
    assert recovered.object_cleanups_completed >= 1
    assert first_upload.staging_object_key not in storage.objects


@pytest.mark.asyncio
async def test_minimal_failure_recorder_dead_letters_without_provider_assembly() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    recorder = ResumeJobFailureRecorder(unit_of_work=factory, clock=clock)

    outcome = await recorder.record_task_failure(
        finalized.job_id,
        "trace",
        "worker_runtime_unavailable",
        retryable=True,
        exhausted=True,
        execution_token=_invocation_token(),
    )

    assert outcome.status == JobStatus.DEAD_LETTERED
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.REJECTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit_kwargs", "extraction", "safe_code"),
    [
        (
            {"max_extracted_blocks": 2},
            ExtractionResult(
                plain_text="a\nb\nc",
                reading_order=tuple(
                    ExtractedBlock(
                        kind="paragraph",
                        text=value,
                        confidence_basis_points=9_000,
                        spans=(SourceSpanView(1, index * 2, index * 2 + 1),),
                    )
                    for index, value in enumerate(("a", "b", "c"))
                ),
                page_count=1,
                image_only=False,
                warnings=(),
                parser_version="fake/bounds",
            ),
            "extracted_block_limit_exceeded",
        ),
        (
            {"max_serialized_artifact_bytes": 200},
            _extraction(),
            "extracted_artifact_limit_exceeded",
        ),
    ],
)
async def test_processor_rejects_unreviewable_extraction_graphs_before_commit(
    limit_kwargs: dict[str, int],
    extraction: ExtractionResult,
    safe_code: str,
) -> None:
    limits = DocumentLimits(**limit_kwargs)
    factory, storage, _, service, processor = _runtime(
        extractor=FakeDocumentExtractor(extraction),
        limits=limits,
        semantic_parser=False,
    )
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)

    outcome = await processor.process_job(
        finalized.job_id, "trace", execution_token=_invocation_token()
    )

    assert outcome.status == JobStatus.FAILED
    assert outcome.safe_error_code == safe_code
    assert factory.state.documents[finalized.document_id].status == DocumentStatus.REJECTED
    assert not factory.state.snapshots
    assert not factory.state.artifacts


@pytest.mark.asyncio
async def test_correction_rejects_cumulative_canonical_text_growth() -> None:
    extraction = ExtractionResult(
        plain_text="first\nsecond",
        reading_order=(
            ExtractedBlock("paragraph", "first", 9_000, (SourceSpanView(1, 0, 5),)),
            ExtractedBlock("paragraph", "second", 9_000, (SourceSpanView(1, 6, 12),)),
        ),
        page_count=1,
        image_only=False,
        warnings=(),
        parser_version="fake/correction-bounds",
    )
    limits = DocumentLimits(
        max_extracted_characters=100,
        max_serialized_artifact_bytes=10_000,
    )
    factory, storage, _, service, processor = _runtime(
        extractor=FakeDocumentExtractor(extraction), limits=limits
    )
    owner = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    canonical = await service.get_canonical_resume(owner, finalized.document_id)
    blocks = tuple(block for section in canonical.resume.sections for block in section.blocks)

    with pytest.raises(ResumeStateConflict):
        await service.correct_canonical_resume(
            owner,
            finalized.document_id,
            canonical.revision,
            tuple(
                CorrectionOperation(block.id, character * 60)
                for block, character in zip(blocks, ("a", "b"), strict=True)
            ),
            ResumeRequestContext("request", "trace"),
        )


@pytest.mark.asyncio
async def test_reconciler_requeues_stale_published_queued_job_once() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    dispatcher = OutboxDispatcher(
        unit_of_work=factory,
        publisher=FakeJobPublisher(),
        clock=clock,
    )
    assert (await dispatcher.dispatch_pending()).published == 1
    clock.value += timedelta(seconds=301)
    reconciler = ResumeJobReconciler(
        unit_of_work=factory,
        clock=clock,
        stale_after_seconds=300,
    )

    result = await reconciler.reconcile_stale()
    duplicate = await reconciler.reconcile_stale()

    assert result.requeued == 1
    assert result.dead_lettered == 0
    assert duplicate.requeued == 0
    job = factory.state.jobs[finalized.job_id]
    assert job.recovery_attempts == 1
    messages = sorted(
        (message for message in factory.state.outbox.values() if message.job_id == job.id),
        key=lambda message: message.generation,
    )
    assert [message.generation for message in messages] == [0, 1]
    assert messages[0].published_at is not None
    assert not messages[1].terminal


@pytest.mark.asyncio
async def test_reconciler_requeues_retryable_failure_and_expired_running_lease() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    failed = await _finalize_pdf(factory, storage, service, owner)
    running = await _finalize_pdf(factory, storage, service, owner)
    dispatcher = OutboxDispatcher(
        unit_of_work=factory,
        publisher=FakeJobPublisher(),
        clock=clock,
    )
    assert (await dispatcher.dispatch_pending()).published == 2
    recorder = ResumeJobFailureRecorder(unit_of_work=factory, clock=clock)
    failed_outcome = await recorder.record_task_failure(
        failed.job_id,
        "trace",
        "provider_temporarily_unavailable",
        retryable=True,
        exhausted=False,
        execution_token=_invocation_token(),
    )
    assert failed_outcome.status == JobStatus.FAILED
    running_job = factory.state.jobs[running.job_id]
    running_job.start(clock.value)
    running_job.acquire_execution_lease(
        b"e" * 32,
        clock.value + timedelta(seconds=1),
        clock.value,
    )
    factory.state.documents[running.document_id].status = DocumentStatus.PROCESSING
    clock.value += timedelta(seconds=301)

    result = await ResumeJobReconciler(
        unit_of_work=factory,
        clock=clock,
        stale_after_seconds=300,
    ).reconcile_stale()

    assert result.requeued == 2
    assert result.dead_lettered == 0
    assert factory.state.jobs[failed.job_id].recovery_attempts == 1
    recovered_running_job = factory.state.jobs[running.job_id]
    assert recovered_running_job.recovery_attempts == 1
    assert recovered_running_job.status == JobStatus.FAILED
    assert recovered_running_job.execution_token_hash is None
    assert recovered_running_job.lease_expires_at is None
    assert recovered_running_job.safe_error_code == "execution_lease_expired"
    assert factory.state.documents[running.document_id].status == DocumentStatus.QUARANTINED
    assert {
        message.job_id
        for message in factory.state.outbox.values()
        if message.generation == 1 and not message.terminal
    } == {failed.job_id, running.job_id}


@pytest.mark.asyncio
async def test_reconciler_dead_letters_after_bounded_recovery_attempts() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    assert (
        await OutboxDispatcher(
            unit_of_work=factory,
            publisher=FakeJobPublisher(),
            clock=clock,
        ).dispatch_pending()
    ).published == 1
    job = factory.state.jobs[finalized.job_id]
    job.recovery_attempts = job.max_recovery_attempts
    clock.value += timedelta(seconds=301)

    result = await ResumeJobReconciler(
        unit_of_work=factory,
        clock=clock,
        stale_after_seconds=300,
    ).reconcile_stale()

    assert result.requeued == 0
    assert result.dead_lettered == 1
    assert job.status == JobStatus.DEAD_LETTERED
    assert job.safe_error_code == "job_recovery_exhausted"
    document = factory.state.documents[finalized.document_id]
    assert document.status == DocumentStatus.REJECTED
    assert document.safe_error_code == "job_recovery_exhausted"


@pytest.mark.asyncio
async def test_reconciler_does_not_redeliver_expired_final_processing_attempt() -> None:
    factory, storage, clock, service, _ = _runtime()
    owner = OwnerScope(user_id=uuid4())
    finalized = await _finalize_pdf(factory, storage, service, owner)
    assert (
        await OutboxDispatcher(
            unit_of_work=factory,
            publisher=FakeJobPublisher(),
            clock=clock,
        ).dispatch_pending()
    ).published == 1
    job = factory.state.jobs[finalized.job_id]
    job.max_attempts = 1
    job.start(clock.value)
    job.acquire_execution_lease(
        b"x" * 32,
        clock.value + timedelta(seconds=1),
        clock.value,
    )
    factory.state.documents[finalized.document_id].status = DocumentStatus.PROCESSING
    clock.value += timedelta(seconds=301)

    result = await ResumeJobReconciler(
        unit_of_work=factory,
        clock=clock,
        stale_after_seconds=300,
    ).reconcile_stale()

    assert result.requeued == 0
    assert result.dead_lettered == 1
    assert job.status == JobStatus.DEAD_LETTERED
    assert job.attempts == job.max_attempts
    assert job.execution_token_hash is None
    assert job.lease_expires_at is None
    assert not any(
        message.job_id == job.id and message.generation > 0
        for message in factory.state.outbox.values()
    )


@pytest.mark.asyncio
async def test_semantic_review_creates_owned_immutable_successor_snapshot() -> None:
    factory, storage, _, service, processor = _runtime()
    owner = OwnerScope(user_id=uuid4())
    other = OwnerScope(user_id=uuid4())
    finalized = await _ready_pdf(factory, storage, service, processor, owner)
    current = await service.get_canonical_resume(owner, finalized.document_id)
    assert current.resume.semantics is not None
    assert current.resume.source_sections == current.resume.sections
    source_sections = current.resume.source_sections
    field = next(
        field
        for entity in current.resume.semantics.entities
        for field in entity.fields
        if field.name == "achievement"
    )

    reviewed = await service.review_canonical_semantics(
        owner,
        finalized.document_id,
        current.revision,
        (CorrectSemanticField(field.id, "Verified fictional achievement."),),
        ResumeRequestContext("request", "trace"),
    )

    assert reviewed.revision == current.revision + 1
    assert reviewed.based_on_snapshot_id == current.id
    assert reviewed.resume.source_sections == source_sections
    assert reviewed.resume.semantics is not None
    assert current.resume.semantics.entities != reviewed.resume.semantics.entities
    revised = next(
        candidate
        for entity in reviewed.resume.semantics.entities
        for candidate in entity.fields
        if candidate.id == field.id
    )
    assert revised.value == "Verified fictional achievement."
    assert revised.anchors == field.anchors
    with pytest.raises(ResumeStateConflict):
        await service.correct_canonical_resume(
            owner,
            finalized.document_id,
            reviewed.revision,
            (
                CorrectionOperation(
                    reviewed.resume.sections[0].blocks[0].id,
                    "Legacy whole-block edits cannot modify typed snapshots.",
                ),
            ),
            ResumeRequestContext("request", "trace"),
        )
    with pytest.raises(ResumeResourceNotFound):
        await service.review_canonical_semantics(
            other,
            finalized.document_id,
            reviewed.revision,
            (),
            ResumeRequestContext("request", "trace"),
            confirm_no_changes=True,
        )
