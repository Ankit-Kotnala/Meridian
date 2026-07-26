"""Live PostgreSQL parity and persistence contracts for all Phase 9 modules."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Never
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.career_analytics.application import (
    AnalyticsReconciliationOutcome,
    CareerAnalyticsPolicy,
    CareerAnalyticsService,
    RefreshAnalytics,
)
from careeros.modules.career_analytics.application import (
    RequestContext as AnalyticsRequestContext,
)
from careeros.modules.career_analytics.domain import (
    AnalyticsAuditAction,
    AnalyticsJobStatus,
    AnalyticsOutboxMessage,
    AnalyticsOutboxStatus,
    AnalyticsRefreshJob,
    AnalyticsScope,
    AnalyticsSnapshot,
    AnalyticsSnapshotStatus,
    CareerAnalyticsIdempotencyConflict,
    CareerAnalyticsQuotaExceeded,
)
from careeros.modules.career_analytics.infrastructure import (
    SqlAlchemyCareerAnalyticsUnitOfWorkFactory,
)
from careeros.modules.career_analytics.infrastructure.models import (
    AnalyticsAuditEventModel,
    AnalyticsOutboxModel,
    AnalyticsRefreshJobModel,
    AnalyticsSnapshotModel,
)
from careeros.modules.career_growth.application import (
    CareerGrowthInsightSource,
    CareerGrowthService,
    CreateCareerReview,
    GrowthAchievementSnapshot,
    ReviewContent,
    ReviseCareerReview,
)
from careeros.modules.career_growth.application import (
    RequestContext as GrowthRequestContext,
)
from careeros.modules.career_growth.domain import (
    CareerGrowthNotFound,
    CareerGrowthSourceSnapshot,
    GrowthEvidenceSnapshot,
    ReviewCadence,
    ReviewVersionStatus,
)
from careeros.modules.career_growth.infrastructure import (
    SqlAlchemyCareerGrowthUnitOfWorkFactory,
)
from careeros.modules.career_growth.infrastructure.models import CareerGrowthIdempotencyModel
from careeros.modules.career_record.infrastructure.models import (
    EvidenceItemModel,
    EvidenceRevisionModel,
)
from careeros.modules.identity.infrastructure.models import UserModel
from careeros.modules.interview_prep.application import (
    CreateStarStory,
    InterviewPrepService,
    InterviewSourceSnapshot,
    SourceClaim,
    SourceRequirement,
    StoryClaimSelection,
    UpdateStarStory,
)
from careeros.modules.interview_prep.application import (
    RequestContext as InterviewRequestContext,
)
from careeros.modules.interview_prep.domain import (
    EvidenceRevisionPin,
    InterviewPrepConflict,
    InterviewPrepNotFound,
    InterviewPrepUnavailable,
    StoryField,
    StoryOrigin,
    StoryStatus,
)
from careeros.modules.interview_prep.infrastructure import (
    SqlAlchemyInterviewPrepUnitOfWorkFactory,
)
from careeros.modules.interview_prep.infrastructure.models import (
    InterviewIdempotencyModel,
    StoryClaimPinModel,
)
from careeros.modules.networking.application import (
    ChangeContactConsent,
    CreateContact,
    CreateContactNote,
    CreateReferral,
    CreateReminder,
    NetworkingApplicationReference,
    NetworkingService,
    RecordInteraction,
)
from careeros.modules.networking.application import (
    RequestContext as NetworkingRequestContext,
)
from careeros.modules.networking.domain import (
    NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS,
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    ConsentPurpose,
    InteractionDirection,
    InteractionKind,
    NetworkingNotFound,
    ReferralStatus,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
    ReminderStatus,
)
from careeros.modules.networking.infrastructure import (
    SqlAlchemyNetworkingUnitOfWorkFactory,
)
from careeros.modules.networking.infrastructure.models import (
    NetworkingConsentEventModel,
    NetworkingContactModel,
    NetworkingContactNoteModel,
    NetworkingInteractionModel,
    NetworkingReferralModel,
    NetworkingReminderModel,
    NetworkingReminderOccurrenceModel,
)

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 7, 25, 9, tzinfo=UTC)


class _Clock:
    def __init__(self, value: datetime = _NOW) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class _Identifiers:
    def new(self) -> UUID:
        return uuid4()


class _UnusedAnalyticsSources:
    async def watermark(self, *_args: object, **_kwargs: object) -> Never:
        raise AssertionError("analytics source should not be read for outbox maintenance")

    async def page(self, *_args: object, **_kwargs: object) -> Never:
        raise AssertionError("analytics source should not be read for outbox maintenance")

    async def snapshot(self, *_args: object, **_kwargs: object) -> Never:
        raise AssertionError("analytics source should not be read for outbox maintenance")


class _InterviewContext:
    def __init__(self, value: InterviewSourceSnapshot) -> None:
        self.value = value

    async def snapshot(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> InterviewSourceSnapshot:
        del owner_user_id
        if application_id != self.value.application_id:
            raise InterviewPrepNotFound
        return self.value

    async def validate_current_evidence(
        self,
        owner_user_id: UUID,
        application_id: UUID,
        evidence_pins: tuple[EvidenceRevisionPin, ...],
    ) -> None:
        del owner_user_id
        if application_id != self.value.application_id:
            raise InterviewPrepNotFound
        expected = tuple(
            {
                pin.evidence_id: pin for claim in self.value.claims for pin in claim.evidence_pins
            }.values()
        )
        if evidence_pins != expected:
            raise InterviewPrepConflict("evidence is no longer current")


class _NoApplications:
    async def get_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> None:
        del owner_user_id, application_id
        return None


class _Applications:
    def __init__(self, owner_user_id: UUID, application_id: UUID) -> None:
        self.owner_user_id = owner_user_id
        self.application_id = application_id

    async def get_reference(
        self,
        owner_user_id: UUID,
        application_id: UUID,
    ) -> NetworkingApplicationReference | None:
        if owner_user_id != self.owner_user_id or application_id != self.application_id:
            return None
        return NetworkingApplicationReference(
            application_id=application_id,
            stage="interview",
        )


class _GrowthSource:
    def __init__(self, value: CareerGrowthSourceSnapshot) -> None:
        self.value = value

    async def snapshot(self, owner_user_id: UUID) -> CareerGrowthSourceSnapshot:
        del owner_user_id
        return self.value

    async def resolve_evidence(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        del owner_user_id
        by_id = {item.evidence_id: item for item in self.value.evidence}
        return tuple(by_id[item] for item in evidence_ids if item in by_id)

    async def current_evidence(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[GrowthEvidenceSnapshot, ...]:
        del owner_user_id
        requested = set(evidence_ids)
        return tuple(item for item in self.value.evidence if item.evidence_id in requested)

    async def insights(self, owner_user_id: UUID) -> CareerGrowthInsightSource:
        del owner_user_id
        return CareerGrowthInsightSource(
            achievements=tuple(
                GrowthAchievementSnapshot(
                    evidence_id=item.evidence_id,
                    evidence_revision_id=item.evidence_revision_id,
                    revision_number=item.revision_number,
                    title="Phase 9 integration evidence",
                    statement="Owner-authored Phase 9 integration evidence.",
                    evidence_type="achievement",
                    strength="confirmed",
                    revised_at=item.revised_at,
                    skill_ids=item.skill_ids,
                )
                for item in self.value.evidence
            ),
            skills=(),
            eligible_evidence=self.value.evidence,
        )


def _database_url() -> str:
    value = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


def _database() -> Database:
    return Database(DatabaseOptions(url=_database_url(), pool_size=2, max_overflow=0))


def _user(user_id: UUID) -> UserModel:
    return UserModel(
        id=user_id,
        email_normalized=f"{user_id}@phase9.example.test",
        password_hash=None,
        status="active",
        email_verified_at=None,
        auth_version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def _add_users(database: Database, *user_ids: UUID) -> None:
    async with database.session() as session:
        session.add_all(_user(user_id) for user_id in user_ids)
        await session.commit()


async def _delete_users(database: Database, *user_ids: UUID) -> None:
    async with database.session() as session:
        await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        await session.commit()


def _alembic_config() -> Config:
    config = Config(str(_PACKAGE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PACKAGE_ROOT / "alembic"))
    return config


def test_current_migration_head_matches_registered_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database_url()
    monkeypatch.setenv("CAREEROS_DATABASE_URL", database_url)
    monkeypatch.setenv("CAREEROS_ENVIRONMENT", "test")
    config = _alembic_config()

    assert ScriptDirectory.from_config(config).get_heads() == ["20260726_0013"]
    command.check(config)


@pytest.mark.asyncio
async def test_phase9_interview_repository_preserves_exact_provenance_and_owner_scope() -> None:
    database = _database()
    owner_id, other_id = uuid4(), uuid4()
    application_id = uuid4()
    claim_id = uuid4()
    evidence_id = uuid4()
    evidence_revision_id = uuid4()
    requirement_id = uuid4()
    statement = "Led a secure cross-functional launch with verified delivery evidence."
    statement_sha256 = hashlib.sha256(statement.encode()).hexdigest()
    evidence_pin = EvidenceRevisionPin(
        evidence_id=evidence_id,
        evidence_revision_id=evidence_revision_id,
        revision_number=4,
        statement=statement,
        statement_sha256=statement_sha256,
        strength="confirmed",
        has_numeric_claim=False,
    )
    source = InterviewSourceSnapshot(
        application_id=application_id,
        job_id=uuid4(),
        job_version=3,
        job_title="Principal Product Engineer",
        company="Example Co",
        resume_version_id=uuid4(),
        resume_version_number=7,
        claims=(
            SourceClaim(
                id=claim_id,
                text=statement,
                text_sha256=statement_sha256,
                strong=True,
                requirement_ids=(requirement_id,),
                evidence_pins=(evidence_pin,),
            ),
        ),
        requirements=(
            SourceRequirement(
                id=requirement_id,
                text="Lead secure cross-functional product delivery.",
                importance="mandatory",
            ),
        ),
    )
    source_provider = _InterviewContext(source)
    service = InterviewPrepService(
        unit_of_work=SqlAlchemyInterviewPrepUnitOfWorkFactory(database),
        clock=_Clock(),
        identifiers=_Identifiers(),
        application_context=source_provider,
    )
    context = InterviewRequestContext(owner_id, "phase9-interview-integration", "a" * 32)
    try:
        await _add_users(database, owner_id, other_id)
        create_command = CreateStarStory(
            application_id=application_id,
            title="Secure product launch",
            situation="A critical launch needed one accountable technical lead.",
            task="Coordinate the product and engineering delivery plan.",
            action="Led the team through a verified release process.",
            result="The release completed with its evidence trail intact.",
            personal_contribution="Owned the delivery decisions and risk controls.",
            metric_explanation=None,
            confidence=5,
            status=StoryStatus.READY,
            origin=StoryOrigin.USER_AUTHORED,
            claim_selections=(
                StoryClaimSelection(
                    claim_id=claim_id,
                    field_names=(
                        StoryField.SITUATION,
                        StoryField.TASK,
                        StoryField.ACTION,
                        StoryField.RESULT,
                        StoryField.PERSONAL_CONTRIBUTION,
                    ),
                ),
            ),
        )
        story_idempotency_key = f"phase9-story-{uuid4().hex}"
        created = await service.create_story(
            owner_id,
            create_command,
            idempotency_key=story_idempotency_key,
            context=context,
        )

        persisted = await service.get_story(owner_id, created.id)
        assert persisted.claim_pins[0].claim_sha256 == statement_sha256
        assert persisted.claim_pins[0].evidence_pins[0] == evidence_pin
        with pytest.raises(InterviewPrepNotFound):
            await service.get_story(other_id, created.id)

        changed_statement = "A later source view that must not rewrite the stored story."
        source_provider.value = InterviewSourceSnapshot(
            application_id=source.application_id,
            job_id=source.job_id,
            job_version=source.job_version,
            job_title=source.job_title,
            company=source.company,
            resume_version_id=source.resume_version_id,
            resume_version_number=source.resume_version_number,
            claims=(
                SourceClaim(
                    id=claim_id,
                    text=changed_statement,
                    text_sha256=hashlib.sha256(changed_statement.encode()).hexdigest(),
                    strong=True,
                    requirement_ids=(requirement_id,),
                    evidence_pins=(evidence_pin,),
                ),
            ),
            requirements=source.requirements,
        )
        unchanged = await service.get_story(owner_id, created.id)
        assert unchanged.claim_pins[0].claim_text == statement
        assert unchanged.claim_pins[0].claim_sha256 == statement_sha256

        updated = await service.update_story(
            owner_id,
            created.id,
            UpdateStarStory(
                title="Edited secure product launch",
                situation=create_command.situation,
                task=create_command.task,
                action=create_command.action,
                result=create_command.result,
                personal_contribution=create_command.personal_contribution,
                metric_explanation=create_command.metric_explanation,
                confidence=create_command.confidence,
                follow_up_questions=create_command.follow_up_questions,
                status=create_command.status,
                claim_selections=create_command.claim_selections,
            ),
            expected_version=created.version,
            context=context,
        )
        replay = await service.create_story(
            owner_id,
            create_command,
            idempotency_key=story_idempotency_key,
            context=context,
        )
        assert replay == created
        assert replay.version == 1
        assert updated.version == 2
        assert (await service.get_story(owner_id, created.id)).title == (
            "Edited secure product launch"
        )

        async with database.session() as session:
            raw_pin = await session.scalar(
                select(StoryClaimPinModel).where(
                    StoryClaimPinModel.owner_user_id == owner_id,
                    StoryClaimPinModel.story_id == created.id,
                )
            )
            assert raw_pin is not None
            assert raw_pin.evidence_pins == [
                {
                    "evidenceId": str(evidence_id),
                    "evidenceRevisionId": str(evidence_revision_id),
                    "revisionNumber": 4,
                    "statement": statement,
                    "statementSha256": statement_sha256,
                    "strength": "confirmed",
                    "hasNumericClaim": False,
                }
            ]
            replay_record = await session.scalar(
                select(InterviewIdempotencyModel).where(
                    InterviewIdempotencyModel.owner_user_id == owner_id,
                    InterviewIdempotencyModel.idempotency_key == story_idempotency_key,
                )
            )
            assert replay_record is not None
            assert replay_record.resource_id == created.id
            assert replay_record.response_snapshot is not None
            assert replay_record.response_snapshot["title"] == create_command.title
            assert replay_record.response_snapshot["version"] == 1

        async with database.session() as session:
            session.add(
                StoryClaimPinModel(
                    id=uuid4(),
                    owner_user_id=other_id,
                    story_id=created.id,
                    source_claim_id=uuid4(),
                    claim_text=statement,
                    claim_sha256=statement_sha256,
                    strong=True,
                    field_names=[StoryField.ACTION.value],
                    evidence_pins=[],
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

        async with database.session() as session:
            replay_record = await session.scalar(
                select(InterviewIdempotencyModel).where(
                    InterviewIdempotencyModel.owner_user_id == owner_id,
                    InterviewIdempotencyModel.idempotency_key == story_idempotency_key,
                )
            )
            assert replay_record is not None
            assert replay_record.response_snapshot is not None
            replay_record.response_snapshot = {
                **replay_record.response_snapshot,
                "unexpectedField": "must fail closed",
            }
            await session.commit()
        with pytest.raises(InterviewPrepUnavailable, match="snapshot is invalid"):
            await service.create_story(
                owner_id,
                create_command,
                idempotency_key=story_idempotency_key,
                context=context,
            )

        await service.delete_story(
            owner_id,
            created.id,
            expected_version=updated.version,
            context=context,
        )
        async with database.session() as session:
            replay_record = await session.scalar(
                select(InterviewIdempotencyModel).where(
                    InterviewIdempotencyModel.owner_user_id == owner_id,
                    InterviewIdempotencyModel.idempotency_key == story_idempotency_key,
                )
            )
            assert replay_record is not None
            assert replay_record.response_snapshot is None
        with pytest.raises(InterviewPrepConflict, match="redacted after deletion"):
            await service.create_story(
                owner_id,
                create_command,
                idempotency_key=story_idempotency_key,
                context=context,
            )
    finally:
        await _delete_users(database, owner_id, other_id)
        await database.dispose()


@pytest.mark.parametrize(
    ("failure_mode", "safe_error_code", "failure_stage"),
    [
        ("explicit", "publish_failed", "outbox_publish"),
        ("expired_outbox_lease", "lease_expired", "outbox_publish"),
        ("expired_job_lease", "lease_expired", "refresh_processing"),
    ],
)
@pytest.mark.asyncio
async def test_phase9_analytics_maintenance_exhaustion_terminalizes_job_and_audits(
    failure_mode: str,
    safe_error_code: str,
    failure_stage: str,
) -> None:
    database = _database()
    owner_id = uuid4()
    clock = _Clock()
    sources = _UnusedAnalyticsSources()
    factory = SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database)
    service = CareerAnalyticsService(
        unit_of_work=factory,
        clock=clock,
        identifiers=_Identifiers(),
        applications=sources,
        supplemental=sources,
        policy=CareerAnalyticsPolicy(max_attempts=1, lease_seconds=30),
    )
    trace_id = uuid4().hex
    try:
        await _add_users(database, owner_id)
        refresh = await service.request_refresh(
            owner_id,
            RefreshAnalytics(
                scope=AnalyticsScope.OVERVIEW,
                window_start=date(2026, 1, 1),
                window_end=date(2026, 7, 25),
                timezone="UTC",
            ),
            idempotency_key=f"phase9-analytics-outbox-{failure_mode}-{uuid4().hex}",
            context=AnalyticsRequestContext(
                actor_user_id=owner_id,
                request_id=f"phase9-analytics-outbox-{failure_mode}",
                trace_id=trace_id,
            ),
        )
        claimed = await service.claim_outbox()
        assert len(claimed) == 1
        if failure_mode == "explicit":
            await service.mark_outbox_failed(
                claimed[0].message_id,
                lease_token=claimed[0].lease_token,
            )
        elif failure_mode == "expired_outbox_lease":
            clock.value += timedelta(seconds=31)
            assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
                recovered_jobs=0,
                dead_lettered_jobs=1,
                recovered_outbox=0,
                dead_lettered_outbox=1,
                requeued_deliveries=0,
            )
        else:
            await service.mark_outbox_published(
                claimed[0].message_id,
                lease_token=claimed[0].lease_token,
                job_version_at_claim=claimed[0].job_version_at_claim,
            )
            async with factory() as uow:
                job = await uow.get_job(owner_id, refresh.id, for_update=True)
                assert job is not None
                job.claim(
                    token=uuid4(),
                    now=clock.value,
                    leased_until=clock.value + timedelta(seconds=30),
                )
                await uow.save_job(job)
                await uow.commit()
            clock.value += timedelta(seconds=31)
            assert await service.reconcile_expired() == AnalyticsReconciliationOutcome(
                recovered_jobs=0,
                dead_lettered_jobs=1,
                recovered_outbox=0,
                dead_lettered_outbox=0,
                requeued_deliveries=0,
            )

        terminal = await service.get_refresh(owner_id, refresh.id)
        assert terminal.status is AnalyticsJobStatus.DEAD_LETTER
        assert terminal.safe_error_code == safe_error_code
        async with factory() as uow:
            assert await uow.count_active_jobs(owner_id) == 0
        async with database.session() as session:
            outbox = await session.scalar(
                select(AnalyticsOutboxModel).where(AnalyticsOutboxModel.job_id == refresh.id)
            )
            audits = (
                await session.scalars(
                    select(AnalyticsAuditEventModel).where(
                        AnalyticsAuditEventModel.owner_user_id == owner_id,
                        AnalyticsAuditEventModel.action
                        == AnalyticsAuditAction.REFRESH_DEAD_LETTERED.value,
                    )
                )
            ).all()
        assert outbox is not None
        assert outbox.status == (
            AnalyticsOutboxStatus.PUBLISHED.value
            if failure_mode == "expired_job_lease"
            else AnalyticsOutboxStatus.DEAD_LETTER.value
        )
        assert outbox.safe_error_code == (
            None if failure_mode == "expired_job_lease" else safe_error_code
        )
        assert len(audits) == 1
        assert audits[0].target_id == refresh.id
        assert audits[0].actor_user_id is None
        assert audits[0].request_id is None
        assert audits[0].trace_id == trace_id
        assert audits[0].metadata_ == {
            "error_code": safe_error_code,
            "failure_stage": failure_stage,
            "scope": AnalyticsScope.OVERVIEW.value,
        }
    finally:
        await _delete_users(database, owner_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_analytics_outbox_claims_lock_jobs_and_skip_locked() -> None:
    database = _database()
    owner_id = uuid4()
    clock = _Clock()
    sources = _UnusedAnalyticsSources()
    factory = SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database)
    service = CareerAnalyticsService(
        unit_of_work=factory,
        clock=clock,
        identifiers=_Identifiers(),
        applications=sources,
        supplemental=sources,
        policy=CareerAnalyticsPolicy(max_attempts=3, lease_seconds=30),
    )
    try:
        await _add_users(database, owner_id)
        expected: dict[UUID, int] = {}
        for index in range(2):
            refresh = await service.request_refresh(
                owner_id,
                RefreshAnalytics(
                    scope=AnalyticsScope.OVERVIEW,
                    window_start=date(2026, 1, 1),
                    window_end=date(2026, 7, 25),
                    timezone="UTC",
                ),
                idempotency_key=f"phase9-analytics-outbox-lock-{index}-{uuid4().hex}",
                context=AnalyticsRequestContext(
                    actor_user_id=owner_id,
                    request_id=f"phase9-outbox-lock-{index}",
                    trace_id=uuid4().hex,
                ),
            )
            expected[refresh.id] = refresh.version

        async with factory() as first:
            first_claim = await first.claim_outbox(now=clock.value, limit=1)
            assert len(first_claim) == 1
            async with factory() as second:
                second_claim = await second.claim_outbox(now=clock.value, limit=2)
                assert len(second_claim) == 1
                claims = first_claim + second_claim
                assert {message.job_id for message, _job in claims} == set(expected)
                assert all(
                    message.job_id == job.id
                    and message.owner_user_id == job.owner_user_id == owner_id
                    and job.version == expected[job.id]
                    for message, job in claims
                )
    finally:
        await _delete_users(database, owner_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_analytics_due_delivery_claims_skip_locked_and_advance() -> None:
    database = _database()
    owner_id = uuid4()
    clock = _Clock()
    sources = _UnusedAnalyticsSources()
    factory = SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database)
    service = CareerAnalyticsService(
        unit_of_work=factory,
        clock=clock,
        identifiers=_Identifiers(),
        applications=sources,
        supplemental=sources,
        policy=CareerAnalyticsPolicy(max_attempts=3, lease_seconds=30),
    )
    try:
        await _add_users(database, owner_id)
        job_ids: list[UUID] = []
        for index in range(2):
            refresh = await service.request_refresh(
                owner_id,
                RefreshAnalytics(
                    scope=AnalyticsScope.OVERVIEW,
                    window_start=date(2026, 1, 1),
                    window_end=date(2026, 7, 25),
                    timezone="UTC",
                ),
                idempotency_key=f"phase9-analytics-delivery-claim-{index}-{uuid4().hex}",
                context=AnalyticsRequestContext(
                    actor_user_id=owner_id,
                    request_id=f"phase9-delivery-claim-{index}",
                    trace_id=uuid4().hex,
                ),
            )
            job_ids.append(refresh.id)
        claimed = await service.claim_outbox(limit=2)
        assert len(claimed) == 2
        for message in claimed:
            await service.mark_outbox_published(
                message.message_id,
                lease_token=message.lease_token,
                job_version_at_claim=message.job_version_at_claim,
            )
        clock.value += timedelta(seconds=31)

        async with factory() as first:
            first_claim = await first.claim_due_deliveries(
                now=clock.value,
                limit=1,
            )
            assert len(first_claim) == 1
            async with factory() as second:
                second_claim = await second.claim_due_deliveries(
                    now=clock.value,
                    limit=2,
                )
                assert len(second_claim) == 1
                assert first_claim[0][1].id != second_claim[0][1].id
                assert {first_claim[0][1].id, second_claim[0][1].id} == set(job_ids)

        first_recovery = await service.reconcile_expired(limit=1)
        second_recovery = await service.reconcile_expired(limit=1)
        third_recovery = await service.reconcile_expired(limit=1)
        assert first_recovery.requeued_deliveries == 1
        assert second_recovery.requeued_deliveries == 1
        assert third_recovery.requeued_deliveries == 0
    finally:
        await _delete_users(database, owner_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_networking_consent_cancels_outbox_and_recovers_expired_lease() -> None:
    database = _database()
    owner_id, other_id = uuid4(), uuid4()
    application_id = uuid4()
    clock = _Clock()
    factory = SqlAlchemyNetworkingUnitOfWorkFactory(database)
    service = NetworkingService(
        unit_of_work=factory,
        clock=clock,
        identifiers=_Identifiers(),
        applications=_Applications(owner_id, application_id),
    )
    context = NetworkingRequestContext(owner_id, "phase9-networking-integration", "b" * 32)
    try:
        await _add_users(database, owner_id, other_id)
        contact_view = await service.create_contact(
            owner_id,
            CreateContact(
                name="A. Contact",
                role="Engineering leader",
                collection_attested=True,
                storage_attested=True,
                outreach_attested=True,
                consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            idempotency_key=f"phase9-contact-{uuid4().hex}",
            context=context,
        )
        note = await service.create_note(
            owner_id,
            contact_view.contact.id,
            CreateContactNote(body="Private networking note"),
            idempotency_key=f"phase9-note-{uuid4().hex}",
            context=context,
        )
        interaction = await service.record_interaction(
            owner_id,
            contact_view.contact.id,
            RecordInteraction(
                kind=InteractionKind.MEETING,
                direction=InteractionDirection.MUTUAL,
                occurred_at=clock.now(),
                summary="Private networking interaction",
            ),
            expected_contact_version=contact_view.contact.version,
            idempotency_key=f"phase9-interaction-{uuid4().hex}",
            context=context,
        )
        after_interaction = await service.get_contact(owner_id, contact_view.contact.id)
        referral = await service.create_referral(
            owner_id,
            contact_view.contact.id,
            CreateReferral(
                application_id=application_id,
                status=ReferralStatus.REQUESTED,
                context="Private referral context",
            ),
            expected_contact_version=after_interaction.contact.version,
            idempotency_key=f"phase9-referral-{uuid4().hex}",
            context=context,
        )
        reminder = await service.create_reminder(
            owner_id,
            contact_view.contact.id,
            CreateReminder(
                title="Review a user-controlled follow-up",
                due_at=clock.now(),
                max_attempts=5,
            ),
            idempotency_key=f"phase9-reminder-{uuid4().hex}",
            context=context,
        )
        second_contact = await service.create_contact(
            owner_id,
            CreateContact(
                name="Second Contact",
                collection_attested=True,
                storage_attested=True,
                outreach_attested=True,
                consent_policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            idempotency_key=f"phase9-second-contact-{uuid4().hex}",
            context=context,
        )
        async with database.session() as session:
            session.add(
                NetworkingReminderOccurrenceModel(
                    id=uuid4(),
                    owner_user_id=owner_id,
                    reminder_id=reminder.id,
                    contact_id=second_contact.contact.id,
                    scheduled_for=clock.now(),
                    occurrence_number=2,
                    status=ReminderOccurrenceStatus.SCHEDULED.value,
                    trace_id="b" * 32,
                    acknowledged_at=None,
                    created_at=clock.now(),
                    updated_at=clock.now(),
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
            session.add(
                NetworkingReminderOccurrenceModel(
                    id=uuid4(),
                    owner_user_id=owner_id,
                    reminder_id=reminder.id,
                    contact_id=contact_view.contact.id,
                    scheduled_for=clock.now(),
                    occurrence_number=2,
                    status=ReminderOccurrenceStatus.SCHEDULED.value,
                    trace_id="B" * 32,
                    acknowledged_at=None,
                    created_at=clock.now(),
                    updated_at=clock.now(),
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        pending_execution = await service.get_reminder_execution(owner_id, reminder.id)
        assert pending_execution is not None
        assert pending_execution.occurrence_number == 1
        assert pending_execution.occurrence_status is ReminderOccurrenceStatus.SCHEDULED
        assert pending_execution.queue_status is ReminderOutboxStatus.PENDING
        assert pending_execution.attempt_count == 0
        assert not hasattr(pending_execution, "lease_token")
        assert not hasattr(pending_execution, "contact_id")
        with pytest.raises(NetworkingNotFound):
            await service.get_reminder_execution(other_id, reminder.id)

        first_claim = await service.claim_due_reminders(
            now=clock.now(),
            lease_seconds=30,
        )
        assert len(first_claim) == 1
        assert first_claim[0].status is ReminderOutboxStatus.LEASED
        assert first_claim[0].trace_id == "b" * 32

        recovery_time = clock.now() + timedelta(seconds=31)
        recovered = await service.recover_expired_leases(now=recovery_time)
        assert len(recovered) == 1
        assert recovered[0].status is ReminderOutboxStatus.PENDING
        assert recovered[0].last_error_code == "lease_expired"
        assert recovered[0].lease_token is None

        second_claim = await service.claim_due_reminders(
            now=recovery_time,
            lease_seconds=30,
        )
        assert len(second_claim) == 1
        assert second_claim[0].attempt_count == 2
        leased_execution = await service.get_reminder_execution(owner_id, reminder.id)
        assert leased_execution is not None
        assert leased_execution.attempt_count == 2
        assert leased_execution.queue_status is ReminderOutboxStatus.LEASED
        assert leased_execution.last_error_code == "lease_expired"
        clock.value = recovery_time
        current = await service.get_contact(owner_id, contact_view.contact.id)
        withdrawn = await service.withdraw_consent(
            owner_id,
            contact_view.contact.id,
            ChangeContactConsent(
                purpose=ConsentPurpose.OUTREACH,
                policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            expected_version=current.contact.version,
            idempotency_key=f"phase9-withdraw-{uuid4().hex}",
            context=context,
        )
        assert withdrawn.consent.outreach is False
        with pytest.raises(NetworkingNotFound):
            await service.get_contact(other_id, contact_view.contact.id)

        async with factory() as uow:
            stored_reminder = await uow.get_reminder(owner_id, reminder.id)
            occurrence = await uow.find_occurrence(owner_id, reminder.id, 1)
            outbox = await uow.get_outbox(second_claim[0].id)
            assert stored_reminder is not None
            assert stored_reminder.status is ReminderStatus.CANCELLED
            assert stored_reminder.title == "[deleted]"
            assert occurrence is not None
            assert occurrence.status is ReminderOccurrenceStatus.CANCELLED
            assert occurrence.trace_id == "b" * 32
            assert outbox is not None
            assert outbox.status is ReminderOutboxStatus.CANCELLED
            assert outbox.trace_id == "b" * 32
            assert outbox.lease_token is None
            assert outbox.lease_expires_at is None
            assert await uow.get_contact(other_id, contact_view.contact.id) is None
        async with database.session() as session:
            stored_note = await session.get(NetworkingContactNoteModel, note.id)
            stored_interaction = await session.get(NetworkingInteractionModel, interaction.id)
            stored_referral = await session.get(NetworkingReferralModel, referral.id)
            stored_reminder_row = await session.get(NetworkingReminderModel, reminder.id)
            assert stored_note is not None
            assert stored_note.body == "Private networking note"
            assert stored_note.deleted_at is None
            assert stored_interaction is not None
            assert stored_interaction.summary == "Private networking interaction"
            assert stored_interaction.deleted_at is None
            assert stored_referral is not None
            assert stored_referral.context is None
            assert stored_referral.status == ReferralStatus.CANCELLED.value
            assert stored_reminder_row is not None
            assert stored_reminder_row.title == "[deleted]"

        second_withdrawal = await service.withdraw_consent(
            owner_id,
            second_contact.contact.id,
            ChangeContactConsent(
                purpose=ConsentPurpose.STORAGE,
                policy_version=NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
            ),
            expected_version=second_contact.contact.version,
            idempotency_key=f"phase9-storage-withdraw-{uuid4().hex}",
            context=context,
        )
        assert second_withdrawal.contact.deleted_at == clock.now()
        assert second_withdrawal.contact.name == "[deleted]"
        assert second_withdrawal.contact.role is None
        assert second_withdrawal.contact.email is None
        assert second_withdrawal.contact.phone is None
        assert second_withdrawal.contact.profile_url is None
        assert second_withdrawal.contact.location is None
        assert second_withdrawal.contact.normalized_search == "[deleted]"
        assert second_withdrawal.consent.collection is False
        assert second_withdrawal.consent.storage is False
        assert second_withdrawal.consent.outreach is False
        with pytest.raises(NetworkingNotFound):
            await service.get_contact(owner_id, second_contact.contact.id)
        with pytest.raises(NetworkingNotFound):
            await service.get_contact(other_id, second_contact.contact.id)
        async with database.session() as session:
            tombstone = await session.get(
                NetworkingContactModel,
                second_contact.contact.id,
            )
            assert tombstone is not None
            assert tombstone.deleted_at == clock.now()
            assert tombstone.name == "[deleted]"
            assert tombstone.role is None
            assert tombstone.email is None
            assert tombstone.phone is None
            assert tombstone.profile_url is None
            assert tombstone.location is None
            assert tombstone.tags == []
            assert tombstone.last_contact_at is None
            assert tombstone.next_contact_at is None
            ledger_rows = (
                await session.scalars(
                    select(NetworkingConsentEventModel)
                    .where(
                        NetworkingConsentEventModel.owner_user_id == owner_id,
                        NetworkingConsentEventModel.contact_id == second_contact.contact.id,
                    )
                    .order_by(NetworkingConsentEventModel.sequence.asc())
                )
            ).all()
            assert len(ledger_rows) == 6
            assert {column.name for column in NetworkingConsentEventModel.__table__.columns} == {
                "id",
                "owner_user_id",
                "contact_id",
                "purpose",
                "action",
                "policy_version",
                "actor_user_id",
                "sequence",
                "occurred_at",
            }
            assert all(
                row.policy_version in NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS
                for row in ledger_rows
            )
            retained_values = "|".join(
                str(getattr(row, column.name))
                for row in ledger_rows
                for column in NetworkingConsentEventModel.__table__.columns
            )
            assert "Second Contact" not in retained_values

            smuggled_pii = "second.contact@example.test"
            session.add(
                NetworkingConsentEventModel(
                    id=uuid4(),
                    owner_user_id=owner_id,
                    contact_id=second_contact.contact.id,
                    purpose="storage",
                    action="withdrawn",
                    policy_version=smuggled_pii,
                    actor_user_id=owner_id,
                    sequence=7,
                    occurred_at=clock.now(),
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
    finally:
        await _delete_users(database, owner_id, other_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_growth_review_versions_and_evidence_pins_are_append_only() -> None:
    database = _database()
    owner_id, other_id = uuid4(), uuid4()
    evidence_id, evidence_revision_id = uuid4(), uuid4()
    statement_sha256 = hashlib.sha256(b"phase9-growth-evidence").hexdigest()
    source = _GrowthSource(
        CareerGrowthSourceSnapshot(
            evidence=(
                GrowthEvidenceSnapshot(
                    evidence_id=evidence_id,
                    evidence_revision_id=evidence_revision_id,
                    revision_number=5,
                    statement_sha256=statement_sha256,
                    revised_at=_NOW - timedelta(days=10),
                    skill_ids=(),
                ),
            ),
            skill_ids=(),
        )
    )
    clock = _Clock()
    service = CareerGrowthService(
        unit_of_work=SqlAlchemyCareerGrowthUnitOfWorkFactory(database),
        clock=clock,
        identifiers=_Identifiers(),
        career_source=source,
    )
    context = GrowthRequestContext(owner_id, "phase9-growth-integration", "c" * 32)
    initial_content = ReviewContent(
        title="Quarterly reflection",
        summary="Reviewed verified delivery evidence and the next development focus.",
        achievements="The evidence pin records the reviewed achievement.",
        growth_areas="Continue deliberate systems design practice.",
        next_focus="Prepare the next evidence-backed review.",
    )
    try:
        await _add_users(database, owner_id, other_id)
        async with database.session() as session:
            session.add(
                EvidenceItemModel(
                    id=evidence_id,
                    owner_user_id=owner_id,
                    lifecycle="active",
                    current_revision=5,
                    version=1,
                    created_at=_NOW - timedelta(days=10),
                    updated_at=_NOW - timedelta(days=10),
                )
            )
            session.add(
                EvidenceRevisionModel(
                    id=evidence_revision_id,
                    owner_user_id=owner_id,
                    evidence_id=evidence_id,
                    revision=5,
                    evidence_type="achievement",
                    title="Phase 9 integration evidence",
                    statement="phase9-growth-evidence",
                    strength="confirmed",
                    input_kind="manual",
                    created_at=_NOW - timedelta(days=10),
                )
            )
            await session.commit()
        created = await service.create_review(
            owner_id,
            CreateCareerReview(
                cadence=ReviewCadence.QUARTERLY,
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                content=initial_content,
                evidence_ids=(evidence_id,),
            ),
            idempotency_key=f"phase9-review-{uuid4().hex}",
            context=context,
        )
        finalize_expected_version = created.review.version
        finalize_key = f"phase9-review-finalize-{uuid4().hex}"
        finalized = await service.finalize_review(
            owner_id,
            created.review.id,
            expected_version=finalize_expected_version,
            idempotency_key=finalize_key,
            context=context,
        )
        assert finalized.current_version.version.status is ReviewVersionStatus.FINALIZED
        finalized_version_id = finalized.current_version.version.id

        clock.value += timedelta(minutes=1)
        revised = await service.revise_review(
            owner_id,
            created.review.id,
            expected_version=finalized.review.version,
            command=ReviseCareerReview(
                content=ReviewContent(
                    title=initial_content.title,
                    summary="A new material reflection preserved every earlier version.",
                    achievements=initial_content.achievements,
                    growth_areas=initial_content.growth_areas,
                    next_focus=initial_content.next_focus,
                ),
                change_reason="Add the next owner-reviewed reflection.",
                evidence_ids=(evidence_id,),
            ),
            context=context,
        )

        assert [item.version.version_number for item in revised.history] == [1, 2, 3]
        assert revised.history[0].version.summary == initial_content.summary
        assert revised.history[1].version.status is ReviewVersionStatus.FINALIZED
        assert revised.current_version.version.status is ReviewVersionStatus.DRAFT
        for version_view in revised.history:
            assert len(version_view.evidence_links) == 1
            pin = version_view.evidence_links[0].link
            assert pin.evidence_id == evidence_id
            assert pin.evidence_revision_id == evidence_revision_id
            assert pin.revision_number == 5
            assert pin.statement_sha256 == statement_sha256

        replay = await service.finalize_review(
            owner_id,
            created.review.id,
            expected_version=finalize_expected_version,
            idempotency_key=finalize_key,
            context=context,
        )
        assert replay.review.version == 2
        assert replay.review.latest_version_id == finalized_version_id
        assert replay.current_version.version.status is ReviewVersionStatus.FINALIZED
        assert [item.version.version_number for item in replay.history] == [1, 2]
        async with database.session() as session:
            replay_record = await session.scalar(
                select(CareerGrowthIdempotencyModel).where(
                    CareerGrowthIdempotencyModel.owner_user_id == owner_id,
                    CareerGrowthIdempotencyModel.idempotency_key == finalize_key,
                )
            )
            assert replay_record is not None
            assert replay_record.result_id == finalized_version_id

        with pytest.raises(CareerGrowthNotFound):
            await service.get_review(other_id, created.review.id)
    finally:
        await _delete_users(database, owner_id, other_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_analytics_idempotency_and_watermarked_snapshot_are_owner_scoped() -> None:
    database = _database()
    owner_id, other_id = uuid4(), uuid4()
    factory = SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database)
    job_id, outbox_id = uuid4(), uuid4()
    idempotency_key = f"phase9-analytics-{uuid4().hex}"
    job = AnalyticsRefreshJob(
        id=job_id,
        owner_user_id=owner_id,
        scope=AnalyticsScope.OVERVIEW,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 7, 25),
        timezone="UTC",
        idempotency_key=idempotency_key,
        request_fingerprint=hashlib.sha256(b"phase9-analytics-request").hexdigest(),
        status=AnalyticsJobStatus.QUEUED,
        attempts=0,
        max_attempts=3,
        trace_id="d" * 32,
        source_watermark_before=None,
        source_watermark_after=None,
        lease_token=None,
        leased_until=None,
        next_attempt_at=_NOW,
        safe_error_code=None,
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
        completed_at=None,
    )
    outbox = AnalyticsOutboxMessage(
        id=outbox_id,
        owner_user_id=owner_id,
        job_id=job_id,
        status=AnalyticsOutboxStatus.PENDING,
        attempts=0,
        max_attempts=3,
        lease_token=None,
        leased_until=None,
        next_attempt_at=_NOW,
        safe_error_code=None,
        created_at=_NOW,
        updated_at=_NOW,
        published_at=None,
    )
    try:
        await _add_users(database, owner_id, other_id)
        async with factory() as uow:
            await uow.add_job(job, outbox)
            await uow.commit()

        async with factory() as uow:
            replay = await uow.find_job_by_idempotency(owner_id, idempotency_key)
            assert replay is not None
            assert replay.id == job_id
            assert await uow.find_job_by_idempotency(other_id, idempotency_key) is None
            assert await uow.get_job(other_id, job_id) is None

        duplicate_job = AnalyticsRefreshJob(
            id=uuid4(),
            owner_user_id=owner_id,
            scope=job.scope,
            window_start=job.window_start,
            window_end=job.window_end,
            timezone=job.timezone,
            idempotency_key=idempotency_key,
            request_fingerprint=job.request_fingerprint,
            status=AnalyticsJobStatus.QUEUED,
            attempts=0,
            max_attempts=3,
            trace_id="e" * 32,
            source_watermark_before=None,
            source_watermark_after=None,
            lease_token=None,
            leased_until=None,
            next_attempt_at=_NOW,
            safe_error_code=None,
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
            completed_at=None,
        )
        duplicate_outbox = AnalyticsOutboxMessage(
            id=uuid4(),
            owner_user_id=owner_id,
            job_id=duplicate_job.id,
            status=AnalyticsOutboxStatus.PENDING,
            attempts=0,
            max_attempts=3,
            lease_token=None,
            leased_until=None,
            next_attempt_at=_NOW,
            safe_error_code=None,
            created_at=_NOW,
            updated_at=_NOW,
            published_at=None,
        )
        with pytest.raises(CareerAnalyticsIdempotencyConflict):
            async with factory() as uow:
                await uow.add_job(duplicate_job, duplicate_outbox)

        watermark_before: dict[str, object] = {
            "applications": {"count": 7, "versionSum": 15},
            "events": {"count": 19},
        }
        watermark_after: dict[str, object] = {
            "applications": {"count": 7, "versionSum": 15},
            "events": {"count": 19},
        }
        payload: dict[str, object] = {
            "counts": {"applications": 7, "interviews": 2},
            "interpretation": "correlation_only",
        }
        payload_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        token = uuid4()
        completed_at = _NOW + timedelta(seconds=1)
        snapshot = AnalyticsSnapshot(
            id=uuid4(),
            owner_user_id=owner_id,
            job_id=job_id,
            scope=AnalyticsScope.OVERVIEW,
            metric_definition_version="career-analytics-v1",
            window_start=job.window_start,
            window_end=job.window_end,
            timezone=job.timezone,
            source_watermark=watermark_after,
            payload=payload,
            payload_sha256=payload_sha256,
            status=AnalyticsSnapshotStatus.READY,
            created_at=completed_at,
            stale_at=None,
        )
        async with factory() as uow:
            stored_job = await uow.get_job(owner_id, job_id, for_update=True)
            assert stored_job is not None
            stored_job.claim(
                token=token,
                now=_NOW,
                leased_until=_NOW + timedelta(seconds=30),
            )
            stored_job.complete(
                token=token,
                before=watermark_before,
                after=watermark_after,
                now=completed_at,
            )
            await uow.save_job(stored_job)
            await uow.add_snapshot(snapshot)
            await uow.commit()

        async with factory() as uow:
            completed = await uow.get_job(owner_id, job_id)
            current = await uow.get_latest_snapshot(
                owner_id,
                AnalyticsScope.OVERVIEW,
                job.window_start,
                job.window_end,
                job.timezone,
            )
            hidden = await uow.get_latest_snapshot(
                other_id,
                AnalyticsScope.OVERVIEW,
                job.window_start,
                job.window_end,
                job.timezone,
            )
            assert completed is not None
            assert completed.status is AnalyticsJobStatus.COMPLETED
            assert completed.source_watermark_before == watermark_before
            assert completed.source_watermark_after == watermark_after
            assert current is not None
            assert current.source_watermark == watermark_after
            assert current.payload_sha256 == payload_sha256
            assert hidden is None
    finally:
        await _delete_users(database, owner_id, other_id)
        await database.dispose()


@pytest.mark.asyncio
async def test_phase9_analytics_retention_is_tenant_scoped_and_concurrency_bounded() -> None:
    database = _database()
    owner_id, other_id = uuid4(), uuid4()
    factory = SqlAlchemyCareerAnalyticsUnitOfWorkFactory(database)
    old_at = _NOW - timedelta(days=1)
    window_start = date(2026, 1, 1)
    window_end = date(2026, 7, 25)

    def terminal_job(
        owner_user_id: UUID,
        *,
        ordinal: int,
    ) -> tuple[AnalyticsRefreshJob, AnalyticsOutboxMessage]:
        job = AnalyticsRefreshJob(
            id=uuid4(),
            owner_user_id=owner_user_id,
            scope=AnalyticsScope.OVERVIEW,
            window_start=window_start,
            window_end=window_end,
            timezone="UTC",
            idempotency_key=f"phase9-retained-{ordinal}-{uuid4().hex}",
            request_fingerprint=hashlib.sha256(f"retained-{ordinal}".encode()).hexdigest(),
            status=AnalyticsJobStatus.COMPLETED,
            attempts=1,
            max_attempts=3,
            trace_id=f"{ordinal:x}".rjust(32, "0"),
            source_watermark_before={},
            source_watermark_after={},
            lease_token=None,
            leased_until=None,
            next_attempt_at=old_at,
            safe_error_code=None,
            version=3,
            created_at=old_at + timedelta(seconds=ordinal),
            updated_at=old_at + timedelta(seconds=ordinal),
            completed_at=old_at + timedelta(seconds=ordinal),
        )
        outbox = AnalyticsOutboxMessage(
            id=uuid4(),
            owner_user_id=owner_user_id,
            job_id=job.id,
            status=AnalyticsOutboxStatus.PUBLISHED,
            attempts=1,
            max_attempts=3,
            lease_token=None,
            leased_until=None,
            next_attempt_at=old_at,
            safe_error_code=None,
            created_at=old_at,
            updated_at=old_at,
            published_at=old_at,
        )
        return job, outbox

    removable, removable_outbox = terminal_job(owner_id, ordinal=1)
    protected, protected_outbox = terminal_job(owner_id, ordinal=2)
    other, other_outbox = terminal_job(other_id, ordinal=3)
    protected_payload = {"counts": {"applications": 1}}
    protected_snapshot = AnalyticsSnapshot(
        id=uuid4(),
        owner_user_id=owner_id,
        job_id=protected.id,
        scope=AnalyticsScope.OVERVIEW,
        metric_definition_version="career-analytics/1.0.0",
        window_start=window_start,
        window_end=window_end,
        timezone="UTC",
        source_watermark={},
        payload=protected_payload,
        payload_sha256=hashlib.sha256(
            json.dumps(
                protected_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        status=AnalyticsSnapshotStatus.READY,
        created_at=old_at + timedelta(seconds=2),
        stale_at=None,
    )
    service = CareerAnalyticsService(
        unit_of_work=factory,
        clock=_Clock(),
        identifiers=_Identifiers(),
        applications=_UnusedAnalyticsSources(),
        supplemental=_UnusedAnalyticsSources(),
        policy=CareerAnalyticsPolicy(
            max_active_jobs_per_owner=1,
            max_job_history_per_owner=1,
            idempotency_replay_seconds=300,
        ),
    )
    context = AnalyticsRequestContext(
        actor_user_id=owner_id,
        request_id="phase9-retention-concurrency",
        trace_id="f" * 32,
    )

    try:
        await _add_users(database, owner_id, other_id)
        async with factory() as uow:
            await uow.add_job(removable, removable_outbox)
            await uow.add_job(protected, protected_outbox)
            await uow.add_job(other, other_outbox)
            await uow.add_snapshot(protected_snapshot)
            await uow.commit()

        outcomes = await asyncio.gather(
            service.request_refresh(
                owner_id,
                RefreshAnalytics(
                    scope=AnalyticsScope.OVERVIEW,
                    window_start=window_start,
                    window_end=window_end,
                    timezone="UTC",
                ),
                idempotency_key=f"phase9-retention-new-a-{uuid4().hex}",
                context=context,
            ),
            service.request_refresh(
                owner_id,
                RefreshAnalytics(
                    scope=AnalyticsScope.OVERVIEW,
                    window_start=window_start,
                    window_end=window_end,
                    timezone="UTC",
                ),
                idempotency_key=f"phase9-retention-new-b-{uuid4().hex}",
                context=context,
            ),
            return_exceptions=True,
        )

        assert sum(not isinstance(value, BaseException) for value in outcomes) == 1
        assert sum(isinstance(value, CareerAnalyticsQuotaExceeded) for value in outcomes) == 1
        async with database.session() as session:
            owner_jobs = set(
                await session.scalars(
                    select(AnalyticsRefreshJobModel.id).where(
                        AnalyticsRefreshJobModel.owner_user_id == owner_id
                    )
                )
            )
            other_job = await session.scalar(
                select(AnalyticsRefreshJobModel.id).where(
                    AnalyticsRefreshJobModel.owner_user_id == other_id,
                    AnalyticsRefreshJobModel.id == other.id,
                )
            )
            retained_snapshot = await session.scalar(
                select(AnalyticsSnapshotModel.id).where(
                    AnalyticsSnapshotModel.owner_user_id == owner_id,
                    AnalyticsSnapshotModel.id == protected_snapshot.id,
                )
            )
        assert removable.id not in owner_jobs
        assert protected.id in owner_jobs
        assert len(owner_jobs) == 2
        assert other_job == other.id
        assert retained_snapshot == protected_snapshot.id
    finally:
        await _delete_users(database, owner_id, other_id)
        await database.dispose()
