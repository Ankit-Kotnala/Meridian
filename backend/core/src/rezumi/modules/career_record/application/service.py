"""Career Record application use cases and atomic policy orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date, datetime
from hmac import compare_digest
from uuid import UUID

from rezumi.modules.career_record.domain import (
    AchievementDraft,
    AchievementMetric,
    AchievementStatus,
    AttachmentStatus,
    AuditAction,
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
    CareerRecordNotFound,
    CareerRecordSourceUnavailable,
    CareerRecordTransitionRejected,
    CareerRecordValidationError,
    CareerRecordVersionConflict,
    CareerRelationshipKind,
    CareerSkillConfirmation,
    ConfirmationState,
    ConflictResolution,
    ConflictStatus,
    EligibilityDecision,
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
    ImportProposal,
    PartialDate,
    PersonalFact,
    PersonalFactKind,
    ProposalStatus,
    ReminderPreferences,
    ResumeProvenance,
    SemanticCandidateKind,
    SemanticFieldOrigin,
    SemanticImportAnchor,
    SemanticImportField,
    SemanticImportFieldState,
    SemanticImportProposal,
    SemanticImportStatus,
    SemanticImportTarget,
    Skill,
    ValidatedSemanticCandidate,
    VerificationDecision,
    evidence_eligibility,
    exact_claim_sha256,
    initial_revision,
    material_revision,
    normalize_semantic_url,
    reorder_entities,
    timeline_findings,
    transition_revision,
)

from .models import (
    AcceptSemanticImportProposal,
    CareerEntityData,
    CareerProfileView,
    CareerRecordAnalyticsGrowthPoint,
    CareerRecordAnalyticsWatermark,
    CareerRecordReadinessSnapshot,
    CreateAchievement,
    CreateCareerProfile,
    CreateEvidence,
    CreateImportProposal,
    CreatePersonalFact,
    CreateSemanticImportProposals,
    CreateSkill,
    EvidenceFilter,
    EvidenceRecord,
    LinkCareerEntityRelationship,
    MetricInput,
    Page,
    PageCursor,
    ProposalFilter,
    ReadinessSnapshotEntity,
    ReadinessSnapshotEvidence,
    ReadinessSnapshotPersonalFact,
    ReadinessSnapshotRelationship,
    ReadinessSnapshotSkill,
    RequestContext,
    ResumeSourceLocator,
    ReviseEvidence,
    SemanticImportAcceptance,
    SemanticImportBatch,
    SemanticImportQuestion,
    UpdateAchievement,
    UpdateCareerProfile,
    UpdatePersonalFact,
    UpdateReminderPreferences,
    UpdateSkill,
    ValidatedResumeSource,
    next_page,
)
from .ports import (
    AttachmentAdmission,
    CareerRecordUnitOfWork,
    CareerRecordUnitOfWorkFactory,
    Clock,
    EvidenceVerificationAuthority,
    IdentifierFactory,
    ResumeSourceQuery,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_MERGE_CONFLICT_CODES = frozenset(
    {"existing_personal_fact", "existing_skill", "existing_entity"},
)
# Career Analytics accepts a public 3,650-day delta and expands both ends by
# one UTC day so every IANA timezone boundary is represented. This internal
# source-only limit is therefore intentionally two days wider.
_ANALYTICS_SOURCE_MAX_WINDOW_DAYS = 3_652
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _semantic_values_by_name(
    fields: tuple[SemanticImportField, ...],
    values: dict[UUID, str],
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for field in fields:
        value = values.get(field.semantic_field_id)
        if value is None:
            continue
        grouped.setdefault(field.name, []).append(value.strip())
    return grouped


def _expand_semantic_candidates(
    candidates: tuple[ValidatedSemanticCandidate, ...],
) -> tuple[ValidatedSemanticCandidate, ...]:
    """Split multi-name skill snapshots into one import candidate per skill."""

    expanded: list[ValidatedSemanticCandidate] = []
    for candidate in candidates:
        if candidate.kind is not SemanticCandidateKind.SKILL:
            expanded.append(candidate)
            continue
        name_fields = [field for field in candidate.fields if field.name == "name"]
        if len(name_fields) <= 1:
            expanded.append(candidate)
            continue
        category = next(
            (field for field in candidate.fields if field.name == "category"),
            None,
        )
        for name_field in name_fields:
            fields = (name_field,) + ((category,) if category is not None else ())
            expanded.append(
                ValidatedSemanticCandidate(
                    document_id=candidate.document_id,
                    snapshot_id=candidate.snapshot_id,
                    snapshot_revision=candidate.snapshot_revision,
                    schema_version=candidate.schema_version,
                    parser_version=candidate.parser_version,
                    semantic_entity_id=name_field.semantic_field_id,
                    kind=candidate.kind,
                    fields=fields,
                )
            )
    return tuple(expanded)


def _semantic_mapping_issues(
    kind: SemanticCandidateKind,
    fields: tuple[SemanticImportField, ...],
    values: dict[UUID, str],
) -> tuple[str, ...]:
    if set(values) != {field.semantic_field_id for field in fields}:
        return ("reviewed_fields",)
    grouped = _semantic_values_by_name(fields, values)
    required: tuple[str, ...]
    if kind is SemanticCandidateKind.CONTACT:
        required = ()
    elif kind is SemanticCandidateKind.SKILL:
        required = ("name",)
    elif kind is SemanticCandidateKind.EXPERIENCE:
        required = ("title", "employer")
    elif kind is SemanticCandidateKind.EDUCATION:
        required = ("institution",)
    elif kind is SemanticCandidateKind.PROJECT:
        required = ("name",)
    else:
        required = ("name",)
    issues = [name for name in required if not grouped.get(name) or not grouped[name][0]]
    if kind is SemanticCandidateKind.EDUCATION and not (
        grouped.get("degree") or grouped.get("field")
    ):
        issues.append("degree_or_field")
    for field in fields:
        value = values[field.semantic_field_id].strip()
        if not value:
            issues.append(field.name)
        if field.field_type == "date" and value.casefold() not in {
            "present",
            "current",
        }:
            try:
                _partial_date_from_semantic(value, field.date_precision)
            except CareerRecordValidationError:
                issues.append(field.name)
        if field.name == "employment_type":
            try:
                _employment_type(value)
            except CareerRecordValidationError:
                issues.append(field.name)
        if field.field_type == "url" and value:
            try:
                normalize_semantic_url(value)
            except CareerRecordValidationError:
                issues.append(field.name)
    return tuple(dict.fromkeys(issues))


def _partial_date_from_semantic(value: str, precision: str | None) -> PartialDate:
    normalized = value.strip().casefold().replace(",", " ")
    if precision == "unknown":
        raise CareerRecordValidationError("unknown date precision requires review")
    year_match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2}|2200)\b", normalized)
    if year_match is None:
        raise CareerRecordValidationError("semantic date requires a supported year")
    year = int(year_match.group(1))
    if precision == "year":
        return PartialDate(year)
    month: int | None = None
    for name, number in _MONTHS.items():
        if re.search(rf"\b{re.escape(name)}\b", normalized):
            month = number
            break
    if month is None:
        numeric = re.fullmatch(
            r"\s*(?:(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?|"
            r"\d{1,2}[-/](\d{1,2})[-/](\d{4})|"
            r"(\d{1,2})[-/](\d{4}))\s*",
            normalized,
        )
        if numeric is not None:
            if numeric.group(1) is not None:
                month = int(numeric.group(2))
            elif numeric.group(4) is not None:
                month = int(numeric.group(3))
            else:
                month = int(numeric.group(5))
    if month is None:
        raise CareerRecordValidationError("semantic month requires review")
    return PartialDate(year, month)


def _employment_type(value: str) -> EmploymentType:
    normalized = re.sub(r"[\s-]+", "_", value.strip().casefold())
    aliases = {
        "fulltime": "full_time",
        "parttime": "part_time",
        "freelance": "contract",
        "temp": "temporary",
    }
    return EmploymentType(aliases.get(normalized, normalized))


def _semantic_entity_data(
    kind: SemanticCandidateKind,
    fields: tuple[SemanticImportField, ...],
    values: dict[UUID, str],
) -> CareerEntityData:
    grouped = _semantic_values_by_name(fields, values)

    def first(name: str) -> str | None:
        candidates = grouped.get(name)
        return candidates[0] if candidates else None

    def date_value(name: str) -> PartialDate | None:
        candidate = next((field for field in fields if field.name == name), None)
        if candidate is None:
            return None
        value = values[candidate.semantic_field_id].strip()
        if value.casefold() in {"present", "current"}:
            return None
        return _partial_date_from_semantic(value, candidate.date_precision)

    description_parts = [
        *grouped.get("description", ()),
        *grouped.get("achievement", ()),
    ]
    description = "\n".join(value for value in description_parts if value) or None
    start_name = "issued_date" if kind is SemanticCandidateKind.CERTIFICATION else "start_date"
    end_name = "expires_date" if kind is SemanticCandidateKind.CERTIFICATION else "end_date"
    end_text = first(end_name)
    is_current = bool(end_text and end_text.casefold() in {"present", "current"})
    if kind is SemanticCandidateKind.EXPERIENCE:
        return CareerEntityData(
            kind=CareerEntityKind.EXPERIENCE,
            title=first("title") or "",
            organization=first("employer"),
            description=description,
            official_title=first("title"),
            display_title=first("title"),
            employment_type=(
                _employment_type(first("employment_type") or "")
                if first("employment_type")
                else None
            ),
            location=first("location"),
            external_url=first("link"),
            start_date=date_value(start_name),
            end_date=date_value(end_name),
            is_current=is_current,
        )
    if kind is SemanticCandidateKind.EDUCATION:
        degree = first("degree") or first("field") or ""
        return CareerEntityData(
            kind=CareerEntityKind.EDUCATION,
            title=degree,
            organization=first("institution"),
            description=first("field") if first("field") != degree else None,
            location=first("location"),
            external_url=first("link"),
            start_date=date_value(start_name),
            end_date=date_value(end_name),
            is_current=is_current,
        )
    if kind is SemanticCandidateKind.PROJECT:
        return CareerEntityData(
            kind=CareerEntityKind.PROJECT,
            title=first("name") or "",
            description=description,
            external_url=first("link"),
            start_date=date_value(start_name),
            end_date=date_value(end_name),
            is_current=is_current,
        )
    if kind is SemanticCandidateKind.CERTIFICATION:
        return CareerEntityData(
            kind=CareerEntityKind.CREDENTIAL,
            title=first("name") or "",
            organization=first("issuer"),
            description=first("credential_id"),
            external_url=first("link"),
            start_date=date_value(start_name),
            end_date=date_value(end_name),
        )
    raise CareerRecordValidationError("semantic candidate is not a career entity")


def _semantic_auto_apply_blocked(proposal: SemanticImportProposal) -> bool:
    """Return True when a reviewed proposal still needs an explicit decision."""

    if proposal.conflict_code is None:
        return False
    return proposal.conflict_code not in _MERGE_CONFLICT_CODES


def _semantic_target_match(
    kind: SemanticCandidateKind,
    fields: tuple[SemanticImportField, ...],
    *,
    entities: list[CareerEntity],
    skills: list[Skill],
    facts: list[PersonalFact],
) -> tuple[SemanticImportTarget, UUID | None, str | None]:
    values = {field.semantic_field_id: field.value for field in fields}
    grouped = _semantic_values_by_name(fields, values)
    if kind is SemanticCandidateKind.CONTACT:
        duplicate = any(
            any(fact.kind.value == field.name and fact.value == field.value for fact in facts)
            for field in fields
        )
        return (
            SemanticImportTarget.PERSONAL_FACTS,
            None,
            "existing_personal_fact" if duplicate else None,
        )
    if kind is SemanticCandidateKind.SKILL:
        name = grouped["name"][0]
        skill_target = next(
            (skill for skill in skills if skill.name.casefold() == name.casefold()),
            None,
        )
        return (
            SemanticImportTarget.SKILL,
            skill_target.id if skill_target is not None else None,
            "existing_skill" if skill_target is not None else None,
        )
    proposed = _semantic_entity_data(kind, fields, values)
    entity_target = next(
        (
            entity
            for entity in entities
            if entity.kind is proposed.kind
            and entity.title.casefold() == proposed.title.casefold()
            and (entity.organization or "").casefold() == (proposed.organization or "").casefold()
        ),
        None,
    )
    return (
        SemanticImportTarget.ENTITY,
        entity_target.id if entity_target is not None else None,
        "existing_entity" if entity_target is not None else None,
    )


def _partial_date_text(value: PartialDate | None) -> str | None:
    if value is None:
        return None
    return f"{value.year:04d}" + (f"-{value.month:02d}" if value.month is not None else "")


def _semantic_entity_provenance_targets(
    kind: SemanticCandidateKind,
    field: SemanticImportField,
    data: CareerEntityData,
) -> tuple[tuple[str, str], ...]:
    """Map one reviewed semantic field to the canonical fields it produced."""

    values = {
        "title": data.title,
        "organization": data.organization,
        "description": data.description,
        "official_title": data.official_title,
        "display_title": data.display_title,
        "employment_type": (
            data.employment_type.value if data.employment_type is not None else None
        ),
        "location": data.location,
        "external_url": data.external_url,
        "start_date": _partial_date_text(data.start_date),
        "end_date": _partial_date_text(data.end_date),
        "is_current": "true" if data.is_current else "false",
    }
    semantic_name = field.name
    targets: tuple[str, ...]
    if kind is SemanticCandidateKind.EXPERIENCE:
        targets = {
            "title": ("title", "official_title", "display_title"),
            "employer": ("organization",),
            "description": ("description",),
            "achievement": ("description",),
            "employment_type": ("employment_type",),
            "location": ("location",),
            "link": ("external_url",),
            "start_date": ("start_date",),
            "end_date": ("is_current",) if data.is_current else ("end_date",),
        }.get(semantic_name, ())
    elif kind is SemanticCandidateKind.EDUCATION:
        targets = {
            "degree": ("title",),
            "field": ("description",) if data.description is not None else ("title",),
            "institution": ("organization",),
            "location": ("location",),
            "link": ("external_url",),
            "start_date": ("start_date",),
            "end_date": ("is_current",) if data.is_current else ("end_date",),
        }.get(semantic_name, ())
    elif kind is SemanticCandidateKind.PROJECT:
        targets = {
            "name": ("title",),
            "description": ("description",),
            "achievement": ("description",),
            "link": ("external_url",),
            "start_date": ("start_date",),
            "end_date": ("is_current",) if data.is_current else ("end_date",),
        }.get(semantic_name, ())
    elif kind is SemanticCandidateKind.CERTIFICATION:
        targets = {
            "name": ("title",),
            "issuer": ("organization",),
            "credential_id": ("description",),
            "link": ("external_url",),
            "issued_date": ("start_date",),
            "expires_date": ("end_date",),
        }.get(semantic_name, ())
    else:
        targets = ()
    return tuple(
        (field_name, value)
        for field_name in targets
        if (value := values.get(field_name)) is not None and value != ""
    )


def _semantic_outcome_field(
    kind: SemanticCandidateKind,
    field: SemanticImportField,
) -> bool:
    """Return True when a reviewed semantic field should become inbox/evidence rows."""

    if field.field_type != "bullet":
        return False
    if field.name == "achievement" and kind in {
        SemanticCandidateKind.EXPERIENCE,
        SemanticCandidateKind.PROJECT,
    }:
        return True
    return field.name == "description" and kind is SemanticCandidateKind.PROJECT


def _achievement_title_from_statement(statement: str, organization: str | None) -> str:
    cleaned = " ".join(statement.strip().split())
    if not cleaned:
        return "Resume outcome"
    if organization:
        return f"{organization}: {cleaned}"[:120]
    return cleaned[:120]


def _normalize_statement(value: str) -> str:
    return " ".join(value.strip().split())


def _resume_locator(
    proposal: SemanticImportProposal,
    anchor: SemanticImportAnchor,
) -> ResumeSourceLocator:
    return ResumeSourceLocator(
        document_id=proposal.document_id,
        snapshot_id=proposal.snapshot_id,
        block_id=anchor.block_id,
        page=anchor.page,
        start_offset=anchor.start_offset,
        end_offset=anchor.end_offset,
    )


def _entity_factual_values(entity: CareerEntity) -> tuple[tuple[str, str], ...]:
    """Serialize only current factual fields for owner-attestation digests."""

    values: tuple[tuple[str, object | None], ...] = (
        ("title", entity.title),
        ("organization", entity.organization),
        ("description", entity.description),
        ("official_title", entity.official_title),
        ("display_title", entity.display_title),
        (
            "employment_type",
            entity.employment_type.value if entity.employment_type is not None else None,
        ),
        ("location", entity.location),
        ("external_url", entity.external_url),
        (
            "start_date",
            _partial_date_text(entity.start_date),
        ),
        (
            "end_date",
            _partial_date_text(entity.end_date),
        ),
        ("is_current", "true" if entity.is_current else "false"),
    )
    return tuple(
        (field_name, str(value))
        for field_name, value in values
        if value is not None and str(value) != ""
    )


def _skill_factual_values(skill: Skill) -> tuple[tuple[str, str], ...]:
    values = (
        ("name", skill.name),
        ("category", skill.category),
        (
            "proficiency",
            skill.proficiency.value if skill.proficiency is not None else None,
        ),
    )
    return tuple(
        (field_name, value) for field_name, value in values if value is not None and value != ""
    )


@dataclass(frozen=True, slots=True)
class CareerRecordPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_entities: int = 500
    max_skills: int = 500
    max_evidence: int = 2_000
    max_achievements: int = 1_000
    max_personal_facts: int = 100
    max_semantic_import_proposals: int = 500

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("career record page limits are invalid")
        if (
            min(
                self.max_entities,
                self.max_skills,
                self.max_evidence,
                self.max_achievements,
                self.max_personal_facts,
                self.max_semantic_import_proposals,
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

    async def _reviewed_semantic_candidates(
        self,
        owner_user_id: UUID,
        document_id: UUID,
        snapshot_id: UUID,
    ) -> tuple[ValidatedSemanticCandidate, ...]:
        return _expand_semantic_candidates(
            await self._resume_sources.reviewed_semantic_candidates(
                owner_user_id,
                document_id,
                snapshot_id,
            )
        )

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

    async def list_personal_facts(self, owner_user_id: UUID) -> tuple[PersonalFact, ...]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            facts = await uow.list_personal_facts(owner_user_id, profile.id)
        return tuple(facts)

    async def list_entity_relationships(
        self, owner_user_id: UUID
    ) -> tuple[CareerEntityRelationship, ...]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            relationships = await uow.list_entity_relationships(owner_user_id, profile.id)
        return tuple(relationships)

    async def link_entity_relationship(
        self,
        owner_user_id: UUID,
        command: LinkCareerEntityRelationship,
        context: RequestContext,
    ) -> CareerEntityRelationship:
        self._authorize(owner_user_id, context)
        if command.kind is not CareerRelationshipKind.EXPERIENCE_PROJECT:
            raise CareerRecordValidationError("unsupported career relationship kind")
        now = self._clock.now()
        async with self._uow() as uow:
            source = await uow.get_entity(owner_user_id, command.source_entity_id)
            target = await uow.get_entity(owner_user_id, command.target_entity_id)
            if (
                source is None
                or target is None
                or source.profile_id != target.profile_id
                or source.kind is not CareerEntityKind.EXPERIENCE
                or target.kind is not CareerEntityKind.PROJECT
            ):
                raise CareerRecordNotFound
            existing = await uow.list_entity_relationships(owner_user_id, source.profile_id)
            if any(
                item.source_entity_id == source.id
                and item.target_entity_id == target.id
                and item.kind is command.kind
                for item in existing
            ):
                raise CareerRecordConflict("career relationship already exists")
            relationship = CareerEntityRelationship(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                profile_id=source.profile_id,
                source_entity_id=source.id,
                target_entity_id=target.id,
                kind=command.kind,
                created_at=now,
            )
            await uow.add_entity_relationship(relationship)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_RELATIONSHIP_LINKED,
                    "career_entity_relationship",
                    relationship.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return relationship

    async def unlink_entity_relationship(
        self,
        owner_user_id: UUID,
        relationship_id: UUID,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            relationship = await uow.get_entity_relationship(owner_user_id, relationship_id)
            if relationship is None:
                raise CareerRecordNotFound
            await uow.delete_entity_relationship(owner_user_id, relationship_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_RELATIONSHIP_UNLINKED,
                    "career_entity_relationship",
                    relationship.id,
                    context,
                    now,
                )
            )
            await uow.commit()

    async def get_personal_fact(self, owner_user_id: UUID, fact_id: UUID) -> PersonalFact:
        async with self._uow() as uow:
            fact = await uow.get_personal_fact(owner_user_id, fact_id)
        if fact is None:
            raise CareerRecordNotFound
        return fact

    async def create_personal_fact(
        self,
        owner_user_id: UUID,
        command: CreatePersonalFact,
        context: RequestContext,
    ) -> PersonalFact:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id, for_update=True)
            if profile is None:
                raise CareerRecordNotFound
            facts = await uow.list_personal_facts(owner_user_id, profile.id)
            if len(facts) >= self._policy.max_personal_facts:
                raise CareerRecordConflict("personal fact limit reached")
            normalized_value = command.value.strip()
            if any(
                item.kind is command.kind and item.value.casefold() == normalized_value.casefold()
                for item in facts
            ):
                raise CareerRecordConflict("personal fact already exists")
            same_kind = [item for item in facts if item.kind is command.kind]
            is_primary = command.is_primary or not same_kind
            if is_primary:
                for item in same_kind:
                    if item.is_primary:
                        item.is_primary = False
                        item.version += 1
                        item.updated_at = now
                        await uow.save_personal_fact(item)
            fact = PersonalFact(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                profile_id=profile.id,
                kind=command.kind,
                value=normalized_value,
                label=command.label,
                is_primary=is_primary,
                confirmation=ConfirmationState.NEEDS_REVIEW,
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_personal_fact(fact)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PERSONAL_FACT_CREATED,
                    "personal_fact",
                    fact.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return fact

    async def update_personal_fact(
        self,
        owner_user_id: UUID,
        fact_id: UUID,
        expected_version: int,
        command: UpdatePersonalFact,
        context: RequestContext,
    ) -> PersonalFact:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            fact = await uow.get_personal_fact(owner_user_id, fact_id, for_update=True)
            if fact is None:
                raise CareerRecordNotFound
            self._version(fact.version, expected_version)
            facts = await uow.list_personal_facts(owner_user_id, fact.profile_id)
            normalized_value = command.value.strip()
            if any(
                item.id != fact.id
                and item.kind is fact.kind
                and item.value.casefold() == normalized_value.casefold()
                for item in facts
            ):
                raise CareerRecordConflict("personal fact already exists")
            if command.is_primary:
                for item in facts:
                    if item.id != fact.id and item.kind is fact.kind and item.is_primary:
                        item.is_primary = False
                        item.version += 1
                        item.updated_at = now
                        await uow.save_personal_fact(item)
            fact.edit(
                value=normalized_value,
                label=command.label,
                is_primary=command.is_primary,
                now=now,
            )
            await uow.save_personal_fact(fact)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PERSONAL_FACT_UPDATED,
                    "personal_fact",
                    fact.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return fact

    async def confirm_personal_fact(
        self,
        owner_user_id: UUID,
        fact_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> PersonalFact:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            fact = await uow.get_personal_fact(owner_user_id, fact_id, for_update=True)
            if fact is None:
                raise CareerRecordNotFound
            self._version(fact.version, expected_version)
            if fact.confirmation is ConfirmationState.CONFIRMED:
                return fact
            fact.confirm(now)
            await uow.save_personal_fact(fact)
            await uow.add_field_provenance(
                CareerFieldProvenance(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    profile_id=fact.profile_id,
                    target=CareerFieldTarget.PERSONAL_FACT,
                    target_id=fact.id,
                    field_name=fact.kind.value,
                    value_sha256=CareerFieldProvenance.digest_value(fact.value),
                    origin=SemanticFieldOrigin.OWNER_ATTESTATION,
                    created_at=now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PERSONAL_FACT_CONFIRMED,
                    "personal_fact",
                    fact.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return fact

    async def delete_personal_fact(
        self,
        owner_user_id: UUID,
        fact_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            fact = await uow.get_personal_fact(owner_user_id, fact_id, for_update=True)
            if fact is None:
                raise CareerRecordNotFound
            self._version(fact.version, expected_version)
            await uow.delete_personal_fact(owner_user_id, fact.id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.PERSONAL_FACT_DELETED,
                    "personal_fact",
                    fact.id,
                    context,
                    now,
                )
            )
            await uow.commit()

    async def get_entity(self, owner_user_id: UUID, entity_id: UUID) -> CareerEntity:
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id)
        if entity is None:
            raise CareerRecordNotFound
        return entity

    async def current_field_provenance(
        self, owner_user_id: UUID, target_id: UUID
    ) -> tuple[CareerFieldProvenance, ...]:
        """Return every provenance record whose digest matches a current field."""

        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, target_id)
            skill = None if entity is not None else await uow.get_skill(owner_user_id, target_id)
            fact = (
                None
                if entity is not None or skill is not None
                else await uow.get_personal_fact(owner_user_id, target_id)
            )
            if entity is None and skill is None and fact is None:
                raise CareerRecordNotFound
            if entity is not None:
                values = _entity_factual_values(entity)
            elif skill is not None:
                values = _skill_factual_values(skill)
            elif fact is not None:
                values = ((fact.kind.value, fact.value),)
            else:
                raise CareerRecordNotFound
            provenance = await uow.list_field_provenance(owner_user_id, target_id)
        expected = {
            field_name: CareerFieldProvenance.digest_value(value) for field_name, value in values
        }
        return tuple(
            item for item in provenance if expected.get(item.field_name) == item.value_sha256
        )

    async def current_field_provenance_with_availability_for_targets(
        self, owner_user_id: UUID, target_ids: tuple[UUID, ...]
    ) -> dict[UUID, tuple[tuple[CareerFieldProvenance, bool], ...]]:
        """Batched `current_field_provenance` + source availability for many targets.

        `field_provenance_source_available` re-derives semantic candidates from
        the underlying resume snapshot per call — the same cost that made
        `list_semantic_import_proposals` slow (see
        `list_semantic_import_proposals_with_availability`). Calling it once
        per provenance record across every entity/skill/fact in a profile
        made `GET /career-items` scale with total provenance record count;
        this shares one candidates-by-(document, snapshot) cache across the
        whole batch instead.
        """

        candidates_cache: dict[tuple[UUID, UUID], tuple[ValidatedSemanticCandidate, ...]] = {}
        result: dict[UUID, tuple[tuple[CareerFieldProvenance, bool], ...]] = {}
        for target_id in target_ids:
            values = await self.current_field_provenance(owner_user_id, target_id)
            entries: list[tuple[CareerFieldProvenance, bool]] = []
            for value in values:
                available = await self.field_provenance_source_available(
                    owner_user_id, value, _candidates_cache=candidates_cache
                )
                entries.append((value, available))
            result[target_id] = tuple(entries)
        return result

    async def field_provenance_source_available(
        self,
        owner_user_id: UUID,
        provenance: CareerFieldProvenance,
        *,
        _candidates_cache: dict[tuple[UUID, UUID], tuple[ValidatedSemanticCandidate, ...]]
        | None = None,
    ) -> bool:
        if provenance.owner_user_id != owner_user_id:
            raise CareerRecordNotFound
        if provenance.origin is SemanticFieldOrigin.OWNER_ATTESTATION:
            return True
        if (
            provenance.document_id is None
            or provenance.snapshot_id is None
            or provenance.semantic_entity_id is None
            or provenance.semantic_field_id is None
        ):
            return False
        source_key = (provenance.document_id, provenance.snapshot_id)
        if _candidates_cache is not None and source_key in _candidates_cache:
            candidates = _candidates_cache[source_key]
        else:
            candidates = await self._reviewed_semantic_candidates(
                owner_user_id,
                provenance.document_id,
                provenance.snapshot_id,
            )
            if _candidates_cache is not None:
                _candidates_cache[source_key] = candidates
        candidate = next(
            (
                item
                for item in candidates
                if item.semantic_entity_id == provenance.semantic_entity_id
                and item.snapshot_revision == provenance.snapshot_revision
                and item.schema_version == provenance.schema_version
                and item.parser_version == provenance.parser_version
            ),
            None,
        )
        if candidate is None:
            return False
        field = next(
            (
                item
                for item in candidate.fields
                if item.semantic_field_id == provenance.semantic_field_id
            ),
            None,
        )
        if field is None or (provenance.anchors and field.anchors != provenance.anchors):
            return False
        if provenance.origin is SemanticFieldOrigin.OWNER_EDIT:
            return True
        if provenance.origin is SemanticFieldOrigin.RESUME_USER_ADDED:
            if field.review_state is not SemanticImportFieldState.USER_ADDED:
                return False
        elif field.review_state is not SemanticImportFieldState.CONFIRMED:
            return False
        if provenance.target is CareerFieldTarget.ENTITY:
            values = {item.semantic_field_id: item.value for item in candidate.fields}
            if _semantic_mapping_issues(candidate.kind, candidate.fields, values):
                return False
            try:
                data = _semantic_entity_data(candidate.kind, candidate.fields, values)
            except CareerRecordValidationError:
                return False
            targets = _semantic_entity_provenance_targets(
                candidate.kind,
                field,
                data,
            )
        else:
            targets = ((field.name, field.value.strip()),)
        return any(
            field_name == provenance.field_name
            and CareerFieldProvenance.digest_value(value) == provenance.value_sha256
            for field_name, value in targets
        )

    async def list_entity_confirmations(
        self, owner_user_id: UUID
    ) -> dict[UUID, CareerEntityConfirmation]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            confirmations = await uow.list_entity_confirmations(owner_user_id, profile.id)
        return {item.entity_id: item for item in confirmations}

    async def confirm_entity(
        self,
        owner_user_id: UUID,
        entity_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> tuple[CareerEntity, CareerEntityConfirmation]:
        """Attest to every current field without claiming a resume source."""

        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            entity = await uow.get_entity(owner_user_id, entity_id, for_update=True)
            if entity is None:
                raise CareerRecordNotFound
            self._version(entity.version, expected_version)
            confirmation = await uow.get_entity_confirmation(
                owner_user_id, entity_id, for_update=True
            )
            if confirmation is not None and confirmation.state is ConfirmationState.CONFIRMED:
                return entity, confirmation
            if confirmation is None:
                confirmation = CareerEntityConfirmation(
                    entity_id=entity.id,
                    owner_user_id=owner_user_id,
                    state=ConfirmationState.CONFIRMED,
                    version=1,
                    updated_at=now,
                    confirmed_at=now,
                )
                await uow.add_entity_confirmation(confirmation)
            else:
                confirmation.confirm(now)
                await uow.save_entity_confirmation(confirmation)
            for field_name, value in _entity_factual_values(entity):
                await uow.add_field_provenance(
                    CareerFieldProvenance(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        profile_id=entity.profile_id,
                        target=CareerFieldTarget.ENTITY,
                        target_id=entity.id,
                        field_name=field_name,
                        value_sha256=CareerFieldProvenance.digest_value(value),
                        origin=SemanticFieldOrigin.OWNER_ATTESTATION,
                        created_at=now,
                    )
                )
            entity.version += 1
            entity.updated_at = now
            await uow.save_entity(entity)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.ENTITY_CONFIRMED,
                    "career_entity",
                    entity.id,
                    context,
                    now,
                    (("entity_kind", entity.kind.value),),
                )
            )
            await uow.commit()
        return entity, confirmation

    async def list_entity_skill_ids(self, owner_user_id: UUID, entity_id: UUID) -> tuple[UUID, ...]:
        """Return only links whose entity is visible in the owner's scope."""

        async with self._uow() as uow:
            if await uow.get_entity(owner_user_id, entity_id) is None:
                raise CareerRecordNotFound
            links = await uow.list_entity_skill_links(owner_user_id, entity_id)
        return tuple(link.skill_id for link in links)

    async def list_entity_skill_ids_by_entity(
        self,
        owner_user_id: UUID,
        entity_ids: tuple[UUID, ...],
    ) -> dict[UUID, tuple[UUID, ...]]:
        """Return skill links for many entities in one owner-scoped read."""

        if not entity_ids:
            return {}
        async with self._uow() as uow:
            links = await uow.list_entity_skill_links_for_owner(owner_user_id, entity_ids)
        grouped: dict[UUID, list[UUID]] = {}
        for link in links:
            grouped.setdefault(link.entity_id, []).append(link.skill_id)
        return {entity_id: tuple(grouped.get(entity_id, ())) for entity_id in entity_ids}

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
            await uow.add_entity_confirmation(
                CareerEntityConfirmation(
                    entity_id=entity.id,
                    owner_user_id=owner_user_id,
                    state=ConfirmationState.NEEDS_REVIEW,
                    version=1,
                    updated_at=now,
                )
            )
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
            confirmation = await uow.get_entity_confirmation(
                owner_user_id, entity_id, for_update=True
            )
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
            if confirmation is None:
                await uow.add_entity_confirmation(
                    CareerEntityConfirmation(
                        entity_id=entity.id,
                        owner_user_id=owner_user_id,
                        state=ConfirmationState.NEEDS_REVIEW,
                        version=1,
                        updated_at=now,
                    )
                )
            elif confirmation.state is ConfirmationState.CONFIRMED:
                confirmation.require_review(now)
                await uow.save_entity_confirmation(confirmation)
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

    async def list_skill_confirmations(
        self, owner_user_id: UUID
    ) -> dict[UUID, CareerSkillConfirmation]:
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            confirmations = await uow.list_skill_confirmations(owner_user_id, profile.id)
        return {item.skill_id: item for item in confirmations}

    async def confirm_skill(
        self,
        owner_user_id: UUID,
        skill_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> tuple[Skill, CareerSkillConfirmation]:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            skill = await uow.get_skill(owner_user_id, skill_id, for_update=True)
            if skill is None:
                raise CareerRecordNotFound
            self._version(skill.version, expected_version)
            confirmation = await uow.get_skill_confirmation(
                owner_user_id, skill_id, for_update=True
            )
            if confirmation is not None and confirmation.state is ConfirmationState.CONFIRMED:
                return skill, confirmation
            if confirmation is None:
                confirmation = CareerSkillConfirmation(
                    skill_id=skill.id,
                    owner_user_id=owner_user_id,
                    state=ConfirmationState.CONFIRMED,
                    version=1,
                    updated_at=now,
                    confirmed_at=now,
                )
                await uow.add_skill_confirmation(confirmation)
            else:
                confirmation.confirm(now)
                await uow.save_skill_confirmation(confirmation)
            for field_name, value in _skill_factual_values(skill):
                await uow.add_field_provenance(
                    CareerFieldProvenance(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        profile_id=skill.profile_id,
                        target=CareerFieldTarget.SKILL,
                        target_id=skill.id,
                        field_name=field_name,
                        value_sha256=CareerFieldProvenance.digest_value(value),
                        origin=SemanticFieldOrigin.OWNER_ATTESTATION,
                        created_at=now,
                    )
                )
            skill.version += 1
            skill.updated_at = now
            await uow.save_skill(skill)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SKILL_CONFIRMED,
                    "skill",
                    skill.id,
                    context,
                    now,
                )
            )
            await uow.commit()
        return skill, confirmation

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
            await uow.add_skill_confirmation(
                CareerSkillConfirmation(
                    skill_id=skill.id,
                    owner_user_id=owner_user_id,
                    state=ConfirmationState.NEEDS_REVIEW,
                    version=1,
                    updated_at=now,
                )
            )
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
            confirmation = await uow.get_skill_confirmation(
                owner_user_id, skill_id, for_update=True
            )
            skill.edit(
                name=command.name,
                category=command.category,
                proficiency=command.proficiency,
                now=now,
            )
            await uow.save_skill(skill)
            if confirmation is None:
                await uow.add_skill_confirmation(
                    CareerSkillConfirmation(
                        skill_id=skill.id,
                        owner_user_id=owner_user_id,
                        state=ConfirmationState.NEEDS_REVIEW,
                        version=1,
                        updated_at=now,
                    )
                )
            elif confirmation.state is ConfirmationState.CONFIRMED:
                confirmation.require_review(now)
                await uow.save_skill_confirmation(confirmation)
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

    async def create_semantic_import_proposals(
        self,
        owner_user_id: UUID,
        command: CreateSemanticImportProposals,
        context: RequestContext,
    ) -> SemanticImportBatch:
        """Create idempotent proposals from reviewed typed semantics only."""

        for attempt in range(2):
            try:
                return await self._create_semantic_import_proposals_once(
                    owner_user_id,
                    command,
                    context,
                )
            except CareerRecordConflict:
                if attempt == 1:
                    raise
        raise CareerRecordConflict("semantic import proposal creation conflict")

    async def _create_semantic_import_proposals_once(
        self,
        owner_user_id: UUID,
        command: CreateSemanticImportProposals,
        context: RequestContext,
    ) -> SemanticImportBatch:
        self._authorize(owner_user_id, context)
        candidates = await self._reviewed_semantic_candidates(
            owner_user_id,
            command.document_id,
            command.snapshot_id,
        )
        if not candidates:
            raise CareerRecordSourceUnavailable("a reviewed owned semantic snapshot is required")
        candidates = _expand_semantic_candidates(candidates)
        now = self._clock.now()
        created: list[SemanticImportProposal] = []
        questions: list[SemanticImportQuestion] = []
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                raise CareerRecordNotFound
            existing_proposals = await uow.list_semantic_proposals(owner_user_id)
            existing_by_source = {
                (proposal.snapshot_id, proposal.semantic_entity_id): proposal
                for proposal in existing_proposals
            }
            new_candidate_count = sum(
                1
                for candidate in candidates
                if (
                    candidate.snapshot_id,
                    candidate.semantic_entity_id,
                )
                not in existing_by_source
                and not _semantic_mapping_issues(
                    candidate.kind,
                    candidate.fields,
                    {field.semantic_field_id: field.value for field in candidate.fields},
                )
            )
            if new_candidate_count > 0 and len(existing_proposals) + new_candidate_count > (
                self._policy.max_semantic_import_proposals
            ):
                raise CareerRecordConflict("semantic import proposal limit reached")
            entities = await uow.list_entities(owner_user_id, profile.id)
            skills = await uow.list_skills(owner_user_id, profile.id)
            facts = await uow.list_personal_facts(owner_user_id, profile.id)
            for candidate in candidates:
                missing = _semantic_mapping_issues(
                    candidate.kind,
                    candidate.fields,
                    {field.semantic_field_id: field.value for field in candidate.fields},
                )
                if missing:
                    questions.append(
                        SemanticImportQuestion(
                            semantic_entity_id=candidate.semantic_entity_id,
                            code="semantic_candidate_requires_review",
                            missing_fields=missing,
                        )
                    )
                    continue
                existing = existing_by_source.get(
                    (candidate.snapshot_id, candidate.semantic_entity_id)
                )
                if existing is not None:
                    created.append(existing)
                    continue
                target, target_record_id, conflict_code = _semantic_target_match(
                    candidate.kind,
                    candidate.fields,
                    entities=entities,
                    skills=skills,
                    facts=facts,
                )
                proposal = SemanticImportProposal(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    profile_id=profile.id,
                    target=target,
                    target_record_id=target_record_id,
                    document_id=candidate.document_id,
                    snapshot_id=candidate.snapshot_id,
                    snapshot_revision=candidate.snapshot_revision,
                    schema_version=candidate.schema_version,
                    parser_version=candidate.parser_version,
                    semantic_entity_id=candidate.semantic_entity_id,
                    semantic_kind=candidate.kind,
                    fields=candidate.fields,
                    status=SemanticImportStatus.PENDING,
                    conflict_code=conflict_code,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                try:
                    await uow.add_semantic_proposal(proposal)
                except CareerRecordConflict:
                    raced = await uow.find_semantic_proposal(
                        owner_user_id,
                        candidate.snapshot_id,
                        candidate.semantic_entity_id,
                    )
                    if raced is None:
                        raise
                    created.append(raced)
                    continue
                await uow.add_audit(
                    self._audit(
                        owner_user_id,
                        AuditAction.SEMANTIC_PROPOSAL_CREATED,
                        "semantic_import_proposal",
                        proposal.id,
                        context,
                        now,
                        (("proposal_status", proposal.status.value),),
                    )
                )
                created.append(proposal)
            await uow.commit()
        return SemanticImportBatch(tuple(created), tuple(questions))

    async def populate_from_reviewed_snapshot(
        self,
        owner_user_id: UUID,
        command: CreateSemanticImportProposals,
        context: RequestContext,
    ) -> SemanticImportBatch:
        """Create proposals from a reviewed snapshot and apply every safe one."""

        batch = await self.create_semantic_import_proposals(owner_user_id, command, context)
        applied = 0
        for proposal in batch.proposals:
            if proposal.status is not SemanticImportStatus.PENDING:
                continue
            if _semantic_auto_apply_blocked(proposal):
                continue
            values = {field.semantic_field_id: field.value for field in proposal.fields}
            try:
                await self.accept_semantic_import_proposal(
                    owner_user_id,
                    proposal.id,
                    proposal.version,
                    AcceptSemanticImportProposal(
                        values=values,
                        idempotency_key=f"auto-import:{proposal.id}",
                        target_record_id=proposal.target_record_id,
                    ),
                    context,
                )
            except (
                CareerRecordConflict,
                CareerRecordNotFound,
                CareerRecordSourceUnavailable,
                CareerRecordTransitionRejected,
                CareerRecordValidationError,
                CareerRecordVersionConflict,
            ):
                continue
            applied += 1
        return SemanticImportBatch(batch.proposals, batch.questions, applied)

    async def get_semantic_import_proposal(
        self, owner_user_id: UUID, proposal_id: UUID
    ) -> SemanticImportProposal:
        async with self._uow() as uow:
            proposal = await uow.get_semantic_proposal(owner_user_id, proposal_id)
        if proposal is None:
            raise CareerRecordNotFound
        return proposal

    async def list_semantic_import_proposals(
        self, owner_user_id: UUID
    ) -> tuple[SemanticImportProposal, ...]:
        async with self._uow() as uow:
            proposals = await uow.list_semantic_proposals(owner_user_id)
        return tuple(proposals)

    async def list_semantic_import_proposals_with_availability(
        self, owner_user_id: UUID
    ) -> tuple[tuple[SemanticImportProposal, bool], ...]:
        """List proposals with source availability, computed per document+snapshot.

        `semantic_import_proposal_source_available` re-derives candidates from
        the underlying resume snapshot per proposal; calling it once per row
        made the list endpoint's cost grow with the number of proposals
        (an N+1 that got slower as proposals accumulated). Every proposal
        sharing a (document_id, snapshot_id) shares the same candidate set,
        so it only needs to be derived once per unique pair.
        """

        proposals = await self.list_semantic_import_proposals(owner_user_id)
        candidates_by_source: dict[tuple[UUID, UUID], tuple[ValidatedSemanticCandidate, ...]] = {}
        results: list[tuple[SemanticImportProposal, bool]] = []
        for proposal in proposals:
            source_key = (proposal.document_id, proposal.snapshot_id)
            if source_key not in candidates_by_source:
                candidates_by_source[source_key] = await self._reviewed_semantic_candidates(
                    owner_user_id, proposal.document_id, proposal.snapshot_id
                )
            candidates = candidates_by_source[source_key]
            available = any(
                candidate.semantic_entity_id == proposal.semantic_entity_id
                and candidate.fields == proposal.fields
                for candidate in candidates
            )
            results.append((proposal, available))
        return tuple(results)

    async def semantic_import_proposal_source_available(
        self, owner_user_id: UUID, proposal_id: UUID
    ) -> bool:
        proposal = await self.get_semantic_import_proposal(owner_user_id, proposal_id)
        candidates = await self._reviewed_semantic_candidates(
            owner_user_id,
            proposal.document_id,
            proposal.snapshot_id,
        )
        return any(
            candidate.semantic_entity_id == proposal.semantic_entity_id
            and candidate.fields == proposal.fields
            for candidate in candidates
        )

    async def accept_semantic_import_proposal(
        self,
        owner_user_id: UUID,
        proposal_id: UUID,
        expected_version: int,
        command: AcceptSemanticImportProposal,
        context: RequestContext,
    ) -> SemanticImportAcceptance:
        self._authorize(owner_user_id, context)
        if not _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key):
            raise CareerRecordValidationError("idempotency key is invalid")
        saved = await self.get_semantic_import_proposal(owner_user_id, proposal_id)
        requested_values = {
            str(field_id): value.strip() for field_id, value in command.values.items()
        }
        if saved.status is SemanticImportStatus.ACCEPTED:
            if (
                saved.decision_idempotency_key != command.idempotency_key
                or saved.accepted_values != requested_values
            ):
                raise CareerRecordIdempotencyConflict
            return await self._semantic_acceptance_view(owner_user_id, saved)
        if saved.status is not SemanticImportStatus.PENDING:
            raise CareerRecordTransitionRejected("a rejected semantic proposal cannot be accepted")
        candidates = await self._reviewed_semantic_candidates(
            owner_user_id,
            saved.document_id,
            saved.snapshot_id,
        )
        current = next(
            (
                candidate
                for candidate in candidates
                if candidate.semantic_entity_id == saved.semantic_entity_id
            ),
            None,
        )
        if current is None or current.fields != saved.fields:
            raise CareerRecordSourceUnavailable("semantic proposal source is no longer available")
        issues = _semantic_mapping_issues(
            saved.semantic_kind,
            saved.fields,
            command.values,
        )
        if issues:
            raise CareerRecordValidationError(
                "semantic proposal requires reviewed values for: " + ", ".join(issues)
            )
        now = self._clock.now()
        accepted_facts: tuple[PersonalFact, ...] = ()
        accepted_entity: CareerEntity | None = None
        accepted_skill: Skill | None = None
        async with self._uow() as uow:
            proposal = await uow.get_semantic_proposal(owner_user_id, proposal_id, for_update=True)
            if proposal is None:
                raise CareerRecordNotFound
            self._version(proposal.version, expected_version)
            if proposal.fields != saved.fields:
                raise CareerRecordVersionConflict
            values = {str(field_id): value for field_id, value in command.values.items()}
            target_record_id = command.target_record_id or proposal.target_record_id
            if proposal.target is SemanticImportTarget.PERSONAL_FACTS:
                if target_record_id is not None:
                    raise CareerRecordValidationError(
                        "contact proposal target is selected per fact"
                    )
                accepted_facts = await self._accept_personal_fact_proposal(
                    uow, proposal, command.values, now
                )
            elif proposal.target is SemanticImportTarget.SKILL:
                accepted_skill = await self._accept_skill_proposal(
                    uow,
                    proposal,
                    command.values,
                    target_record_id,
                    now,
                )
                target_record_id = accepted_skill.id
            else:
                accepted_entity = await self._accept_entity_proposal(
                    uow,
                    proposal,
                    command.values,
                    target_record_id,
                    now,
                    context,
                )
                target_record_id = accepted_entity.id
            proposal.target_record_id = target_record_id
            proposal.accept(values, command.idempotency_key, now)
            await uow.save_semantic_proposal(proposal)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SEMANTIC_PROPOSAL_ACCEPTED,
                    "semantic_import_proposal",
                    proposal.id,
                    context,
                    now,
                    (("proposal_status", proposal.status.value),),
                )
            )
            await uow.commit()
        return SemanticImportAcceptance(
            proposal=proposal,
            personal_facts=accepted_facts,
            entity=accepted_entity,
            skill=accepted_skill,
        )

    async def _semantic_acceptance_view(
        self,
        owner_user_id: UUID,
        proposal: SemanticImportProposal,
    ) -> SemanticImportAcceptance:
        facts: tuple[PersonalFact, ...] = ()
        entity: CareerEntity | None = None
        skill: Skill | None = None
        async with self._uow() as uow:
            if proposal.target is SemanticImportTarget.PERSONAL_FACTS:
                available = await uow.list_personal_facts(owner_user_id, proposal.profile_id)
                accepted_values = proposal.accepted_values or {}
                selected: list[PersonalFact] = []
                for field in proposal.fields:
                    expected = accepted_values.get(str(field.semantic_field_id))
                    match = next(
                        (
                            fact
                            for fact in available
                            if fact.kind.value == field.name and fact.value == expected
                        ),
                        None,
                    )
                    if match is None:
                        raise CareerRecordConflict("accepted semantic fact is unavailable")
                    selected.append(match)
                facts = tuple(selected)
            elif proposal.target is SemanticImportTarget.ENTITY:
                if proposal.target_record_id is None:
                    raise CareerRecordConflict("accepted semantic entity target is unavailable")
                entity = await uow.get_entity(owner_user_id, proposal.target_record_id)
                if entity is None:
                    raise CareerRecordConflict("accepted semantic entity is unavailable")
            else:
                if proposal.target_record_id is None:
                    raise CareerRecordConflict("accepted semantic skill target is unavailable")
                skill = await uow.get_skill(owner_user_id, proposal.target_record_id)
                if skill is None:
                    raise CareerRecordConflict("accepted semantic skill is unavailable")
        return SemanticImportAcceptance(
            proposal=proposal,
            personal_facts=facts,
            entity=entity,
            skill=skill,
        )

    async def reject_semantic_import_proposal(
        self,
        owner_user_id: UUID,
        proposal_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> SemanticImportProposal:
        self._authorize(owner_user_id, context)
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise CareerRecordValidationError("idempotency key is invalid")
        saved = await self.get_semantic_import_proposal(owner_user_id, proposal_id)
        if saved.status is SemanticImportStatus.REJECTED:
            if saved.decision_idempotency_key != idempotency_key:
                raise CareerRecordIdempotencyConflict
            return saved
        if saved.status is not SemanticImportStatus.PENDING:
            raise CareerRecordTransitionRejected("an accepted semantic proposal cannot be rejected")
        now = self._clock.now()
        async with self._uow() as uow:
            proposal = await uow.get_semantic_proposal(owner_user_id, proposal_id, for_update=True)
            if proposal is None:
                raise CareerRecordNotFound
            self._version(proposal.version, expected_version)
            proposal.reject(idempotency_key, now)
            await uow.save_semantic_proposal(proposal)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    AuditAction.SEMANTIC_PROPOSAL_REJECTED,
                    "semantic_import_proposal",
                    proposal.id,
                    context,
                    now,
                    (("proposal_status", proposal.status.value),),
                )
            )
            await uow.commit()
        return proposal

    async def _accept_personal_fact_proposal(
        self,
        uow: CareerRecordUnitOfWork,
        proposal: SemanticImportProposal,
        values: dict[UUID, str],
        now: datetime,
    ) -> tuple[PersonalFact, ...]:
        existing = await uow.list_personal_facts(proposal.owner_user_id, proposal.profile_id)
        accepted: list[PersonalFact] = []
        for field in proposal.fields:
            kind = PersonalFactKind(field.name)
            value = values[field.semantic_field_id].strip()
            if field.field_type == "url":
                value = normalize_semantic_url(value)
            fact = next(
                (item for item in existing if item.kind is kind and item.value == value),
                None,
            )
            if fact is None:
                fact = PersonalFact(
                    id=self._ids.new(),
                    owner_user_id=proposal.owner_user_id,
                    profile_id=proposal.profile_id,
                    kind=kind,
                    value=value,
                    label=None,
                    is_primary=not any(item.kind is kind for item in existing),
                    confirmation=ConfirmationState.CONFIRMED,
                    version=1,
                    created_at=now,
                    updated_at=now,
                    confirmed_at=now,
                )
                await uow.add_personal_fact(fact)
                existing.append(fact)
            elif fact.confirmation is not ConfirmationState.CONFIRMED:
                fact.confirmation = ConfirmationState.CONFIRMED
                fact.confirmed_at = now
                fact.updated_at = now
                fact.version += 1
                await uow.save_personal_fact(fact)
            await uow.add_field_provenance(
                self._semantic_provenance(
                    proposal,
                    field,
                    value,
                    CareerFieldTarget.PERSONAL_FACT,
                    fact.id,
                    now,
                )
            )
            accepted.append(fact)
        return tuple(accepted)

    async def _accept_skill_proposal(
        self,
        uow: CareerRecordUnitOfWork,
        proposal: SemanticImportProposal,
        values: dict[UUID, str],
        target_record_id: UUID | None,
        now: datetime,
    ) -> Skill:
        by_name = _semantic_values_by_name(proposal.fields, values)
        names = by_name.get("name", [])
        if not names:
            raise CareerRecordValidationError("skill proposal requires a name")
        category = by_name.get("category", [None])[0]
        name_fields = [field for field in proposal.fields if field.name == "name"]
        last_skill: Skill | None = None
        for index, name in enumerate(names):
            record_id = target_record_id if index == 0 else None
            field = name_fields[index] if index < len(name_fields) else name_fields[-1]
            last_skill = await self._upsert_confirmed_skill(
                uow,
                proposal,
                name=name,
                category=category,
                target_record_id=record_id,
                now=now,
            )
            await uow.add_field_provenance(
                self._semantic_provenance(
                    proposal,
                    field,
                    values[field.semantic_field_id],
                    CareerFieldTarget.SKILL,
                    last_skill.id,
                    now,
                )
            )
        if last_skill is None:
            raise CareerRecordValidationError("skill proposal requires a name")
        for field in proposal.fields:
            if field.name == "name":
                continue
            await uow.add_field_provenance(
                self._semantic_provenance(
                    proposal,
                    field,
                    values[field.semantic_field_id],
                    CareerFieldTarget.SKILL,
                    last_skill.id,
                    now,
                )
            )
        return last_skill

    async def _upsert_confirmed_skill(
        self,
        uow: CareerRecordUnitOfWork,
        proposal: SemanticImportProposal,
        *,
        name: str,
        category: str | None,
        target_record_id: UUID | None,
        now: datetime,
    ) -> Skill:
        skill = (
            await uow.get_skill(proposal.owner_user_id, target_record_id, for_update=True)
            if target_record_id is not None
            else None
        )
        if target_record_id is not None and (
            skill is None or skill.profile_id != proposal.profile_id
        ):
            raise CareerRecordNotFound
        if skill is None:
            skills = await uow.list_skills(proposal.owner_user_id, proposal.profile_id)
            skill = next(
                (item for item in skills if item.name.casefold() == name.casefold()),
                None,
            )
        if skill is None:
            skills = await uow.list_skills(proposal.owner_user_id, proposal.profile_id)
            skill = Skill(
                id=self._ids.new(),
                owner_user_id=proposal.owner_user_id,
                profile_id=proposal.profile_id,
                name=name,
                category=category,
                proficiency=None,
                sort_order=len(skills),
                version=1,
                created_at=now,
                updated_at=now,
            )
            await uow.add_skill(skill)
            await uow.add_skill_confirmation(
                CareerSkillConfirmation(
                    skill_id=skill.id,
                    owner_user_id=proposal.owner_user_id,
                    state=ConfirmationState.CONFIRMED,
                    version=1,
                    updated_at=now,
                    confirmed_at=now,
                )
            )
        else:
            confirmation = await uow.get_skill_confirmation(
                proposal.owner_user_id, skill.id, for_update=True
            )
            skill.edit(
                name=name,
                category=category,
                proficiency=skill.proficiency,
                now=now,
            )
            await uow.save_skill(skill)
            if confirmation is None:
                await uow.add_skill_confirmation(
                    CareerSkillConfirmation(
                        skill_id=skill.id,
                        owner_user_id=proposal.owner_user_id,
                        state=ConfirmationState.CONFIRMED,
                        version=1,
                        updated_at=now,
                        confirmed_at=now,
                    )
                )
            elif confirmation.state is not ConfirmationState.CONFIRMED:
                confirmation.confirm(now)
                await uow.save_skill_confirmation(confirmation)
        return skill

    async def _accept_entity_proposal(
        self,
        uow: CareerRecordUnitOfWork,
        proposal: SemanticImportProposal,
        values: dict[UUID, str],
        target_record_id: UUID | None,
        now: datetime,
        context: RequestContext,
    ) -> CareerEntity:
        data = _semantic_entity_data(proposal.semantic_kind, proposal.fields, values)
        entity = (
            await uow.get_entity(proposal.owner_user_id, target_record_id, for_update=True)
            if target_record_id is not None
            else None
        )
        if target_record_id is not None and (
            entity is None
            or entity.profile_id != proposal.profile_id
            or entity.kind is not data.kind
        ):
            raise CareerRecordNotFound
        if entity is None:
            entities = await uow.list_entities(proposal.owner_user_id, proposal.profile_id)
            entity = self._entity(
                proposal.owner_user_id,
                proposal.profile_id,
                data,
                sort_order=len(entities),
                now=now,
            )
            await uow.add_entity(entity)
        else:
            entity.edit(
                title=data.title,
                organization=data.organization,
                description=data.description,
                official_title=data.official_title,
                display_title=data.display_title,
                employment_type=data.employment_type,
                location=data.location,
                external_url=data.external_url,
                start_date=data.start_date,
                end_date=data.end_date,
                is_current=data.is_current,
                group_id=data.group_id,
                now=now,
            )
            await uow.save_entity(entity)
        confirmation = await uow.get_entity_confirmation(
            proposal.owner_user_id, entity.id, for_update=True
        )
        if confirmation is None:
            confirmation = CareerEntityConfirmation(
                entity_id=entity.id,
                owner_user_id=proposal.owner_user_id,
                state=ConfirmationState.CONFIRMED,
                version=1,
                updated_at=now,
                confirmed_at=now,
            )
            await uow.add_entity_confirmation(confirmation)
        elif confirmation.state is not ConfirmationState.CONFIRMED:
            confirmation.state = ConfirmationState.CONFIRMED
            confirmation.version += 1
            confirmation.updated_at = now
            confirmation.confirmed_at = now
            await uow.save_entity_confirmation(confirmation)
        for field in proposal.fields:
            for field_name, canonical_value in _semantic_entity_provenance_targets(
                proposal.semantic_kind,
                field,
                data,
            ):
                await uow.add_field_provenance(
                    self._semantic_provenance(
                        proposal,
                        field,
                        values[field.semantic_field_id],
                        CareerFieldTarget.ENTITY,
                        entity.id,
                        now,
                        field_name=field_name,
                        canonical_value=canonical_value,
                    )
                )
        await self._materialize_semantic_outcomes(
            uow,
            proposal,
            entity,
            values,
            context,
            now,
        )
        return entity

    async def _materialize_semantic_outcomes(
        self,
        uow: CareerRecordUnitOfWork,
        proposal: SemanticImportProposal,
        entity: CareerEntity,
        values: dict[UUID, str],
        context: RequestContext,
        now: datetime,
    ) -> None:
        """Turn reviewed resume bullets into achievement drafts and resume evidence."""

        existing_achievements = await uow.list_achievements(
            proposal.owner_user_id,
            None,
            self._policy.max_achievements + 1,
        )
        if len(existing_achievements) >= self._policy.max_achievements:
            return

        existing_evidence = await uow.list_evidence(
            proposal.owner_user_id,
            EvidenceFilter(include_archived=True),
            None,
            self._policy.max_evidence + 1,
        )
        evidence_at_limit = len(existing_evidence) >= self._policy.max_evidence

        for field in proposal.fields:
            if not _semantic_outcome_field(proposal.semantic_kind, field):
                continue
            raw_value = values.get(field.semantic_field_id)
            if raw_value is None:
                continue
            statement = _normalize_statement(raw_value)
            if not statement:
                continue
            if any(
                item.entity_id == entity.id
                and _normalize_statement(item.delivered or "") == statement
                for item in existing_achievements
            ):
                continue

            achievement = self._achievement(
                proposal.owner_user_id,
                proposal.profile_id,
                CreateAchievement(
                    title=_achievement_title_from_statement(statement, entity.organization),
                    delivered=statement,
                    entity_id=entity.id,
                ),
                now,
            )
            await uow.add_achievement(achievement)
            existing_achievements.append(achievement)
            await uow.add_audit(
                self._audit(
                    proposal.owner_user_id,
                    AuditAction.ACHIEVEMENT_CREATED,
                    "achievement",
                    achievement.id,
                    context,
                    now,
                    (("achievement_status", achievement.status.value),),
                )
            )

            if evidence_at_limit or not field.anchors:
                continue
            anchor = field.anchors[0]
            locator = _resume_locator(proposal, anchor)
            if any(
                source.provenance is not None
                and source.provenance.document_id == locator.document_id
                and source.provenance.snapshot_id == locator.snapshot_id
                and source.provenance.block_id == locator.block_id
                and source.provenance.page == locator.page
                and source.provenance.start_offset == locator.start_offset
                and source.provenance.end_offset == locator.end_offset
                for record in existing_evidence
                for source in record.sources
            ):
                continue
            try:
                validated = await self._resolve_source(
                    proposal.owner_user_id,
                    locator,
                    expected_claim=statement,
                )
            except CareerRecordSourceUnavailable:
                continue

            evidence_id = self._ids.new()
            revision_id = self._ids.new()
            revision = initial_revision(
                revision_id=revision_id,
                owner_user_id=proposal.owner_user_id,
                evidence_id=evidence_id,
                evidence_type=EvidenceType.RESUME_STATEMENT,
                title=validated.review_excerpt[:300],
                statement=statement,
                context=None,
                organization=None,
                project=None,
                start_date=None,
                end_date=None,
                input_kind=EvidenceInputKind.EXACT_SOURCE_SPAN,
                exact_span_validated=True,
                created_at=now,
            )
            transition = EvidenceStateTransition(
                id=self._ids.new(),
                owner_user_id=proposal.owner_user_id,
                evidence_id=evidence_id,
                from_revision_id=None,
                to_revision_id=revision.id,
                previous_strength=None,
                next_strength=revision.strength,
                authority=EvidenceAuthority.SYSTEM_SOURCE_VALIDATION,
                reason_code="exact_source_span_validated",
                actor_user_id=context.actor_user_id,
                verifier_reference=None,
                request_id=context.request_id,
                trace_id=context.trace_id,
                created_at=now,
            )
            source = EvidenceSource(
                id=self._ids.new(),
                owner_user_id=proposal.owner_user_id,
                evidence_revision_id=revision.id,
                kind=EvidenceSourceKind.RESUME,
                label="Imported resume source",
                provenance=validated.provenance(),
                attachment_id=None,
                external_url=None,
                available=True,
                exact_span_validated=True,
                created_at=now,
            )
            record = EvidenceRecord(
                item=EvidenceItem(
                    id=evidence_id,
                    owner_user_id=proposal.owner_user_id,
                    lifecycle=EvidenceLifecycle.ACTIVE,
                    current_revision=1,
                    version=1,
                    created_at=now,
                    updated_at=now,
                ),
                revision=revision,
                revisions=(revision,),
                transitions=(transition,),
                sources=(source,),
                metrics=(),
                attachments=(),
                conflicts=(),
                entity_ids=(entity.id,),
                skill_ids=(),
                usage=(),
            )
            await uow.add_evidence(record)
            await uow.add_evidence_entity_link(
                EvidenceEntityLink(
                    self._ids.new(),
                    proposal.owner_user_id,
                    evidence_id,
                    entity.id,
                    now,
                )
            )
            existing_evidence.append(record)
            await uow.add_audit(
                self._audit(
                    proposal.owner_user_id,
                    AuditAction.EVIDENCE_CREATED,
                    "evidence",
                    evidence_id,
                    context,
                    now,
                    (("next_strength", revision.strength.value),),
                )
            )

    def _semantic_provenance(
        self,
        proposal: SemanticImportProposal,
        field: SemanticImportField,
        accepted_value: str,
        target: CareerFieldTarget,
        target_id: UUID,
        now: datetime,
        *,
        field_name: str | None = None,
        canonical_value: str | None = None,
    ) -> CareerFieldProvenance:
        original = accepted_value.strip() == field.value
        origin = (
            SemanticFieldOrigin.RESUME_USER_ADDED
            if original and field.review_state is SemanticImportFieldState.USER_ADDED
            else (
                SemanticFieldOrigin.RESUME_PARSER
                if original and field.review_state is SemanticImportFieldState.CONFIRMED
                else SemanticFieldOrigin.OWNER_EDIT
            )
        )
        return CareerFieldProvenance(
            id=self._ids.new(),
            owner_user_id=proposal.owner_user_id,
            profile_id=proposal.profile_id,
            target=target,
            target_id=target_id,
            field_name=field_name or field.name,
            value_sha256=CareerFieldProvenance.digest_value(
                canonical_value if canonical_value is not None else accepted_value.strip()
            ),
            origin=origin,
            document_id=proposal.document_id,
            snapshot_id=proposal.snapshot_id,
            snapshot_revision=proposal.snapshot_revision,
            schema_version=proposal.schema_version,
            parser_version=proposal.parser_version,
            semantic_entity_id=proposal.semantic_entity_id,
            semantic_field_id=field.semantic_field_id,
            anchors=field.anchors,
            created_at=now,
        )

    async def create_evidence(
        self, owner_user_id: UUID, command: CreateEvidence, context: RequestContext
    ) -> EvidenceRecord:
        self._authorize(owner_user_id, context)
        self._validate_evidence_sources(command)
        validated_source = (
            await self._resolve_source(
                owner_user_id,
                command.resume_source,
                expected_claim=command.statement,
            )
            if command.resume_source is not None
            else None
        )
        exact_span = (
            command.input_kind is EvidenceInputKind.EXACT_SOURCE_SPAN
            and validated_source is not None
        )
        title = (
            validated_source.review_excerpt[:300]
            if exact_span and validated_source is not None
            else command.title
        )
        now = self._clock.now()
        evidence_id = self._ids.new()
        revision = initial_revision(
            revision_id=self._ids.new(),
            owner_user_id=owner_user_id,
            evidence_id=evidence_id,
            evidence_type=command.evidence_type,
            title=title,
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

    async def list_analytics_growth(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
    ) -> tuple[CareerRecordAnalyticsGrowthPoint, ...]:
        """Return current policy-eligible achievement milestones without evidence text."""

        if (
            window_end < window_start
            or (window_end - window_start).days > _ANALYTICS_SOURCE_MAX_WINDOW_DAYS
        ):
            raise CareerRecordValidationError(
                "analytics source window exceeds the bounded timezone guard"
            )
        async with self._uow() as uow:
            candidates = await uow.list_analytics_growth(
                owner_user_id,
                window_start,
                window_end,
                self._policy.max_evidence + 1,
            )
            if len(candidates) > self._policy.max_evidence:
                raise CareerRecordValidationError(
                    "analytics achievement source exceeded its bounded history"
                )
            records = await uow.get_evidence_batch(
                owner_user_id,
                tuple(candidate.evidence_id for candidate in candidates),
            )
        records_by_id = {record.item.id: record for record in records}
        eligible: list[CareerRecordAnalyticsGrowthPoint] = []
        for candidate in candidates:
            record = records_by_id.get(candidate.evidence_id)
            if (
                record is None
                or record.revision.id != candidate.evidence_revision_id
                or record.revision.evidence_type is not EvidenceType.ACHIEVEMENT
                or candidate.category != EvidenceType.ACHIEVEMENT.value
            ):
                raise CareerRecordValidationError(
                    "analytics achievement source changed during selection"
                )
            decision, _refreshed = await self._evaluate_record(owner_user_id, record)
            if decision.eligible:
                eligible.append(candidate)
        return tuple(eligible)

    async def analytics_watermark(
        self,
        owner_user_id: UUID,
    ) -> CareerRecordAnalyticsWatermark:
        async with self._uow() as uow:
            state = await uow.get_analytics_source_state(owner_user_id)
        return state.watermark()

    async def readiness_snapshot(
        self, owner_user_id: UUID, *, evidence_limit: int = 100
    ) -> CareerRecordReadinessSnapshot:
        """Return owner-scoped profile signal plus only generation-eligible evidence."""

        if not 1 <= evidence_limit <= self._policy.max_evidence:
            raise CareerRecordValidationError("readiness evidence limit is out of range")
        async with self._uow() as uow:
            profile = await uow.get_profile(owner_user_id)
            if profile is None:
                return CareerRecordReadinessSnapshot(skills=(), entities=(), evidence=())
            entities = await uow.list_entities(owner_user_id, profile.id)
            confirmations = await uow.list_entity_confirmations(owner_user_id, profile.id)
            skills = await uow.list_skills(owner_user_id, profile.id)
            skill_confirmations = await uow.list_skill_confirmations(owner_user_id, profile.id)
            personal_facts = await uow.list_personal_facts(
                owner_user_id,
                profile.id,
            )
            relationships = await uow.list_entity_relationships(owner_user_id, profile.id)
            records = await uow.list_evidence(
                owner_user_id,
                EvidenceFilter(lifecycle=EvidenceLifecycle.ACTIVE),
                None,
                evidence_limit,
            )
        eligible: list[ReadinessSnapshotEvidence] = []
        for record in records:
            decision, refreshed = await self._evaluate_record(owner_user_id, record)
            if decision.eligible:
                eligible.append(
                    ReadinessSnapshotEvidence(
                        id=refreshed.item.id,
                        evidence_revision_id=refreshed.revision.id,
                        revision_number=refreshed.revision.revision,
                        statement_sha256=hashlib.sha256(
                            refreshed.revision.statement.encode("utf-8")
                        ).hexdigest(),
                        title=refreshed.revision.title,
                        statement=refreshed.revision.statement,
                        context=refreshed.revision.context,
                        strength=refreshed.revision.strength.value,
                        skill_ids=refreshed.skill_ids,
                        entity_ids=refreshed.entity_ids,
                        has_numeric_claim=bool(refreshed.metrics),
                    )
                )
        confirmed_entity_ids = {
            item.entity_id for item in confirmations if item.state is ConfirmationState.CONFIRMED
        }
        confirmed_skill_ids = {
            item.skill_id
            for item in skill_confirmations
            if item.state is ConfirmationState.CONFIRMED
        }
        return CareerRecordReadinessSnapshot(
            skills=tuple(
                ReadinessSnapshotSkill(
                    id=skill.id,
                    name=skill.name,
                    category=skill.category,
                    proficiency=skill.proficiency.value if skill.proficiency is not None else None,
                )
                for skill in sorted(skills, key=lambda item: (item.sort_order, str(item.id)))
                if skill.id in confirmed_skill_ids
            ),
            entities=tuple(
                ReadinessSnapshotEntity(
                    id=entity.id,
                    kind=entity.kind.value,
                    title=entity.title,
                    organization=entity.organization,
                    description=entity.description,
                    official_title=entity.official_title,
                    display_title=entity.display_title,
                    location=entity.location,
                    start_date=entity.start_date,
                    end_date=entity.end_date,
                    is_current=entity.is_current,
                )
                for entity in sorted(entities, key=lambda item: (item.sort_order, str(item.id)))
                if entity.id in confirmed_entity_ids
            ),
            evidence=tuple(eligible),
            personal_facts=tuple(
                ReadinessSnapshotPersonalFact(
                    id=fact.id,
                    kind=fact.kind.value,
                    value=fact.value,
                    label=fact.label,
                    is_primary=fact.is_primary,
                )
                for fact in personal_facts
                if fact.confirmation is ConfirmationState.CONFIRMED
            ),
            relationships=tuple(
                ReadinessSnapshotRelationship(
                    id=relationship.id,
                    source_entity_id=relationship.source_entity_id,
                    target_entity_id=relationship.target_entity_id,
                    kind=relationship.kind.value,
                )
                for relationship in relationships
                if relationship.source_entity_id in confirmed_entity_ids
                and relationship.target_entity_id in confirmed_entity_ids
            ),
        )

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

    async def get_evidence_batch_with_eligibility(
        self,
        owner_user_id: UUID,
        evidence_ids: tuple[UUID, ...],
    ) -> tuple[tuple[EvidenceRecord, EligibilityDecision], ...]:
        """Return a bounded exact-ID snapshot without per-evidence database reads."""

        unique_ids = tuple(dict.fromkeys(evidence_ids))
        if not unique_ids or len(unique_ids) > 200:
            raise CareerRecordValidationError("evidence batch must contain between 1 and 200 IDs")
        async with self._uow() as uow:
            records = await uow.get_evidence_batch(owner_user_id, unique_ids)
        records_by_id = {
            record.item.id: record
            for record in records
            if record.item.lifecycle is not EvidenceLifecycle.DELETED
        }
        if set(records_by_id) != set(unique_ids):
            raise CareerRecordNotFound

        semaphore = asyncio.Semaphore(8)

        async def evaluate(
            evidence_id: UUID,
        ) -> tuple[EvidenceRecord, EligibilityDecision]:
            async with semaphore:
                decision, refreshed = await self._evaluate_record(
                    owner_user_id,
                    records_by_id[evidence_id],
                )
            return refreshed, decision

        return tuple(await asyncio.gather(*(evaluate(value) for value in unique_ids)))

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
        self,
        owner_user_id: UUID,
        locator: ResumeSourceLocator,
        *,
        expected_claim: str | None = None,
    ) -> ValidatedResumeSource:
        source = await self._resume_sources.resolve_exact_span(
            owner_user_id,
            locator,
            expected_claim,
        )
        if source is None:
            raise CareerRecordSourceUnavailable("source span is unavailable or unauthorized")
        if (
            source.document_id != locator.document_id
            or source.snapshot_id != locator.snapshot_id
            or source.block_id != locator.block_id
            or source.page != locator.page
            or source.start_offset != locator.start_offset
            or source.end_offset != locator.end_offset
            or (
                expected_claim is not None
                and not compare_digest(
                    exact_claim_sha256(expected_claim),
                    source.source_sha256,
                )
            )
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
            if command.input_kind is EvidenceInputKind.EXACT_SOURCE_SPAN and (
                command.evidence_type is not EvidenceType.RESUME_STATEMENT
                or command.context is not None
                or command.organization is not None
                or command.project is not None
                or command.start_date is not None
                or command.end_date is not None
                or command.metrics
                or command.entity_ids
                or command.skill_ids
            ):
                raise CareerRecordValidationError(
                    "exact resume evidence is limited to the exact source statement"
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

    async def _source_state(
        self,
        owner_user_id: UUID,
        source: EvidenceSource,
        expected_claim: str,
    ) -> tuple[bool, bool]:
        if source.kind is EvidenceSourceKind.RESUME:
            if source.provenance is None:
                return False, False
            persisted = self._validated_source(source.provenance)
            available = await self._resume_sources.is_available(owner_user_id, persisted)
            if not available:
                return False, True
            if not source.exact_span_validated:
                return True, True
            if not compare_digest(
                exact_claim_sha256(expected_claim),
                source.provenance.source_sha256,
            ):
                return True, False
            locator = ResumeSourceLocator(
                document_id=source.provenance.document_id,
                snapshot_id=source.provenance.snapshot_id,
                block_id=source.provenance.block_id,
                page=source.provenance.page,
                start_offset=source.provenance.start_offset,
                end_offset=source.provenance.end_offset,
            )
            resolved = await self._resume_sources.resolve_exact_span(
                owner_user_id,
                locator,
                expected_claim,
            )
            return (
                True,
                resolved is not None and resolved.provenance() == source.provenance,
            )
        if source.kind is EvidenceSourceKind.ATTACHMENT:
            if source.attachment_id is None or self._attachments is None:
                return False, True
            return (
                (
                    await self._attachments.status(owner_user_id, source.attachment_id)
                    is AttachmentStatus.CLEAN
                ),
                True,
            )
        return source.available, True

    @staticmethod
    def _supported_shape_valid(record: EvidenceRecord) -> bool:
        revision = record.revision
        return (
            revision.evidence_type is EvidenceType.RESUME_STATEMENT
            and revision.title == revision.statement.strip()[:300]
            and revision.context is None
            and revision.organization is None
            and revision.project is None
            and revision.start_date is None
            and revision.end_date is None
            and not record.metrics
            and not record.entity_ids
            and not record.skill_ids
        )

    async def _evaluate_record(
        self, owner_user_id: UUID, record: EvidenceRecord
    ) -> tuple[EligibilityDecision, EvidenceRecord]:
        source_states = {
            source.id: await self._source_state(
                owner_user_id,
                source,
                record.revision.statement,
            )
            for source in record.sources
        }
        source_availability = {source_id: state[0] for source_id, state in source_states.items()}
        exact_shape_valid = (
            record.revision.strength is not EvidenceStrength.SUPPORTED
            or self._supported_shape_valid(record)
        )
        source_scope_validity = {
            source.id: (
                state[1]
                and (
                    exact_shape_valid
                    or not source.exact_span_validated
                    or source.kind is not EvidenceSourceKind.RESUME
                )
            )
            for source in record.sources
            for state in (source_states[source.id],)
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
            source_scope_validity=source_scope_validity,
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
