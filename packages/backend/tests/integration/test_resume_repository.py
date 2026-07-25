"""PostgreSQL ownership, state, audit, and optimistic snapshot integration tests."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.resume_health.domain import (
    AnalysisStatus,
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    CanonicalSemantics,
    CanonicalSnapshot,
    DocumentStatus,
    FeatureContribution,
    FindingSeverity,
    GuestSession,
    JobKind,
    JobStatus,
    MalwareStatus,
    OutboxMessage,
    OwnerScope,
    ProcessingJob,
    ProcessingStage,
    ResumeFinding,
    ResumeHealthAnalysis,
    ResumeMediaType,
    ScoreComponent,
    SectionKind,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    SemanticSourceAnchor,
    SourceDocument,
    SourceSpan,
    UploadIntent,
    UploadStatus,
)
from careeros.modules.resume_health.infrastructure.models import GuestResumeSessionModel
from careeros.modules.resume_health.infrastructure.repository import (
    SqlAlchemyResumeUnitOfWorkFactory,
)


@pytest.mark.asyncio
async def test_repository_scopes_every_resource_and_persists_job_state() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyResumeUnitOfWorkFactory(database)
    first_user = uuid4()
    second_user = uuid4()
    guest_id = uuid4()
    now = datetime.now(UTC)
    try:
        async with database.session() as session:
            session.add_all(
                [
                    UserModel(
                        id=user_id,
                        email_normalized=f"resume-{user_id}@example.test",
                        password_hash=None,
                        status="active",
                        email_verified_at=now,
                        auth_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    for user_id in (first_user, second_user)
                ]
            )
            await session.commit()

        first_scope = OwnerScope(user_id=first_user)
        upload = UploadIntent(
            id=uuid4(),
            owner=first_scope,
            display_filename="fictional.pdf",
            expected_media_type=ResumeMediaType.PDF,
            expected_size=1_024,
            staging_object_key=f"staging/user/{first_user}/{uuid4().hex}",
            status=UploadStatus.ISSUED,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        document = SourceDocument(
            id=uuid4(),
            upload_id=upload.id,
            owner=first_scope,
            display_filename="fictional.pdf",
            media_type=ResumeMediaType.PDF,
            size_bytes=1_024,
            quarantine_object_key=f"quarantine/user/{first_user}/{uuid4().hex}",
            status=DocumentStatus.QUARANTINED,
            malware_status=MalwareStatus.PENDING,
            created_at=now,
            updated_at=now,
            retention_expires_at=None,
        )
        job = ProcessingJob(
            id=uuid4(),
            document_id=document.id,
            owner=first_scope,
            kind=JobKind.PARSE,
            idempotency_key=f"integration-{uuid4()}",
            request_hash=b"r" * 32,
            trace_id="integration-trace",
            status=JobStatus.QUEUED,
            stage=ProcessingStage.QUEUED,
            progress=None,
            attempts=0,
            max_attempts=3,
            created_at=now,
            updated_at=now,
        )
        outbox = OutboxMessage(
            id=uuid4(),
            job_id=job.id,
            task_name="resume_health.process",
            trace_id=job.trace_id,
            created_at=now - timedelta(minutes=10),
            next_attempt_at=now - timedelta(minutes=10),
            published_at=now - timedelta(minutes=10),
            attempts=1,
        )
        async with factory() as uow:
            await uow.add_upload(upload)
            await uow.add_document(document)
            upload.status = UploadStatus.FINALIZED
            upload.finalized_document_id = document.id
            await uow.save_upload(upload)
            await uow.add_job(job)
            await uow.add_outbox(outbox)
            await uow.commit()

        async with factory() as uow:
            assert await uow.get_document(first_scope, document.id) is not None
            assert await uow.get_document(OwnerScope(user_id=second_user), document.id) is None
            assert await uow.get_job(OwnerScope(user_id=second_user), job.id) is None
            reconcilable = await uow.list_reconcilable_jobs(
                now,
                now - timedelta(minutes=5),
                10,
            )
            assert [item.id for item in reconcilable] == [job.id]
            await uow.add_outbox(
                OutboxMessage(
                    id=uuid4(),
                    job_id=job.id,
                    task_name="resume_health.process",
                    trace_id=job.trace_id,
                    created_at=now,
                    next_attempt_at=now,
                    generation=1,
                )
            )
            assert (
                await uow.list_reconcilable_jobs(
                    now,
                    now - timedelta(minutes=5),
                    10,
                )
                == []
            )
            persisted = await uow.get_job(first_scope, job.id, for_update=True)
            assert persisted is not None
            persisted.start(now)
            persisted.acquire_execution_lease(b"e" * 32, now + timedelta(minutes=6), now)
            persisted.advance(ProcessingStage.EXTRACTION, 50, now)
            await uow.save_job(persisted)
            await uow.commit()

        async with factory() as uow:
            persisted = await uow.get_job(first_scope, job.id)
            assert persisted is not None
            assert persisted.status == JobStatus.RUNNING
            assert persisted.progress == 50

        section_id = uuid4()
        block_id = uuid4()
        block = CanonicalBlock(
            id=block_id,
            kind=BlockKind.BULLET,
            text="Built a fictional integration fixture.",
            confidence_basis_points=9_000,
            spans=(SourceSpan(1, 0, 38),),
        )
        section = CanonicalSection(
            id=section_id,
            kind=SectionKind.EXPERIENCE,
            title="Experience",
            confidence_basis_points=9_000,
            blocks=(block,),
        )
        semantic_field = SemanticField(
            id=uuid4(),
            name="achievement",
            field_type=SemanticFieldType.BULLET,
            value=block.text,
            confidence_basis_points=9_000,
            review_state=SemanticReviewState.CONFIRMED,
            anchors=(
                SemanticSourceAnchor(
                    block_id=block_id,
                    page=1,
                    start=0,
                    end=38,
                    source_sha256="ab" * 32,
                ),
            ),
        )
        snapshot = CanonicalSnapshot(
            id=uuid4(),
            document_id=document.id,
            owner=first_scope,
            revision=1,
            resume=CanonicalResume(
                schema_version="canonical-resume/2.0.0",
                sections=(section,),
                source_sections=(section,),
                semantics=CanonicalSemantics(
                    schema_version="canonical-semantics/1.0.0",
                    parser_version="integration-semantic/1",
                    entities=(
                        SemanticEntity(
                            id=uuid4(),
                            kind=SemanticEntityKind.EXPERIENCE,
                            review_state=SemanticReviewState.CONFIRMED,
                            fields=(semantic_field,),
                            source_section_id=section_id,
                        ),
                    ),
                    review_state=SemanticReviewState.CONFIRMED,
                ),
                warnings=(),
            ),
            plain_text_sha256=b"p" * 32,
            parser_version="integration/1",
            created_at=now,
        )
        analysis_id = uuid4()
        analysis_job = ProcessingJob(
            id=uuid4(),
            document_id=document.id,
            owner=first_scope,
            kind=JobKind.ANALYZE,
            idempotency_key=f"integration-analysis-{uuid4()}",
            request_hash=b"a" * 32,
            trace_id="integration-analysis",
            status=JobStatus.SUCCEEDED,
            stage=ProcessingStage.COMPLETE,
            progress=100,
            attempts=1,
            max_attempts=3,
            created_at=now,
            updated_at=now,
            completed_at=now,
            result_id=analysis_id,
            input_snapshot_id=snapshot.id,
        )
        analysis = ResumeHealthAnalysis(
            id=analysis_id,
            job_id=analysis_job.id,
            document_id=document.id,
            snapshot_id=snapshot.id,
            owner=first_scope,
            status=AnalysisStatus.SUCCEEDED,
            engine_version="resume-health/2.0.0",
            configuration_version="resume-health-default/2",
            feature_schema_version="resume-health-features/2",
            feature_values={
                "text_characters": 500,
                "page_count": 1,
                "image_only": False,
                "section_count": 1,
                "recognized_section_count": 1,
                "block_count": 3,
                "concise_block_count": 3,
                "bullet_count": 1,
                "action_bullet_count": 1,
                "outcome_bullet_count": 0,
                "duplicate_block_count": 0,
                "chronology_signal_count": 0,
                "warning_count": 0,
                "reading_order_violation_count": 0,
                "average_confidence_basis_points": 9_000,
                "semantic_entity_count": 1,
                "semantic_field_count": 1,
                "parsed_semantic_field_count": 1,
                "source_anchored_field_count": 1,
                "reviewed_semantic_field_count": 1,
                "date_field_count": 0,
                "precise_date_field_count": 0,
            },
            feature_set_hash=b"f" * 32,
            raw_score_basis_points=5_000,
            display_score=50,
            computed_at=now,
        )
        component = ScoreComponent(
            id=uuid4(),
            analysis_id=analysis.id,
            code="machine_readability",
            weight_basis_points=2_500,
            score_basis_points=5_000,
            contribution_basis_points=1_250,
            explanation="Fictional integration component.",
        )
        contribution = FeatureContribution(
            id=uuid4(),
            analysis_id=analysis.id,
            component_code="machine_readability",
            feature_code="searchable_text",
            feature_value_basis_points=5_000,
            weight_basis_points=10_000,
            contribution_basis_points=5_000,
        )
        finding = ResumeFinding(
            id=uuid4(),
            analysis_id=analysis.id,
            code="fictional_finding",
            severity=FindingSeverity.INFO,
            component_code="machine_readability",
            message="Fictional integration finding.",
            quick_win=False,
            sort_order=0,
        )
        async with factory() as uow:
            await uow.add_snapshot(snapshot)
            await uow.commit()
        async with factory() as uow:
            persisted_snapshot = await uow.get_latest_snapshot(first_scope, document.id)
            assert persisted_snapshot is not None
            assert persisted_snapshot.resume == snapshot.resume
        async with factory() as uow:
            await uow.add_job(analysis_job)
            await uow.add_analysis(analysis, (component,), (contribution,), (finding,))
            await uow.commit()
        async with factory() as uow:
            persisted_analysis = await uow.get_analysis(first_scope, analysis.id)
            assert persisted_analysis is not None
            assert persisted_analysis[0].feature_values == analysis.feature_values
            assert persisted_analysis[2] == [contribution]
            assert await uow.get_analysis(OwnerScope(user_id=second_user), analysis.id) is None

        guest = GuestSession(
            id=guest_id,
            capability_hash=b"g" * 32,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        async with factory() as uow:
            await uow.add_guest_session(guest)
            await uow.commit()
        assert guest.id == guest_id
    finally:
        async with database.session() as session:
            await session.execute(
                delete(GuestResumeSessionModel).where(GuestResumeSessionModel.id == guest_id)
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([first_user, second_user]))
            )
            await session.commit()
        await database.dispose()
