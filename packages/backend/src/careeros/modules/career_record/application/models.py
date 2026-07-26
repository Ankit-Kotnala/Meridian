"""Commands, query views, and transport-neutral pagination for Career Record."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from careeros.modules.career_record.domain import (
    AttachmentStatus,
    CareerEntity,
    CareerEntityKind,
    CareerEntityRelationship,
    CareerProfile,
    CareerRelationshipKind,
    ConflictStatus,
    EmploymentType,
    EvidenceAttachment,
    EvidenceConflict,
    EvidenceInputKind,
    EvidenceItem,
    EvidenceLifecycle,
    EvidenceMetric,
    EvidenceRevision,
    EvidenceSource,
    EvidenceStateTransition,
    EvidenceStrength,
    EvidenceType,
    EvidenceUsage,
    MetricPrecision,
    PartialDate,
    PersonalFact,
    PersonalFactKind,
    ProposalStatus,
    ReminderCadence,
    ResumeProvenance,
    SemanticImportProposal,
    Skill,
    SkillProficiency,
    TimelineFinding,
)
from careeros.modules.career_record.domain.errors import (
    CareerRecordCursorInvalid,
    CareerRecordValidationError,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class CreateCareerProfile:
    professional_headline: str | None = None
    summary: str | None = None
    work_authorization: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateCareerProfile:
    professional_headline: str | None
    summary: str | None
    work_authorization: str | None


@dataclass(frozen=True, slots=True)
class CreatePersonalFact:
    kind: PersonalFactKind
    value: str
    label: str | None = None
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class UpdatePersonalFact:
    value: str
    label: str | None = None
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class LinkCareerEntityRelationship:
    source_entity_id: UUID
    target_entity_id: UUID
    kind: CareerRelationshipKind


@dataclass(frozen=True, slots=True)
class CareerEntityData:
    kind: CareerEntityKind
    title: str
    organization: str | None = None
    description: str | None = None
    official_title: str | None = None
    display_title: str | None = None
    employment_type: EmploymentType | None = None
    location: str | None = None
    external_url: str | None = None
    start_date: PartialDate | None = None
    end_date: PartialDate | None = None
    is_current: bool = False
    group_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateSkill:
    name: str
    category: str | None = None
    proficiency: SkillProficiency | None = None


@dataclass(frozen=True, slots=True)
class UpdateSkill(CreateSkill):
    pass


@dataclass(frozen=True, slots=True)
class ResumeSourceLocator:
    document_id: UUID
    snapshot_id: UUID
    block_id: UUID
    page: int
    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if self.page < 1 or self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise CareerRecordValidationError("resume source locator is invalid")


@dataclass(frozen=True, slots=True)
class ValidatedResumeSource:
    document_id: UUID
    snapshot_id: UUID
    snapshot_revision: int
    schema_version: str
    parser_version: str
    block_id: UUID
    page: int
    start_offset: int
    end_offset: int
    source_sha256: bytes
    review_excerpt: str

    def provenance(self) -> ResumeProvenance:
        return ResumeProvenance(
            document_id=self.document_id,
            snapshot_id=self.snapshot_id,
            snapshot_revision=self.snapshot_revision,
            schema_version=self.schema_version,
            parser_version=self.parser_version,
            block_id=self.block_id,
            page=self.page,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            source_sha256=self.source_sha256,
            review_excerpt=self.review_excerpt,
        )


@dataclass(frozen=True, slots=True)
class CreateImportProposal:
    proposed_entity: CareerEntityData
    source: ResumeSourceLocator
    target_entity_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateSemanticImportProposals:
    document_id: UUID
    snapshot_id: UUID


@dataclass(frozen=True, slots=True)
class AcceptSemanticImportProposal:
    values: dict[UUID, str]
    idempotency_key: str
    target_record_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SemanticImportQuestion:
    semantic_entity_id: UUID
    code: str
    missing_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticImportBatch:
    proposals: tuple[SemanticImportProposal, ...]
    questions: tuple[SemanticImportQuestion, ...]


@dataclass(frozen=True, slots=True)
class SemanticImportAcceptance:
    proposal: SemanticImportProposal
    personal_facts: tuple[PersonalFact, ...] = ()
    entity: CareerEntity | None = None
    skill: Skill | None = None


@dataclass(frozen=True, slots=True)
class MetricInput:
    name: str | None
    value: Decimal
    value_max: Decimal | None
    unit: str
    currency: str | None
    period: str
    baseline: str | None
    comparator: str | None
    comparison_applicable: bool
    precision: MetricPrecision
    attribution: str


@dataclass(frozen=True, slots=True)
class CreateEvidence:
    evidence_type: EvidenceType
    title: str
    statement: str
    context: str | None = None
    organization: str | None = None
    project: str | None = None
    start_date: PartialDate | None = None
    end_date: PartialDate | None = None
    input_kind: EvidenceInputKind = EvidenceInputKind.MANUAL
    resume_source: ResumeSourceLocator | None = None
    external_url_source: str | None = None
    metrics: tuple[MetricInput, ...] = ()
    entity_ids: tuple[UUID, ...] = ()
    skill_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviseEvidence:
    evidence_type: EvidenceType
    title: str
    statement: str
    context: str | None
    organization: str | None = None
    project: str | None = None
    start_date: PartialDate | None = None
    end_date: PartialDate | None = None
    metrics: tuple[MetricInput, ...] = ()
    reason_code: str = "owner_material_edit"


@dataclass(frozen=True, slots=True)
class CreateAchievement:
    title: str
    delivered: str | None = None
    problem: str | None = None
    audience: str | None = None
    measurement: str | None = None
    effect: str | None = None
    collaboration: str | None = None
    methods: str | None = None
    entity_id: UUID | None = None
    metric: MetricInput | None = None
    reminder_cadence: ReminderCadence = ReminderCadence.NONE
    remind_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UpdateAchievement(CreateAchievement):
    pass


@dataclass(frozen=True, slots=True)
class UpdateReminderPreferences:
    enabled: bool
    day_of_month: int | None
    timezone: str


@dataclass(frozen=True, slots=True)
class AttachmentAdmissionRequest:
    evidence_id: UUID
    display_filename: str
    media_type: str
    expected_size: int


@dataclass(frozen=True, slots=True)
class AttachmentAdmissionResult:
    attachment_id: UUID
    status: AttachmentStatus
    expires_at: datetime
    upload_url: str


@dataclass(frozen=True, slots=True)
class AttachmentFinalization:
    attachment_id: UUID
    status: AttachmentStatus
    size_bytes: int
    content_sha256: bytes | None


@dataclass(frozen=True, slots=True)
class AttachmentUploadView:
    attachment: EvidenceAttachment
    admission: AttachmentAdmissionResult


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    item: EvidenceItem
    revision: EvidenceRevision
    revisions: tuple[EvidenceRevision, ...]
    transitions: tuple[EvidenceStateTransition, ...]
    sources: tuple[EvidenceSource, ...]
    metrics: tuple[EvidenceMetric, ...]
    attachments: tuple[EvidenceAttachment, ...]
    conflicts: tuple[EvidenceConflict, ...]
    entity_ids: tuple[UUID, ...]
    skill_ids: tuple[UUID, ...]
    usage: tuple[EvidenceUsage, ...]

    @property
    def id(self) -> UUID:
        return self.item.id

    @property
    def created_at(self) -> datetime:
        return self.item.created_at


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotSkill:
    id: UUID
    name: str
    category: str | None
    proficiency: str | None


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotEntity:
    id: UUID
    kind: str
    title: str
    organization: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotRelationship:
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    kind: str


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotPersonalFact:
    id: UUID
    kind: str
    value: str
    label: str | None
    is_primary: bool


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotEvidence:
    id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    title: str
    statement: str
    context: str | None
    strength: str
    skill_ids: tuple[UUID, ...]
    entity_ids: tuple[UUID, ...]
    has_numeric_claim: bool


@dataclass(frozen=True, slots=True)
class CareerRecordReadinessSnapshot:
    """Application-level, eligibility-filtered facts for downstream matching."""

    skills: tuple[ReadinessSnapshotSkill, ...]
    entities: tuple[ReadinessSnapshotEntity, ...]
    evidence: tuple[ReadinessSnapshotEvidence, ...]
    relationships: tuple[ReadinessSnapshotRelationship, ...] = ()
    personal_facts: tuple[ReadinessSnapshotPersonalFact, ...] = ()


@dataclass(frozen=True, slots=True)
class CareerRecordAnalyticsGrowthPoint:
    """Content-free current eligible achievement milestone for growth analytics."""

    evidence_id: UUID
    evidence_revision_id: UUID
    category: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class CareerRecordAnalyticsSourceState:
    record_count: int
    item_version_sum: int
    max_item_updated_at: datetime | None
    max_revision_created_at: datetime | None

    def watermark(self) -> CareerRecordAnalyticsWatermark:
        payload = {
            "itemVersionSum": self.item_version_sum,
            "maxItemUpdatedAt": (
                self.max_item_updated_at.isoformat()
                if self.max_item_updated_at is not None
                else None
            ),
            "maxRevisionCreatedAt": (
                self.max_revision_created_at.isoformat()
                if self.max_revision_created_at is not None
                else None
            ),
            "recordCount": self.record_count,
            "v": 1,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return CareerRecordAnalyticsWatermark(
            token=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            record_count=self.record_count,
            max_updated_at=max(
                (
                    value
                    for value in (
                        self.max_item_updated_at,
                        self.max_revision_created_at,
                    )
                    if value is not None
                ),
                default=None,
            ),
        )


@dataclass(frozen=True, slots=True)
class CareerRecordAnalyticsWatermark:
    token: str
    record_count: int
    max_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class CareerProfileView:
    profile: CareerProfile
    entities: tuple[CareerEntity, ...]
    skills: tuple[Skill, ...]
    findings: tuple[TimelineFinding, ...]
    personal_facts: tuple[PersonalFact, ...] = ()
    relationships: tuple[CareerEntityRelationship, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceFilter:
    query: str | None = None
    strength: EvidenceStrength | None = None
    lifecycle: EvidenceLifecycle | None = None
    include_archived: bool = False
    conflict_status: ConflictStatus | None = None


@dataclass(frozen=True, slots=True)
class ProposalFilter:
    status: ProposalStatus | None = None


@dataclass(frozen=True, slots=True)
class PageCursor:
    created_at: datetime
    item_id: UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.item_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str | None) -> PageCursor | None:
        if value is None:
            return None
        if not 1 <= len(value) <= 512:
            raise CareerRecordCursorInvalid("cursor is outside supported bounds")
        try:
            padded = value + "=" * (-len(value) % 4)
            decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode("utf-8")
            created_at, separator, item_id = decoded.partition("|")
            if separator != "|":
                raise ValueError
            timestamp = datetime.fromisoformat(created_at)
            if timestamp.tzinfo is None:
                raise ValueError
            return cls(timestamp, UUID(item_id))
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise CareerRecordCursorInvalid("cursor is malformed") from exc


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: tuple[T, ...]
    next_cursor: str | None


def next_page[T](items: tuple[T, ...], limit: int) -> Page[T]:
    if len(items) <= limit:
        return Page(items=items, next_cursor=None)
    visible = items[:limit]
    last = visible[-1]
    created_at = getattr(last, "created_at", None)
    item_id = getattr(last, "id", None)
    if not isinstance(created_at, datetime) or not isinstance(item_id, UUID):
        raise TypeError("cursor page items must expose created_at and id")
    return Page(items=visible, next_cursor=PageCursor(created_at, item_id).encode())
