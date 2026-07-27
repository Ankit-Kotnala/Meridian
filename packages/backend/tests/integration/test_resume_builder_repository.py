"""PostgreSQL integration coverage for resume builder persistence and ownership."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import delete, select

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.resume_builder.application import (
    CreateResume,
    ExportResume,
    RequestContext,
    ResumeBuilderPolicy,
    ResumeBuilderService,
    ResumeExportCleanupProcessor,
    ResumeExportProcessor,
)
from careeros.modules.resume_builder.domain import (
    ResumeBuilderNotFound,
    ResumeFormat,
    ResumeTemplate,
)
from careeros.modules.resume_builder.infrastructure.models import (
    ResumeBuilderAuditEventModel,
    ResumeExportModel,
    ResumeExportObjectCleanupModel,
    ResumeExportOutboxModel,
    ResumeModel,
    ResumeVerificationReportModel,
)
from careeros.modules.resume_builder.infrastructure.repository import (
    SqlAlchemyResumeBuilderUnitOfWorkFactory,
)
from resume_builder_memory import (
    OTHER_ID,
    OWNER_ID,
    FixedClock,
    MemoryStorage,
    PlainTextExtractor,
    StaticResumeSourceProvider,
    TextOnlyRenderer,
    UuidFactory,
)


def _context(owner_id) -> RequestContext:
    return RequestContext(owner_id, f"integration-{owner_id.hex[:8]}", "7" * 32)


@pytest.mark.asyncio
async def test_repository_persists_resume_export_and_denies_cross_user_access() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    storage = MemoryStorage()
    service = ResumeBuilderService(
        unit_of_work=SqlAlchemyResumeBuilderUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=UuidFactory(),
        sources=StaticResumeSourceProvider(),
        storage=storage,
        policy=ResumeBuilderPolicy(),
    )
    try:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([OWNER_ID, OTHER_ID])))
            session.add_all(
                [
                    UserModel(
                        id=OWNER_ID,
                        email_normalized="resume-builder-owner@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                    UserModel(
                        id=OTHER_ID,
                        email_normalized="resume-builder-other@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=None,
                        auth_version=1,
                        created_at=FixedClock().now(),
                        updated_at=FixedClock().now(),
                    ),
                ]
            )
            await session.commit()

        created = await service.create_resume(
            OWNER_ID,
            CreateResume(
                title="Integration Resume",
                target_role="Product Lead",
                template=ResumeTemplate.EXECUTIVE,
            ),
            idempotency_key="integration-resume-create",
            context=_context(OWNER_ID),
        )
        exported = await service.export_version(
            OWNER_ID,
            created.current_version.id,
            ExportResume(format=ResumeFormat.TEXT),
            idempotency_key="integration-resume-export",
            context=_context(OWNER_ID),
        )
        processor = ResumeExportProcessor(
            unit_of_work=SqlAlchemyResumeBuilderUnitOfWorkFactory(database),
            clock=FixedClock(),
            identifiers=UuidFactory(),
            renderer=TextOnlyRenderer(),
            extractor=PlainTextExtractor(),
            storage=storage,
        )
        outcome = await processor.process(exported.export.id, "integration-worker-token")
        assert outcome.status.value == "verified"
        intent = await service.create_download_intent(
            OWNER_ID,
            exported.export.id,
            idempotency_key="integration-resume-download",
            context=_context(OWNER_ID),
        )
        assert "resume-exports" in intent.url
        with pytest.raises(ResumeBuilderNotFound):
            await service.get_export(OTHER_ID, exported.export.id)
        deletion = await service.delete_export(
            OWNER_ID,
            exported.export.id,
            idempotency_key="integration-resume-delete",
            context=_context(OWNER_ID),
        )
        assert deletion.export.status.value == "deletion_pending"
        cleanup = ResumeExportCleanupProcessor(
            unit_of_work=SqlAlchemyResumeBuilderUnitOfWorkFactory(database),
            clock=FixedClock(),
            identifiers=UuidFactory(),
            storage=storage,
        )
        cleanup_outcome = await cleanup.process(
            exported.export.id,
            "integration-cleanup-token",
        )
        assert cleanup_outcome.status.value == "deleted"

        async with database.session() as session:
            persisted = await session.scalar(
                select(ResumeModel).where(ResumeModel.id == created.resume.id)
            )
            assert persisted is not None
            assert persisted.owner_user_id == OWNER_ID
            export = await session.scalar(
                select(ResumeExportModel).where(ResumeExportModel.id == exported.export.id)
            )
            assert export is not None
            assert export.object_key is None
            assert export.deleted_at is not None
            outboxes = tuple(
                await session.scalars(
                    select(ResumeExportOutboxModel).where(
                        ResumeExportOutboxModel.export_id == exported.export.id
                    )
                )
            )
            assert {outbox.operation for outbox in outboxes} == {"delete", "render"}
            assert all(outbox.trace_id == _context(OWNER_ID).trace_id for outbox in outboxes)
            candidate_cleanups = tuple(
                await session.scalars(
                    select(ResumeExportObjectCleanupModel).where(
                        ResumeExportObjectCleanupModel.export_id == exported.export.id
                    )
                )
            )
            assert len(candidate_cleanups) == 1
            assert candidate_cleanups[0].cancelled_at is not None
            assert candidate_cleanups[0].completed_at is None
            verification = await session.scalar(
                select(ResumeVerificationReportModel).where(
                    ResumeVerificationReportModel.export_id == exported.export.id
                )
            )
            assert verification is not None
            assert verification.status == "passed"
            audits = tuple(
                await session.scalars(
                    select(ResumeBuilderAuditEventModel).where(
                        ResumeBuilderAuditEventModel.owner_user_id == OWNER_ID,
                        ResumeBuilderAuditEventModel.target_id == exported.export.id,
                    )
                )
            )
            assert {audit.action for audit in audits} >= {
                "export_deletion_requested",
                "export_deleted",
                "export_requested",
                "export_verified",
            }
            assert all(
                "Confirmed product discovery" not in repr(audit.metadata_) for audit in audits
            )
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([OWNER_ID, OTHER_ID])))
            await session.commit()
        await database.dispose()
