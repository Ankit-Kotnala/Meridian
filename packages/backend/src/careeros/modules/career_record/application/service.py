"""Career Record application use cases and atomic policy orchestration."""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

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
    CareerRecordNotFound,
    CareerRecordSourceUnavailable,
    CareerRecordTransitionRejected,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
    ConflictResolution,
    ConflictStatus,
    EligibilityDecision,
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
    ImportProposal,
    ProposalStatus,
    ReminderPreferences,
    ResumeProvenance,
    Skill,
    VerificationDecision,
    evidence_eligibility,
    initial_revision,
    material_revision,
    reorder_entities,
    timeline_findings,
    transition_revision,
)

from .models import (
    CareerEntityData,
    CareerProfileView,
    CreateAchievement,
    CreateCareerProfile,
    CreateEvidence,
    CreateImportProposal,
    CreateSkill,
    EvidenceFilter,
    EvidenceRecord,
    MetricInput,
    Page,
    PageCursor,
    ProposalFilter,
    RequestContext,
    ResumeSourceLocator,
    ReviseEvidence,
    UpdateAchievement,
    UpdateCareerProfile,
    UpdateReminderPreferences,
    UpdateSkill,
    ValidatedResumeSource,
    next_page,
)
from .ports import (
    AttachmentAdmission,
    CareerRecordUnitOfWorkFactory,
    Clock,
    EvidenceVerificationAuthority,
    IdentifierFactory,
    ResumeSourceQuery,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class CareerRecordPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_entities: int = 500
    max_skills: int = 500
    max_evidence: int = 2_000
    max_achievements: int = 1_000

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("career record page limits are invalid")
        if (
            min(
                self.max_entities,
                self.max_skills,
                self.max_evidence,
                self.max_achievements,
            )
            < 1
        ):
            raise ValueError("career record collection limits must be positive")


class CareerRecordService:
    """Single Phase 3 transactional boundary for owned career and evidence data."""

    def __init__(
        self,
        *,
        unit_of_work: CareerRecordUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        resume_sources: ResumeSourceQuery,
        attachments: AttachmentAdmission | None = None,
        verification_authority: EvidenceVerificationAuthority | None = None,
        policy: CareerRecordPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._resume_sources = resume_sources
        self._attachments = attachments
        self._verification_authority = verification_authority
        self._policy = policy or CareerRecordPolicy()

    async def create_profile(
        self, owner_user_id: UUID, command: CreateCareerProfile, context: RequestContext
    ) -> CareerProfile:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        profile = CareerProfile(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            professional_headline=command.professional_headline,
            summary=command.summary,
            work_authorization=command.work_authorization,
            version=1,
            created_at=now,
            updated_at=now,
        )
        async with self._uow() as uow:
            if await uow.get_profile(owner_user_id, for_update=True) is not None:
                raise CareerRecordConflict("career profile already exists")
            await uow.add_profile(profile)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PROFILE_CREATED,
                    "career_profile",
                    profile.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return profile

    async def get_or_create_profile(
        self, owner_user_id: UUID, context: RequestContext
    ) -> CareerProfileView:
        """Idempotently initialize the empty owned aggregate for the first GET."""

        self._authorize(owner_user_id, context)
        try:
            return await self.get_profile(owner_user_id)
        except CareerRecordNotFound:
            with suppress(CareerRecordConflict):
                await self.create_profile(owner_user_id, CreateCareerProfile(), context)
            return await self.get_profile(owner_user_id)

    async def get_profile(self, owner_user_id: UUID) -> CareerProfileView:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            entities = await uow.list_entities(owner_user_id, profile.id)
            skills = await uow.list_skills(owner_user_id, profile.id)
        return CareerProfileView(
            profile=profile,
            entities=tuple(sorted(entities, key=lambda item: (item.sort_order, str(item.id)))),
            skills=tuple(sorted(skills, key=lambda item: (item.sort_order, str(item.id)))),
            findings=timeline_findings(entities),
        )

    async def update_profile(
        self,
        owner_user_id: UUID,
        expected_version: int,
        command: UpdateCareerProfile,
        context: RequestContext,
    ) -> CareerProfile:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id, for_update=True)
            if profile is None:
                raise CareerRecordNotFound
            self._version(profile.version, expected_version)
            profile.edit(
                professional_headline=command.professional_headline,
                summary=command.summary,
                work_authorization=command.work_authorization,
                now=now,
            )
            await uow.save_profile(profile)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PROFILE_UPDATED,
                    "career_profile",
                    profile.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return profile

    async def list_entities(self, owner_user_id: UUID) -> tuple[CareerEntity, ...]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            entities = await uow.list_entities(owner_user_id, profile.id)
        return tuple(sorted(entities, key=lambda item: (item.sort_order, str(item.id))))

    async def get_entity(self, owner_user_id: UUID, entity_id: UUID) -> CareerEntity:
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id)
        if entity is None:
            raise CareerRecordNotFound
        return entity

    async def list_entity_skill_ids(self, owner_user_id: UUID, entity_id: UUID) -> tuple[UUID, ...]:
        """Return only links whose entity is visible in the owner's scope."""

        async with self._uow() as uow:
            if await uow.get_entity(owner_user_id, entity_id) is None:
                raise CareerRecordNotFound
            links = await uow.list_entity_skill_links(owner_user_id, entity_id)
        return tuple(link.skill_id for link in links)

    async def create_entity(
        self,
        owner_user_id: UUID,
        command: CareerEntityData,
        context: RequestContext,
        *,
        skill_ids: tuple[UUID, ...] = (),
        group_with_entity_id: UUID | None = None,
    ) -> CareerEntity:
        self._authorize(owner_user_id, context)
        self._validate_link_ids(skill_ids)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id, for_update=True)
            if profile is None:
                raise CareerRecordNotFound
            entities = await uow.list_entities(owner_user_id, profile.id, for_update=True)
            if len(entities) >= self._policy.max_entities:
                raise CareerRecordConflict("career entity limit reached")
            if group_with_entity_id is not None:
                if command.kind is not CareerEntityKind.EXPERIENCE:
                    raise CareerRecordValidationError(
                        "only experiences can use relationship grouping"
                    )
                grouped = await uow.get_entity(owner_user_id, group_with_entity_id, for_update=True)
                if (
                    grouped is None
                    or grouped.profile_id != profile.id
                    or grouped.kind is not CareerEntityKind.EXPERIENCE
                ):
                    raise CareerRecordNotFound
                group_id = grouped.group_id or self._ids.new()
                command = replace(command, group_id=group_id)
                if grouped.group_id is None:
                    grouped.group_id = group_id
                    grouped.version += 1
                    grouped.updated_at = now
                    await uow.save_entity(grouped)
                    await uow.add_audit(
                        self._audit(
                            owner_user_id,
                            AuditAction.ENTITY_UPDATED,
                            "career_entity",
                            grouped.id,
                            context,
                            now,
                            (("entity_kind", grouped.kind.value),),
                        )
                    )
            entity = self._entity(
                owner_user_id,
                profile.id,
                command,
                sort_order=len(entities),
                now=now,
            )
            links: list[EntitySkillLink] = []
            for skill_id in skill_ids:
                skill = await uow.get_skill(owner_user_id, skill_id)
                if skill is None or skill.profile_id != profile.id:
                    raise CareerRecordNotFound
                links.append(
                    EntitySkillLink(self._ids.new(), owner_user_id, entity.id, skill_id, now)
                )
            await uow.add_entity(entity)
            await uow.replace_entity_skill_links(owner_user_id, entity.id, links)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_CREATED,
                    "career_entity",
                    entity.id,
                    context,
                    now,
                    (("entity_kind", entity.kind.value),),
                )
            )
            await uow.commit()
        return entity

    async def update_entity(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        expected_version: int,
        command: CareerEntityData,
        context: RequestContext,
        *,
        skill_ids: tuple[UUID, ...] | None = None,
        group_with_entity_id: UUID | None = None,
        replace_group: bool = False,
    ) -> CareerEntity:
        self._authorize(owner_user_id, context)
        if skill_ids is not None:
            self._validate_link_ids(skill_ids)
        now = self._clock.now()
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id, for_update=True)
            if entity is None:
                raise CareerRecordNotFound
            self._version(entity.version, expected_version)
            if entity.kind is not command.kind:
                raise CareerRecordValidationError("career entity kind cannot be changed")
            if group_with_entity_id is not None:
                if command.kind is not CareerEntityKind.EXPERIENCE:
                    raise CareerRecordValidationError(
                        "only experiences can use relationship grouping"
                    )
                if group_with_entity_id == entity.id:
                    raise CareerRecordValidationError("an experience cannot be grouped with itself")
                grouped = await uow.get_entity(owner_user_id, group_with_entity_id, for_update=True)
                if (
                    grouped is None
                    or grouped.profile_id != entity.profile_id
                    or grouped.kind is not CareerEntityKind.EXPERIENCE
                ):
                    raise CareerRecordNotFound
                group_id = grouped.group_id or self._ids.new()
                command = replace(command, group_id=group_id)
                if grouped.group_id is None:
                    grouped.group_id = group_id
                    grouped.version += 1
                    grouped.updated_at = now
                    await uow.save_entity(grouped)
                    await uow.add_audit(
                        self._audit(
                            owner_user_id,
                            AuditAction.ENTITY_UPDATED,
                            "career_entity",
                            grouped.id,
                            context,
                            now,
                            (("entity_kind", grouped.kind.value),),
                        )
                    )
            elif replace_group:
                command = replace(command, group_id=None)
            entity.edit(
                title=command.title,
                organization=command.organization,
                description=command.description,
                official_title=command.official_title,
                display_title=command.display_title,
                employment_type=command.employment_type,
                location=command.location,
                external_url=command.external_url,
                start_date=command.start_date,
                end_date=command.end_date,
                is_current=command.is_current,
                group_id=command.group_id,
                now=now,
            )
            links: list[EntitySkillLink] | None = None
            if skill_ids is not None:
                links = []
                for skill_id in skill_ids:
                    skill = await uow.get_skill(owner_user_id, skill_id)
                    if skill is None or skill.profile_id != entity.profile_id:
                        raise CareerRecordNotFound
                    links.append(
                        EntitySkillLink(self._ids.new(), owner_user_id, entity.id, skill_id, now)
                    )
            await uow.save_entity(entity)
            if links is not None:
                await uow.replace_entity_skill_links(owner_user_id, entity.id, links)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_UPDATED,
                    "career_entity",
                    entity.id,
                    context,
                    now,
                    (("entity_kind", entity.kind.value),),
                )
            )
            await uow.commit()
        return entity

    async def delete_entity(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id, for_update=True)
            if entity is None:
                raise CareerRecordNotFound
            self._version(entity.version, expected_version)
            await uow.delete_entity(owner_user_id, entity_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_DELETED,
                    "career_entity",
                    entity.id,
                    context,
                    now,
                    (("entity_kind", entity.kind.value),),
                )
            )
            await uow.commit()

    async def reorder_entity_list(
        self,
        owner_user_id: UUID,
        ordered_ids: tuple[UUID, ...],
        expected_profile_version: int,
        context: RequestContext,
    ) -> CareerProfileView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id, for_update=True)
            if profile is None:
                raise CareerRecordNotFound
            self._version(profile.version, expected_profile_version)
            entities = await uow.list_entities(owner_user_id, profile.id, for_update=True)
            reorder_entities(entities, ordered_ids)
            for entity in entities:
                entity.version += 1
                entity.updated_at = now
                await uow.save_entity(entity)
            profile.version += 1
            profile.updated_at = now
            await uow.save_profile(profile)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITIES_REORDERED,
                    "career_profile",
                    profile.id,
                    context,
                    now,
                    (("count", str(len(entities))),),
                )
            )
            skills = await uow.list_skills(owner_user_id, profile.id)
            await uow.commit()
        return CareerProfileView(
            profile=profile,
            entities=tuple(sorted(entities, key=lambda item: item.sort_order)),
            skills=tuple(sorted(skills, key=lambda item: item.sort_order)),
            findings=timeline_findings(entities),
        )

    async def list_skills(self, owner_user_id: UUID) -> tuple[Skill, ...]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            skills = await uow.list_skills(owner_user_id, profile.id)
        return tuple(sorted(skills, key=lambda item: (item.sort_order, str(item.id))))

    async def get_skill(self, owner_user_id: UUID, skill_id: UUID) -> Skill:
        async with self._uow() as uow:
            skill = await uow.get_skill(owner_user_id, skill_id)
        if skill is None:
            raise CareerRecordNotFound
        return skill

    async def create_skill(
        self, owner_user_id: UUID, command: CreateSkill, context: RequestContext
    ) -> Skill:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            skills = await uow.list_skills(owner_user_id, profile.id)
            if len(skills) >= self._policy.max_skills:
                raise CareerRecordConflict("skill limit reached")
            if any(item.name.casefold() == command.name.strip().casefold() for item in skills):
                raise CareerRecordConflict("skill already exists")
            skill = Skill(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                profile_id=profile.id,
                name=command.name,
                category=command.category,
                proficiency=command.proficiency,
                sort_order=len(skills),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_skill(skill)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SKILL_CREATED,
                    "skill",
                    skill.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return skill

    async def update_skill(
        self,
        owner_user_id: UUID,
        skill_id: UUID,
        expected_version: int,
        command: UpdateSkill,
        context: RequestContext,
    ) -> Skill:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            skill = await uow.get_skill(owner_user_id, skill_id, for_update=True)
            if skill is None:
                raise CareerRecordNotFound
            self._version(skill.version, expected_version)
            skill.edit(
                name=command.name,
                category=command.category,
                proficiency=command.proficiency,
                now=now,
            )
            await uow.save_skill(skill)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SKILL_UPDATED,
                    "skill",
                    skill.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return skill

    async def delete_skill(
        self,
        owner_user_id: UUID,
        skill_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            skill = await uow.get_skill(owner_user_id, skill_id, for_update=True)
            if skill is None:
                raise CareerRecordNotFound
            self._version(skill.version, expected_version)
            await uow.delete_skill(owner_user_id, skill_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SKILL_DELETED,
                    "skill",
                    skill.id,
                    context,
                    now,
                )
            )
            await uow.commit()

    async def link_entity_skill(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        skill_id: UUID,
        context: RequestContext,
    ) -> EntitySkillLink:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id)
            skill = await uow.get_skill(owner_user_id, skill_id)
            if entity is None or skill is None or entity.profile_id != skill.profile_id:
                raise CareerRecordNotFound
            link = EntitySkillLink(self._ids.new(), owner_user_id, entity_id, skill_id, now)
            await uow.add_entity_skill_link(link)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_SKILL_LINKED,
                    "entity_skill_link",
                    link.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return link

    async def create_import_proposal(
        self, owner_user_id: UUID, command: CreateImportProposal, context: RequestContext
    ) -> ImportProposal:
        self._authorize(owner_user_id, context)
        source = await self._resolve_source(owner_user_id, command.source)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            entities = await uow.list_entities(owner_user_id, profile.id)
            target = None
            if command.target_entity_id is not None:
                target = await uow.get_entity(owner_user_id, command.target_entity_id)
                if target is None or target.profile_id != profile.id:
                    raise CareerRecordNotFound
                if target.kind is not command.proposed_entity.kind:
                    raise CareerRecordValidationError("proposal target kind does not match")
            proposed = self._entity(
                owner_user_id,
                profile.id,
                command.proposed_entity,
                sort_order=target.sort_order if target is not None else len(entities),
                now=now,
            )
            proposal = ImportProposal(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                profile_id=profile.id,
                target_entity_id=target.id if target is not None else None,
                proposed_entity=proposed,
                provenance=source.provenance(),
                status=ProposalStatus.PENDING,
                conflict_code=self._proposal_conflict(target, proposed),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_proposal(proposal)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PROPOSAL_CREATED,
                    "import_proposal",
                    proposal.id,
                    context,
                    now,
                    (("proposal_status", proposal.status.value),),
                )
            )
            await uow.commit()
        return proposal

    async def get_import_proposal(self, owner_user_id: UUID, proposal_id: UUID) -> ImportProposal:
        async with self._uow() as uow:
            proposal = await uow.get_proposal(owner_user_id, proposal_id)
        if proposal is None:
            raise CareerRecordNotFound
        return proposal

    async def import_proposal_source_available(
        self, owner_user_id: UUID, proposal_id: UUID
    ) -> bool:
        proposal = await self.get_import_proposal(owner_user_id, proposal_id)
        return await self._resume_sources.is_available(
            owner_user_id, self._validated_source(proposal.provenance)
        )

    async def list_import_proposals(
        self,
        owner_user_id: UUID,
        *,
        filter_by: ProposalFilter | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[ImportProposal]:
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            proposals = await uow.list_proposals(
                owner_user_id,
                filter_by or ProposalFilter(),
                PageCursor.decode(cursor),
                page_size + 1,
            )
        return next_page(tuple(proposals), page_size)

    async def accept_import_proposal(
        self,
        owner_user_id: UUID,
        proposal_id: UUID,
        expected_version: int,
        context: RequestContext,
        *,
        edited_entity: CareerEntityData | None = None,
    ) -> CareerEntity:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            proposal = await uow.get_proposal(owner_user_id, proposal_id, for_update=True)
            if proposal is None:
                raise CareerRecordNotFound
            self._version(proposal.version, expected_version)
            if not await self._resume_sources.is_available(
                owner_user_id, self._validated_source(proposal.provenance)
            ):
                raise CareerRecordSourceUnavailable("proposal source is no longer available")
            incoming = proposal.proposed_entity
            if edited_entity is not None:
                if edited_entity.kind is not incoming.kind:
                    raise CareerRecordValidationError("proposal entity kind cannot be changed")
                incoming = self._copy_entity_with_data(incoming, edited_entity, now)
                proposal.proposed_entity = incoming
            if proposal.target_entity_id is None:
                entity = incoming
                await uow.add_entity(entity)
            else:
                existing_entity = await uow.get_entity(
                    owner_user_id, proposal.target_entity_id, for_update=True
                )
                if existing_entity is None:
                    raise CareerRecordNotFound
                entity = existing_entity
                entity.edit(
                    title=incoming.title,
                    organization=incoming.organization,
                    description=incoming.description,
                    official_title=incoming.official_title,
                    display_title=incoming.display_title,
                    employment_type=incoming.employment_type,
                    location=incoming.location,
                    external_url=incoming.external_url,
                    start_date=incoming.start_date,
                    end_date=incoming.end_date,
                    is_current=incoming.is_current,
                    group_id=incoming.group_id,
                    now=now,
                )
                await uow.save_entity(entity)
            proposal.accept(now)
            await uow.save_proposal(proposal)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PROPOSAL_ACCEPTED,
                    "import_proposal",
                    proposal.id,
                    context,
                    now,
                    (("proposal_status", proposal.status.value),),
                )
            )
            await uow.commit()
        return entity

    async def reject_import_proposal(
        self,
        owner_user_id: UUID,
        proposal_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> ImportProposal:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            proposal = await uow.get_proposal(owner_user_id, proposal_id, for_update=True)
            if proposal is None:
                raise CareerRecordNotFound
            self._version(proposal.version, expected_version)
            proposal.reject(now)
            await uow.save_proposal(proposal)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PROPOSAL_REJECTED,
                    "import_proposal",
                    proposal.id,
                    context,
                    now,
                    (("proposal_status", proposal.status.value),),
                )
            )
            await uow.commit()
        return proposal

    async def create_evidence(
        self, owner_user_id: UUID, command: CreateEvidence, context: RequestContext
    ) -> EvidenceRecord:
        self._authorize(owner_user_id, context)
        self._validate_evidence_sources(command)
        validated_source = (
            await self._resolve_source(owner_user_id, command.resume_source)
            if command.resume_source is not None
            else None
        )
        exact_span = command.input_kind is EvidenceInputKind.EXACT_SOURCE_SPAN
        now = self._clock.now()
        evidence_id = self._ids.new()
        revision = initial_revision(
            revision_id=self._ids.new(),
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            evidence_type=command.evidence_type,
            title=command.title,
            statement=command.statement,
            context=command.context,
            organization=command.organization,
            project=command.project,
            start_date=command.start_date,
            end_date=command.end_date,
            input_kind=command.input_kind,
            exact_span_validated=exact_span,
            created_at=now,
        )
        item = EvidenceItem(
            id=evidence_id,
            owner_user_id=owner_user_id,
            lifecycle=EvidenceLifecycle.ACTIVE,
            current_revision=1,
            version=1,
            created_at=now,
            updated_at=now,
        )
        sources = self._initial_sources(
            owner_user_id,
            revision.id,
            command,
            validated_source,
            now,
        )
        metrics = self._metrics(owner_user_id, revision.id, command.metrics, now)
        transition = EvidenceStateTransition(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            from_revision_id=None,
            to_revision_id=revision.id,
            previous_strength=None,
            next_strength=revision.strength,
            authority=(
                EvidenceAuthority.SYSTEM_SOURCE_VALIDATION
                if exact_span
                else EvidenceAuthority.DETERMINISTIC_POLICY
            ),
            reason_code=(
                "exact_source_span_validated" if exact_span else "input_classified_inferred"
            ),
            actor_user_id=context.actor_user_id,
            verifier_reference=None,
            request_id=context.request_id,
            trace_id=context.trace_id,
            created_at=now,
        )
        entity_ids = tuple(dict.fromkeys(command.entity_ids))
        skill_ids = tuple(dict.fromkeys(command.skill_ids))
        record = EvidenceRecord(
            item=item,
            revision=revision,
            revisions=(revision,),
            transitions=(transition,),
            sources=sources,
            metrics=metrics,
            attachments=(),
            conflicts=(),
            entity_ids=entity_ids,
            skill_ids=skill_ids,
            usage=(),
        )
        async with self._uow() as uow:
            existing = await uow.list_evidence(
                owner_user_id,
                EvidenceFilter(include_archived=True),
                None,
                self._policy.max_evidence + 1,
            )
            if len(existing) >= self._policy.max_evidence:
                raise CareerRecordConflict("evidence limit reached")
            for entity_id in entity_ids:
                if await uow.get_entity(owner_user_id, entity_id) is None:
                    raise CareerRecordNotFound
            for skill_id in skill_ids:
                if await uow.get_skill(owner_user_id, skill_id) is None:
                    raise CareerRecordNotFound
            await uow.add_evidence(record)
            detected_conflicts = self._detect_evidence_conflicts(
                owner_user_id, record, existing, now
            )
            for conflict in detected_conflicts:
                await uow.add_conflict(conflict)
            for entity_id in entity_ids:
                await uow.add_evidence_entity_link(
                    EvidenceEntityLink(self._ids.new(), owner_user_id, evidence_id, entity_id, now)
                )
            for skill_id in skill_ids:
                await uow.add_evidence_skill_link(
                    EvidenceSkillLink(self._ids.new(), owner_user_id, evidence_id, skill_id, now)
                )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_CREATED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (("next_strength", revision.strength.value),),
                )
            )
            await uow.commit()
        return replace(record, conflicts=detected_conflicts)

    async def get_evidence(self, owner_user_id: UUID, evidence_id: UUID) -> EvidenceRecord:
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
        if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
            raise CareerRecordNotFound
        return record

    async def list_evidence(
        self,
        owner_user_id: UUID,
        *,
        filter_by: EvidenceFilter | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[EvidenceRecord]:
        page_size = self._page_size(limit)
        selected = filter_by or EvidenceFilter()
        if selected.query is not None:
            query = selected.query.strip()
            if not 1 <= len(query) <= 200:
                raise CareerRecordValidationError("evidence query must be 1 to 200 characters")
            selected = replace(selected, query=query)
        async with self._uow() as uow:
            records = await uow.list_evidence(
                owner_user_id,
                selected,
                PageCursor.decode(cursor),
                page_size + 1,
            )
        return next_page(tuple(records), page_size)

    async def revise_evidence(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        command: ReviseEvidence,
        context: RequestContext,
    ) -> EvidenceRecord:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id, for_update=True)
            if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
                raise CareerRecordNotFound
            self._version(record.item.version, expected_version)
            revision, transition = material_revision(
                current=record.revision,
                revision_id=self._ids.new(),
                transition_id=self._ids.new(),
                evidence_type=command.evidence_type,
                title=command.title,
                statement=command.statement,
                context=command.context,
                organization=command.organization,
                project=command.project,
                start_date=command.start_date,
                end_date=command.end_date,
                actor_user_id=context.actor_user_id,
                reason_code=command.reason_code,
                request_id=context.request_id,
                trace_id=context.trace_id,
                created_at=now,
            )
            sources = tuple(
                replace(
                    source,
                    id=self._ids.new(),
                    evidence_revision_id=revision.id,
                    exact_span_validated=False,
                    created_at=now,
                )
                for source in record.sources
            )
            metrics = self._metrics(owner_user_id, revision.id, command.metrics, now)
            self._advance_item(record.item, revision, now)
            candidate = self._record_successor(record, revision, transition, sources, metrics)
            existing = await uow.list_evidence(
                owner_user_id,
                EvidenceFilter(include_archived=True),
                None,
                self._policy.max_evidence,
            )
            detected_conflicts = self._detect_evidence_conflicts(
                owner_user_id, candidate, existing, now
            )
            await uow.append_evidence_revision(record.item, revision, transition, sources, metrics)
            for conflict in detected_conflicts:
                await uow.add_conflict(conflict)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_REVISED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (
                        ("previous_strength", record.revision.strength.value),
                        ("next_strength", revision.strength.value),
                        ("reason_code", command.reason_code),
                    ),
                )
            )
            await uow.commit()
        return replace(
            candidate,
            conflicts=(*candidate.conflicts, *detected_conflicts),
        )

    async def confirm_evidence(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> EvidenceRecord:
        return await self._transition_evidence(
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            expected_version=expected_version,
            next_strength=EvidenceStrength.CONFIRMED,
            authority=EvidenceAuthority.OWNER_CONFIRMATION,
            reason_code="owner_confirmed_scope",
            context=context,
        )

    async def mark_evidence_unsupported(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        reason_code: str,
        context: RequestContext,
    ) -> EvidenceRecord:
        return await self._transition_evidence(
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            expected_version=expected_version,
            next_strength=EvidenceStrength.UNSUPPORTED,
            authority=EvidenceAuthority.OWNER_REJECTION,
            reason_code=reason_code,
            context=context,
        )

    async def verify_evidence_internal(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        decision: VerificationDecision,
        context: RequestContext,
    ) -> EvidenceRecord:
        """Internal-only path; production composition intentionally has no authority."""

        self._authorize(owner_user_id, context)
        if self._verification_authority is None or not await self._verification_authority.authorize(
            owner_user_id, evidence_id, decision
        ):
            raise CareerRecordTransitionRejected("independent verification is not configured")
        return await self._transition_evidence(
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            expected_version=expected_version,
            next_strength=EvidenceStrength.VERIFIED,
            authority=EvidenceAuthority.SERVER_VERIFICATION,
            reason_code="server_verification_authorized",
            context=context,
            verification=decision,
        )

    async def archive_evidence(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> EvidenceItem:
        return await self._change_evidence_lifecycle(
            owner_user_id,
            evidence_id,
            expected_version,
            EvidenceLifecycle.ARCHIVED,
            context,
        )

    async def restore_evidence(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> EvidenceItem:
        return await self._change_evidence_lifecycle(
            owner_user_id,
            evidence_id,
            expected_version,
            EvidenceLifecycle.ACTIVE,
            context,
        )

    async def delete_evidence(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id, for_update=True)
            if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
                raise CareerRecordNotFound
            self._version(record.item.version, expected_version)
            if self._attachments is not None:
                for attachment in record.attachments:
                    if attachment.status is not AttachmentStatus.DELETED:
                        await self._attachments.delete(owner_user_id, attachment.id)
            record.item.delete(now)
            await uow.save_evidence_item(record.item)
            await uow.redact_evidence_content(owner_user_id, evidence_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_DELETED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (("lifecycle", EvidenceLifecycle.DELETED.value),),
                )
            )
            await uow.commit()

    async def link_evidence_entity(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        entity_id: UUID,
        context: RequestContext,
    ) -> EvidenceEntityLink:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
            entity = await uow.get_entity(owner_user_id, entity_id)
            if record is None or entity is None:
                raise CareerRecordNotFound
            if entity_id in record.entity_ids:
                raise CareerRecordConflict("evidence is already linked to entity")
            link = EvidenceEntityLink(self._ids.new(), owner_user_id, evidence_id, entity_id, now)
            await uow.add_evidence_entity_link(link)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_LINKED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return link

    async def link_evidence_skill(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        skill_id: UUID,
        context: RequestContext,
    ) -> EvidenceSkillLink:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
            skill = await uow.get_skill(owner_user_id, skill_id)
            if record is None or skill is None:
                raise CareerRecordNotFound
            if skill_id in record.skill_ids:
                raise CareerRecordConflict("evidence is already linked to skill")
            link = EvidenceSkillLink(self._ids.new(), owner_user_id, evidence_id, skill_id, now)
            await uow.add_evidence_skill_link(link)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_LINKED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return link

    async def create_evidence_conflict(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        conflicting_evidence_id: UUID | None,
        kind: EvidenceConflictKind,
        code: str,
        context: RequestContext,
    ) -> EvidenceConflict:
        """Internal deterministic detector hook; no public client route may call this."""

        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
            other = (
                await uow.get_evidence(owner_user_id, conflicting_evidence_id)
                if conflicting_evidence_id is not None
                else record
            )
            if record is None or other is None:
                raise CareerRecordNotFound
            conflict = EvidenceConflict(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_id=evidence_id,
                conflicting_evidence_id=conflicting_evidence_id,
                kind=kind,
                code=code,
                status=ConflictStatus.OPEN,
                resolution=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_conflict(conflict)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.CONFLICT_CREATED,
                    "evidence_conflict",
                    conflict.id,
                    context,
                    now,
                    (("conflict_kind", kind.value),),
                )
            )
            await uow.commit()
        return conflict

    async def resolve_evidence_conflict(
        self,
        owner_user_id: UUID,
        conflict_id: UUID,
        expected_version: int,
        resolution: ConflictResolution,
        context: RequestContext,
    ) -> EvidenceConflict:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            conflict = await uow.get_conflict(owner_user_id, conflict_id, for_update=True)
            if conflict is None:
                raise CareerRecordNotFound
            self._version(conflict.version, expected_version)
            conflict.resolve(resolution, now)
            await uow.save_conflict(conflict)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.CONFLICT_RESOLVED,
                    "evidence_conflict",
                    conflict.id,
                    context,
                    now,
                    (
                        ("conflict_kind", conflict.kind.value),
                        ("resolution", resolution.value),
                    ),
                )
            )
            await uow.commit()
        return conflict

    async def resolve_evidence_conflict_for_record(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_evidence_version: int,
        conflict_id: UUID,
        resolution: ConflictResolution,
        context: RequestContext,
        *,
        mark_unsupported: bool = False,
    ) -> EvidenceRecord:
        """Resolve an owned conflict and optional rejection in one transaction."""

        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id, for_update=True)
            conflict = await uow.get_conflict(owner_user_id, conflict_id, for_update=True)
            if (
                record is None
                or record.item.lifecycle is EvidenceLifecycle.DELETED
                or conflict is None
                or conflict.evidence_id != evidence_id
            ):
                raise CareerRecordNotFound
            self._version(record.item.version, expected_evidence_version)
            conflict.resolve(resolution, now)
            await uow.save_conflict(conflict)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.CONFLICT_RESOLVED,
                    "evidence_conflict",
                    conflict.id,
                    context,
                    now,
                    (
                        ("conflict_kind", conflict.kind.value),
                        ("resolution", resolution.value),
                    ),
                )
            )

            successor = record
            if mark_unsupported:
                revision, transition = transition_revision(
                    current=record.revision,
                    revision_id=self._ids.new(),
                    transition_id=self._ids.new(),
                    next_strength=EvidenceStrength.UNSUPPORTED,
                    authority=EvidenceAuthority.OWNER_REJECTION,
                    reason_code="conflict_owner_marked_unsupported",
                    actor_user_id=context.actor_user_id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    created_at=now,
                    metrics=record.metrics,
                )
                sources = tuple(
                    replace(
                        source,
                        id=self._ids.new(),
                        evidence_revision_id=revision.id,
                        created_at=now,
                    )
                    for source in record.sources
                )
                metrics = tuple(
                    replace(
                        metric,
                        id=self._ids.new(),
                        evidence_revision_id=revision.id,
                        created_at=now,
                    )
                    for metric in record.metrics
                )
                self._advance_item(record.item, revision, now)
                await uow.append_evidence_revision(
                    record.item, revision, transition, sources, metrics
                )
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        AuditAction.EVIDENCE_TRANSITIONED,
                        "evidence",
                        evidence_id,
                        context,
                        now,
                        (
                            ("previous_strength", record.revision.strength.value),
                            ("next_strength", EvidenceStrength.UNSUPPORTED.value),
                            ("reason_code", "conflict_owner_marked_unsupported"),
                        ),
                    )
                )
                successor = self._record_successor(record, revision, transition, sources, metrics)
            await uow.commit()
        return replace(
            successor,
            conflicts=tuple(
                conflict if item.id == conflict.id else item for item in successor.conflicts
            ),
        )

    async def list_eligible_evidence(
        self, owner_user_id: UUID, *, limit: int = 100
    ) -> tuple[EvidenceRecord, ...]:
        """Server-only owner-scoped evidence boundary for downstream modules."""

        page_size = self._page_size(limit)
        async with self._uow() as uow:
            records = await uow.list_evidence(
                owner_user_id,
                EvidenceFilter(lifecycle=EvidenceLifecycle.ACTIVE),
                None,
                page_size,
            )
        eligible: list[EvidenceRecord] = []
        for record in records:
            decision, refreshed = await self._evaluate_record(owner_user_id, record)
            if decision.eligible:
                eligible.append(refreshed)
        return tuple(eligible)

    async def evaluate_evidence(
        self, owner_user_id: UUID, evidence_id: UUID
    ) -> EligibilityDecision:
        """Explain factual/numeric eligibility using live server-side source state."""

        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
        if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
            raise CareerRecordNotFound
        decision, _ = await self._evaluate_record(owner_user_id, record)
        return decision

    async def get_evidence_with_eligibility(
        self, owner_user_id: UUID, evidence_id: UUID
    ) -> tuple[EvidenceRecord, EligibilityDecision]:
        """Return the owner-scoped record with live source/attachment availability."""

        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id)
        if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
            raise CareerRecordNotFound
        decision, refreshed = await self._evaluate_record(owner_user_id, record)
        return refreshed, decision

    async def create_achievement(
        self, owner_user_id: UUID, command: CreateAchievement, context: RequestContext
    ) -> AchievementDraft:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            if command.entity_id is not None:
                entity = await uow.get_entity(owner_user_id, command.entity_id)
                if entity is None or entity.profile_id != profile.id:
                    raise CareerRecordNotFound
            existing = await uow.list_achievements(
                owner_user_id, None, self._policy.max_achievements + 1
            )
            if len(existing) >= self._policy.max_achievements:
                raise CareerRecordConflict("achievement limit reached")
            achievement = self._achievement(owner_user_id, profile.id, command, now)
            await uow.add_achievement(achievement)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ACHIEVEMENT_CREATED,
                    "achievement",
                    achievement.id,
                    context,
                    now,
                    (("achievement_status", achievement.status.value),),
                )
            )
            await uow.commit()
        return achievement

    async def get_achievement(self, owner_user_id: UUID, achievement_id: UUID) -> AchievementDraft:
        async with self._uow() as uow:
            achievement = await uow.get_achievement(owner_user_id, achievement_id)
        if achievement is None:
            raise CareerRecordNotFound
        return achievement

    async def list_achievements(
        self,
        owner_user_id: UUID,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[AchievementDraft]:
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            achievements = await uow.list_achievements(
                owner_user_id,
                PageCursor.decode(cursor),
                page_size + 1,
            )
        return next_page(tuple(achievements), page_size)

    async def update_achievement(
        self,
        owner_user_id: UUID,
        achievement_id: UUID,
        expected_version: int,
        command: UpdateAchievement,
        context: RequestContext,
    ) -> AchievementDraft:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            achievement = await uow.get_achievement(owner_user_id, achievement_id, for_update=True)
            if achievement is None:
                raise CareerRecordNotFound
            self._version(achievement.version, expected_version)
            if achievement.status is not AchievementStatus.DRAFT:
                raise CareerRecordTransitionRejected("only a draft achievement can be edited")
            if (
                command.entity_id is not None
                and await uow.get_entity(owner_user_id, command.entity_id) is None
            ):
                raise CareerRecordNotFound
            candidate = self._achievement(
                owner_user_id,
                achievement.profile_id,
                command,
                achievement.created_at,
                achievement_id=achievement.id,
            )
            achievement.title = candidate.title
            achievement.delivered = candidate.delivered
            achievement.problem = candidate.problem
            achievement.audience = candidate.audience
            achievement.measurement = candidate.measurement
            achievement.effect = candidate.effect
            achievement.collaboration = candidate.collaboration
            achievement.methods = candidate.methods
            achievement.entity_id = candidate.entity_id
            achievement.metric = candidate.metric
            achievement.reminder_cadence = candidate.reminder_cadence
            achievement.remind_at = candidate.remind_at
            achievement.updated_at = now
            achievement.version += 1
            await uow.save_achievement(achievement)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ACHIEVEMENT_UPDATED,
                    "achievement",
                    achievement.id,
                    context,
                    now,
                    (("achievement_status", achievement.status.value),),
                )
            )
            await uow.commit()
        return achievement

    async def archive_achievement(
        self,
        owner_user_id: UUID,
        achievement_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> AchievementDraft:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            achievement = await uow.get_achievement(owner_user_id, achievement_id, for_update=True)
            if achievement is None:
                raise CareerRecordNotFound
            self._version(achievement.version, expected_version)
            if achievement.status is not AchievementStatus.DRAFT:
                raise CareerRecordTransitionRejected("only a draft achievement can be archived")
            achievement.status = AchievementStatus.ARCHIVED
            achievement.updated_at = now
            achievement.version += 1
            await uow.save_achievement(achievement)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ACHIEVEMENT_ARCHIVED,
                    "achievement",
                    achievement.id,
                    context,
                    now,
                    (("achievement_status", achievement.status.value),),
                )
            )
            await uow.commit()
        return achievement

    async def convert_achievement(
        self,
        owner_user_id: UUID,
        achievement_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> EvidenceRecord:
        """Explicitly and idempotently convert answered fields into confirmed evidence."""

        self._authorize(owner_user_id, context)
        self._idempotency_key(idempotency_key)
        now = self._clock.now()
        async with self._uow() as uow:
            prior = await uow.find_achievement_conversion(owner_user_id, idempotency_key)
            if prior is not None:
                if prior.id != achievement_id or prior.converted_evidence_id is None:
                    raise CareerRecordIdempotencyConflict
                existing = await uow.get_evidence(owner_user_id, prior.converted_evidence_id)
                if existing is None:
                    raise CareerRecordConflict("converted evidence is unavailable")
                return existing
            achievement = await uow.get_achievement(owner_user_id, achievement_id, for_update=True)
            if achievement is None:
                raise CareerRecordNotFound
            self._version(achievement.version, expected_version)
            if achievement.status is not AchievementStatus.DRAFT:
                raise CareerRecordTransitionRejected("only a draft achievement can be converted")
            if achievement.delivered is None:
                raise CareerRecordValidationError(
                    "delivered outcome must be answered before conversion"
                )
            entity = (
                await uow.get_entity(owner_user_id, achievement.entity_id)
                if achievement.entity_id is not None
                else None
            )
            evidence_id = self._ids.new()
            first_revision = initial_revision(
                revision_id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_id=evidence_id,
                evidence_type=EvidenceType.ACHIEVEMENT,
                title=achievement.title,
                statement=achievement.delivered,
                context=self._achievement_context(achievement),
                organization=entity.organization if entity is not None else None,
                project=(
                    entity.title if entity is not None and entity.kind.value == "project" else None
                ),
                start_date=entity.start_date if entity is not None else None,
                end_date=entity.end_date if entity is not None else None,
                input_kind=EvidenceInputKind.ACHIEVEMENT,
                exact_span_validated=False,
                created_at=now,
            )
            first_metrics = self._achievement_metrics(
                owner_user_id, first_revision.id, achievement.metric, now
            )
            confirmed_revision, confirmation = transition_revision(
                current=first_revision,
                revision_id=self._ids.new(),
                transition_id=self._ids.new(),
                next_strength=EvidenceStrength.CONFIRMED,
                authority=EvidenceAuthority.OWNER_CONFIRMATION,
                reason_code="achievement_owner_confirmed",
                actor_user_id=owner_user_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                created_at=now,
                metrics=first_metrics,
            )
            confirmed_metrics = tuple(
                replace(
                    metric,
                    id=self._ids.new(),
                    evidence_revision_id=confirmed_revision.id,
                    created_at=now,
                )
                for metric in first_metrics
            )
            source = EvidenceSource(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_revision_id=confirmed_revision.id,
                kind=EvidenceSourceKind.ACHIEVEMENT,
                label="Owner-confirmed achievement",
                provenance=None,
                attachment_id=None,
                external_url=None,
                available=True,
                exact_span_validated=False,
                created_at=now,
            )
            initial_transition = EvidenceStateTransition(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_id=evidence_id,
                from_revision_id=None,
                to_revision_id=first_revision.id,
                previous_strength=None,
                next_strength=EvidenceStrength.INFERRED,
                authority=EvidenceAuthority.DETERMINISTIC_POLICY,
                reason_code="achievement_draft_normalized",
                actor_user_id=owner_user_id,
                verifier_reference=None,
                request_id=context.request_id,
                trace_id=context.trace_id,
                created_at=now,
            )
            item = EvidenceItem(
                id=evidence_id,
                owner_user_id=owner_user_id,
                lifecycle=EvidenceLifecycle.ACTIVE,
                current_revision=confirmed_revision.revision,
                version=1,
                created_at=now,
                updated_at=now,
            )
            record = EvidenceRecord(
                item=item,
                revision=confirmed_revision,
                revisions=(first_revision, confirmed_revision),
                transitions=(initial_transition, confirmation),
                sources=(source,),
                metrics=confirmed_metrics,
                attachments=(),
                conflicts=(),
                entity_ids=((achievement.entity_id,) if achievement.entity_id is not None else ()),
                skill_ids=(),
                usage=(),
            )
            await uow.add_evidence(record)
            if achievement.entity_id is not None:
                await uow.add_evidence_entity_link(
                    EvidenceEntityLink(
                        self._ids.new(),
                        owner_user_id,
                        evidence_id,
                        achievement.entity_id,
                        now,
                    )
                )
            achievement.convert(evidence_id, idempotency_key, now)
            await uow.save_achievement(achievement)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ACHIEVEMENT_CONVERTED,
                    "achievement",
                    achievement.id,
                    context,
                    now,
                    (
                        ("achievement_status", achievement.status.value),
                        ("next_strength", EvidenceStrength.CONFIRMED.value),
                    ),
                )
            )
            await uow.commit()
        return record

    async def get_or_create_reminder_preferences(
        self, owner_user_id: UUID, context: RequestContext
    ) -> ReminderPreferences:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            preferences = await uow.get_reminder_preferences(owner_user_id, for_update=True)
            if preferences is None:
                preferences = ReminderPreferences(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    enabled=False,
                    day_of_month=None,
                    timezone="UTC",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.add_reminder_preferences(preferences)
                await uow.commit()
        return preferences

    async def update_reminder_preferences(
        self,
        owner_user_id: UUID,
        expected_version: int,
        command: UpdateReminderPreferences,
        context: RequestContext,
    ) -> ReminderPreferences:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            preferences = await uow.get_reminder_preferences(owner_user_id, for_update=True)
            if preferences is None:
                raise CareerRecordNotFound
            self._version(preferences.version, expected_version)
            preferences.edit(
                command.enabled,
                command.day_of_month,
                command.timezone,
                now,
            )
            await uow.save_reminder_preferences(preferences)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.REMINDERS_UPDATED,
                    "reminder_preferences",
                    preferences.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return preferences

    async def _transition_evidence(
        self,
        *,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        next_strength: EvidenceStrength,
        authority: EvidenceAuthority,
        reason_code: str,
        context: RequestContext,
        verification: VerificationDecision | None = None,
    ) -> EvidenceRecord:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id, for_update=True)
            if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
                raise CareerRecordNotFound
            self._version(record.item.version, expected_version)
            revision, transition = transition_revision(
                current=record.revision,
                revision_id=self._ids.new(),
                transition_id=self._ids.new(),
                next_strength=next_strength,
                authority=authority,
                reason_code=reason_code,
                actor_user_id=context.actor_user_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                created_at=now,
                metrics=record.metrics,
                verification=verification,
            )
            sources = tuple(
                replace(
                    source,
                    id=self._ids.new(),
                    evidence_revision_id=revision.id,
                    created_at=now,
                )
                for source in record.sources
            )
            if next_strength is EvidenceStrength.CONFIRMED:
                sources += (
                    EvidenceSource(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        evidence_revision_id=revision.id,
                        kind=EvidenceSourceKind.USER_ATTESTATION,
                        label="Owner confirmation",
                        provenance=None,
                        attachment_id=None,
                        external_url=None,
                        available=True,
                        exact_span_validated=False,
                        created_at=now,
                    ),
                )
            metrics = tuple(
                replace(
                    metric,
                    id=self._ids.new(),
                    evidence_revision_id=revision.id,
                    created_at=now,
                )
                for metric in record.metrics
            )
            self._advance_item(record.item, revision, now)
            await uow.append_evidence_revision(record.item, revision, transition, sources, metrics)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.EVIDENCE_TRANSITIONED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (
                        ("previous_strength", record.revision.strength.value),
                        ("next_strength", next_strength.value),
                        ("reason_code", reason_code),
                    ),
                )
            )
            await uow.commit()
        return self._record_successor(record, revision, transition, sources, metrics)

    async def _change_evidence_lifecycle(
        self,
        owner_user_id: UUID,
        evidence_id: UUID,
        expected_version: int,
        lifecycle: EvidenceLifecycle,
        context: RequestContext,
    ) -> EvidenceItem:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            record = await uow.get_evidence(owner_user_id, evidence_id, for_update=True)
            if record is None or record.item.lifecycle is EvidenceLifecycle.DELETED:
                raise CareerRecordNotFound
            self._version(record.item.version, expected_version)
            if lifecycle is EvidenceLifecycle.ARCHIVED:
                record.item.archive(now)
                action = AuditAction.EVIDENCE_ARCHIVED
            elif lifecycle is EvidenceLifecycle.ACTIVE:
                record.item.restore(now)
                action = AuditAction.EVIDENCE_RESTORED
            else:
                raise CareerRecordValidationError("unsupported evidence lifecycle operation")
            await uow.save_evidence_item(record.item)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    action,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (("lifecycle", lifecycle.value),),
                )
            )
            await uow.commit()
        return record.item

    def _entity(
        self,
        owner_user_id: UUID,
        profile_id: UUID,
        command: CareerEntityData,
        *,
        sort_order: int,
        now: datetime,
    ) -> CareerEntity:
        return CareerEntity(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            profile_id=profile_id,
            kind=command.kind,
            title=command.title,
            organization=command.organization,
            description=command.description,
            official_title=command.official_title,
            display_title=command.display_title,
            employment_type=command.employment_type,
            location=command.location,
            external_url=command.external_url,
            start_date=command.start_date,
            end_date=command.end_date,
            is_current=command.is_current,
            sort_order=sort_order,
            group_id=command.group_id,
            version=1,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _copy_entity_with_data(
        current: CareerEntity, command: CareerEntityData, now: datetime
    ) -> CareerEntity:
        """Validate and retain proposal identity while recording reviewed edits."""

        return CareerEntity(
            id=current.id,
            owner_user_id=current.owner_user_id,
            profile_id=current.profile_id,
            kind=command.kind,
            title=command.title,
            organization=command.organization,
            description=command.description,
            official_title=command.official_title,
            display_title=command.display_title,
            employment_type=command.employment_type,
            location=command.location,
            external_url=command.external_url,
            start_date=command.start_date,
            end_date=command.end_date,
            is_current=command.is_current,
            sort_order=current.sort_order,
            group_id=command.group_id,
            version=current.version,
            created_at=current.created_at,
            updated_at=now,
        )

    async def _resolve_source(
        self, owner_user_id: UUID, locator: ResumeSourceLocator
    ) -> ValidatedResumeSource:
        source = await self._resume_sources.resolve_exact_span(owner_user_id, locator)
        if source is None:
            raise CareerRecordSourceUnavailable("source span is unavailable or unauthorized")
        if (
            source.document_id != locator.document_id
            or source.snapshot_id != locator.snapshot_id
            or source.block_id != locator.block_id
            or source.page != locator.page
            or source.start_offset != locator.start_offset
            or source.end_offset != locator.end_offset
        ):
            raise CareerRecordSourceUnavailable("source query returned a mismatched span")
        if not await self._resume_sources.is_available(owner_user_id, source):
            raise CareerRecordSourceUnavailable("source span is no longer available")
        return source

    @staticmethod
    def _validated_source(provenance: ResumeProvenance) -> ValidatedResumeSource:
        return ValidatedResumeSource(
            document_id=provenance.document_id,
            snapshot_id=provenance.snapshot_id,
            snapshot_revision=provenance.snapshot_revision,
            schema_version=provenance.schema_version,
            parser_version=provenance.parser_version,
            block_id=provenance.block_id,
            page=provenance.page,
            start_offset=provenance.start_offset,
            end_offset=provenance.end_offset,
            source_sha256=provenance.source_sha256,
            review_excerpt=provenance.review_excerpt,
        )

    @staticmethod
    def _proposal_conflict(target: CareerEntity | None, proposed: CareerEntity) -> str | None:
        if target is None:
            return None
        if target.organization != proposed.organization:
            return "entity_organization_conflict"
        if (
            target.official_title != proposed.official_title
            or target.display_title != proposed.display_title
            or target.title != proposed.title
        ):
            return "entity_title_conflict"
        if target.start_date != proposed.start_date or target.end_date != proposed.end_date:
            return "entity_date_conflict"
        return None

    @staticmethod
    def _validate_evidence_sources(command: CreateEvidence) -> None:
        if command.input_kind in {
            EvidenceInputKind.EXACT_SOURCE_SPAN,
            EvidenceInputKind.PARSER,
        }:
            if command.resume_source is None or command.external_url_source is not None:
                raise CareerRecordValidationError(
                    "resume-derived evidence requires exactly one resume source"
                )
            return
        if command.input_kind is not EvidenceInputKind.MANUAL:
            raise CareerRecordValidationError(
                "input kind is not valid for public evidence creation"
            )
        if command.resume_source is not None:
            raise CareerRecordValidationError(
                "manual evidence cannot claim an unvalidated resume source"
            )

    def _initial_sources(
        self,
        owner_user_id: UUID,
        revision_id: UUID,
        command: CreateEvidence,
        validated_source: ValidatedResumeSource | None,
        now: datetime,
    ) -> tuple[EvidenceSource, ...]:
        sources: list[EvidenceSource] = []
        if validated_source is not None:
            sources.append(
                EvidenceSource(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    evidence_revision_id=revision_id,
                    kind=EvidenceSourceKind.RESUME,
                    label="Imported resume source",
                    provenance=validated_source.provenance(),
                    attachment_id=None,
                    external_url=None,
                    available=True,
                    exact_span_validated=(
                        command.input_kind is EvidenceInputKind.EXACT_SOURCE_SPAN
                    ),
                    created_at=now,
                )
            )
        if command.input_kind is EvidenceInputKind.MANUAL:
            sources.append(
                EvidenceSource(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    evidence_revision_id=revision_id,
                    kind=EvidenceSourceKind.USER_ATTESTATION,
                    label="Owner-provided draft",
                    provenance=None,
                    attachment_id=None,
                    external_url=None,
                    available=True,
                    exact_span_validated=False,
                    created_at=now,
                )
            )
        if command.external_url_source is not None:
            sources.append(
                EvidenceSource(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    evidence_revision_id=revision_id,
                    kind=EvidenceSourceKind.EXTERNAL_URL,
                    label="Owner-provided external link",
                    provenance=None,
                    attachment_id=None,
                    external_url=command.external_url_source,
                    available=True,
                    exact_span_validated=False,
                    created_at=now,
                )
            )
        return tuple(sources)

    def _metrics(
        self,
        owner_user_id: UUID,
        revision_id: UUID,
        values: tuple[MetricInput, ...],
        now: datetime,
    ) -> tuple[EvidenceMetric, ...]:
        if len(values) > 20:
            raise CareerRecordValidationError("an evidence revision supports at most 20 metrics")
        return tuple(
            EvidenceMetric(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_revision_id=revision_id,
                name=value.name,
                value=value.value,
                value_max=value.value_max,
                unit=value.unit,
                currency=value.currency,
                period=value.period,
                baseline=value.baseline,
                comparator=value.comparator,
                comparison_applicable=value.comparison_applicable,
                precision=value.precision,
                attribution=value.attribution,
                created_at=now,
            )
            for value in values
        )

    def _detect_evidence_conflicts(
        self,
        owner_user_id: UUID,
        candidate: EvidenceRecord,
        existing: list[EvidenceRecord],
        now: datetime,
    ) -> tuple[EvidenceConflict, ...]:
        """Detect only exact normalized contradictions; ambiguity stays untouched."""

        detected: list[EvidenceConflict] = []
        current = candidate.revision
        for other in existing:
            if other.item.id == candidate.item.id:
                continue
            comparison = other.revision
            same_type = current.evidence_type is comparison.evidence_type
            same_title = self._normalized(current.title) == self._normalized(comparison.title)
            same_org = self._normalized(current.organization) == self._normalized(
                comparison.organization
            )
            same_project = self._normalized(current.project) == self._normalized(comparison.project)
            kinds: list[tuple[EvidenceConflictKind, str]] = []
            if same_type and same_title and same_org and same_project:
                current_dates = (current.start_date, current.end_date)
                other_dates = (comparison.start_date, comparison.end_date)
                if any(value is not None for value in (*current_dates, *other_dates)) and (
                    current_dates != other_dates
                ):
                    kinds.append((EvidenceConflictKind.DATE, "exact_subject_date_mismatch"))
                if self._metric_values_conflict(candidate.metrics, other.metrics):
                    kinds.append((EvidenceConflictKind.METRIC, "exact_metric_value_mismatch"))
            same_statement = self._normalized(current.statement) == self._normalized(
                comparison.statement
            )
            if same_type and same_org and same_project and same_statement and not same_title:
                kinds.append((EvidenceConflictKind.TITLE, "exact_statement_title_mismatch"))
            if (
                same_type
                and same_title
                and same_project
                and current.organization is not None
                and comparison.organization is not None
                and not same_org
            ):
                kinds.append((EvidenceConflictKind.ENTITY, "exact_subject_entity_mismatch"))
            for kind, code in kinds:
                detected.append(
                    EvidenceConflict(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        evidence_id=candidate.item.id,
                        conflicting_evidence_id=other.item.id,
                        kind=kind,
                        code=code,
                        status=ConflictStatus.OPEN,
                        resolution=None,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return tuple(detected)

    @classmethod
    def _metric_values_conflict(
        cls, left: tuple[EvidenceMetric, ...], right: tuple[EvidenceMetric, ...]
    ) -> bool:
        left_by_scope = {
            (
                cls._normalized(metric.name),
                cls._normalized(metric.unit),
                cls._normalized(metric.period),
            ): (metric.value, metric.value_max)
            for metric in left
        }
        right_by_scope = {
            (
                cls._normalized(metric.name),
                cls._normalized(metric.unit),
                cls._normalized(metric.period),
            ): (metric.value, metric.value_max)
            for metric in right
        }
        shared = left_by_scope.keys() & right_by_scope.keys()
        return any(left_by_scope[key] != right_by_scope[key] for key in shared)

    @staticmethod
    def _normalized(value: str | None) -> str:
        return " ".join((value or "").casefold().split())

    def _achievement(
        self,
        owner_user_id: UUID,
        profile_id: UUID,
        command: CreateAchievement,
        created_at: datetime,
        *,
        achievement_id: UUID | None = None,
    ) -> AchievementDraft:
        return AchievementDraft(
            id=achievement_id or self._ids.new(),
            owner_user_id=owner_user_id,
            profile_id=profile_id,
            title=command.title,
            delivered=command.delivered,
            problem=command.problem,
            audience=command.audience,
            measurement=command.measurement,
            effect=command.effect,
            collaboration=command.collaboration,
            methods=command.methods,
            entity_id=command.entity_id,
            metric=(
                self._achievement_metric(command.metric) if command.metric is not None else None
            ),
            reminder_cadence=command.reminder_cadence,
            remind_at=command.remind_at,
            status=AchievementStatus.DRAFT,
            converted_evidence_id=None,
            conversion_idempotency_key=None,
            version=1,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def _achievement_metric(value: MetricInput) -> AchievementMetric:
        return AchievementMetric(
            name=value.name,
            value=value.value,
            value_max=value.value_max,
            unit=value.unit,
            currency=value.currency,
            period=value.period,
            baseline=value.baseline,
            comparator=value.comparator,
            comparison_applicable=value.comparison_applicable,
            precision=value.precision,
            attribution=value.attribution,
        )

    def _achievement_metrics(
        self,
        owner_user_id: UUID,
        revision_id: UUID,
        value: AchievementMetric | None,
        now: datetime,
    ) -> tuple[EvidenceMetric, ...]:
        if value is None:
            return ()
        return (
            EvidenceMetric(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                evidence_revision_id=revision_id,
                name=value.name,
                value=value.value,
                value_max=value.value_max,
                unit=value.unit,
                currency=value.currency,
                period=value.period,
                baseline=value.baseline,
                comparator=value.comparator,
                comparison_applicable=value.comparison_applicable,
                precision=value.precision,
                attribution=value.attribution,
                created_at=now,
            ),
        )

    @staticmethod
    def _achievement_context(achievement: AchievementDraft) -> str | None:
        answers = (
            ("Problem", achievement.problem),
            ("Audience", achievement.audience),
            ("Measurement", achievement.measurement),
            ("Effect", achievement.effect),
            ("Collaboration", achievement.collaboration),
            ("Methods", achievement.methods),
        )
        present = [f"{label}: {value}" for label, value in answers if value is not None]
        return "\n".join(present) or None

    async def _source_available(self, owner_user_id: UUID, source: EvidenceSource) -> bool:
        if source.kind is EvidenceSourceKind.RESUME:
            if source.provenance is None:
                return False
            return await self._resume_sources.is_available(
                owner_user_id, self._validated_source(source.provenance)
            )
        if source.kind is EvidenceSourceKind.ATTACHMENT:
            if source.attachment_id is None or self._attachments is None:
                return False
            return (
                await self._attachments.status(owner_user_id, source.attachment_id)
                is AttachmentStatus.CLEAN
            )
        return source.available

    async def _evaluate_record(
        self, owner_user_id: UUID, record: EvidenceRecord
    ) -> tuple[EligibilityDecision, EvidenceRecord]:
        source_availability = {
            source.id: await self._source_available(owner_user_id, source)
            for source in record.sources
        }
        attachments: list[EvidenceAttachment] = []
        for attachment in record.attachments:
            status = attachment.status
            if self._attachments is not None and status is not AttachmentStatus.DELETED:
                status = await self._attachments.status(owner_user_id, attachment.id)
            attachments.append(replace(attachment, status=status))
        refreshed_sources = tuple(
            replace(source, available=source_availability[source.id]) for source in record.sources
        )
        decision = evidence_eligibility(
            item=record.item,
            revision=record.revision,
            sources=record.sources,
            metrics=record.metrics,
            attachments=attachments,
            conflicts=record.conflicts,
            source_availability=source_availability,
            authorized_owner_user_id=owner_user_id,
        )
        return decision, replace(
            record,
            sources=refreshed_sources,
            attachments=tuple(attachments),
        )

    @staticmethod
    def _advance_item(item: EvidenceItem, revision: EvidenceRevision, now: datetime) -> None:
        item.current_revision = revision.revision
        item.version += 1
        item.updated_at = now

    @staticmethod
    def _record_successor(
        record: EvidenceRecord,
        revision: EvidenceRevision,
        transition: EvidenceStateTransition,
        sources: tuple[EvidenceSource, ...],
        metrics: tuple[EvidenceMetric, ...],
    ) -> EvidenceRecord:
        return replace(
            record,
            revision=revision,
            revisions=(*record.revisions, revision),
            transitions=(*record.transitions, transition),
            sources=sources,
            metrics=metrics,
        )

    @staticmethod
    def _authorize(owner_user_id: UUID, context: RequestContext) -> None:
        if context.actor_user_id != owner_user_id:
            raise CareerRecordNotFound

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if not 1 <= expected <= 2_147_483_647:
            raise CareerRecordValidationError("expected version must be a positive int32")
        if actual != expected:
            raise CareerRecordVersionConflict

    def _page_size(self, requested: int | None) -> int:
        value = requested if requested is not None else self._policy.default_page_size
        if not 1 <= value <= self._policy.max_page_size:
            raise CareerRecordValidationError(
                f"page size must be between 1 and {self._policy.max_page_size}"
            )
        return value

    @staticmethod
    def _validate_link_ids(values: tuple[UUID, ...]) -> None:
        if len(values) > 100:
            raise CareerRecordValidationError("an entity supports at most 100 skill links")
        if len(set(values)) != len(values):
            raise CareerRecordValidationError("skill links must be unique")

    @staticmethod
    def _idempotency_key(value: str) -> None:
        if _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise CareerRecordValidationError("idempotency key is invalid")

    def _audit(
        self,
        owner_user_id: UUID,
        action: AuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        details: tuple[tuple[str, str], ...] = (),
    ) -> CareerAuditEvent:
        return CareerAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            details=details,
            created_at=created_at,
        )
