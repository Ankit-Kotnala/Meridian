"""PostgreSQL integration coverage for Career Record persistence and ownership."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text

from careeros.foundation.config import DatabaseOptions
from careeros.foundation.database import Database
from careeros.modules.career_record.application.models import (
    EvidenceFilter,
    EvidenceRecord,
    ProposalFilter,
)
from careeros.modules.career_record.domain import (
    AchievementDraft,
    AchievementMetric,
    AchievementStatus,
    AttachmentStatus,
    AuditAction,
    CareerAuditEvent,
    CareerEntity,
    CareerEntityKind,
    CareerProfile,
    CareerRecordConflict,
    CareerRecordIdempotencyConflict,
    ConflictStatus,
    EmploymentType,
    EntitySkillLink,
    EvidenceAttachment,
    EvidenceAuthority,
    EvidenceConflict,
    EvidenceConflictKind,
    EvidenceEntityLink,
    EvidenceInputKind,
    EvidenceItem,
    EvidenceLifecycle,
    EvidenceMetric,
    EvidenceRevision,
    EvidenceSkillLink,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceStateTransition,
    EvidenceStrength,
    EvidenceType,
    EvidenceUsage,
    ImportProposal,
    MetricPrecision,
    PartialDate,
    ProposalStatus,
    ReminderCadence,
    ReminderPreferences,
    ResumeProvenance,
    Skill,
    SkillProficiency,
)
from careeros.modules.career_record.infrastructure.models import (
    CareerAuditEventModel,
    EvidenceEntityLinkModel,
    EvidenceItemModel,
    EvidenceRevisionModel,
)
from careeros.modules.career_record.infrastructure.repository import (
    SqlAlchemyCareerRecordUnitOfWorkFactory,
)
from careeros.modules.identity.infrastructure.models import UserModel


def _profile(owner_user_id: UUID, now: datetime) -> CareerProfile:
    return CareerProfile(
        id=uuid4(),
        owner_user_id=owner_user_id,
        professional_headline="Principal engineer",
        summary="Builds secure product systems.",
        work_authorization=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _experience(owner_user_id: UUID, profile_id: UUID, now: datetime) -> CareerEntity:
    return CareerEntity(
        id=uuid4(),
        owner_user_id=owner_user_id,
        profile_id=profile_id,
        kind=CareerEntityKind.EXPERIENCE,
        title="Principal Engineer",
        organization="Example Systems",
        description="Owned a platform migration.",
        official_title="Staff Engineer",
        display_title="Principal Engineer",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
        external_url=None,
        start_date=PartialDate(2021),
        end_date=None,
        is_current=True,
        sort_order=0,
        group_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _skill(owner_user_id: UUID, profile_id: UUID, name: str, order: int, now: datetime) -> Skill:
    return Skill(
        id=uuid4(),
        owner_user_id=owner_user_id,
        profile_id=profile_id,
        name=name,
        category="Engineering",
        proficiency=SkillProficiency.ADVANCED,
        sort_order=order,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _evidence_record(
    owner_user_id: UUID,
    now: datetime,
    *,
    title: str,
    statement: str,
    with_attachment: bool,
    evidence_type: EvidenceType = EvidenceType.ACHIEVEMENT,
) -> EvidenceRecord:
    evidence_id = uuid4()
    revision_id = uuid4()
    item = EvidenceItem(
        id=evidence_id,
        owner_user_id=owner_user_id,
        lifecycle=EvidenceLifecycle.ACTIVE,
        current_revision=1,
        version=1,
        created_at=now,
        updated_at=now,
    )
    revision = EvidenceRevision(
        id=revision_id,
        owner_user_id=owner_user_id,
        evidence_id=evidence_id,
        revision=1,
        evidence_type=evidence_type,
        title=title,
        statement=statement,
        context="Production migration",
        organization="Example Systems",
        project="CareerOS",
        start_date=PartialDate(2023),
        end_date=PartialDate(2024, 6),
        strength=EvidenceStrength.SUPPORTED,
        input_kind=EvidenceInputKind.MANUAL,
        created_at=now,
    )
    transition = EvidenceStateTransition(
        id=uuid4(),
        owner_user_id=owner_user_id,
        evidence_id=evidence_id,
        from_revision_id=None,
        to_revision_id=revision_id,
        previous_strength=None,
        next_strength=EvidenceStrength.SUPPORTED,
        authority=EvidenceAuthority.DETERMINISTIC_POLICY,
        reason_code="initial_policy_evaluation",
        actor_user_id=owner_user_id,
        verifier_reference=None,
        request_id="integration-create",
        trace_id="a" * 32,
        created_at=now,
    )
    sources = [
        EvidenceSource(
            id=uuid4(),
            owner_user_id=owner_user_id,
            evidence_revision_id=revision_id,
            kind=EvidenceSourceKind.USER_ATTESTATION,
            label="Owner attestation",
            provenance=None,
            attachment_id=None,
            external_url=None,
            available=True,
            exact_span_validated=False,
            created_at=now,
        )
    ]
    attachments: tuple[EvidenceAttachment, ...] = ()
    if with_attachment:
        attachment = EvidenceAttachment(
            id=uuid4(),
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            display_filename="support.pdf",
            media_type="application/pdf",
            size_bytes=512,
            content_sha256=None,
            status=AttachmentStatus.PENDING,
            version=1,
            created_at=now,
            updated_at=now,
        )
        attachments = (attachment,)
        sources.append(
            EvidenceSource(
                id=uuid4(),
                owner_user_id=owner_user_id,
                evidence_revision_id=revision_id,
                kind=EvidenceSourceKind.ATTACHMENT,
                label="Supporting document",
                provenance=None,
                attachment_id=attachment.id,
                external_url=None,
                available=False,
                exact_span_validated=False,
                created_at=now,
            )
        )
    metric = EvidenceMetric(
        id=uuid4(),
        owner_user_id=owner_user_id,
        evidence_revision_id=revision_id,
        name="Migration completion",
        value=Decimal("42.5"),
        value_max=None,
        unit="percent",
        currency=None,
        period="2024 H1",
        baseline="Prior release",
        comparator=None,
        comparison_applicable=True,
        precision=MetricPrecision.EXACT,
        attribution="Owner-confirmed delivery record",
        created_at=now,
    )
    usage = EvidenceUsage(
        id=uuid4(),
        owner_user_id=owner_user_id,
        evidence_id=evidence_id,
        consumer_kind="resume_version",
        consumer_id=uuid4(),
        purpose="achievement bullet",
        created_at=now,
    )
    return EvidenceRecord(
        item=item,
        revision=revision,
        revisions=(revision,),
        transitions=(transition,),
        sources=tuple(sources),
        metrics=(metric,),
        attachments=attachments,
        conflicts=(),
        entity_ids=(),
        skill_ids=(),
        usage=(usage,),
    )


@pytest.mark.asyncio
async def test_analytics_growth_includes_only_achievement_evidence() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyCareerRecordUnitOfWorkFactory(database)
    owner_user_id, cleanup_user_id = uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    achievement = _evidence_record(
        owner_user_id,
        now,
        title="Eligible achievement",
        statement="Delivered the reviewed migration.",
        with_attachment=False,
    )
    note = _evidence_record(
        owner_user_id,
        now + timedelta(seconds=1),
        title="Eligible note",
        statement="Private context that is not an achievement.",
        with_attachment=False,
        evidence_type=EvidenceType.NOTE,
    )

    try:
        await _add_users(database, (owner_user_id, cleanup_user_id), now)
        async with factory() as uow:
            await uow.add_evidence(achievement)
            await uow.add_evidence(note)
            await uow.commit()
        async with factory() as uow:
            growth = await uow.list_analytics_growth(
                owner_user_id,
                date(2026, 1, 1),
                date(2099, 12, 31),
                101,
            )

        assert [point.evidence_revision_id for point in growth] == [achievement.revision.id]
        assert growth[0].category == EvidenceType.ACHIEVEMENT.value
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_user_id, cleanup_user_id)))
            )
            await session.commit()
        await database.dispose()


async def _add_users(database: Database, user_ids: tuple[UUID, UUID], now: datetime) -> None:
    async with database.session() as session:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    email_normalized=f"career-record-{user_id.hex}@example.com",
                    password_hash=None,
                    status="active",
                    email_verified_at=now,
                    auth_version=1,
                    created_at=now,
                    updated_at=now,
                )
                for user_id in user_ids
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_repository_round_trips_owned_profile_proposal_and_evidence_graph() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyCareerRecordUnitOfWorkFactory(database)
    owner_user_id, other_user_id = uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    profile = _profile(owner_user_id, now)
    other_profile = _profile(other_user_id, now)
    entity = _experience(owner_user_id, profile.id, now)
    skill_one = _skill(owner_user_id, profile.id, "Architecture", 0, now)
    skill_two = _skill(owner_user_id, profile.id, "Security", 1, now)
    proposal_entity = _experience(owner_user_id, profile.id, now)
    proposal_entity.title = "Imported Principal Engineer"
    proposal = ImportProposal(
        id=uuid4(),
        owner_user_id=owner_user_id,
        profile_id=profile.id,
        target_entity_id=None,
        proposed_entity=proposal_entity,
        provenance=ResumeProvenance(
            document_id=uuid4(),
            snapshot_id=uuid4(),
            snapshot_revision=3,
            schema_version="canonical-resume/v1",
            parser_version="local-parser/1",
            block_id=uuid4(),
            page=2,
            start_offset=10,
            end_offset=42,
            source_sha256=b"p" * 32,
            review_excerpt="Principal Engineer at Example Systems",
        ),
        status=ProposalStatus.PENDING,
        conflict_code=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    first_evidence = _evidence_record(
        owner_user_id,
        now,
        title="Platform migration",
        statement="Delivered 100%_growth migration coverage for the release.",
        with_attachment=True,
    )
    second_evidence = _evidence_record(
        owner_user_id,
        now + timedelta(seconds=1),
        title="Conflicting migration record",
        statement="Delivered an alternate migration result.",
        with_attachment=False,
    )

    try:
        await _add_users(database, (owner_user_id, other_user_id), now)
        async with factory() as uow:
            await uow.add_profile(profile)
            await uow.add_profile(other_profile)
            await uow.add_entity(entity)
            await uow.add_skill(skill_one)
            await uow.add_skill(skill_two)
            await uow.add_entity_skill_link(
                EntitySkillLink(uuid4(), owner_user_id, entity.id, skill_one.id, now)
            )
            await uow.add_proposal(proposal)
            await uow.add_evidence(first_evidence)
            await uow.add_evidence(second_evidence)
            await uow.add_evidence_entity_link(
                EvidenceEntityLink(uuid4(), owner_user_id, first_evidence.id, entity.id, now)
            )
            await uow.add_evidence_skill_link(
                EvidenceSkillLink(uuid4(), owner_user_id, first_evidence.id, skill_one.id, now)
            )
            await uow.add_conflict(
                EvidenceConflict(
                    id=uuid4(),
                    owner_user_id=owner_user_id,
                    evidence_id=second_evidence.id,
                    conflicting_evidence_id=first_evidence.id,
                    kind=EvidenceConflictKind.METRIC,
                    code="metric_overlap",
                    status=ConflictStatus.OPEN,
                    resolution=None,
                    version=1,
                    created_at=now + timedelta(seconds=2),
                    updated_at=now + timedelta(seconds=2),
                )
            )
            await uow.add_audit(
                CareerAuditEvent(
                    id=uuid4(),
                    owner_user_id=owner_user_id,
                    actor_user_id=owner_user_id,
                    action=AuditAction.EVIDENCE_CREATED,
                    target_kind="evidence",
                    target_id=first_evidence.id,
                    request_id="integration-create",
                    trace_id="a" * 32,
                    details=(("next_strength", EvidenceStrength.SUPPORTED.value),),
                    created_at=now,
                )
            )
            await uow.commit()

        async with factory() as uow:
            persisted_entity = await uow.get_entity(owner_user_id, entity.id)
            assert persisted_entity is not None
            assert persisted_entity.start_date == PartialDate(2021)
            assert persisted_entity.start_date.month is None
            assert await uow.get_entity(other_user_id, entity.id) is None
            assert [
                link.skill_id
                for link in await uow.list_entity_skill_links(owner_user_id, entity.id)
            ] == [skill_one.id]
            replacement = EntitySkillLink(
                uuid4(), owner_user_id, entity.id, skill_two.id, now + timedelta(seconds=3)
            )
            await uow.replace_entity_skill_links(owner_user_id, entity.id, (replacement,))
            stored_proposal = await uow.get_proposal(owner_user_id, proposal.id, for_update=True)
            assert stored_proposal is not None
            stored_proposal.proposed_entity.title = "Edited imported title"
            stored_proposal.version += 1
            stored_proposal.updated_at = now + timedelta(seconds=3)
            await uow.save_proposal(stored_proposal)
            await uow.commit()

        async with factory() as uow:
            links = await uow.list_entity_skill_links(owner_user_id, entity.id)
            assert [link.skill_id for link in links] == [skill_two.id]
            proposals = await uow.list_proposals(
                owner_user_id, ProposalFilter(status=ProposalStatus.PENDING), None, 10
            )
            assert proposals[0].proposed_entity.title == "Edited imported title"
            assert proposals[0].proposed_entity.start_date == PartialDate(2021)
            assert proposals[0].provenance.source_sha256 == b"p" * 32

            record = await uow.get_evidence(owner_user_id, first_evidence.id)
            assert record is not None
            assert record.revision.start_date == PartialDate(2023)
            assert record.revision.start_date.month is None
            assert record.metrics[0].value == Decimal("42.5")
            assert record.attachments[0].content_sha256 is None
            assert record.attachments[0].status is AttachmentStatus.PENDING
            assert len(record.sources) == 2
            assert len(record.usage) == 1
            assert record.conflicts[0].evidence_id == second_evidence.id
            assert await uow.get_evidence(other_user_id, first_evidence.id) is None
            matches = await uow.list_evidence(
                owner_user_id, EvidenceFilter(query="100%_growth"), None, 10
            )
            assert [match.id for match in matches] == [first_evidence.id]
            conflicted = await uow.list_evidence(
                owner_user_id,
                EvidenceFilter(conflict_status=ConflictStatus.OPEN),
                None,
                10,
            )
            assert {match.id for match in conflicted} == {
                first_evidence.id,
                second_evidence.id,
            }

        async with database.session() as session:
            phase_two_targets = set(
                (
                    await session.scalars(
                        text(
                            "SELECT confrelid::regclass::text "
                            "FROM pg_constraint "
                            "WHERE contype = 'f' AND conrelid IN "
                            "('career_import_proposals'::regclass, 'evidence_sources'::regclass)"
                        )
                    )
                ).all()
            )
            assert phase_two_targets.isdisjoint({"source_documents", "canonical_resume_snapshots"})

        async with factory() as uow:
            await uow.delete_entity(owner_user_id, entity.id)
            await uow.delete_skill(owner_user_id, skill_one.id)
            await uow.commit()

        async with database.session() as session:
            assert (
                await session.scalar(
                    select(EvidenceEntityLinkModel).where(
                        EvidenceEntityLinkModel.owner_user_id == owner_user_id,
                        EvidenceEntityLinkModel.evidence_id == first_evidence.id,
                    )
                )
                is None
            )
            assert (
                await session.scalar(
                    select(EvidenceItemModel.id).where(
                        EvidenceItemModel.id == first_evidence.id,
                        EvidenceItemModel.owner_user_id == owner_user_id,
                    )
                )
                == first_evidence.id
            )
            assert (
                await session.scalar(
                    select(EvidenceRevisionModel.id).where(
                        EvidenceRevisionModel.evidence_id == first_evidence.id,
                        EvidenceRevisionModel.owner_user_id == owner_user_id,
                    )
                )
                == first_evidence.revision.id
            )
            audit = await session.scalar(
                select(CareerAuditEventModel).where(
                    CareerAuditEventModel.owner_user_id == owner_user_id,
                    CareerAuditEventModel.target_id == first_evidence.id,
                )
            )
            assert audit is not None
            assert audit.details == {"next_strength": "supported"}
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_user_id, other_user_id)))
            )
            await session.commit()
        await database.dispose()


@pytest.mark.asyncio
async def test_repository_persists_achievement_conversion_and_reminders() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyCareerRecordUnitOfWorkFactory(database)
    owner_user_id, cleanup_user_id = uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    profile = _profile(owner_user_id, now)
    evidence = _evidence_record(
        owner_user_id,
        now,
        title="Achievement evidence",
        statement="Completed a production migration.",
        with_attachment=False,
    )
    achievement = AchievementDraft(
        id=uuid4(),
        owner_user_id=owner_user_id,
        profile_id=profile.id,
        title="Production migration",
        delivered="Migrated the production workload.",
        problem="Legacy platform risk",
        audience="Platform customers",
        measurement="Deployment completion",
        effect="Safer releases",
        collaboration="Platform team",
        methods="Incremental cutover",
        entity_id=None,
        metric=AchievementMetric(
            name="Completion",
            value=Decimal("100"),
            value_max=None,
            unit="percent",
            currency=None,
            period="2024",
            baseline="Legacy deployment",
            comparator=None,
            comparison_applicable=True,
            precision=MetricPrecision.EXACT,
            attribution="Owner-confirmed delivery record",
        ),
        reminder_cadence=ReminderCadence.QUARTERLY,
        remind_at=None,
        status=AchievementStatus.DRAFT,
        converted_evidence_id=None,
        conversion_idempotency_key=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    preferences = ReminderPreferences(
        id=uuid4(),
        owner_user_id=owner_user_id,
        enabled=True,
        day_of_month=15,
        timezone="Asia/Kolkata",
        version=1,
        created_at=now,
        updated_at=now,
    )
    duplicate_achievement = replace(achievement, id=uuid4())

    try:
        await _add_users(database, (owner_user_id, cleanup_user_id), now)
        async with factory() as uow:
            await uow.add_profile(profile)
            await uow.add_evidence(evidence)
            await uow.add_achievement(achievement)
            await uow.add_achievement(duplicate_achievement)
            await uow.add_reminder_preferences(preferences)
            await uow.commit()

        async with factory() as uow:
            stored = await uow.get_achievement(owner_user_id, achievement.id, for_update=True)
            assert stored is not None
            assert stored.metric is not None
            assert stored.metric.value == Decimal("100")
            stored.convert(evidence.id, "integration-conversion-key", now + timedelta(seconds=1))
            await uow.save_achievement(stored)
            await uow.commit()

        with pytest.raises(CareerRecordIdempotencyConflict):
            async with factory() as uow:
                duplicate = await uow.get_achievement(
                    owner_user_id, duplicate_achievement.id, for_update=True
                )
                assert duplicate is not None
                duplicate.convert(
                    evidence.id,
                    "integration-conversion-key",
                    now + timedelta(seconds=2),
                )
                await uow.save_achievement(duplicate)
                await uow.commit()

        async with factory() as uow:
            converted = await uow.find_achievement_conversion(
                owner_user_id, "integration-conversion-key"
            )
            assert converted is not None
            assert converted.converted_evidence_id == evidence.id
            assert (
                await uow.find_achievement_conversion(cleanup_user_id, "integration-conversion-key")
                is None
            )
            reminder = await uow.get_reminder_preferences(owner_user_id)
            assert reminder is not None
            assert reminder.timezone == "Asia/Kolkata"
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_user_id, cleanup_user_id)))
            )
            await session.commit()
        await database.dispose()


@pytest.mark.asyncio
async def test_concurrent_profile_creation_has_one_winner_and_truthful_reread() -> None:
    database_url = os.environ.get("CAREEROS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("CAREEROS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database = Database(DatabaseOptions(url=database_url, pool_size=2, max_overflow=0))
    factory = SqlAlchemyCareerRecordUnitOfWorkFactory(database)
    owner_user_id, cleanup_user_id = uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    candidates = (_profile(owner_user_id, now), _profile(owner_user_id, now))

    async def create(candidate: CareerProfile) -> bool:
        try:
            async with factory() as uow:
                await uow.add_profile(candidate)
                await uow.commit()
        except CareerRecordConflict:
            return False
        return True

    try:
        await _add_users(database, (owner_user_id, cleanup_user_id), now)
        outcomes = await asyncio.gather(*(create(candidate) for candidate in candidates))
        assert sorted(outcomes) == [False, True]
        async with factory() as uow:
            stored = await uow.get_profile(owner_user_id)
            assert stored is not None
            assert stored.id in {candidate.id for candidate in candidates}
    finally:
        async with database.session() as session:
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_user_id, cleanup_user_id)))
            )
            await session.commit()
        await database.dispose()
