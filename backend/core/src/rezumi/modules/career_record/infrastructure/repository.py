"""Async SQLAlchemy unit of work for the Career Record module."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from types import TracebackType
from typing import Any, NoReturn
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rezumi.foundation.database import Database
from rezumi.modules.career_record.application.models import (
    CareerRecordAnalyticsGrowthPoint,
    CareerRecordAnalyticsSourceState,
    EvidenceFilter,
    EvidenceRecord,
    PageCursor,
    ProposalFilter,
)
from rezumi.modules.career_record.application.ports import CareerRecordUnitOfWork
from rezumi.modules.career_record.domain import (
    AchievementDraft,
    AchievementMetric,
    AchievementStatus,
    AttachmentStatus,
    CareerAuditEvent,
    CareerEntity,
    CareerEntityConfirmation,
    CareerEntityKind,
    CareerEntityRelationship,
    CareerFieldProvenance,
    CareerFieldTarget,
    CareerProfile,
    CareerRecordConflict,
    CareerRecordIdempotencyConflict,
    CareerRelationshipKind,
    CareerSkillConfirmation,
    ConfirmationState,
    ConflictResolution,
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
    PersonalFact,
    PersonalFactKind,
    ProposalStatus,
    ReminderCadence,
    ReminderPreferences,
    ResumeProvenance,
    SemanticCandidateKind,
    SemanticFieldOrigin,
    SemanticImportAnchor,
    SemanticImportField,
    SemanticImportProposal,
    SemanticImportStatus,
    SemanticImportTarget,
    Skill,
    SkillProficiency,
)

from .models import (
    AchievementDraftModel,
    CareerAuditEventModel,
    CareerEntityConfirmationModel,
    CareerEntityModel,
    CareerEntityRelationshipModel,
    CareerEntitySkillModel,
    CareerFieldProvenanceModel,
    CareerImportProposalModel,
    CareerPersonalFactModel,
    CareerProfileModel,
    CareerSemanticImportProposalModel,
    CareerSkillConfirmationModel,
    CareerSkillModel,
    EvidenceAttachmentModel,
    EvidenceConflictModel,
    EvidenceEntityLinkModel,
    EvidenceItemModel,
    EvidenceMetricModel,
    EvidenceRevisionModel,
    EvidenceSkillLinkModel,
    EvidenceSourceModel,
    EvidenceStateTransitionModel,
    EvidenceUsageModel,
    ReminderPreferencesModel,
)


class SqlAlchemyCareerRecordUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyCareerRecordUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("career record unit of work is not active")
        return self._session

    async def get_profile(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> CareerProfile | None:
        statement = select(CareerProfileModel).where(
            CareerProfileModel.owner_user_id == owner_user_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _profile(model) if model is not None else None

    async def add_profile(self, profile: CareerProfile) -> None:
        self.session.add(CareerProfileModel(**_profile_values(profile)))
        await self._flush()

    async def save_profile(self, profile: CareerProfile) -> None:
        await self._execute(
            update(CareerProfileModel)
            .where(
                CareerProfileModel.owner_user_id == profile.owner_user_id,
                CareerProfileModel.id == profile.id,
            )
            .values(**_profile_values(profile, include_identity=False))
        )

    async def list_entities(
        self, owner_user_id: UUID, profile_id: UUID, *, for_update: bool = False
    ) -> list[CareerEntity]:
        statement = (
            select(CareerEntityModel)
            .where(
                CareerEntityModel.owner_user_id == owner_user_id,
                CareerEntityModel.profile_id == profile_id,
            )
            .order_by(CareerEntityModel.sort_order, CareerEntityModel.id)
        )
        if for_update:
            statement = statement.with_for_update()
        models = (await self.session.scalars(statement)).all()
        return [_entity(model) for model in models]

    async def get_entity(
        self, owner_user_id: UUID, entity_id: UUID, *, for_update: bool = False
    ) -> CareerEntity | None:
        statement = select(CareerEntityModel).where(
            CareerEntityModel.owner_user_id == owner_user_id,
            CareerEntityModel.id == entity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _entity(model) if model is not None else None

    async def add_entity(self, entity: CareerEntity) -> None:
        self.session.add(CareerEntityModel(**_entity_values(entity)))
        await self._flush()

    async def save_entity(self, entity: CareerEntity) -> None:
        await self._execute(
            update(CareerEntityModel)
            .where(
                CareerEntityModel.owner_user_id == entity.owner_user_id,
                CareerEntityModel.id == entity.id,
            )
            .values(**_entity_values(entity, include_identity=False))
        )

    async def delete_entity(self, owner_user_id: UUID, entity_id: UUID) -> None:
        await self._execute(
            delete(CareerEntityModel).where(
                CareerEntityModel.owner_user_id == owner_user_id,
                CareerEntityModel.id == entity_id,
            )
        )

    async def get_entity_confirmation(
        self, owner_user_id: UUID, entity_id: UUID, *, for_update: bool = False
    ) -> CareerEntityConfirmation | None:
        statement = select(CareerEntityConfirmationModel).where(
            CareerEntityConfirmationModel.owner_user_id == owner_user_id,
            CareerEntityConfirmationModel.entity_id == entity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _entity_confirmation(model) if model is not None else None

    async def list_entity_confirmations(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerEntityConfirmation]:
        models = (
            await self.session.scalars(
                select(CareerEntityConfirmationModel)
                .join(
                    CareerEntityModel,
                    (CareerEntityModel.owner_user_id == CareerEntityConfirmationModel.owner_user_id)
                    & (CareerEntityModel.id == CareerEntityConfirmationModel.entity_id),
                )
                .where(
                    CareerEntityConfirmationModel.owner_user_id == owner_user_id,
                    CareerEntityModel.profile_id == profile_id,
                )
                .order_by(CareerEntityConfirmationModel.entity_id)
            )
        ).all()
        return [_entity_confirmation(model) for model in models]

    async def add_entity_confirmation(self, confirmation: CareerEntityConfirmation) -> None:
        self.session.add(CareerEntityConfirmationModel(**_entity_confirmation_values(confirmation)))
        await self._flush()

    async def save_entity_confirmation(self, confirmation: CareerEntityConfirmation) -> None:
        await self._execute(
            update(CareerEntityConfirmationModel)
            .where(
                CareerEntityConfirmationModel.owner_user_id == confirmation.owner_user_id,
                CareerEntityConfirmationModel.entity_id == confirmation.entity_id,
            )
            .values(**_entity_confirmation_values(confirmation, include_identity=False))
        )

    async def list_personal_facts(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[PersonalFact]:
        models = (
            await self.session.scalars(
                select(CareerPersonalFactModel)
                .where(
                    CareerPersonalFactModel.owner_user_id == owner_user_id,
                    CareerPersonalFactModel.profile_id == profile_id,
                )
                .order_by(
                    CareerPersonalFactModel.kind,
                    CareerPersonalFactModel.is_primary.desc(),
                    CareerPersonalFactModel.created_at,
                    CareerPersonalFactModel.id,
                )
            )
        ).all()
        return [_personal_fact(model) for model in models]

    async def get_personal_fact(
        self, owner_user_id: UUID, fact_id: UUID, *, for_update: bool = False
    ) -> PersonalFact | None:
        statement = select(CareerPersonalFactModel).where(
            CareerPersonalFactModel.owner_user_id == owner_user_id,
            CareerPersonalFactModel.id == fact_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _personal_fact(model) if model is not None else None

    async def add_personal_fact(self, fact: PersonalFact) -> None:
        self.session.add(CareerPersonalFactModel(**_personal_fact_values(fact)))
        await self._flush()

    async def save_personal_fact(self, fact: PersonalFact) -> None:
        await self._execute(
            update(CareerPersonalFactModel)
            .where(
                CareerPersonalFactModel.owner_user_id == fact.owner_user_id,
                CareerPersonalFactModel.id == fact.id,
            )
            .values(**_personal_fact_values(fact, include_identity=False))
        )

    async def delete_personal_fact(self, owner_user_id: UUID, fact_id: UUID) -> None:
        await self._execute(
            delete(CareerPersonalFactModel).where(
                CareerPersonalFactModel.owner_user_id == owner_user_id,
                CareerPersonalFactModel.id == fact_id,
            )
        )

    async def add_field_provenance(self, provenance: CareerFieldProvenance) -> None:
        self.session.add(CareerFieldProvenanceModel(**_field_provenance_values(provenance)))
        await self._flush()

    async def list_field_provenance(
        self, owner_user_id: UUID, target_id: UUID
    ) -> list[CareerFieldProvenance]:
        models = (
            await self.session.scalars(
                select(CareerFieldProvenanceModel)
                .where(
                    CareerFieldProvenanceModel.owner_user_id == owner_user_id,
                    or_(
                        CareerFieldProvenanceModel.personal_fact_id == target_id,
                        CareerFieldProvenanceModel.entity_id == target_id,
                        CareerFieldProvenanceModel.skill_id == target_id,
                    ),
                )
                .order_by(
                    CareerFieldProvenanceModel.created_at,
                    CareerFieldProvenanceModel.id,
                )
            )
        ).all()
        return [_field_provenance(model) for model in models]

    async def add_entity_relationship(self, relationship: CareerEntityRelationship) -> None:
        self.session.add(CareerEntityRelationshipModel(**_entity_relationship_values(relationship)))
        await self._flush()

    async def get_entity_relationship(
        self, owner_user_id: UUID, relationship_id: UUID
    ) -> CareerEntityRelationship | None:
        model = await self.session.scalar(
            select(CareerEntityRelationshipModel).where(
                CareerEntityRelationshipModel.owner_user_id == owner_user_id,
                CareerEntityRelationshipModel.id == relationship_id,
            )
        )
        return _entity_relationship(model) if model is not None else None

    async def list_entity_relationships(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerEntityRelationship]:
        models = (
            await self.session.scalars(
                select(CareerEntityRelationshipModel)
                .where(
                    CareerEntityRelationshipModel.owner_user_id == owner_user_id,
                    CareerEntityRelationshipModel.profile_id == profile_id,
                )
                .order_by(
                    CareerEntityRelationshipModel.created_at,
                    CareerEntityRelationshipModel.id,
                )
            )
        ).all()
        return [_entity_relationship(model) for model in models]

    async def delete_entity_relationship(self, owner_user_id: UUID, relationship_id: UUID) -> None:
        await self._execute(
            delete(CareerEntityRelationshipModel).where(
                CareerEntityRelationshipModel.owner_user_id == owner_user_id,
                CareerEntityRelationshipModel.id == relationship_id,
            )
        )

    async def list_skills(self, owner_user_id: UUID, profile_id: UUID) -> list[Skill]:
        models = (
            await self.session.scalars(
                select(CareerSkillModel)
                .where(
                    CareerSkillModel.owner_user_id == owner_user_id,
                    CareerSkillModel.profile_id == profile_id,
                )
                .order_by(CareerSkillModel.sort_order, CareerSkillModel.id)
            )
        ).all()
        return [_skill(model) for model in models]

    async def get_skill(
        self, owner_user_id: UUID, skill_id: UUID, *, for_update: bool = False
    ) -> Skill | None:
        statement = select(CareerSkillModel).where(
            CareerSkillModel.owner_user_id == owner_user_id,
            CareerSkillModel.id == skill_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _skill(model) if model is not None else None

    async def add_skill(self, skill: Skill) -> None:
        self.session.add(CareerSkillModel(**_skill_values(skill)))
        await self._flush()

    async def save_skill(self, skill: Skill) -> None:
        await self._execute(
            update(CareerSkillModel)
            .where(
                CareerSkillModel.owner_user_id == skill.owner_user_id,
                CareerSkillModel.id == skill.id,
            )
            .values(**_skill_values(skill, include_identity=False))
        )

    async def delete_skill(self, owner_user_id: UUID, skill_id: UUID) -> None:
        await self._execute(
            delete(CareerSkillModel).where(
                CareerSkillModel.owner_user_id == owner_user_id,
                CareerSkillModel.id == skill_id,
            )
        )

    async def get_skill_confirmation(
        self, owner_user_id: UUID, skill_id: UUID, *, for_update: bool = False
    ) -> CareerSkillConfirmation | None:
        statement = select(CareerSkillConfirmationModel).where(
            CareerSkillConfirmationModel.owner_user_id == owner_user_id,
            CareerSkillConfirmationModel.skill_id == skill_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _skill_confirmation(model) if model is not None else None

    async def list_skill_confirmations(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerSkillConfirmation]:
        models = (
            await self.session.scalars(
                select(CareerSkillConfirmationModel)
                .join(
                    CareerSkillModel,
                    (CareerSkillModel.owner_user_id == CareerSkillConfirmationModel.owner_user_id)
                    & (CareerSkillModel.id == CareerSkillConfirmationModel.skill_id),
                )
                .where(
                    CareerSkillConfirmationModel.owner_user_id == owner_user_id,
                    CareerSkillModel.profile_id == profile_id,
                )
                .order_by(CareerSkillConfirmationModel.skill_id)
            )
        ).all()
        return [_skill_confirmation(model) for model in models]

    async def add_skill_confirmation(self, confirmation: CareerSkillConfirmation) -> None:
        self.session.add(CareerSkillConfirmationModel(**_skill_confirmation_values(confirmation)))
        await self._flush()

    async def save_skill_confirmation(self, confirmation: CareerSkillConfirmation) -> None:
        await self._execute(
            update(CareerSkillConfirmationModel)
            .where(
                CareerSkillConfirmationModel.owner_user_id == confirmation.owner_user_id,
                CareerSkillConfirmationModel.skill_id == confirmation.skill_id,
            )
            .values(**_skill_confirmation_values(confirmation, include_identity=False))
        )

    async def add_entity_skill_link(self, link: EntitySkillLink) -> None:
        self.session.add(_entity_skill_model(link))

    async def list_entity_skill_links(
        self, owner_user_id: UUID, entity_id: UUID
    ) -> list[EntitySkillLink]:
        models = (
            await self.session.scalars(
                select(CareerEntitySkillModel)
                .where(
                    CareerEntitySkillModel.owner_user_id == owner_user_id,
                    CareerEntitySkillModel.entity_id == entity_id,
                )
                .order_by(CareerEntitySkillModel.created_at, CareerEntitySkillModel.id)
            )
        ).all()
        return [_entity_skill(model) for model in models]

    async def list_entity_skill_links_for_owner(
        self,
        owner_user_id: UUID,
        entity_ids: tuple[UUID, ...] | None = None,
    ) -> list[EntitySkillLink]:
        statement = select(CareerEntitySkillModel).where(
            CareerEntitySkillModel.owner_user_id == owner_user_id
        )
        if entity_ids:
            statement = statement.where(CareerEntitySkillModel.entity_id.in_(entity_ids))
        models = (
            await self.session.scalars(
                statement.order_by(
                    CareerEntitySkillModel.entity_id,
                    CareerEntitySkillModel.created_at,
                    CareerEntitySkillModel.id,
                )
            )
        ).all()
        return [_entity_skill(model) for model in models]

    async def replace_entity_skill_links(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        links: Sequence[EntitySkillLink],
    ) -> None:
        if any(
            link.owner_user_id != owner_user_id or link.entity_id != entity_id for link in links
        ):
            raise CareerRecordConflict("entity-skill link ownership does not match")
        await self._execute(
            delete(CareerEntitySkillModel).where(
                CareerEntitySkillModel.owner_user_id == owner_user_id,
                CareerEntitySkillModel.entity_id == entity_id,
            )
        )
        self.session.add_all([_entity_skill_model(link) for link in links])

    async def get_proposal(
        self, owner_user_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> ImportProposal | None:
        statement = select(CareerImportProposalModel).where(
            CareerImportProposalModel.owner_user_id == owner_user_id,
            CareerImportProposalModel.id == proposal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _proposal(model) if model is not None else None

    async def list_proposals(
        self,
        owner_user_id: UUID,
        filter_by: ProposalFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ImportProposal]:
        statement = select(CareerImportProposalModel).where(
            CareerImportProposalModel.owner_user_id == owner_user_id
        )
        if filter_by.status is not None:
            statement = statement.where(CareerImportProposalModel.status == filter_by.status.value)
        if after is not None:
            statement = statement.where(
                _after_cursor(
                    CareerImportProposalModel.created_at,
                    CareerImportProposalModel.id,
                    after,
                )
            )
        models = (
            await self.session.scalars(
                statement.order_by(
                    CareerImportProposalModel.created_at.desc(),
                    CareerImportProposalModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_proposal(model) for model in models]

    async def add_proposal(self, proposal: ImportProposal) -> None:
        self.session.add(CareerImportProposalModel(**_proposal_values(proposal)))

    async def save_proposal(self, proposal: ImportProposal) -> None:
        await self._execute(
            update(CareerImportProposalModel)
            .where(
                CareerImportProposalModel.owner_user_id == proposal.owner_user_id,
                CareerImportProposalModel.id == proposal.id,
            )
            .values(**_proposal_values(proposal, include_identity=False))
        )

    async def find_semantic_proposal(
        self,
        owner_user_id: UUID,
        snapshot_id: UUID,
        semantic_entity_id: UUID,
    ) -> SemanticImportProposal | None:
        model = await self.session.scalar(
            select(CareerSemanticImportProposalModel).where(
                CareerSemanticImportProposalModel.owner_user_id == owner_user_id,
                CareerSemanticImportProposalModel.snapshot_id == snapshot_id,
                CareerSemanticImportProposalModel.semantic_entity_id == semantic_entity_id,
            )
        )
        return _semantic_proposal(model) if model is not None else None

    async def get_semantic_proposal(
        self, owner_user_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> SemanticImportProposal | None:
        statement = select(CareerSemanticImportProposalModel).where(
            CareerSemanticImportProposalModel.owner_user_id == owner_user_id,
            CareerSemanticImportProposalModel.id == proposal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _semantic_proposal(model) if model is not None else None

    async def list_semantic_proposals(self, owner_user_id: UUID) -> list[SemanticImportProposal]:
        models = (
            await self.session.scalars(
                select(CareerSemanticImportProposalModel)
                .where(CareerSemanticImportProposalModel.owner_user_id == owner_user_id)
                .order_by(
                    CareerSemanticImportProposalModel.created_at.desc(),
                    CareerSemanticImportProposalModel.id.desc(),
                )
            )
        ).all()
        return [_semantic_proposal(model) for model in models]

    async def add_semantic_proposal(self, proposal: SemanticImportProposal) -> None:
        self.session.add(CareerSemanticImportProposalModel(**_semantic_proposal_values(proposal)))
        await self._flush()

    async def save_semantic_proposal(self, proposal: SemanticImportProposal) -> None:
        await self._execute(
            update(CareerSemanticImportProposalModel)
            .where(
                CareerSemanticImportProposalModel.owner_user_id == proposal.owner_user_id,
                CareerSemanticImportProposalModel.id == proposal.id,
            )
            .values(**_semantic_proposal_values(proposal, include_identity=False))
        )

    async def get_evidence(
        self, owner_user_id: UUID, evidence_id: UUID, *, for_update: bool = False
    ) -> EvidenceRecord | None:
        statement = select(EvidenceItemModel).where(
            EvidenceItemModel.owner_user_id == owner_user_id,
            EvidenceItemModel.id == evidence_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        records = await self._evidence_records(owner_user_id, [model])
        return records[0] if records else None

    async def get_evidence_batch(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> list[EvidenceRecord]:
        if not evidence_ids:
            return []
        models = list(
            (
                await self.session.scalars(
                    select(EvidenceItemModel).where(
                        EvidenceItemModel.owner_user_id == owner_user_id,
                        EvidenceItemModel.id.in_(evidence_ids),
                    )
                )
            ).all()
        )
        by_id = {model.id: model for model in models}
        ordered = [by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in by_id]
        return await self._evidence_records(owner_user_id, ordered)

    async def list_evidence(
        self,
        owner_user_id: UUID,
        filter_by: EvidenceFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[EvidenceRecord]:
        current_revision = and_(
            EvidenceRevisionModel.owner_user_id == EvidenceItemModel.owner_user_id,
            EvidenceRevisionModel.evidence_id == EvidenceItemModel.id,
            EvidenceRevisionModel.revision == EvidenceItemModel.current_revision,
        )
        statement = (
            select(EvidenceItemModel)
            .join(EvidenceRevisionModel, current_revision)
            .where(EvidenceItemModel.owner_user_id == owner_user_id)
        )
        if filter_by.lifecycle is not None:
            statement = statement.where(EvidenceItemModel.lifecycle == filter_by.lifecycle.value)
        elif filter_by.include_archived:
            statement = statement.where(EvidenceItemModel.lifecycle.in_(("active", "archived")))
        else:
            statement = statement.where(EvidenceItemModel.lifecycle == "active")
        if filter_by.strength is not None:
            statement = statement.where(EvidenceRevisionModel.strength == filter_by.strength.value)
        if filter_by.query is not None:
            escaped = _escape_like(filter_by.query)
            pattern = f"%{escaped}%"
            statement = statement.where(
                or_(
                    EvidenceRevisionModel.title.ilike(pattern, escape="\\"),
                    EvidenceRevisionModel.statement.ilike(pattern, escape="\\"),
                    EvidenceRevisionModel.context.ilike(pattern, escape="\\"),
                    EvidenceRevisionModel.organization.ilike(pattern, escape="\\"),
                    EvidenceRevisionModel.project.ilike(pattern, escape="\\"),
                )
            )
        if filter_by.conflict_status is not None:
            statement = statement.where(
                exists(
                    select(EvidenceConflictModel.id).where(
                        EvidenceConflictModel.owner_user_id == owner_user_id,
                        EvidenceConflictModel.status == filter_by.conflict_status.value,
                        or_(
                            EvidenceConflictModel.evidence_id == EvidenceItemModel.id,
                            EvidenceConflictModel.conflicting_evidence_id == EvidenceItemModel.id,
                        ),
                    )
                )
            )
        if after is not None:
            statement = statement.where(
                _after_cursor(EvidenceItemModel.created_at, EvidenceItemModel.id, after)
            )
        models = (
            await self.session.scalars(
                statement.order_by(
                    EvidenceItemModel.created_at.desc(), EvidenceItemModel.id.desc()
                ).limit(limit)
            )
        ).all()
        return await self._evidence_records(owner_user_id, list(models))

    async def list_analytics_growth(
        self,
        owner_user_id: UUID,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> list[CareerRecordAnalyticsGrowthPoint]:
        rows = (
            await self.session.execute(
                select(
                    EvidenceRevisionModel.evidence_id,
                    EvidenceRevisionModel.id,
                    EvidenceRevisionModel.evidence_type,
                    EvidenceRevisionModel.created_at,
                )
                .join(
                    EvidenceItemModel,
                    and_(
                        EvidenceItemModel.owner_user_id == EvidenceRevisionModel.owner_user_id,
                        EvidenceItemModel.id == EvidenceRevisionModel.evidence_id,
                        EvidenceItemModel.current_revision == EvidenceRevisionModel.revision,
                    ),
                )
                .where(
                    EvidenceItemModel.owner_user_id == owner_user_id,
                    EvidenceItemModel.lifecycle == EvidenceLifecycle.ACTIVE.value,
                    EvidenceRevisionModel.evidence_type == EvidenceType.ACHIEVEMENT.value,
                    EvidenceRevisionModel.strength.in_(
                        (
                            EvidenceStrength.SUPPORTED.value,
                            EvidenceStrength.CONFIRMED.value,
                            EvidenceStrength.VERIFIED.value,
                        )
                    ),
                    func.date(EvidenceRevisionModel.created_at) >= window_start,
                    func.date(EvidenceRevisionModel.created_at) <= window_end,
                )
                .order_by(
                    EvidenceRevisionModel.created_at.asc(),
                    EvidenceRevisionModel.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [
            CareerRecordAnalyticsGrowthPoint(
                evidence_id=row[0],
                evidence_revision_id=row[1],
                category=row[2],
                occurred_at=row[3],
            )
            for row in rows
        ]

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> CareerRecordAnalyticsSourceState:
        row = (
            await self.session.execute(
                select(
                    func.count(EvidenceRevisionModel.id),
                    func.coalesce(func.sum(EvidenceItemModel.version), 0),
                    func.max(EvidenceItemModel.updated_at),
                    func.max(EvidenceRevisionModel.created_at),
                )
                .join(
                    EvidenceItemModel,
                    and_(
                        EvidenceItemModel.owner_user_id == EvidenceRevisionModel.owner_user_id,
                        EvidenceItemModel.id == EvidenceRevisionModel.evidence_id,
                        EvidenceItemModel.current_revision == EvidenceRevisionModel.revision,
                    ),
                )
                .where(
                    EvidenceItemModel.owner_user_id == owner_user_id,
                    EvidenceItemModel.lifecycle == EvidenceLifecycle.ACTIVE.value,
                    EvidenceRevisionModel.evidence_type == EvidenceType.ACHIEVEMENT.value,
                    EvidenceRevisionModel.strength.in_(
                        (
                            EvidenceStrength.SUPPORTED.value,
                            EvidenceStrength.CONFIRMED.value,
                            EvidenceStrength.VERIFIED.value,
                        )
                    ),
                )
            )
        ).one()
        return CareerRecordAnalyticsSourceState(
            record_count=int(row[0] or 0),
            item_version_sum=int(row[1] or 0),
            max_item_updated_at=row[2],
            max_revision_created_at=row[3],
        )

    async def add_evidence(self, record: EvidenceRecord) -> None:
        _validate_record_ownership(record)
        self.session.add(EvidenceItemModel(**_evidence_item_values(record.item)))
        await self._flush()
        self.session.add_all([_revision_model(value) for value in record.revisions])
        await self._flush()
        self.session.add_all([_attachment_model(value) for value in record.attachments])
        await self._flush()
        self.session.add_all([_transition_model(value) for value in record.transitions])
        self.session.add_all([_source_model(value) for value in record.sources])
        self.session.add_all([_metric_model(value) for value in record.metrics])
        self.session.add_all([_conflict_model(value) for value in record.conflicts])
        self.session.add_all([_usage_model(value) for value in record.usage])

    async def save_evidence_item(self, item: EvidenceItem) -> None:
        await self._execute(
            update(EvidenceItemModel)
            .where(
                EvidenceItemModel.owner_user_id == item.owner_user_id,
                EvidenceItemModel.id == item.id,
            )
            .values(**_evidence_item_values(item, include_identity=False))
        )

    async def append_evidence_revision(
        self,
        item: EvidenceItem,
        revision: EvidenceRevision,
        transition: EvidenceStateTransition,
        sources: Sequence[EvidenceSource],
        metrics: Sequence[EvidenceMetric],
    ) -> None:
        if (
            revision.owner_user_id != item.owner_user_id
            or revision.evidence_id != item.id
            or transition.owner_user_id != item.owner_user_id
            or transition.evidence_id != item.id
            or transition.to_revision_id != revision.id
            or any(
                source.owner_user_id != item.owner_user_id
                or source.evidence_revision_id != revision.id
                for source in sources
            )
            or any(
                metric.owner_user_id != item.owner_user_id
                or metric.evidence_revision_id != revision.id
                for metric in metrics
            )
        ):
            raise CareerRecordConflict("evidence revision ownership does not match")
        await self.save_evidence_item(item)
        self.session.add(_revision_model(revision))
        await self._flush()
        self.session.add(_transition_model(transition))
        self.session.add_all([_source_model(value) for value in sources])
        self.session.add_all([_metric_model(value) for value in metrics])

    async def redact_evidence_content(self, owner_user_id: UUID, evidence_id: UUID) -> None:
        revision_ids = select(EvidenceRevisionModel.id).where(
            EvidenceRevisionModel.owner_user_id == owner_user_id,
            EvidenceRevisionModel.evidence_id == evidence_id,
        )
        operations: tuple[tuple[Any, Any], ...] = (
            (
                EvidenceSourceModel,
                EvidenceSourceModel.evidence_revision_id.in_(revision_ids),
            ),
            (
                EvidenceMetricModel,
                EvidenceMetricModel.evidence_revision_id.in_(revision_ids),
            ),
            (
                EvidenceStateTransitionModel,
                EvidenceStateTransitionModel.evidence_id == evidence_id,
            ),
            (
                EvidenceEntityLinkModel,
                EvidenceEntityLinkModel.evidence_id == evidence_id,
            ),
            (
                EvidenceSkillLinkModel,
                EvidenceSkillLinkModel.evidence_id == evidence_id,
            ),
            (EvidenceUsageModel, EvidenceUsageModel.evidence_id == evidence_id),
            (
                EvidenceConflictModel,
                or_(
                    EvidenceConflictModel.evidence_id == evidence_id,
                    EvidenceConflictModel.conflicting_evidence_id == evidence_id,
                ),
            ),
        )
        for model, predicate in operations:
            await self._execute(
                delete(model).where(model.owner_user_id == owner_user_id, predicate)
            )
        # Keep workflow-owned rows as durable tombstones until account deletion;
        # deleting them here would cascade away object cleanups before private
        # storage is erased. Legacy rows have no workflow admission or object
        # lifecycle and can still be removed with the evidence content.
        await self._execute(
            delete(EvidenceAttachmentModel).where(
                EvidenceAttachmentModel.owner_user_id == owner_user_id,
                EvidenceAttachmentModel.evidence_id == evidence_id,
                EvidenceAttachmentModel.upload_expires_at.is_(None),
            )
        )
        await self._execute(
            delete(EvidenceRevisionModel).where(
                EvidenceRevisionModel.owner_user_id == owner_user_id,
                EvidenceRevisionModel.evidence_id == evidence_id,
            )
        )

    async def add_evidence_entity_link(self, link: EvidenceEntityLink) -> None:
        self.session.add(
            EvidenceEntityLinkModel(
                id=link.id,
                owner_user_id=link.owner_user_id,
                evidence_id=link.evidence_id,
                entity_id=link.entity_id,
                created_at=link.created_at,
            )
        )

    async def add_evidence_skill_link(self, link: EvidenceSkillLink) -> None:
        self.session.add(
            EvidenceSkillLinkModel(
                id=link.id,
                owner_user_id=link.owner_user_id,
                evidence_id=link.evidence_id,
                skill_id=link.skill_id,
                created_at=link.created_at,
            )
        )

    async def add_attachment(self, attachment: EvidenceAttachment) -> None:
        self.session.add(_attachment_model(attachment))

    async def save_attachment(self, attachment: EvidenceAttachment) -> None:
        await self._execute(
            update(EvidenceAttachmentModel)
            .where(
                EvidenceAttachmentModel.owner_user_id == attachment.owner_user_id,
                EvidenceAttachmentModel.id == attachment.id,
            )
            .values(**_attachment_values(attachment, include_identity=False))
        )

    async def add_conflict(self, conflict: EvidenceConflict) -> None:
        self.session.add(_conflict_model(conflict))

    async def get_conflict(
        self, owner_user_id: UUID, conflict_id: UUID, *, for_update: bool = False
    ) -> EvidenceConflict | None:
        statement = select(EvidenceConflictModel).where(
            EvidenceConflictModel.owner_user_id == owner_user_id,
            EvidenceConflictModel.id == conflict_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _conflict(model) if model is not None else None

    async def save_conflict(self, conflict: EvidenceConflict) -> None:
        await self._execute(
            update(EvidenceConflictModel)
            .where(
                EvidenceConflictModel.owner_user_id == conflict.owner_user_id,
                EvidenceConflictModel.id == conflict.id,
            )
            .values(**_conflict_values(conflict, include_identity=False))
        )

    async def _evidence_records(
        self, owner_user_id: UUID, items: list[EvidenceItemModel]
    ) -> list[EvidenceRecord]:
        if not items:
            return []
        evidence_ids = [item.id for item in items]
        revisions = list(
            (
                await self.session.scalars(
                    select(EvidenceRevisionModel)
                    .where(
                        EvidenceRevisionModel.owner_user_id == owner_user_id,
                        EvidenceRevisionModel.evidence_id.in_(evidence_ids),
                    )
                    .order_by(
                        EvidenceRevisionModel.evidence_id,
                        EvidenceRevisionModel.revision,
                    )
                )
            ).all()
        )
        revisions_by_evidence: defaultdict[UUID, list[EvidenceRevisionModel]] = defaultdict(list)
        for revision in revisions:
            revisions_by_evidence[revision.evidence_id].append(revision)
        current_by_evidence: dict[UUID, EvidenceRevisionModel] = {}
        for item in items:
            current = next(
                (
                    revision
                    for revision in revisions_by_evidence[item.id]
                    if revision.revision == item.current_revision
                ),
                None,
            )
            if current is not None:
                current_by_evidence[item.id] = current
        current_revision_ids = [revision.id for revision in current_by_evidence.values()]

        transitions = await self._group_models(
            EvidenceStateTransitionModel,
            EvidenceStateTransitionModel.evidence_id,
            owner_user_id,
            EvidenceStateTransitionModel.evidence_id.in_(evidence_ids),
            EvidenceStateTransitionModel.created_at,
            EvidenceStateTransitionModel.id,
        )
        attachments = await self._group_models(
            EvidenceAttachmentModel,
            EvidenceAttachmentModel.evidence_id,
            owner_user_id,
            and_(
                EvidenceAttachmentModel.evidence_id.in_(evidence_ids),
                EvidenceAttachmentModel.workflow_status != "deleted",
            ),
            EvidenceAttachmentModel.created_at,
            EvidenceAttachmentModel.id,
        )
        usage = await self._group_models(
            EvidenceUsageModel,
            EvidenceUsageModel.evidence_id,
            owner_user_id,
            EvidenceUsageModel.evidence_id.in_(evidence_ids),
            EvidenceUsageModel.created_at,
            EvidenceUsageModel.id,
        )
        entity_links = await self._group_models(
            EvidenceEntityLinkModel,
            EvidenceEntityLinkModel.evidence_id,
            owner_user_id,
            EvidenceEntityLinkModel.evidence_id.in_(evidence_ids),
            EvidenceEntityLinkModel.created_at,
            EvidenceEntityLinkModel.id,
        )
        skill_links = await self._group_models(
            EvidenceSkillLinkModel,
            EvidenceSkillLinkModel.evidence_id,
            owner_user_id,
            EvidenceSkillLinkModel.evidence_id.in_(evidence_ids),
            EvidenceSkillLinkModel.created_at,
            EvidenceSkillLinkModel.id,
        )
        sources_by_revision = await self._group_models(
            EvidenceSourceModel,
            EvidenceSourceModel.evidence_revision_id,
            owner_user_id,
            EvidenceSourceModel.evidence_revision_id.in_(current_revision_ids),
            EvidenceSourceModel.created_at,
            EvidenceSourceModel.id,
        )
        metrics_by_revision = await self._group_models(
            EvidenceMetricModel,
            EvidenceMetricModel.evidence_revision_id,
            owner_user_id,
            EvidenceMetricModel.evidence_revision_id.in_(current_revision_ids),
            EvidenceMetricModel.created_at,
            EvidenceMetricModel.id,
        )
        conflict_models = list(
            (
                await self.session.scalars(
                    select(EvidenceConflictModel)
                    .where(
                        EvidenceConflictModel.owner_user_id == owner_user_id,
                        or_(
                            EvidenceConflictModel.evidence_id.in_(evidence_ids),
                            EvidenceConflictModel.conflicting_evidence_id.in_(evidence_ids),
                        ),
                    )
                    .order_by(EvidenceConflictModel.created_at, EvidenceConflictModel.id)
                )
            ).all()
        )
        conflicts: defaultdict[UUID, list[EvidenceConflictModel]] = defaultdict(list)
        evidence_id_set = set(evidence_ids)
        for conflict in conflict_models:
            if conflict.evidence_id in evidence_id_set:
                conflicts[conflict.evidence_id].append(conflict)
            if (
                conflict.conflicting_evidence_id in evidence_id_set
                and conflict.conflicting_evidence_id != conflict.evidence_id
            ):
                conflicts[conflict.conflicting_evidence_id].append(conflict)

        records: list[EvidenceRecord] = []
        for item in items:
            current = current_by_evidence.get(item.id)
            if current is None:
                continue
            records.append(
                EvidenceRecord(
                    item=_evidence_item(item),
                    revision=_revision(current),
                    revisions=tuple(_revision(value) for value in revisions_by_evidence[item.id]),
                    transitions=tuple(_transition(value) for value in transitions[item.id]),
                    sources=tuple(_source(value) for value in sources_by_revision[current.id]),
                    metrics=tuple(_metric(value) for value in metrics_by_revision[current.id]),
                    attachments=tuple(_attachment(value) for value in attachments[item.id]),
                    conflicts=tuple(_conflict(value) for value in conflicts[item.id]),
                    entity_ids=tuple(value.entity_id for value in entity_links[item.id]),
                    skill_ids=tuple(value.skill_id for value in skill_links[item.id]),
                    usage=tuple(_usage(value) for value in usage[item.id]),
                )
            )
        return records

    async def _group_models(
        self,
        model: Any,
        group_column: Any,
        owner_user_id: UUID,
        predicate: Any,
        *order_columns: Any,
    ) -> defaultdict[UUID, list[Any]]:
        statement = select(model).where(model.owner_user_id == owner_user_id, predicate)
        if order_columns:
            statement = statement.order_by(*order_columns)
        values = (await self.session.scalars(statement)).all()
        grouped: defaultdict[UUID, list[Any]] = defaultdict(list)
        for value in values:
            grouped[getattr(value, group_column.key)].append(value)
        return grouped

    async def get_achievement(
        self, owner_user_id: UUID, achievement_id: UUID, *, for_update: bool = False
    ) -> AchievementDraft | None:
        statement = select(AchievementDraftModel).where(
            AchievementDraftModel.owner_user_id == owner_user_id,
            AchievementDraftModel.id == achievement_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _achievement(model) if model is not None else None

    async def list_achievements(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[AchievementDraft]:
        statement = select(AchievementDraftModel).where(
            AchievementDraftModel.owner_user_id == owner_user_id
        )
        if after is not None:
            statement = statement.where(
                _after_cursor(AchievementDraftModel.created_at, AchievementDraftModel.id, after)
            )
        models = (
            await self.session.scalars(
                statement.order_by(
                    AchievementDraftModel.created_at.desc(),
                    AchievementDraftModel.id.desc(),
                ).limit(limit)
            )
        ).all()
        return [_achievement(model) for model in models]

    async def add_achievement(self, achievement: AchievementDraft) -> None:
        self.session.add(AchievementDraftModel(**_achievement_values(achievement)))

    async def save_achievement(self, achievement: AchievementDraft) -> None:
        await self._execute(
            update(AchievementDraftModel)
            .where(
                AchievementDraftModel.owner_user_id == achievement.owner_user_id,
                AchievementDraftModel.id == achievement.id,
            )
            .values(**_achievement_values(achievement, include_identity=False))
        )

    async def find_achievement_conversion(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AchievementDraft | None:
        model = await self.session.scalar(
            select(AchievementDraftModel).where(
                AchievementDraftModel.owner_user_id == owner_user_id,
                AchievementDraftModel.conversion_idempotency_key == idempotency_key,
            )
        )
        return _achievement(model) if model is not None else None

    async def get_reminder_preferences(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> ReminderPreferences | None:
        statement = select(ReminderPreferencesModel).where(
            ReminderPreferencesModel.owner_user_id == owner_user_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _reminder_preferences(model) if model is not None else None

    async def add_reminder_preferences(self, preferences: ReminderPreferences) -> None:
        self.session.add(ReminderPreferencesModel(**_reminder_values(preferences)))

    async def save_reminder_preferences(self, preferences: ReminderPreferences) -> None:
        await self._execute(
            update(ReminderPreferencesModel)
            .where(
                ReminderPreferencesModel.owner_user_id == preferences.owner_user_id,
                ReminderPreferencesModel.id == preferences.id,
            )
            .values(**_reminder_values(preferences, include_identity=False))
        )

    async def add_audit(self, event: CareerAuditEvent) -> None:
        self.session.add(
            CareerAuditEventModel(
                id=event.id,
                owner_user_id=event.owner_user_id,
                actor_user_id=event.actor_user_id,
                action=event.action.value,
                target_kind=event.target_kind,
                target_id=event.target_id,
                request_id=event.request_id,
                trace_id=event.trace_id,
                details=dict(event.details),
                created_at=event.created_at,
            )
        )

    async def _execute(self, statement: Any) -> None:
        try:
            await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyCareerRecordUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> CareerRecordUnitOfWork:
        return SqlAlchemyCareerRecordUnitOfWork(self._database)


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    constraint_name = _constraint_name(exc)
    if "conversion_key" in constraint_name:
        raise CareerRecordIdempotencyConflict from exc
    raise CareerRecordConflict from exc


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = getattr(current, "constraint_name", None)
        if isinstance(value, str):
            return value
        current = current.__cause__ or current.__context__
    return ""


def _after_cursor(created_column: Any, id_column: Any, after: PageCursor) -> Any:
    return or_(
        created_column < after.created_at,
        and_(created_column == after.created_at, id_column < after.item_id),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _partial_date(year: int | None, month: int | None) -> PartialDate | None:
    return PartialDate(year=year, month=month) if year is not None else None


def _profile(model: CareerProfileModel) -> CareerProfile:
    return CareerProfile(
        id=model.id,
        owner_user_id=model.owner_user_id,
        professional_headline=model.professional_headline,
        summary=model.summary,
        work_authorization=model.work_authorization,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _profile_values(profile: CareerProfile, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "professional_headline": profile.professional_headline,
        "summary": profile.summary,
        "work_authorization": profile.work_authorization,
        "version": profile.version,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }
    if include_identity:
        values.update(id=profile.id, owner_user_id=profile.owner_user_id)
    return values


def _entity(model: CareerEntityModel) -> CareerEntity:
    return CareerEntity(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        kind=CareerEntityKind(model.kind),
        title=model.title,
        organization=model.organization,
        description=model.description,
        official_title=model.official_title,
        display_title=model.display_title,
        employment_type=(
            EmploymentType(model.employment_type) if model.employment_type is not None else None
        ),
        location=model.location,
        external_url=model.external_url,
        start_date=_partial_date(model.start_year, model.start_month),
        end_date=_partial_date(model.end_year, model.end_month),
        is_current=model.is_current,
        sort_order=model.sort_order,
        group_id=model.group_id,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _entity_values(entity: CareerEntity, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_id": entity.profile_id,
        "kind": entity.kind.value,
        "title": entity.title,
        "organization": entity.organization,
        "description": entity.description,
        "official_title": entity.official_title,
        "display_title": entity.display_title,
        "employment_type": (
            entity.employment_type.value if entity.employment_type is not None else None
        ),
        "location": entity.location,
        "external_url": entity.external_url,
        "start_year": entity.start_date.year if entity.start_date is not None else None,
        "start_month": entity.start_date.month if entity.start_date is not None else None,
        "end_year": entity.end_date.year if entity.end_date is not None else None,
        "end_month": entity.end_date.month if entity.end_date is not None else None,
        "is_current": entity.is_current,
        "sort_order": entity.sort_order,
        "group_id": entity.group_id,
        "version": entity.version,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
    if include_identity:
        values.update(id=entity.id, owner_user_id=entity.owner_user_id)
    return values


def _entity_confirmation(
    model: CareerEntityConfirmationModel,
) -> CareerEntityConfirmation:
    return CareerEntityConfirmation(
        entity_id=model.entity_id,
        owner_user_id=model.owner_user_id,
        state=ConfirmationState(model.state),
        version=model.version,
        updated_at=model.updated_at,
        confirmed_at=model.confirmed_at,
    )


def _entity_confirmation_values(
    confirmation: CareerEntityConfirmation, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "state": confirmation.state.value,
        "version": confirmation.version,
        "updated_at": confirmation.updated_at,
        "confirmed_at": confirmation.confirmed_at,
    }
    if include_identity:
        values.update(
            entity_id=confirmation.entity_id,
            owner_user_id=confirmation.owner_user_id,
        )
    return values


def _skill_confirmation(
    model: CareerSkillConfirmationModel,
) -> CareerSkillConfirmation:
    return CareerSkillConfirmation(
        skill_id=model.skill_id,
        owner_user_id=model.owner_user_id,
        state=ConfirmationState(model.state),
        version=model.version,
        updated_at=model.updated_at,
        confirmed_at=model.confirmed_at,
    )


def _skill_confirmation_values(
    confirmation: CareerSkillConfirmation, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "state": confirmation.state.value,
        "version": confirmation.version,
        "updated_at": confirmation.updated_at,
        "confirmed_at": confirmation.confirmed_at,
    }
    if include_identity:
        values.update(
            skill_id=confirmation.skill_id,
            owner_user_id=confirmation.owner_user_id,
        )
    return values


def _skill(model: CareerSkillModel) -> Skill:
    return Skill(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        name=model.name,
        category=model.category,
        proficiency=(
            SkillProficiency(model.proficiency) if model.proficiency is not None else None
        ),
        sort_order=model.sort_order,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _skill_values(skill: Skill, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_id": skill.profile_id,
        "name": skill.name,
        "name_normalized": skill.name.casefold(),
        "category": skill.category,
        "proficiency": skill.proficiency.value if skill.proficiency is not None else None,
        "sort_order": skill.sort_order,
        "version": skill.version,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }
    if include_identity:
        values.update(id=skill.id, owner_user_id=skill.owner_user_id)
    return values


def _personal_fact(model: CareerPersonalFactModel) -> PersonalFact:
    return PersonalFact(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        kind=PersonalFactKind(model.kind),
        value=model.value,
        label=model.label,
        is_primary=model.is_primary,
        confirmation=ConfirmationState(model.confirmation),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        confirmed_at=model.confirmed_at,
    )


def _personal_fact_values(
    fact: PersonalFact, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_id": fact.profile_id,
        "kind": fact.kind.value,
        "value": fact.value,
        "value_sha256": CareerFieldProvenance.digest_value(fact.value),
        "label": fact.label,
        "is_primary": fact.is_primary,
        "confirmation": fact.confirmation.value,
        "version": fact.version,
        "created_at": fact.created_at,
        "updated_at": fact.updated_at,
        "confirmed_at": fact.confirmed_at,
    }
    if include_identity:
        values.update(id=fact.id, owner_user_id=fact.owner_user_id)
    return values


def _field_provenance(
    model: CareerFieldProvenanceModel,
) -> CareerFieldProvenance:
    target_id = {
        CareerFieldTarget.PERSONAL_FACT: model.personal_fact_id,
        CareerFieldTarget.ENTITY: model.entity_id,
        CareerFieldTarget.SKILL: model.skill_id,
    }[CareerFieldTarget(model.target)]
    if target_id is None:
        raise CareerRecordConflict("field provenance target is unavailable")
    return CareerFieldProvenance(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        target=CareerFieldTarget(model.target),
        target_id=target_id,
        field_name=model.field_name,
        value_sha256=model.value_sha256,
        origin=SemanticFieldOrigin(model.origin),
        document_id=model.document_id,
        snapshot_id=model.snapshot_id,
        snapshot_revision=model.snapshot_revision,
        schema_version=model.schema_version,
        parser_version=model.parser_version,
        semantic_entity_id=model.semantic_entity_id,
        semantic_field_id=model.semantic_field_id,
        anchors=tuple(SemanticImportAnchor.from_dict(anchor) for anchor in model.anchors_json),
        created_at=model.created_at,
    )


def _field_provenance_values(
    provenance: CareerFieldProvenance,
) -> dict[str, object]:
    target_values: dict[str, object] = {
        "personal_fact_id": None,
        "entity_id": None,
        "skill_id": None,
    }
    target_values[
        {
            CareerFieldTarget.PERSONAL_FACT: "personal_fact_id",
            CareerFieldTarget.ENTITY: "entity_id",
            CareerFieldTarget.SKILL: "skill_id",
        }[provenance.target]
    ] = provenance.target_id
    return {
        "id": provenance.id,
        "owner_user_id": provenance.owner_user_id,
        "profile_id": provenance.profile_id,
        "target": provenance.target.value,
        **target_values,
        "field_name": provenance.field_name,
        "value_sha256": provenance.value_sha256,
        "origin": provenance.origin.value,
        "document_id": provenance.document_id,
        "snapshot_id": provenance.snapshot_id,
        "snapshot_revision": provenance.snapshot_revision,
        "schema_version": provenance.schema_version,
        "parser_version": provenance.parser_version,
        "semantic_entity_id": provenance.semantic_entity_id,
        "semantic_field_id": provenance.semantic_field_id,
        "anchors_json": [anchor.to_dict() for anchor in provenance.anchors],
        "created_at": provenance.created_at,
    }


def _entity_relationship(
    model: CareerEntityRelationshipModel,
) -> CareerEntityRelationship:
    return CareerEntityRelationship(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        source_entity_id=model.source_entity_id,
        target_entity_id=model.target_entity_id,
        kind=CareerRelationshipKind(model.kind),
        created_at=model.created_at,
    )


def _entity_relationship_values(
    relationship: CareerEntityRelationship,
) -> dict[str, object]:
    return {
        "id": relationship.id,
        "owner_user_id": relationship.owner_user_id,
        "profile_id": relationship.profile_id,
        "source_entity_id": relationship.source_entity_id,
        "target_entity_id": relationship.target_entity_id,
        "kind": relationship.kind.value,
        "created_at": relationship.created_at,
    }


def _entity_skill_model(link: EntitySkillLink) -> CareerEntitySkillModel:
    return CareerEntitySkillModel(
        id=link.id,
        owner_user_id=link.owner_user_id,
        entity_id=link.entity_id,
        skill_id=link.skill_id,
        created_at=link.created_at,
    )


def _entity_skill(model: CareerEntitySkillModel) -> EntitySkillLink:
    return EntitySkillLink(
        id=model.id,
        owner_user_id=model.owner_user_id,
        entity_id=model.entity_id,
        skill_id=model.skill_id,
        created_at=model.created_at,
    )


def _proposal(model: CareerImportProposalModel) -> ImportProposal:
    proposed = CareerEntity(
        id=model.proposed_entity_id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        kind=CareerEntityKind(model.proposed_kind),
        title=model.proposed_title,
        organization=model.proposed_organization,
        description=model.proposed_description,
        official_title=model.proposed_official_title,
        display_title=model.proposed_display_title,
        employment_type=(
            EmploymentType(model.proposed_employment_type)
            if model.proposed_employment_type is not None
            else None
        ),
        location=model.proposed_location,
        external_url=model.proposed_external_url,
        start_date=_partial_date(model.proposed_start_year, model.proposed_start_month),
        end_date=_partial_date(model.proposed_end_year, model.proposed_end_month),
        is_current=model.proposed_is_current,
        sort_order=model.proposed_sort_order,
        group_id=model.proposed_group_id,
        version=1,
        created_at=model.created_at,
        updated_at=model.created_at,
    )
    return ImportProposal(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        target_entity_id=model.target_entity_id,
        proposed_entity=proposed,
        provenance=ResumeProvenance(
            document_id=model.document_id,
            snapshot_id=model.snapshot_id,
            snapshot_revision=model.snapshot_revision,
            schema_version=model.schema_version,
            parser_version=model.parser_version,
            block_id=model.block_id,
            page=model.page,
            start_offset=model.start_offset,
            end_offset=model.end_offset,
            source_sha256=model.source_sha256,
            review_excerpt=model.review_excerpt,
        ),
        status=ProposalStatus(model.status),
        conflict_code=model.conflict_code,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        reviewed_at=model.reviewed_at,
    )


def _proposal_values(
    proposal: ImportProposal, *, include_identity: bool = True
) -> dict[str, object]:
    entity = proposal.proposed_entity
    provenance = proposal.provenance
    values: dict[str, object] = {
        "profile_id": proposal.profile_id,
        "target_entity_id": proposal.target_entity_id,
        "proposed_entity_id": entity.id,
        "proposed_kind": entity.kind.value,
        "proposed_title": entity.title,
        "proposed_organization": entity.organization,
        "proposed_description": entity.description,
        "proposed_official_title": entity.official_title,
        "proposed_display_title": entity.display_title,
        "proposed_employment_type": (
            entity.employment_type.value if entity.employment_type is not None else None
        ),
        "proposed_location": entity.location,
        "proposed_external_url": entity.external_url,
        "proposed_start_year": (entity.start_date.year if entity.start_date is not None else None),
        "proposed_start_month": (
            entity.start_date.month if entity.start_date is not None else None
        ),
        "proposed_end_year": entity.end_date.year if entity.end_date is not None else None,
        "proposed_end_month": (entity.end_date.month if entity.end_date is not None else None),
        "proposed_is_current": entity.is_current,
        "proposed_sort_order": entity.sort_order,
        "proposed_group_id": entity.group_id,
        "document_id": provenance.document_id,
        "snapshot_id": provenance.snapshot_id,
        "snapshot_revision": provenance.snapshot_revision,
        "schema_version": provenance.schema_version,
        "parser_version": provenance.parser_version,
        "block_id": provenance.block_id,
        "page": provenance.page,
        "start_offset": provenance.start_offset,
        "end_offset": provenance.end_offset,
        "source_sha256": provenance.source_sha256,
        "review_excerpt": provenance.review_excerpt,
        "status": proposal.status.value,
        "conflict_code": proposal.conflict_code,
        "version": proposal.version,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
        "reviewed_at": proposal.reviewed_at,
    }
    if include_identity:
        values.update(id=proposal.id, owner_user_id=proposal.owner_user_id)
    return values


def _semantic_proposal(
    model: CareerSemanticImportProposalModel,
) -> SemanticImportProposal:
    return SemanticImportProposal(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        target=SemanticImportTarget(model.target),
        target_record_id=model.target_record_id,
        document_id=model.document_id,
        snapshot_id=model.snapshot_id,
        snapshot_revision=model.snapshot_revision,
        schema_version=model.schema_version,
        parser_version=model.parser_version,
        semantic_entity_id=model.semantic_entity_id,
        semantic_kind=SemanticCandidateKind(model.semantic_kind),
        fields=tuple(SemanticImportField.from_dict(field) for field in model.fields_json),
        accepted_values=(
            dict(model.accepted_values_json) if model.accepted_values_json is not None else None
        ),
        decision_idempotency_key=model.decision_idempotency_key,
        status=SemanticImportStatus(model.status),
        conflict_code=model.conflict_code,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        reviewed_at=model.reviewed_at,
    )


def _semantic_proposal_values(
    proposal: SemanticImportProposal, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_id": proposal.profile_id,
        "target": proposal.target.value,
        "target_record_id": proposal.target_record_id,
        "document_id": proposal.document_id,
        "snapshot_id": proposal.snapshot_id,
        "snapshot_revision": proposal.snapshot_revision,
        "schema_version": proposal.schema_version,
        "parser_version": proposal.parser_version,
        "semantic_entity_id": proposal.semantic_entity_id,
        "semantic_kind": proposal.semantic_kind.value,
        "fields_json": [field.to_dict() for field in proposal.fields],
        "accepted_values_json": proposal.accepted_values,
        "decision_idempotency_key": proposal.decision_idempotency_key,
        "status": proposal.status.value,
        "conflict_code": proposal.conflict_code,
        "version": proposal.version,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
        "reviewed_at": proposal.reviewed_at,
    }
    if include_identity:
        values.update(id=proposal.id, owner_user_id=proposal.owner_user_id)
    return values


def _validate_record_ownership(record: EvidenceRecord) -> None:
    owner_user_id = record.item.owner_user_id
    evidence_id = record.item.id
    revision_ids = {revision.id for revision in record.revisions}
    if (
        record.revision.id not in revision_ids
        or record.revision.evidence_id != evidence_id
        or record.revision.revision != record.item.current_revision
        or any(
            revision.owner_user_id != owner_user_id or revision.evidence_id != evidence_id
            for revision in record.revisions
        )
        or any(
            transition.owner_user_id != owner_user_id
            or transition.evidence_id != evidence_id
            or transition.to_revision_id not in revision_ids
            or (
                transition.from_revision_id is not None
                and transition.from_revision_id not in revision_ids
            )
            for transition in record.transitions
        )
        or any(
            source.owner_user_id != owner_user_id or source.evidence_revision_id not in revision_ids
            for source in record.sources
        )
        or any(
            metric.owner_user_id != owner_user_id or metric.evidence_revision_id not in revision_ids
            for metric in record.metrics
        )
        or any(
            attachment.owner_user_id != owner_user_id or attachment.evidence_id != evidence_id
            for attachment in record.attachments
        )
        or any(
            conflict.owner_user_id != owner_user_id
            or (
                conflict.evidence_id != evidence_id
                and conflict.conflicting_evidence_id != evidence_id
            )
            for conflict in record.conflicts
        )
        or any(
            usage.owner_user_id != owner_user_id or usage.evidence_id != evidence_id
            for usage in record.usage
        )
    ):
        raise CareerRecordConflict("evidence record ownership does not match")


def _evidence_item(model: EvidenceItemModel) -> EvidenceItem:
    return EvidenceItem(
        id=model.id,
        owner_user_id=model.owner_user_id,
        lifecycle=EvidenceLifecycle(model.lifecycle),
        current_revision=model.current_revision,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        archived_at=model.archived_at,
        deleted_at=model.deleted_at,
    )


def _evidence_item_values(
    item: EvidenceItem, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "lifecycle": item.lifecycle.value,
        "current_revision": item.current_revision,
        "version": item.version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "archived_at": item.archived_at,
        "deleted_at": item.deleted_at,
    }
    if include_identity:
        values.update(id=item.id, owner_user_id=item.owner_user_id)
    return values


def _revision(model: EvidenceRevisionModel) -> EvidenceRevision:
    return EvidenceRevision(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        revision=model.revision,
        evidence_type=EvidenceType(model.evidence_type),
        title=model.title,
        statement=model.statement,
        context=model.context,
        organization=model.organization,
        project=model.project,
        start_date=_partial_date(model.start_year, model.start_month),
        end_date=_partial_date(model.end_year, model.end_month),
        strength=EvidenceStrength(model.strength),
        input_kind=EvidenceInputKind(model.input_kind),
        created_at=model.created_at,
    )


def _revision_model(revision: EvidenceRevision) -> EvidenceRevisionModel:
    return EvidenceRevisionModel(
        id=revision.id,
        owner_user_id=revision.owner_user_id,
        evidence_id=revision.evidence_id,
        revision=revision.revision,
        evidence_type=revision.evidence_type.value,
        title=revision.title,
        statement=revision.statement,
        context=revision.context,
        organization=revision.organization,
        project=revision.project,
        start_year=revision.start_date.year if revision.start_date is not None else None,
        start_month=revision.start_date.month if revision.start_date is not None else None,
        end_year=revision.end_date.year if revision.end_date is not None else None,
        end_month=revision.end_date.month if revision.end_date is not None else None,
        strength=revision.strength.value,
        input_kind=revision.input_kind.value,
        created_at=revision.created_at,
    )


def _transition(model: EvidenceStateTransitionModel) -> EvidenceStateTransition:
    return EvidenceStateTransition(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        from_revision_id=model.from_revision_id,
        to_revision_id=model.to_revision_id,
        previous_strength=(
            EvidenceStrength(model.previous_strength)
            if model.previous_strength is not None
            else None
        ),
        next_strength=EvidenceStrength(model.next_strength),
        authority=EvidenceAuthority(model.authority),
        reason_code=model.reason_code,
        actor_user_id=model.actor_user_id,
        verifier_reference=model.verifier_reference,
        request_id=model.request_id,
        trace_id=model.trace_id,
        created_at=model.created_at,
    )


def _transition_model(
    transition: EvidenceStateTransition,
) -> EvidenceStateTransitionModel:
    return EvidenceStateTransitionModel(
        id=transition.id,
        owner_user_id=transition.owner_user_id,
        evidence_id=transition.evidence_id,
        from_revision_id=transition.from_revision_id,
        to_revision_id=transition.to_revision_id,
        previous_strength=(
            transition.previous_strength.value if transition.previous_strength is not None else None
        ),
        next_strength=transition.next_strength.value,
        authority=transition.authority.value,
        reason_code=transition.reason_code,
        actor_user_id=transition.actor_user_id,
        verifier_reference=transition.verifier_reference,
        request_id=transition.request_id,
        trace_id=transition.trace_id,
        created_at=transition.created_at,
    )


def _source(model: EvidenceSourceModel) -> EvidenceSource:
    provenance = None
    if model.document_id is not None:
        if (
            model.snapshot_id is None
            or model.snapshot_revision is None
            or model.schema_version is None
            or model.parser_version is None
            or model.block_id is None
            or model.page is None
            or model.start_offset is None
            or model.end_offset is None
            or model.source_sha256 is None
            or model.review_excerpt is None
        ):
            raise CareerRecordConflict("stored evidence provenance is incomplete")
        provenance = ResumeProvenance(
            document_id=model.document_id,
            snapshot_id=model.snapshot_id,
            snapshot_revision=model.snapshot_revision,
            schema_version=model.schema_version,
            parser_version=model.parser_version,
            block_id=model.block_id,
            page=model.page,
            start_offset=model.start_offset,
            end_offset=model.end_offset,
            source_sha256=model.source_sha256,
            review_excerpt=model.review_excerpt,
        )
    return EvidenceSource(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_revision_id=model.evidence_revision_id,
        kind=EvidenceSourceKind(model.kind),
        label=model.label,
        provenance=provenance,
        attachment_id=model.attachment_id,
        external_url=model.external_url,
        available=model.available,
        exact_span_validated=model.exact_span_validated,
        created_at=model.created_at,
    )


def _source_model(source: EvidenceSource) -> EvidenceSourceModel:
    provenance = source.provenance
    return EvidenceSourceModel(
        id=source.id,
        owner_user_id=source.owner_user_id,
        evidence_revision_id=source.evidence_revision_id,
        kind=source.kind.value,
        label=source.label,
        attachment_id=source.attachment_id,
        external_url=source.external_url,
        available=source.available,
        exact_span_validated=source.exact_span_validated,
        document_id=provenance.document_id if provenance is not None else None,
        snapshot_id=provenance.snapshot_id if provenance is not None else None,
        snapshot_revision=provenance.snapshot_revision if provenance is not None else None,
        schema_version=provenance.schema_version if provenance is not None else None,
        parser_version=provenance.parser_version if provenance is not None else None,
        block_id=provenance.block_id if provenance is not None else None,
        page=provenance.page if provenance is not None else None,
        start_offset=provenance.start_offset if provenance is not None else None,
        end_offset=provenance.end_offset if provenance is not None else None,
        source_sha256=provenance.source_sha256 if provenance is not None else None,
        review_excerpt=provenance.review_excerpt if provenance is not None else None,
        created_at=source.created_at,
    )


def _metric(model: EvidenceMetricModel) -> EvidenceMetric:
    return EvidenceMetric(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_revision_id=model.evidence_revision_id,
        name=model.name,
        value=model.value,
        value_max=model.value_max,
        unit=model.unit,
        currency=model.currency,
        period=model.period,
        baseline=model.baseline,
        comparator=model.comparator,
        comparison_applicable=model.comparison_applicable,
        precision=MetricPrecision(model.precision),
        attribution=model.attribution,
        created_at=model.created_at,
    )


def _metric_model(metric: EvidenceMetric) -> EvidenceMetricModel:
    return EvidenceMetricModel(
        id=metric.id,
        owner_user_id=metric.owner_user_id,
        evidence_revision_id=metric.evidence_revision_id,
        name=metric.name,
        value=metric.value,
        value_max=metric.value_max,
        unit=metric.unit,
        currency=metric.currency,
        period=metric.period,
        baseline=metric.baseline,
        comparator=metric.comparator,
        comparison_applicable=metric.comparison_applicable,
        precision=metric.precision.value,
        attribution=metric.attribution,
        created_at=metric.created_at,
    )


def _attachment(model: EvidenceAttachmentModel) -> EvidenceAttachment:
    if model.display_filename is None or model.media_type is None or model.size_bytes is None:
        raise CareerRecordConflict("stored active attachment metadata is incomplete")
    return EvidenceAttachment(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        display_filename=model.display_filename,
        media_type=model.media_type,
        size_bytes=model.size_bytes,
        content_sha256=model.content_sha256,
        status=AttachmentStatus(model.status),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _attachment_values(
    attachment: EvidenceAttachment, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "evidence_id": attachment.evidence_id,
        "display_filename": attachment.display_filename,
        "media_type": attachment.media_type,
        "size_bytes": attachment.size_bytes,
        "content_sha256": attachment.content_sha256,
        "status": attachment.status.value,
        "version": attachment.version,
        "created_at": attachment.created_at,
        "updated_at": attachment.updated_at,
    }
    if include_identity:
        values.update(id=attachment.id, owner_user_id=attachment.owner_user_id)
    return values


def _attachment_model(attachment: EvidenceAttachment) -> EvidenceAttachmentModel:
    return EvidenceAttachmentModel(**_attachment_values(attachment))


def _conflict(model: EvidenceConflictModel) -> EvidenceConflict:
    return EvidenceConflict(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        conflicting_evidence_id=model.conflicting_evidence_id,
        kind=EvidenceConflictKind(model.kind),
        code=model.code,
        status=ConflictStatus(model.status),
        resolution=(ConflictResolution(model.resolution) if model.resolution is not None else None),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        resolved_at=model.resolved_at,
    )


def _conflict_values(
    conflict: EvidenceConflict, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "evidence_id": conflict.evidence_id,
        "conflicting_evidence_id": conflict.conflicting_evidence_id,
        "kind": conflict.kind.value,
        "code": conflict.code,
        "status": conflict.status.value,
        "resolution": conflict.resolution.value if conflict.resolution is not None else None,
        "version": conflict.version,
        "created_at": conflict.created_at,
        "updated_at": conflict.updated_at,
        "resolved_at": conflict.resolved_at,
    }
    if include_identity:
        values.update(id=conflict.id, owner_user_id=conflict.owner_user_id)
    return values


def _conflict_model(conflict: EvidenceConflict) -> EvidenceConflictModel:
    return EvidenceConflictModel(**_conflict_values(conflict))


def _usage(model: EvidenceUsageModel) -> EvidenceUsage:
    return EvidenceUsage(
        id=model.id,
        owner_user_id=model.owner_user_id,
        evidence_id=model.evidence_id,
        consumer_kind=model.consumer_kind,
        consumer_id=model.consumer_id,
        purpose=model.purpose,
        created_at=model.created_at,
    )


def _usage_model(usage: EvidenceUsage) -> EvidenceUsageModel:
    return EvidenceUsageModel(
        id=usage.id,
        owner_user_id=usage.owner_user_id,
        evidence_id=usage.evidence_id,
        consumer_kind=usage.consumer_kind,
        consumer_id=usage.consumer_id,
        purpose=usage.purpose,
        created_at=usage.created_at,
    )


def _achievement(model: AchievementDraftModel) -> AchievementDraft:
    metric = None
    if model.metric_value is not None:
        if (
            model.metric_unit is None
            or model.metric_period is None
            or model.metric_comparison_applicable is None
            or model.metric_precision is None
            or model.metric_attribution is None
        ):
            raise CareerRecordConflict("stored achievement metric is incomplete")
        metric = AchievementMetric(
            name=model.metric_name,
            value=model.metric_value,
            value_max=model.metric_value_max,
            unit=model.metric_unit,
            currency=model.metric_currency,
            period=model.metric_period,
            baseline=model.metric_baseline,
            comparator=model.metric_comparator,
            comparison_applicable=model.metric_comparison_applicable,
            precision=MetricPrecision(model.metric_precision),
            attribution=model.metric_attribution,
        )
    return AchievementDraft(
        id=model.id,
        owner_user_id=model.owner_user_id,
        profile_id=model.profile_id,
        title=model.title,
        delivered=model.delivered,
        problem=model.problem,
        audience=model.audience,
        measurement=model.measurement,
        effect=model.effect,
        collaboration=model.collaboration,
        methods=model.methods,
        entity_id=model.entity_id,
        metric=metric,
        reminder_cadence=ReminderCadence(model.reminder_cadence),
        remind_at=model.remind_at,
        status=AchievementStatus(model.status),
        converted_evidence_id=model.converted_evidence_id,
        conversion_idempotency_key=model.conversion_idempotency_key,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _achievement_values(
    achievement: AchievementDraft, *, include_identity: bool = True
) -> dict[str, object]:
    metric = achievement.metric
    values: dict[str, object] = {
        "profile_id": achievement.profile_id,
        "title": achievement.title,
        "delivered": achievement.delivered,
        "problem": achievement.problem,
        "audience": achievement.audience,
        "measurement": achievement.measurement,
        "effect": achievement.effect,
        "collaboration": achievement.collaboration,
        "methods": achievement.methods,
        "entity_id": achievement.entity_id,
        "metric_name": metric.name if metric is not None else None,
        "metric_value": metric.value if metric is not None else None,
        "metric_value_max": metric.value_max if metric is not None else None,
        "metric_unit": metric.unit if metric is not None else None,
        "metric_currency": metric.currency if metric is not None else None,
        "metric_period": metric.period if metric is not None else None,
        "metric_baseline": metric.baseline if metric is not None else None,
        "metric_comparator": metric.comparator if metric is not None else None,
        "metric_comparison_applicable": (
            metric.comparison_applicable if metric is not None else None
        ),
        "metric_precision": metric.precision.value if metric is not None else None,
        "metric_attribution": metric.attribution if metric is not None else None,
        "reminder_cadence": achievement.reminder_cadence.value,
        "remind_at": achievement.remind_at,
        "status": achievement.status.value,
        "converted_evidence_id": achievement.converted_evidence_id,
        "conversion_idempotency_key": achievement.conversion_idempotency_key,
        "version": achievement.version,
        "created_at": achievement.created_at,
        "updated_at": achievement.updated_at,
    }
    if include_identity:
        values.update(id=achievement.id, owner_user_id=achievement.owner_user_id)
    return values


def _reminder_preferences(model: ReminderPreferencesModel) -> ReminderPreferences:
    return ReminderPreferences(
        id=model.id,
        owner_user_id=model.owner_user_id,
        enabled=model.enabled,
        day_of_month=model.day_of_month,
        timezone=model.timezone,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _reminder_values(
    preferences: ReminderPreferences, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "enabled": preferences.enabled,
        "day_of_month": preferences.day_of_month,
        "timezone": preferences.timezone,
        "version": preferences.version,
        "created_at": preferences.created_at,
        "updated_at": preferences.updated_at,
    }
    if include_identity:
        values.update(id=preferences.id, owner_user_id=preferences.owner_user_id)
    return values
