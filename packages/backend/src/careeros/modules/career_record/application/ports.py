"""Inward-facing ports for the Career Record application service."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from careeros.modules.career_record.domain import (
    AchievementDraft,
    AttachmentStatus,
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
    VerificationDecision,
)

from .models import (
    AttachmentAdmissionRequest,
    AttachmentAdmissionResult,
    AttachmentFinalization,
    EvidenceFilter,
    EvidenceRecord,
    PageCursor,
    ProposalFilter,
    ResumeSourceLocator,
    ValidatedResumeSource,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...


class ResumeSourceQuery(Protocol):
    """Owner-checked Phase 2 application query; never a table adapter."""

    async def resolve_exact_span(
        self, owner_user_id: UUID, locator: ResumeSourceLocator
    ) -> ValidatedResumeSource | None: ...

    async def is_available(self, owner_user_id: UUID, source: ValidatedResumeSource) -> bool: ...


class AttachmentAdmission(Protocol):
    """Provider-neutral private attachment workflow boundary."""

    async def request_upload(
        self, owner_user_id: UUID, command: AttachmentAdmissionRequest
    ) -> AttachmentAdmissionResult: ...

    async def status(self, owner_user_id: UUID, attachment_id: UUID) -> AttachmentStatus: ...

    async def finalize(
        self, owner_user_id: UUID, attachment_id: UUID
    ) -> AttachmentFinalization: ...

    async def delete(self, owner_user_id: UUID, attachment_id: UUID) -> None: ...


class EvidenceVerificationAuthority(Protocol):
    """Internal-only authority; production composition leaves it unconfigured."""

    async def authorize(
        self, owner_user_id: UUID, evidence_id: UUID, decision: VerificationDecision
    ) -> bool: ...


class CareerRecordUnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def get_profile(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> CareerProfile | None: ...

    async def add_profile(self, profile: CareerProfile) -> None: ...

    async def save_profile(self, profile: CareerProfile) -> None: ...

    async def list_entities(
        self, owner_user_id: UUID, profile_id: UUID, *, for_update: bool = False
    ) -> list[CareerEntity]: ...

    async def get_entity(
        self, owner_user_id: UUID, entity_id: UUID, *, for_update: bool = False
    ) -> CareerEntity | None: ...

    async def add_entity(self, entity: CareerEntity) -> None: ...

    async def save_entity(self, entity: CareerEntity) -> None: ...

    async def delete_entity(self, owner_user_id: UUID, entity_id: UUID) -> None: ...

    async def list_skills(self, owner_user_id: UUID, profile_id: UUID) -> list[Skill]: ...

    async def get_skill(
        self, owner_user_id: UUID, skill_id: UUID, *, for_update: bool = False
    ) -> Skill | None: ...

    async def add_skill(self, skill: Skill) -> None: ...

    async def save_skill(self, skill: Skill) -> None: ...

    async def delete_skill(self, owner_user_id: UUID, skill_id: UUID) -> None: ...

    async def add_entity_skill_link(self, link: EntitySkillLink) -> None: ...

    async def list_entity_skill_links(
        self, owner_user_id: UUID, entity_id: UUID
    ) -> list[EntitySkillLink]: ...

    async def replace_entity_skill_links(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        links: Sequence[EntitySkillLink],
    ) -> None: ...

    async def get_proposal(
        self, owner_user_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> ImportProposal | None: ...

    async def list_proposals(
        self,
        owner_user_id: UUID,
        filter_by: ProposalFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[ImportProposal]: ...

    async def add_proposal(self, proposal: ImportProposal) -> None: ...

    async def save_proposal(self, proposal: ImportProposal) -> None: ...

    async def get_evidence(
        self, owner_user_id: UUID, evidence_id: UUID, *, for_update: bool = False
    ) -> EvidenceRecord | None: ...

    async def list_evidence(
        self,
        owner_user_id: UUID,
        filter_by: EvidenceFilter,
        after: PageCursor | None,
        limit: int,
    ) -> list[EvidenceRecord]: ...

    async def add_evidence(self, record: EvidenceRecord) -> None: ...

    async def save_evidence_item(self, item: EvidenceItem) -> None: ...

    async def append_evidence_revision(
        self,
        item: EvidenceItem,
        revision: EvidenceRevision,
        transition: EvidenceStateTransition,
        sources: Sequence[EvidenceSource],
        metrics: Sequence[EvidenceMetric],
    ) -> None: ...

    async def redact_evidence_content(self, owner_user_id: UUID, evidence_id: UUID) -> None: ...

    async def add_evidence_entity_link(self, link: EvidenceEntityLink) -> None: ...

    async def add_evidence_skill_link(self, link: EvidenceSkillLink) -> None: ...

    async def add_attachment(self, attachment: EvidenceAttachment) -> None: ...

    async def save_attachment(self, attachment: EvidenceAttachment) -> None: ...

    async def add_conflict(self, conflict: EvidenceConflict) -> None: ...

    async def get_conflict(
        self, owner_user_id: UUID, conflict_id: UUID, *, for_update: bool = False
    ) -> EvidenceConflict | None: ...

    async def save_conflict(self, conflict: EvidenceConflict) -> None: ...

    async def get_achievement(
        self, owner_user_id: UUID, achievement_id: UUID, *, for_update: bool = False
    ) -> AchievementDraft | None: ...

    async def list_achievements(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[AchievementDraft]: ...

    async def add_achievement(self, achievement: AchievementDraft) -> None: ...

    async def save_achievement(self, achievement: AchievementDraft) -> None: ...

    async def find_achievement_conversion(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AchievementDraft | None: ...

    async def get_reminder_preferences(
        self, owner_user_id: UUID, *, for_update: bool = False
    ) -> ReminderPreferences | None: ...

    async def add_reminder_preferences(self, preferences: ReminderPreferences) -> None: ...

    async def save_reminder_preferences(self, preferences: ReminderPreferences) -> None: ...

    async def add_audit(self, event: CareerAuditEvent) -> None: ...

    async def commit(self) -> None: ...


CareerRecordUnitOfWorkFactory = Callable[[], CareerRecordUnitOfWork]
