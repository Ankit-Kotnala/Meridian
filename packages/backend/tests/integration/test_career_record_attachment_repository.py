"""PostgreSQL integration coverage for the private evidence attachment workflow."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from career_record_attachment_memory import (
    FakeAttachmentStorage,
    FakeClock,
    FakeExtractor,
    FakePublisher,
    FakeScanner,
    SequentialIds,
    SequentialTokens,
)
from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.career_record.application.attachment_workflow import (
    PROCESS_EVIDENCE_ATTACHMENT_TASK,
    AdmitAttachment,
    AttachmentCleanupProcessor,
    AttachmentDownloadPurpose,
    AttachmentLimits,
    AttachmentNotFound,
    AttachmentOutboxDispatcher,
    AttachmentProcessor,
    AttachmentRequestContext,
    AttachmentStatus,
    AttachmentWorkflowService,
)
from careeros.modules.career_record.infrastructure.attachment_repository import (
    SqlAlchemyAttachmentUnitOfWorkFactory,
)
from careeros.modules.career_record.infrastructure.models import (
    EvidenceAttachmentAuditEventModel,
    EvidenceAttachmentModel,
    EvidenceItemModel,
)
from careeros.modules.identity.infrastructure.models import UserModel

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"


@pytest.mark.asyncio
async def test_attachment_workflow_round_trips_owner_scope_outbox_and_tombstone(
    tmp_path: Path,
) -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyAttachmentUnitOfWorkFactory(database)
    owner_user_id, other_user_id, evidence_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    storage = FakeAttachmentStorage()
    clock = FakeClock()
    ids = SequentialIds()
    limits = AttachmentLimits(temp_root=tmp_path.resolve())
    workflow = AttachmentWorkflowService(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        limits=limits,
        ids=ids,
        tokens=SequentialTokens(),
    )
    processor = AttachmentProcessor(
        unit_of_work=factory,
        clock=clock,
        storage=storage,
        scanner=FakeScanner(),
        extractor=FakeExtractor(),
        limits=limits,
        ids=ids,
    )
    publisher = FakePublisher()
    dispatcher = AttachmentOutboxDispatcher(
        unit_of_work=factory,
        publisher=publisher,
        clock=clock,
        ids=ids,
    )
    cleanup = AttachmentCleanupProcessor(
        unit_of_work=factory,
        storage=storage,
        clock=clock,
        ids=ids,
    )
    context = AttachmentRequestContext(owner_user_id, "attachment-integration", "a" * 32)

    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=user_id,
                        email_normalized=f"attachment-{user_id.hex}@example.com",
                        password_hash=None,
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    for user_id in (owner_user_id, other_user_id)
                ]
            )
            await session.flush()
            session.add(
                EvidenceItemModel(
                    id=evidence_id,
                    owner_user_id=owner_user_id,
                    lifecycle="active",
                    current_revision=1,
                    version=1,
                    created_at=now,
                    updated_at=now,
                    archived_at=None,
                    deleted_at=None,
                )
            )
            await session.commit()

        admitted = await workflow.admit(
            owner_user_id,
            AdmitAttachment(
                evidence_id=evidence_id,
                display_filename="private-support.pdf",
                media_type="application/pdf",
                expected_size=len(PDF),
            ),
            context,
        )
        storage.upload_latest(PDF)
        with pytest.raises(AttachmentNotFound):
            await workflow.get(
                other_user_id,
                admitted.attachment_id,
                AttachmentRequestContext(other_user_id, "cross-owner", "b" * 32),
            )

        finalized = await workflow.finalize(
            owner_user_id, admitted.attachment_id, "attachment-finalize-integration", context
        )
        replay = await workflow.finalize(
            owner_user_id, admitted.attachment_id, "attachment-finalize-integration", context
        )
        assert replay == finalized
        dispatched = await dispatcher.dispatch_pending()
        assert dispatched.published == 1
        assert publisher.calls == [(PROCESS_EVIDENCE_ATTACHMENT_TASK, finalized.job_id, "a" * 32)]

        outcome = await processor.process_job(finalized.job_id, "integration-worker-token")
        assert outcome.status.value == "succeeded"
        view = await workflow.get(owner_user_id, admitted.attachment_id, context)
        assert view.status is AttachmentStatus.CLEAN
        assert view.content_sha256 is not None
        grant = await workflow.download(
            owner_user_id,
            admitted.attachment_id,
            AttachmentDownloadPurpose.OWNER_EVIDENCE_REVIEW,
            context,
        )
        assert grant.operation.method == "GET"

        deleting = await workflow.delete(owner_user_id, admitted.attachment_id, context)
        assert deleting.status is AttachmentStatus.DELETING
        cleaned = await cleanup.process_due()
        assert cleaned.completed == 2
        with pytest.raises(AttachmentNotFound):
            await workflow.get(owner_user_id, admitted.attachment_id, context)

        async with database.session() as session:
            tombstone = await session.scalar(
                select(EvidenceAttachmentModel).where(
                    EvidenceAttachmentModel.id == admitted.attachment_id,
                    EvidenceAttachmentModel.owner_user_id == owner_user_id,
                )
            )
            assert tombstone is not None
            assert tombstone.workflow_status == "deleted"
            assert tombstone.display_filename is None
            assert tombstone.media_type is None
            assert tombstone.size_bytes is None
            audits = (
                await session.scalars(
                    select(EvidenceAttachmentAuditEventModel).where(
                        EvidenceAttachmentAuditEventModel.owner_user_id == owner_user_id,
                        EvidenceAttachmentAuditEventModel.attachment_id == admitted.attachment_id,
                    )
                )
            ).all()
            assert audits
            assert "private-support.pdf" not in repr(
                [(audit.action, audit.safe_details) for audit in audits]
            )
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_user_id, other_user_id)))
            )
            await session.commit()
        await database.dispose()
