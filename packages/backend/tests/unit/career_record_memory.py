"""Deterministic in-memory Career Record ports for focused service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from careeros.modules.career_record.application.models import (
    EvidenceFilter,
    EvidenceRecord,
    PageCursor,
    ProposalFilter,
    ResumeSourceLocator,
    ValidatedResumeSource,
)
from careeros.modules.career_record.domain import (
    AchievementDraft,
    CareerAuditEvent,
    CareerEntity,
    CareerProfile,
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
    ReminderPreferences,
    Skill,
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

    def add(self, owner_user_id: UUID, source: ValidatedResumeSource) -> None:
        self.sources[(owner_user_id, source.snapshot_id)] = source
        self.available.add(source.snapshot_id)

    async def resolve_exact_span(
        self, owner_user_id: UUID, locator: ResumeSourceLocator
    ) -> ValidatedResumeSource | None:
        source = self.sources.get((owner_user_id, locator.snapshot_id))
        if source is None or source.block_id != locator.block_id:
            return None
        return source

    async def is_available(self, owner_user_id: UUID, source: ValidatedResumeSource) -> bool:
        return (
            owner_user_id,
            source.snapshot_id,
        ) in self.sources and source.snapshot_id in self.available


class AllowingVerificationAuthority:
    async def authorize(self, owner_user_id: UUID, evidence_id: UUID, decision: object) -> bool:
        del owner_user_id, evidence_id, decision
        return True


class MemoryCareerRecord:
    def __init__(self) -> None:
        self.profiles: dict[UUID, CareerProfile] = {}
        self.entities: dict[UUID, CareerEntity] = {}
        self.skills: dict[UUID, Skill] = {}
        self.entity_skill_links: list[EntitySkillLink] = []
        self.proposals: dict[UUID, ImportProposal] = {}
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
            self.entity_skill_links = [
                link for link in self.entity_skill_links if link.skill_id != skill_id
            ]

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

    async def get_evidence(
        self, owner_user_id: UUID, evidence_id: UUID, *, for_update: bool = False
    ) -> EvidenceRecord | None:
        del for_update
        record = self.evidence.get(evidence_id)
        return record if record is not None and record.item.owner_user_id == owner_user_id else None

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
