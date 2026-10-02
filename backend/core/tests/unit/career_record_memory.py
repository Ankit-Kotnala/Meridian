"""Deterministic in-memory Career Record ports for focused service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import TracebackType
from uuid import UUID, uuid4

from rezumi.modules.career_record.application.models import (
    CareerRecordAnalyticsGrowthPoint,
    CareerRecordAnalyticsSourceState,
    EvidenceFilter,
    EvidenceRecord,
    PageCursor,
    ProposalFilter,
    ResumeSourceLocator,
    ValidatedResumeSource,
)
from rezumi.modules.career_record.domain import (
    AchievementDraft,
    CareerAuditEvent,
    CareerEntity,
    CareerEntityConfirmation,
    CareerEntityRelationship,
    CareerFieldProvenance,
    CareerProfile,
    CareerSkillConfirmation,
    EntitySkillLink,
    EvidenceAttachment,
    EvidenceConflict,
    EvidenceEntityLink,
    EvidenceItem,
    EvidenceMetric,
    EvidenceRevision,
    EvidenceSkillLink,
    EvidenceSource,
    EvidenceStateTransition,
    ImportProposal,
    PersonalFact,
    ReminderPreferences,
    SemanticImportProposal,
    Skill,
    ValidatedSemanticCandidate,
    exact_claim_sha256,
)


class FixedClock:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value or datetime(2026, 7, 15, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


class UuidFactory:
    def new(self) -> UUID:
        return uuid4()


class FakeResumeSourceQuery:
    def __init__(self) -> None:
        self.sources: dict[tuple[UUID, UUID], ValidatedResumeSource] = {}
        self.available: set[UUID] = set()
        self.semantic_candidates: dict[
            tuple[UUID, UUID, UUID], tuple[ValidatedSemanticCandidate, ...]
        ] = {}
        self.active_resume = True

    async def has_active_resume(self, owner_user_id: UUID) -> bool:
        del owner_user_id
        return self.active_resume

    def add(self, owner_user_id: UUID, source: ValidatedResumeSource) -> None:
        self.sources[(owner_user_id, source.snapshot_id)] = source
        self.available.add(source.snapshot_id)

    async def resolve_exact_span(
        self,
        owner_user_id: UUID,
        locator: ResumeSourceLocator,
        expected_claim: str | None = None,
    ) -> ValidatedResumeSource | None:
        source = self.sources.get((owner_user_id, locator.snapshot_id))
        if (
            source is None
            or source.block_id != locator.block_id
            or (
                expected_claim is not None
                and exact_claim_sha256(expected_claim) != source.source_sha256
            )
        ):
            return None
        return source

    async def is_available(self, owner_user_id: UUID, source: ValidatedResumeSource) -> bool:
        return (
            owner_user_id,
            source.snapshot_id,
        ) in self.sources and source.snapshot_id in self.available

    def add_semantic(
        self,
        owner_user_id: UUID,
        document_id: UUID,
        snapshot_id: UUID,
        candidates: tuple[ValidatedSemanticCandidate, ...],
    ) -> None:
        self.semantic_candidates[(owner_user_id, document_id, snapshot_id)] = candidates

    async def reviewed_semantic_candidates(
        self,
        owner_user_id: UUID,
        document_id: UUID,
        snapshot_id: UUID,
    ) -> tuple[ValidatedSemanticCandidate, ...]:
        return self.semantic_candidates.get((owner_user_id, document_id, snapshot_id), ())


class AllowingVerificationAuthority:
    async def authorize(self, owner_user_id: UUID, evidence_id: UUID, decision: object) -> bool:
        del owner_user_id, evidence_id, decision
        return True


class MemoryCareerRecord:
    def __init__(self) -> None:
        self.profiles: dict[UUID, CareerProfile] = {}
        self.entities: dict[UUID, CareerEntity] = {}
        self.entity_confirmations: dict[UUID, CareerEntityConfirmation] = {}
        self.personal_facts: dict[UUID, PersonalFact] = {}
        self.field_provenance: list[CareerFieldProvenance] = []
        self.entity_relationships: list[CareerEntityRelationship] = []
        self.skills: dict[UUID, Skill] = {}
        self.skill_confirmations: dict[UUID, CareerSkillConfirmation] = {}
        self.entity_skill_links: list[EntitySkillLink] = []
        self.proposals: dict[UUID, ImportProposal] = {}
        self.semantic_proposals: dict[UUID, SemanticImportProposal] = {}
        self.evidence: dict[UUID, EvidenceRecord] = {}
        self.conflicts: dict[UUID, EvidenceConflict] = {}
        self.attachments: dict[UUID, EvidenceAttachment] = {}
        self.achievements: dict[UUID, AchievementDraft] = {}
        self.reminders: dict[UUID, ReminderPreferences] = {}
        self.audits: list[CareerAuditEvent] = []

    def __call__(self) -> MemoryCareerRecord:
        return self

    async def __aenter__(self) -> MemoryCareerRecord:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def get_profile(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> CareerProfile | None:
        del for_update
        return self.profiles.get(owner_user_id)

    async def add_profile(self, profile: CareerProfile) -> None:
        if profile.owner_user_id in self.profiles:
            raise RuntimeError("duplicate profile")
        self.profiles[profile.owner_user_id] = profile

    async def save_profile(self, profile: CareerProfile) -> None:
        self.profiles[profile.owner_user_id] = profile

    async def clear_profile_content(
        self, owner_user_id: UUID, profile_id: UUID, *, now: datetime
    ) -> None:
        del profile_id, now
        self.entities = {
            key: value
            for key, value in self.entities.items()
            if value.owner_user_id != owner_user_id
        }
        self.entity_confirmations = {
            key: value
            for key, value in self.entity_confirmations.items()
            if value.owner_user_id != owner_user_id
        }
        self.personal_facts = {
            key: value
            for key, value in self.personal_facts.items()
            if value.owner_user_id != owner_user_id
        }
        self.field_provenance = [
            value for value in self.field_provenance if value.owner_user_id != owner_user_id
        ]
        self.entity_relationships = [
            value for value in self.entity_relationships if value.owner_user_id != owner_user_id
        ]
        self.skills = {
            key: value for key, value in self.skills.items() if value.owner_user_id != owner_user_id
        }
        self.skill_confirmations = {
            key: value
            for key, value in self.skill_confirmations.items()
            if value.owner_user_id != owner_user_id
        }
        self.entity_skill_links = [
            value for value in self.entity_skill_links if value.owner_user_id != owner_user_id
        ]
        self.proposals = {
            key: value
            for key, value in self.proposals.items()
            if value.owner_user_id != owner_user_id
        }
        self.semantic_proposals = {
            key: value
            for key, value in self.semantic_proposals.items()
            if value.owner_user_id != owner_user_id
        }
        self.achievements = {
            key: value
            for key, value in self.achievements.items()
            if value.owner_user_id != owner_user_id
        }

    async def list_entities(
        self, owner_user_id: UUID, profile_id: UUID, *, for_update: bool = False
    ) -> list[CareerEntity]:
        del for_update
        return sorted(
            [
                item
                for item in self.entities.values()
                if item.owner_user_id == owner_user_id and item.profile_id == profile_id
            ],
            key=lambda item: (item.sort_order, str(item.id)),
        )

    async def get_entity(
        self, owner_user_id: UUID, entity_id: UUID, *, for_update: bool = False
    ) -> CareerEntity | None:
        del for_update
        item = self.entities.get(entity_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def add_entity(self, entity: CareerEntity) -> None:
        self.entities[entity.id] = entity

    async def save_entity(self, entity: CareerEntity) -> None:
        self.entities[entity.id] = entity

    async def delete_entity(self, owner_user_id: UUID, entity_id: UUID) -> None:
        item = await self.get_entity(owner_user_id, entity_id)
        if item is not None:
            del self.entities[item.id]
            self.entity_skill_links = [
                link for link in self.entity_skill_links if link.entity_id != entity_id
            ]

    async def get_entity_confirmation(
        self, owner_user_id: UUID, entity_id: UUID, *, for_update: bool = False
    ) -> CareerEntityConfirmation | None:
        del for_update
        item = self.entity_confirmations.get(entity_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def list_entity_confirmations(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerEntityConfirmation]:
        return [
            confirmation
            for entity_id, confirmation in self.entity_confirmations.items()
            if confirmation.owner_user_id == owner_user_id
            and (entity := self.entities.get(entity_id)) is not None
            and entity.profile_id == profile_id
        ]

    async def add_entity_confirmation(self, confirmation: CareerEntityConfirmation) -> None:
        self.entity_confirmations[confirmation.entity_id] = confirmation

    async def save_entity_confirmation(self, confirmation: CareerEntityConfirmation) -> None:
        self.entity_confirmations[confirmation.entity_id] = confirmation

    async def list_personal_facts(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[PersonalFact]:
        return [
            fact
            for fact in self.personal_facts.values()
            if fact.owner_user_id == owner_user_id and fact.profile_id == profile_id
        ]

    async def get_personal_fact(
        self, owner_user_id: UUID, fact_id: UUID, *, for_update: bool = False
    ) -> PersonalFact | None:
        del for_update
        fact = self.personal_facts.get(fact_id)
        return fact if fact is not None and fact.owner_user_id == owner_user_id else None

    async def add_personal_fact(self, fact: PersonalFact) -> None:
        self.personal_facts[fact.id] = fact

    async def save_personal_fact(self, fact: PersonalFact) -> None:
        self.personal_facts[fact.id] = fact

    async def delete_personal_fact(self, owner_user_id: UUID, fact_id: UUID) -> None:
        fact = await self.get_personal_fact(owner_user_id, fact_id)
        if fact is not None:
            del self.personal_facts[fact.id]

    async def add_field_provenance(self, provenance: CareerFieldProvenance) -> None:
        self.field_provenance.append(provenance)

    async def list_field_provenance(
        self, owner_user_id: UUID, target_id: UUID
    ) -> list[CareerFieldProvenance]:
        return [
            item
            for item in self.field_provenance
            if item.owner_user_id == owner_user_id and item.target_id == target_id
        ]

    async def add_entity_relationship(self, relationship: CareerEntityRelationship) -> None:
        self.entity_relationships.append(relationship)

    async def get_entity_relationship(
        self, owner_user_id: UUID, relationship_id: UUID
    ) -> CareerEntityRelationship | None:
        return next(
            (
                relationship
                for relationship in self.entity_relationships
                if relationship.owner_user_id == owner_user_id
                and relationship.id == relationship_id
            ),
            None,
        )

    async def list_entity_relationships(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerEntityRelationship]:
        return [
            item
            for item in self.entity_relationships
            if item.owner_user_id == owner_user_id and item.profile_id == profile_id
        ]

    async def delete_entity_relationship(self, owner_user_id: UUID, relationship_id: UUID) -> None:
        self.entity_relationships = [
            relationship
            for relationship in self.entity_relationships
            if not (
                relationship.owner_user_id == owner_user_id and relationship.id == relationship_id
            )
        ]

    async def list_skills(self, owner_user_id: UUID, profile_id: UUID) -> list[Skill]:
        return sorted(
            [
                item
                for item in self.skills.values()
                if item.owner_user_id == owner_user_id and item.profile_id == profile_id
            ],
            key=lambda item: (item.sort_order, str(item.id)),
        )

    async def get_skill(
        self, owner_user_id: UUID, skill_id: UUID, *, for_update: bool = False
    ) -> Skill | None:
        del for_update
        item = self.skills.get(skill_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def add_skill(self, skill: Skill) -> None:
        self.skills[skill.id] = skill

    async def save_skill(self, skill: Skill) -> None:
        self.skills[skill.id] = skill

    async def delete_skill(self, owner_user_id: UUID, skill_id: UUID) -> None:
        item = await self.get_skill(owner_user_id, skill_id)
        if item is not None:
            del self.skills[item.id]
            self.skill_confirmations.pop(item.id, None)
            self.entity_skill_links = [
                link for link in self.entity_skill_links if link.skill_id != skill_id
            ]

    async def get_skill_confirmation(
        self, owner_user_id: UUID, skill_id: UUID, *, for_update: bool = False
    ) -> CareerSkillConfirmation | None:
        del for_update
        item = self.skill_confirmations.get(skill_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def list_skill_confirmations(
        self, owner_user_id: UUID, profile_id: UUID
    ) -> list[CareerSkillConfirmation]:
        return [
            confirmation
            for skill_id, confirmation in self.skill_confirmations.items()
            if confirmation.owner_user_id == owner_user_id
            and (skill := self.skills.get(skill_id)) is not None
            and skill.profile_id == profile_id
        ]

    async def add_skill_confirmation(self, confirmation: CareerSkillConfirmation) -> None:
        self.skill_confirmations[confirmation.skill_id] = confirmation

    async def save_skill_confirmation(self, confirmation: CareerSkillConfirmation) -> None:
        self.skill_confirmations[confirmation.skill_id] = confirmation

    async def add_entity_skill_link(self, link: EntitySkillLink) -> None:
        self.entity_skill_links.append(link)

    async def list_entity_skill_links(
        self, owner_user_id: UUID, entity_id: UUID
    ) -> list[EntitySkillLink]:
        return [
            link
            for link in self.entity_skill_links
            if link.owner_user_id == owner_user_id and link.entity_id == entity_id
        ]

    async def list_entity_skill_links_for_owner(
        self,
        owner_user_id: UUID,
        entity_ids: tuple[UUID, ...] | None = None,
    ) -> list[EntitySkillLink]:
        links = [link for link in self.entity_skill_links if link.owner_user_id == owner_user_id]
        if entity_ids:
            allowed = set(entity_ids)
            links = [link for link in links if link.entity_id in allowed]
        return links

    async def replace_entity_skill_links(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        links: object,
    ) -> None:
        self.entity_skill_links = [
            link
            for link in self.entity_skill_links
            if not (link.owner_user_id == owner_user_id and link.entity_id == entity_id)
        ]
        self.entity_skill_links.extend(links)  # type: ignore[arg-type]

    async def get_proposal(
        self, owner_user_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> ImportProposal | None:
        del for_update
        item = self.proposals.get(proposal_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def list_proposals(
        self,
        owner_user_id: UUID,
        filter_by: ProposalFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ImportProposal]:
        values = [item for item in self.proposals.values() if item.owner_user_id == owner_user_id]
        if filter_by.status is not None:
            values = [item for item in values if item.status is filter_by.status]
        return self._page(values, after, limit)

    async def add_proposal(self, proposal: ImportProposal) -> None:
        self.proposals[proposal.id] = proposal

    async def save_proposal(self, proposal: ImportProposal) -> None:
        self.proposals[proposal.id] = proposal

    async def find_semantic_proposal(
        self,
        owner_user_id: UUID,
        snapshot_id: UUID,
        semantic_entity_id: UUID,
    ) -> SemanticImportProposal | None:
        return next(
            (
                proposal
                for proposal in self.semantic_proposals.values()
                if proposal.owner_user_id == owner_user_id
                and proposal.snapshot_id == snapshot_id
                and proposal.semantic_entity_id == semantic_entity_id
            ),
            None,
        )

    async def get_semantic_proposal(
        self, owner_user_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> SemanticImportProposal | None:
        del for_update
        proposal = self.semantic_proposals.get(proposal_id)
        return (
            proposal if proposal is not None and proposal.owner_user_id == owner_user_id else None
        )

    async def list_semantic_proposals(self, owner_user_id: UUID) -> list[SemanticImportProposal]:
        return [
            proposal
            for proposal in self.semantic_proposals.values()
            if proposal.owner_user_id == owner_user_id
        ]

    async def add_semantic_proposal(self, proposal: SemanticImportProposal) -> None:
        self.semantic_proposals[proposal.id] = proposal

    async def save_semantic_proposal(self, proposal: SemanticImportProposal) -> None:
        self.semantic_proposals[proposal.id] = proposal

    async def get_evidence(
        self, owner_user_id: UUID, evidence_id: UUID, *, for_update: bool = False
    ) -> EvidenceRecord | None:
        del for_update
        record = self.evidence.get(evidence_id)
        return record if record is not None and record.item.owner_user_id == owner_user_id else None

    async def get_evidence_batch(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> list[EvidenceRecord]:
        return [
            record
            for evidence_id in evidence_ids
            if (record := self.evidence.get(evidence_id)) is not None
            and record.item.owner_user_id == owner_user_id
        ]

    async def list_evidence(
        self,
        owner_user_id: UUID,
        filter_by: EvidenceFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[EvidenceRecord]:
        values = [
            record
            for record in self.evidence.values()
            if record.item.owner_user_id == owner_user_id
        ]
        if not filter_by.include_archived and filter_by.lifecycle is None:
            values = [record for record in values if record.item.lifecycle.value == "active"]
        if filter_by.lifecycle is not None:
            values = [record for record in values if record.item.lifecycle is filter_by.lifecycle]
        if filter_by.strength is not None:
            values = [record for record in values if record.revision.strength is filter_by.strength]
        if filter_by.conflict_status is not None:
            values = [
                record
                for record in values
                if any(item.status is filter_by.conflict_status for item in record.conflicts)
            ]
        if filter_by.query is not None:
            query = filter_by.query.casefold()
            values = [
                record
                for record in values
                if query in record.revision.title.casefold()
                or query in record.revision.statement.casefold()
            ]
        return self._page(values, after, limit)

    async def add_evidence(self, record: EvidenceRecord) -> None:
        self.evidence[record.item.id] = record

    async def list_analytics_growth(
        self,
        owner_user_id: UUID,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> list[CareerRecordAnalyticsGrowthPoint]:
        return [
            CareerRecordAnalyticsGrowthPoint(
                evidence_id=record.item.id,
                evidence_revision_id=record.revision.id,
                category=record.revision.evidence_type.value,
                occurred_at=record.revision.created_at,
            )
            for record in sorted(
                self.evidence.values(),
                key=lambda value: (value.revision.created_at, str(value.revision.id)),
            )
            if record.item.owner_user_id == owner_user_id
            and record.item.lifecycle.value == "active"
            and record.revision.evidence_type.value == "achievement"
            and record.revision.strength.value in {"supported", "confirmed", "verified"}
            and window_start <= record.revision.created_at.date() <= window_end
        ][:limit]

    async def get_analytics_source_state(
        self,
        owner_user_id: UUID,
    ) -> CareerRecordAnalyticsSourceState:
        records = [
            record
            for record in self.evidence.values()
            if record.item.owner_user_id == owner_user_id
            and record.item.lifecycle.value == "active"
            and record.revision.evidence_type.value == "achievement"
            and record.revision.strength.value in {"supported", "confirmed", "verified"}
        ]
        return CareerRecordAnalyticsSourceState(
            record_count=len(records),
            item_version_sum=sum(record.item.version for record in records),
            max_item_updated_at=max(
                (record.item.updated_at for record in records),
                default=None,
            ),
            max_revision_created_at=max(
                (record.revision.created_at for record in records),
                default=None,
            ),
        )

    async def save_evidence_item(self, item: EvidenceItem) -> None:
        record = self.evidence[item.id]
        self.evidence[item.id] = replace_record(record, item=item)

    async def append_evidence_revision(
        self,
        item: EvidenceItem,
        revision: EvidenceRevision,
        transition: EvidenceStateTransition,
        sources: list[EvidenceSource] | tuple[EvidenceSource, ...],
        metrics: list[EvidenceMetric] | tuple[EvidenceMetric, ...],
    ) -> None:
        record = self.evidence[item.id]
        self.evidence[item.id] = replace_record(
            record,
            item=item,
            revision=revision,
            revisions=(*record.revisions, revision),
            transitions=(*record.transitions, transition),
            sources=tuple(sources),
            metrics=tuple(metrics),
        )

    async def redact_evidence_content(self, owner_user_id: UUID, evidence_id: UUID) -> None:
        del owner_user_id, evidence_id

    async def add_evidence_entity_link(self, link: EvidenceEntityLink) -> None:
        record = self.evidence[link.evidence_id]
        if link.entity_id not in record.entity_ids:
            self.evidence[link.evidence_id] = replace_record(
                record, entity_ids=(*record.entity_ids, link.entity_id)
            )

    async def add_evidence_skill_link(self, link: EvidenceSkillLink) -> None:
        record = self.evidence[link.evidence_id]
        if link.skill_id not in record.skill_ids:
            self.evidence[link.evidence_id] = replace_record(
                record, skill_ids=(*record.skill_ids, link.skill_id)
            )

    async def add_attachment(self, attachment: EvidenceAttachment) -> None:
        self.attachments[attachment.id] = attachment
        record = self.evidence[attachment.evidence_id]
        self.evidence[attachment.evidence_id] = replace_record(
            record, attachments=(*record.attachments, attachment)
        )

    async def save_attachment(self, attachment: EvidenceAttachment) -> None:
        self.attachments[attachment.id] = attachment

    async def add_conflict(self, conflict: EvidenceConflict) -> None:
        self.conflicts[conflict.id] = conflict
        record = self.evidence.get(conflict.evidence_id)
        if record is not None and conflict.id not in {item.id for item in record.conflicts}:
            self.evidence[conflict.evidence_id] = replace_record(
                record, conflicts=(*record.conflicts, conflict)
            )
        if conflict.conflicting_evidence_id is not None:
            other = self.evidence.get(conflict.conflicting_evidence_id)
            if other is not None and conflict.id not in {item.id for item in other.conflicts}:
                self.evidence[other.item.id] = replace_record(
                    other, conflicts=(*other.conflicts, conflict)
                )

    async def get_conflict(
        self, owner_user_id: UUID, conflict_id: UUID, *, for_update: bool = False
    ) -> EvidenceConflict | None:
        del for_update
        item = self.conflicts.get(conflict_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def save_conflict(self, conflict: EvidenceConflict) -> None:
        self.conflicts[conflict.id] = conflict

    async def get_achievement(
        self, owner_user_id: UUID, achievement_id: UUID, *, for_update: bool = False
    ) -> AchievementDraft | None:
        del for_update
        item = self.achievements.get(achievement_id)
        return item if item is not None and item.owner_user_id == owner_user_id else None

    async def list_achievements(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[AchievementDraft]:
        values = [
            item for item in self.achievements.values() if item.owner_user_id == owner_user_id
        ]
        return self._page(values, after, limit)

    async def add_achievement(self, achievement: AchievementDraft) -> None:
        self.achievements[achievement.id] = achievement

    async def save_achievement(self, achievement: AchievementDraft) -> None:
        self.achievements[achievement.id] = achievement

    async def find_achievement_conversion(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AchievementDraft | None:
        return next(
            (
                item
                for item in self.achievements.values()
                if item.owner_user_id == owner_user_id
                and item.conversion_idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_reminder_preferences(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> ReminderPreferences | None:
        del for_update
        return self.reminders.get(owner_user_id)

    async def add_reminder_preferences(self, preferences: ReminderPreferences) -> None:
        self.reminders[preferences.owner_user_id] = preferences

    async def save_reminder_preferences(self, preferences: ReminderPreferences) -> None:
        self.reminders[preferences.owner_user_id] = preferences

    async def add_audit(self, event: CareerAuditEvent) -> None:
        self.audits.append(event)

    async def commit(self) -> None:
        return None

    @staticmethod
    def _page[T](values: list[T], after: PageCursor | None, limit: int) -> list[T]:
        ordered = sorted(
            values,
            key=lambda item: (item.created_at, str(item.id)),  # type: ignore[attr-defined]
            reverse=True,
        )
        if after is not None:
            ordered = [
                item
                for item in ordered
                if (item.created_at, str(item.id))  # type: ignore[attr-defined]
                < (after.created_at, str(after.item_id))
            ]
        return ordered[:limit]


def replace_record(record: EvidenceRecord, **changes: object) -> EvidenceRecord:
    values = {
        "item": record.item,
        "revision": record.revision,
        "revisions": record.revisions,
        "transitions": record.transitions,
        "sources": record.sources,
        "metrics": record.metrics,
        "attachments": record.attachments,
        "conflicts": record.conflicts,
        "entity_ids": record.entity_ids,
        "skill_ids": record.skill_ids,
        "usage": record.usage,
    }
    values.update(changes)
    return EvidenceRecord(**values)  # type: ignore[arg-type]
