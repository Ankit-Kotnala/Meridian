"""PostgreSQL ownership, grounding, quota-lock, and deletion coverage for Phase 8."""

from __future__ import annotations

import hashlib
import os
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.application_workspace.application import (
    ApplicationJobSnapshot,
    ApplicationSourceEvidenceReference,
    ApplicationWorkspaceService,
    CreateApplication,
    CreateApplicationTask,
    GenerateApplicationPack,
    RequestContext,
    UpdateApplication,
)
from careeros.modules.application_workspace.domain import (
    ApplicationEvidencePin,
    ApplicationRequirementSnapshot,
    ApplicationStage,
    ApplicationWorkspaceNotFound,
)
from careeros.modules.application_workspace.infrastructure import (
    ResumeBuilderVersionSnapshotProvider,
    SqlAlchemyApplicationWorkspaceUnitOfWorkFactory,
)
from careeros.modules.application_workspace.infrastructure.models import (
    ApplicationAuditEventModel,
    ApplicationDocumentModel,
    ApplicationEventModel,
    ApplicationPackModel,
    ApplicationRecordModel,
    ApplicationTaskModel,
)
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.resume_builder.application import (
    CreateResume,
    ResumeBuilderPolicy,
    ResumeBuilderService,
)
from careeros.modules.resume_builder.application import (
    RequestContext as ResumeRequestContext,
)
from careeros.modules.resume_builder.domain import ResumeTemplate
from careeros.modules.resume_builder.infrastructure.repository import (
    SqlAlchemyResumeBuilderUnitOfWorkFactory,
)
from resume_builder_memory import (
    EVIDENCE_ID,
    SKILL_EVIDENCE_ID,
    FixedClock,
    MemoryStorage,
    PlainTextExtractor,
    StaticResumeSourceProvider,
    TextOnlyRenderer,
)


class _RandomIdentifiers:
    def new(self) -> UUID:
        return uuid4()


class _JobProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        job_id: UUID,
    ) -> ApplicationJobSnapshot:
        _ = owner_user_id
        requirement = ApplicationRequirementSnapshot(
            id=uuid4(),
            requirement_type="responsibility",
            importance="mandatory",
            text="Lead product discovery and delivery.",
            source_start=0,
            source_end=36,
        )
        return ApplicationJobSnapshot(
            job_id=job_id,
            version=2,
            title="Principal Product Lead",
            company="Example Co",
            location="Remote",
            application_deadline=date(2026, 8, 30),
            latest_analysis_id=None,
            source_sha256="a" * 64,
            source="referral",
            industry="software",
            requirements=(requirement,),
            requirement_support=(),
        )


class _EvidenceProvider:
    async def snapshot(
        self,
        owner_user_id: UUID,
        references: tuple[ApplicationSourceEvidenceReference, ...],
    ) -> tuple[ApplicationEvidencePin, ...]:
        _ = owner_user_id
        statements = {
            EVIDENCE_ID: "Confirmed product discovery work across customer interviews.",
            SKILL_EVIDENCE_ID: "Applied product discovery methods.",
        }
        unique_references = {reference.evidence_id: reference for reference in references}
        return tuple(
            ApplicationEvidencePin(
                evidence_id=reference.evidence_id,
                evidence_revision_id=reference.evidence_revision_id,
                revision_number=reference.revision_number,
                statement=statements[reference.evidence_id],
                statement_sha256=hashlib.sha256(
                    statements[reference.evidence_id].encode("utf-8")
                ).hexdigest(),
                strength="confirmed",
                has_numeric_claim=False,
            )
            for reference in unique_references.values()
        )


def _user(user_id: UUID, email: str) -> UserModel:
    now = FixedClock().now()
    return UserModel(
        id=user_id,
        email_normalized=email,
        password_hash=None,
        status="active",
        email_verified_at=None,
        auth_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_application_aggregate_is_owner_scoped_and_hard_deleted() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    owner_id = uuid4()
    other_id = uuid4()
    job_id = uuid4()
    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    resume_service = ResumeBuilderService(
        unit_of_work=SqlAlchemyResumeBuilderUnitOfWorkFactory(database),
        clock=FixedClock(),
        identifiers=_RandomIdentifiers(),
        sources=StaticResumeSourceProvider(),
        renderer=TextOnlyRenderer(),
        extractor=PlainTextExtractor(),
        storage=MemoryStorage(),
        policy=ResumeBuilderPolicy(),
    )
    workspace_factory = SqlAlchemyApplicationWorkspaceUnitOfWorkFactory(database)
    service = ApplicationWorkspaceService(
        unit_of_work=workspace_factory,
        clock=FixedClock(),
        identifiers=_RandomIdentifiers(),
        jobs=_JobProvider(),
        resumes=ResumeBuilderVersionSnapshotProvider(resume_service),
        evidence=_EvidenceProvider(),
    )
    context = RequestContext(owner_id, "phase8-integration", "8" * 32)
    try:
        async with database.session() as session:
            session.add_all(
                [
                    _user(owner_id, f"{owner_id}@example.test"),
                    _user(other_id, f"{other_id}@example.test"),
                ]
            )
            await session.commit()
        resume = await resume_service.create_resume(
            owner_id,
            CreateResume(
                title="Product leadership resume",
                target_role="Principal Product Lead",
                template=ResumeTemplate.EXECUTIVE,
            ),
            idempotency_key=f"resume-{uuid4().hex}",
            context=ResumeRequestContext(owner_id, "resume-integration", "7" * 32),
        )
        application_key = f"application-{uuid4().hex}"
        created = await service.create_application(
            owner_id,
            CreateApplication(
                job_id=job_id,
                resume_version_id=resume.current_version.id,
            ),
            idempotency_key=application_key,
            context=context,
        )
        replay = await service.create_application(
            owner_id,
            CreateApplication(
                job_id=job_id,
                resume_version_id=resume.current_version.id,
            ),
            idempotency_key=application_key,
            context=context,
        )
        assert replay.application.id == created.application.id
        await service.create_task(
            owner_id,
            created.application.id,
            CreateApplicationTask(title="Review application pack"),
            idempotency_key=f"task-{uuid4().hex}",
            context=context,
        )
        generated = await service.generate_pack(
            owner_id,
            created.application.id,
            GenerateApplicationPack(include_kinds=("cover_letter",)),
            idempotency_key=f"pack-{uuid4().hex}",
            context=context,
        )
        assert generated.pack.evidence_revision_ids
        replacement_version = await resume_service.create_version(
            owner_id,
            resume.resume.id,
            expected_version=resume.resume.version,
            idempotency_key=f"resume-version-{uuid4().hex}",
            context=ResumeRequestContext(owner_id, "resume-integration", "7" * 32),
        )
        resume_changed = await service.update_application(
            owner_id,
            created.application.id,
            UpdateApplication(
                resume_version_id=replacement_version.id,
                resume_change_reason="Use the reviewed checkpoint for this application.",
            ),
            expected_version=created.application.version,
            context=context,
        )
        applied = await service.update_application(
            owner_id,
            created.application.id,
            UpdateApplication(stage=ApplicationStage.APPLIED),
            expected_version=resume_changed.application.version,
            context=context,
        )
        interview = await service.update_application(
            owner_id,
            created.application.id,
            UpdateApplication(stage=ApplicationStage.INTERVIEW),
            expected_version=applied.application.version,
            context=context,
        )
        analytics = await service.list_analytics_snapshots(owner_id)
        assert analytics[0].first_applied_at is not None
        assert analytics[0].first_response_at is not None
        assert analytics[0].first_interview_at is not None
        with pytest.raises(ApplicationWorkspaceNotFound):
            await service.get_application(other_id, created.application.id)

        async with workspace_factory() as uow:
            summary = await uow.get_application_summary(
                owner_id,
                created.application.id,
            )
            assert summary is not None
            assert summary.task_count == 1
            assert summary.pack_count == 1
            assert summary.event_count >= 5
            assert await uow.count_manual_events(owner_id, created.application.id) == 0

            task_page = await uow.list_tasks(
                owner_id,
                created.application.id,
                None,
                2,
            )
            pack_page = await uow.list_packs(
                owner_id,
                created.application.id,
                None,
                2,
            )
            first_events = await uow.list_events(
                owner_id,
                created.application.id,
                None,
                None,
                2,
            )
            later_events = await uow.list_events(
                owner_id,
                created.application.id,
                first_events[-1].occurred_at,
                first_events[-1].id,
                2,
            )

            assert len(task_page) == 1
            assert len(pack_page) == 1
            assert not hasattr(pack_page[0], "documents")
            assert len(first_events) == 2
            assert {event.id for event in first_events}.isdisjoint(
                event.id for event in later_events
            )
            assert any(
                event.event_kind.value == "resume_version_changed"
                for event in (*first_events, *later_events)
            )
            assert await uow.get_application_summary(other_id, created.application.id) is None
            assert (
                await uow.list_tasks(
                    other_id,
                    created.application.id,
                    None,
                    2,
                )
                == []
            )

        async with database.session() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(ApplicationRecordModel)
                    .where(
                        ApplicationRecordModel.owner_user_id == owner_id,
                        ApplicationRecordModel.id == created.application.id,
                    )
                    .values(stage="offer", outcome_status="none")
                )
                await session.commit()
            await session.rollback()

        async with database.session() as session:
            resume_change_events = await session.scalar(
                select(func.count())
                .select_from(ApplicationEventModel)
                .where(
                    ApplicationEventModel.owner_user_id == owner_id,
                    ApplicationEventModel.application_id == created.application.id,
                    ApplicationEventModel.event_kind == "resume_version_changed",
                )
            )
            resume_change_audits = await session.scalar(
                select(func.count())
                .select_from(ApplicationAuditEventModel)
                .where(
                    ApplicationAuditEventModel.owner_user_id == owner_id,
                    ApplicationAuditEventModel.target_id == created.application.id,
                    ApplicationAuditEventModel.action == "resume_version_changed",
                )
            )
            assert resume_change_events == 1
            assert resume_change_audits == 1

        await service.delete_application(
            owner_id,
            created.application.id,
            expected_version=interview.application.version,
            context=context,
        )
        with pytest.raises(ApplicationWorkspaceNotFound):
            await service.get_application(owner_id, created.application.id)

        async with database.session() as session:
            for model in (
                ApplicationRecordModel,
                ApplicationTaskModel,
                ApplicationEventModel,
                ApplicationPackModel,
                ApplicationDocumentModel,
            ):
                count = await session.scalar(
                    select(func.count()).select_from(model).where(model.owner_user_id == owner_id)
                )
                assert count == 0
            deletion_audits = await session.scalar(
                select(func.count())
                .select_from(ApplicationAuditEventModel)
                .where(
                    ApplicationAuditEventModel.owner_user_id == owner_id,
                    ApplicationAuditEventModel.action == "application_deleted",
                )
            )
            assert deletion_audits == 1
    finally:
        async with database.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
            await session.commit()
        await database.dispose()
