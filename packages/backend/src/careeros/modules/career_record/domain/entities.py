"""Career Record domain entities and value objects.

These types deliberately contain no delivery, persistence, queue, or provider
dependencies.  Durable adapters may map them to relational rows, while every
mutation continues to be decided here or by the application service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import CareerRecordTransitionRejected, CareerRecordValidationError

MAX_INT32 = 2_147_483_647


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise CareerRecordValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise CareerRecordValidationError(f"{field} must not exceed {maximum} characters")
    return normalized


def _positive_version(value: int) -> None:
    if not 1 <= value <= MAX_INT32:
        raise CareerRecordValidationError("version must be a positive int32")


def _http_url(value: str, field: str) -> str:
    normalized = _text(value, field, 2_048)
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise CareerRecordValidationError(f"{field} must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise CareerRecordValidationError(f"{field} must not contain credentials")
    return normalized


class CareerEntityKind(StrEnum):
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECT = "project"
    CREDENTIAL = "credential"
    PUBLICATION = "publication"
    AWARD = "award"
    VOLUNTEERING = "volunteering"
    LANGUAGE = "language"
    PORTFOLIO_LINK = "portfolio_link"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    VOLUNTEER = "volunteer"
    OTHER = "other"


class DatePrecision(StrEnum):
    YEAR = "year"
    MONTH = "month"


@dataclass(frozen=True, slots=True, order=True)
class PartialDate:
    """A career date that never invents a day of month."""

    year: int
    month: int | None = None

    def __post_init__(self) -> None:
        if not 1900 <= self.year <= 2200:
            raise CareerRecordValidationError("year must be between 1900 and 2200")
        if self.month is not None and not 1 <= self.month <= 12:
            raise CareerRecordValidationError("month must be between 1 and 12")

    @property
    def precision(self) -> DatePrecision:
        return DatePrecision.MONTH if self.month is not None else DatePrecision.YEAR

    @property
    def earliest_month(self) -> int:
        return self.year * 12 + ((self.month or 1) - 1)

    @property
    def latest_month(self) -> int:
        return self.year * 12 + ((self.month or 12) - 1)


@dataclass(slots=True)
class CareerProfile:
    id: UUID
    owner_user_id: UUID
    professional_headline: str | None
    summary: str | None
    work_authorization: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.professional_headline = _optional_text(
            self.professional_headline, "professional headline", 240
        )
        self.summary = _optional_text(self.summary, "summary", 4_000)
        self.work_authorization = _optional_text(self.work_authorization, "work authorization", 500)
        _positive_version(self.version)

    def edit(
        self,
        *,
        professional_headline: str | None,
        summary: str | None,
        work_authorization: str | None,
        now: datetime,
    ) -> None:
        self.professional_headline = _optional_text(
            professional_headline, "professional headline", 240
        )
        self.summary = _optional_text(summary, "summary", 4_000)
        self.work_authorization = _optional_text(work_authorization, "work authorization", 500)
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(slots=True)
class CareerEntity:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    kind: CareerEntityKind
    title: str
    organization: str | None
    description: str | None
    official_title: str | None
    display_title: str | None
    employment_type: EmploymentType | None
    location: str | None
    external_url: str | None
    start_date: PartialDate | None
    end_date: PartialDate | None
    is_current: bool
    sort_order: int
    group_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "entity title", 300)
        self.organization = _optional_text(self.organization, "organization", 300)
        self.description = _optional_text(self.description, "description", 8_000)
        self.official_title = _optional_text(self.official_title, "official title", 300)
        self.display_title = _optional_text(self.display_title, "display title", 300)
        self.location = _optional_text(self.location, "location", 240)
        if self.external_url is not None:
            self.external_url = _http_url(self.external_url, "external URL")
        if self.kind is CareerEntityKind.EXPERIENCE and self.organization is None:
            raise CareerRecordValidationError("experience requires an organization")
        if self.kind is not CareerEntityKind.EXPERIENCE and self.employment_type is not None:
            raise CareerRecordValidationError("employment type is only valid for experience")
        if self.kind is CareerEntityKind.EDUCATION and self.organization is None:
            raise CareerRecordValidationError("education requires an institution")
        if self.kind is CareerEntityKind.PORTFOLIO_LINK and self.external_url is None:
            raise CareerRecordValidationError("portfolio link requires an HTTP(S) URL")
        if self.is_current and self.end_date is not None:
            raise CareerRecordValidationError("a current entity cannot have an end date")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date.latest_month < self.start_date.earliest_month
        ):
            raise CareerRecordValidationError("end date cannot precede start date")
        if not 0 <= self.sort_order <= MAX_INT32:
            raise CareerRecordValidationError("sort order must be a non-negative int32")
        _positive_version(self.version)

    def edit(
        self,
        *,
        title: str,
        organization: str | None,
        description: str | None,
        official_title: str | None,
        display_title: str | None,
        employment_type: EmploymentType | None,
        location: str | None,
        external_url: str | None,
        start_date: PartialDate | None,
        end_date: PartialDate | None,
        is_current: bool,
        group_id: UUID | None,
        now: datetime,
    ) -> None:
        candidate = replace(
            self,
            title=title,
            organization=organization,
            description=description,
            official_title=official_title,
            display_title=display_title,
            employment_type=employment_type,
            location=location,
            external_url=external_url,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
            group_id=group_id,
        )
        self.title = candidate.title
        self.organization = candidate.organization
        self.description = candidate.description
        self.official_title = candidate.official_title
        self.display_title = candidate.display_title
        self.employment_type = candidate.employment_type
        self.location = candidate.location
        self.external_url = candidate.external_url
        self.start_date = candidate.start_date
        self.end_date = candidate.end_date
        self.is_current = candidate.is_current
        self.group_id = candidate.group_id
        self.version += 1
        _positive_version(self.version)
        self.updated_at = now


@dataclass(slots=True)
class Skill:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    name: str
    category: str | None
    proficiency: SkillProficiency | None
    sort_order: int
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.name = _text(self.name, "skill name", 160)
        self.category = _optional_text(self.category, "skill category", 120)
        if not 0 <= self.sort_order <= MAX_INT32:
            raise CareerRecordValidationError("sort order must be a non-negative int32")
        _positive_version(self.version)

    def edit(
        self,
        *,
        name: str,
        category: str | None,
        proficiency: SkillProficiency | None,
        now: datetime,
    ) -> None:
        self.name = _text(name, "skill name", 160)
        self.category = _optional_text(category, "skill category", 120)
        self.proficiency = proficiency
        self.updated_at = now
        self.version += 1


class SkillProficiency(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass(frozen=True, slots=True)
class EntitySkillLink:
    id: UUID
    owner_user_id: UUID
    entity_id: UUID
    skill_id: UUID
    created_at: datetime


class TimelineFindingKind(StrEnum):
    NEUTRAL_GAP = "neutral_gap"
    CONCURRENT_ROLES = "concurrent_roles"
    PROMOTION_SEQUENCE = "promotion_sequence"
    REVIEW_OVERLAP = "review_overlap"


@dataclass(frozen=True, slots=True)
class TimelineFinding:
    kind: TimelineFindingKind
    entity_ids: tuple[UUID, ...]
    start: PartialDate | None
    end: PartialDate | None
    code: str


@dataclass(frozen=True, slots=True)
class ResumeProvenance:
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

    def __post_init__(self) -> None:
        if self.snapshot_revision < 1:
            raise CareerRecordValidationError("snapshot revision must be positive")
        _text(self.schema_version, "source schema version", 80)
        _text(self.parser_version, "parser version", 120)
        if self.page < 1 or self.start_offset < 0 or self.end_offset < self.start_offset:
            raise CareerRecordValidationError("source span is invalid")
        if len(self.source_sha256) != 32:
            raise CareerRecordValidationError("source digest must be SHA-256")
        _text(self.review_excerpt, "review excerpt", 1_000)


class ProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(slots=True)
class ImportProposal:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    target_entity_id: UUID | None
    proposed_entity: CareerEntity
    provenance: ResumeProvenance
    status: ProposalStatus
    conflict_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.proposed_entity.owner_user_id != self.owner_user_id:
            raise CareerRecordValidationError("proposal entity owner does not match")
        if self.proposed_entity.profile_id != self.profile_id:
            raise CareerRecordValidationError("proposal entity profile does not match")
        self.conflict_code = _optional_text(self.conflict_code, "conflict code", 80)
        _positive_version(self.version)

    def accept(self, now: datetime) -> None:
        if self.status is not ProposalStatus.PENDING:
            raise CareerRecordTransitionRejected("only a pending proposal can be accepted")
        self.status = ProposalStatus.ACCEPTED
        self.reviewed_at = now
        self.updated_at = now
        self.version += 1

    def reject(self, now: datetime) -> None:
        if self.status is not ProposalStatus.PENDING:
            raise CareerRecordTransitionRejected("only a pending proposal can be rejected")
        self.status = ProposalStatus.REJECTED
        self.reviewed_at = now
        self.updated_at = now
        self.version += 1


class EvidenceLifecycle(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class EvidenceStrength(StrEnum):
    VERIFIED = "verified"
    CONFIRMED = "confirmed"
    SUPPORTED = "supported"
    INFERRED = "inferred"
    UNSUPPORTED = "unsupported"


class EvidenceType(StrEnum):
    RESUME_STATEMENT = "resume_statement"
    ACHIEVEMENT = "achievement"
    METRIC = "metric"
    PROJECT = "project"
    CREDENTIAL = "credential"
    PUBLICATION = "publication"
    AWARD = "award"
    REVIEW_EXCERPT = "review_excerpt"
    PORTFOLIO = "portfolio"
    TESTIMONIAL = "testimonial"
    SUPPORT_DOCUMENT = "support_document"
    NOTE = "note"


class EvidenceInputKind(StrEnum):
    MANUAL = "manual"
    PARSER = "parser"
    EXACT_SOURCE_SPAN = "exact_source_span"
    ACHIEVEMENT = "achievement"
    MATERIAL_EDIT = "material_edit"


class EvidenceSourceKind(StrEnum):
    USER_ATTESTATION = "user_attestation"
    RESUME = "resume"
    ATTACHMENT = "attachment"
    ACHIEVEMENT = "achievement"
    EXTERNAL_URL = "external_url"
    INDEPENDENT_VERIFIER = "independent_verifier"


class EvidenceAuthority(StrEnum):
    SYSTEM_SOURCE_VALIDATION = "system_source_validation"
    OWNER_CONFIRMATION = "owner_confirmation"
    OWNER_REJECTION = "owner_rejection"
    DETERMINISTIC_POLICY = "deterministic_policy"
    SERVER_VERIFICATION = "server_verification"
    MATERIAL_EDIT = "material_edit"


class VerificationMethod(StrEnum):
    DOCUMENT_SIGNATURE = "document_signature"
    CREDENTIAL_REGISTRY = "credential_registry"
    APPROVED_MANUAL_REVIEW = "approved_manual_review"


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    method: VerificationMethod
    verifier_reference: str
    source_reference: str
    scope: str
    decided_at: datetime

    def __post_init__(self) -> None:
        _text(self.verifier_reference, "verifier reference", 240)
        _text(self.source_reference, "verification source reference", 500)
        _text(self.scope, "verification scope", 1_000)


@dataclass(slots=True)
class EvidenceItem:
    id: UUID
    owner_user_id: UUID
    lifecycle: EvidenceLifecycle
    current_revision: int
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.current_revision < 1:
            raise CareerRecordValidationError("current evidence revision must be positive")
        _positive_version(self.version)

    def archive(self, now: datetime) -> None:
        if self.lifecycle is EvidenceLifecycle.DELETED:
            raise CareerRecordTransitionRejected("deleted evidence cannot be archived")
        self.lifecycle = EvidenceLifecycle.ARCHIVED
        self.archived_at = now
        self.updated_at = now
        self.version += 1

    def restore(self, now: datetime) -> None:
        if self.lifecycle is not EvidenceLifecycle.ARCHIVED:
            raise CareerRecordTransitionRejected("only archived evidence can be restored")
        self.lifecycle = EvidenceLifecycle.ACTIVE
        self.archived_at = None
        self.updated_at = now
        self.version += 1

    def delete(self, now: datetime) -> None:
        if self.lifecycle is EvidenceLifecycle.DELETED:
            raise CareerRecordTransitionRejected("evidence is already deleted")
        self.lifecycle = EvidenceLifecycle.DELETED
        self.archived_at = None
        self.deleted_at = now
        self.updated_at = now
        self.version += 1


@dataclass(frozen=True, slots=True)
class EvidenceRevision:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    revision: int
    evidence_type: EvidenceType
    title: str
    statement: str
    context: str | None
    organization: str | None
    project: str | None
    start_date: PartialDate | None
    end_date: PartialDate | None
    strength: EvidenceStrength
    input_kind: EvidenceInputKind
    created_at: datetime

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise CareerRecordValidationError("evidence revision must be positive")
        object.__setattr__(self, "title", _text(self.title, "evidence title", 300))
        object.__setattr__(self, "statement", _text(self.statement, "evidence statement", 8_000))
        object.__setattr__(self, "context", _optional_text(self.context, "evidence context", 4_000))
        object.__setattr__(
            self, "organization", _optional_text(self.organization, "evidence organization", 300)
        )
        object.__setattr__(self, "project", _optional_text(self.project, "evidence project", 300))
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date.latest_month < self.start_date.earliest_month
        ):
            raise CareerRecordValidationError("evidence end date cannot precede start date")

    @property
    def has_numeric_claim(self) -> bool:
        """Conservatively identify numbers that need structured metric evidence."""

        return re.search(r"(?<![A-Za-z])[-+]?\d", self.statement) is not None


@dataclass(frozen=True, slots=True)
class EvidenceStateTransition:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    from_revision_id: UUID | None
    to_revision_id: UUID
    previous_strength: EvidenceStrength | None
    next_strength: EvidenceStrength
    authority: EvidenceAuthority
    reason_code: str
    actor_user_id: UUID | None
    verifier_reference: str | None
    request_id: str
    trace_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.reason_code, "transition reason code", 80)
        _text(self.request_id, "request ID", 128)
        _text(self.trace_id, "trace ID", 128)
        if self.verifier_reference is not None:
            _text(self.verifier_reference, "verifier reference", 240)


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    id: UUID
    owner_user_id: UUID
    evidence_revision_id: UUID
    kind: EvidenceSourceKind
    label: str
    provenance: ResumeProvenance | None
    attachment_id: UUID | None
    external_url: str | None
    available: bool
    exact_span_validated: bool
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _text(self.label, "evidence source label", 300))
        if self.kind is EvidenceSourceKind.RESUME and self.provenance is None:
            raise CareerRecordValidationError("resume evidence requires copied provenance")
        if self.kind is EvidenceSourceKind.ATTACHMENT and self.attachment_id is None:
            raise CareerRecordValidationError("attachment evidence requires an attachment")
        if self.kind is EvidenceSourceKind.EXTERNAL_URL:
            if self.external_url is None:
                raise CareerRecordValidationError("external URL evidence requires a URL")
            object.__setattr__(self, "external_url", _http_url(self.external_url, "source URL"))
            if self.exact_span_validated:
                raise CareerRecordValidationError("an external URL alone is never an exact source")
        elif self.external_url is not None:
            raise CareerRecordValidationError("source URL is only valid for external URL evidence")
        if self.exact_span_validated and self.provenance is None:
            raise CareerRecordValidationError("validated span requires copied provenance")


class MetricPrecision(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    RANGE = "range"


@dataclass(frozen=True, slots=True)
class EvidenceMetric:
    id: UUID
    owner_user_id: UUID
    evidence_revision_id: UUID
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
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_text(self.name, "metric name", 160))
        if not self.value.is_finite():
            raise CareerRecordValidationError("metric value must be finite")
        if self.value_max is not None and (
            not self.value_max.is_finite() or self.value_max < self.value
        ):
            raise CareerRecordValidationError("metric range maximum is invalid")
        if self.precision is MetricPrecision.RANGE and self.value_max is None:
            raise CareerRecordValidationError("range metric requires a maximum value")
        object.__setattr__(self, "unit", _text(self.unit, "metric unit", 80))
        object.__setattr__(self, "currency", _optional_text(self.currency, "currency", 12))
        object.__setattr__(self, "period", _text(self.period, "metric period", 240))
        object.__setattr__(self, "baseline", _optional_text(self.baseline, "metric baseline", 500))
        object.__setattr__(
            self, "comparator", _optional_text(self.comparator, "metric comparator", 500)
        )
        object.__setattr__(self, "attribution", _text(self.attribution, "metric attribution", 500))
        if self.currency is not None and len(self.currency) != 3:
            raise CareerRecordValidationError("currency must be a three-letter code")

    @property
    def complete(self) -> bool:
        comparison_complete = not self.comparison_applicable or bool(
            self.baseline or self.comparator
        )
        return bool(self.unit and self.period and self.attribution and comparison_complete)


class AttachmentStatus(StrEnum):
    PENDING = "pending"
    QUARANTINED = "quarantined"
    CLEAN = "clean"
    REJECTED = "rejected"
    DELETING = "deleting"
    DELETED = "deleted"


@dataclass(slots=True)
class EvidenceAttachment:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    display_filename: str
    media_type: str
    size_bytes: int
    content_sha256: bytes | None
    status: AttachmentStatus
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.display_filename = _text(self.display_filename, "attachment filename", 255)
        self.media_type = _text(self.media_type, "attachment media type", 100)
        if self.media_type not in {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            raise CareerRecordValidationError("unsupported evidence attachment media type")
        if self.size_bytes < 1:
            raise CareerRecordValidationError("attachment size must be positive")
        if self.content_sha256 is not None and len(self.content_sha256) != 32:
            raise CareerRecordValidationError("attachment digest must be SHA-256")
        _positive_version(self.version)


@dataclass(frozen=True, slots=True)
class EvidenceEntityLink:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    entity_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceSkillLink:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    skill_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceUsage:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    consumer_kind: str
    consumer_id: UUID
    purpose: str
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.consumer_kind, "usage consumer kind", 80)
        _text(self.purpose, "usage purpose", 120)


class EvidenceConflictKind(StrEnum):
    DATE = "date"
    TITLE = "title"
    METRIC = "metric"
    ENTITY = "entity"
    SOURCE = "source"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ConflictResolution(StrEnum):
    KEEP_CURRENT = "keep_current"
    ACCEPT_INCOMING = "accept_incoming"
    KEEP_BOTH = "keep_both"
    NOT_A_CONFLICT = "not_a_conflict"


@dataclass(slots=True)
class EvidenceConflict:
    id: UUID
    owner_user_id: UUID
    evidence_id: UUID
    conflicting_evidence_id: UUID | None
    kind: EvidenceConflictKind
    code: str
    status: ConflictStatus
    resolution: ConflictResolution | None
    version: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        self.code = _text(self.code, "conflict code", 80)
        _positive_version(self.version)

    def resolve(self, resolution: ConflictResolution, now: datetime) -> None:
        if self.status is not ConflictStatus.OPEN:
            raise CareerRecordTransitionRejected("only an open conflict can be resolved")
        self.status = (
            ConflictStatus.DISMISSED
            if resolution is ConflictResolution.NOT_A_CONFLICT
            else ConflictStatus.RESOLVED
        )
        self.resolution = resolution
        self.resolved_at = now
        self.updated_at = now
        self.version += 1


class AchievementStatus(StrEnum):
    DRAFT = "draft"
    CONVERTED = "converted"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class AchievementMetric:
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

    def __post_init__(self) -> None:
        probe = EvidenceMetric(
            id=UUID(int=0),
            owner_user_id=UUID(int=0),
            evidence_revision_id=UUID(int=0),
            name=self.name,
            value=self.value,
            value_max=self.value_max,
            unit=self.unit,
            currency=self.currency,
            period=self.period,
            baseline=self.baseline,
            comparator=self.comparator,
            comparison_applicable=self.comparison_applicable,
            precision=self.precision,
            attribution=self.attribution,
            created_at=datetime.min,
        )
        object.__setattr__(self, "name", probe.name)
        object.__setattr__(self, "unit", probe.unit)
        object.__setattr__(self, "currency", probe.currency)
        object.__setattr__(self, "period", probe.period)
        object.__setattr__(self, "baseline", probe.baseline)
        object.__setattr__(self, "comparator", probe.comparator)
        object.__setattr__(self, "attribution", probe.attribution)

    @property
    def complete(self) -> bool:
        return not self.comparison_applicable or bool(self.baseline or self.comparator)


class ReminderCadence(StrEnum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


@dataclass(slots=True)
class ReminderPreferences:
    id: UUID
    owner_user_id: UUID
    enabled: bool
    day_of_month: int | None
    timezone: str
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.timezone = _text(self.timezone, "reminder timezone", 64)
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise CareerRecordValidationError(
                "reminder timezone must be a valid IANA zone"
            ) from exc
        if self.enabled and (self.day_of_month is None or not 1 <= self.day_of_month <= 28):
            raise CareerRecordValidationError("enabled reminders require day of month 1 through 28")
        if not self.enabled and self.day_of_month is not None:
            raise CareerRecordValidationError("disabled reminders cannot set a day of month")
        _positive_version(self.version)

    def edit(self, enabled: bool, day_of_month: int | None, timezone: str, now: datetime) -> None:
        candidate = replace(
            self,
            enabled=enabled,
            day_of_month=day_of_month,
            timezone=timezone,
        )
        self.enabled = candidate.enabled
        self.day_of_month = candidate.day_of_month
        self.timezone = candidate.timezone
        self.updated_at = now
        self.version += 1


@dataclass(slots=True)
class AchievementDraft:
    id: UUID
    owner_user_id: UUID
    profile_id: UUID
    title: str
    delivered: str | None
    problem: str | None
    audience: str | None
    measurement: str | None
    effect: str | None
    collaboration: str | None
    methods: str | None
    entity_id: UUID | None
    metric: AchievementMetric | None
    reminder_cadence: ReminderCadence
    remind_at: datetime | None
    status: AchievementStatus
    converted_evidence_id: UUID | None
    conversion_idempotency_key: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.title = _text(self.title, "achievement title", 300)
        for field in (
            "delivered",
            "problem",
            "audience",
            "measurement",
            "effect",
            "collaboration",
            "methods",
        ):
            setattr(self, field, _optional_text(getattr(self, field), field, 4_000))
        if self.reminder_cadence is ReminderCadence.CUSTOM and self.remind_at is None:
            raise CareerRecordValidationError("custom reminder cadence requires a reminder time")
        if self.status is AchievementStatus.CONVERTED and self.converted_evidence_id is None:
            raise CareerRecordValidationError("converted achievement requires an evidence ID")
        _positive_version(self.version)

    def convert(self, evidence_id: UUID, idempotency_key: str, now: datetime) -> None:
        if self.status is AchievementStatus.CONVERTED:
            if (
                self.converted_evidence_id == evidence_id
                and self.conversion_idempotency_key == idempotency_key
            ):
                return
            raise CareerRecordTransitionRejected("achievement was already converted")
        if self.status is not AchievementStatus.DRAFT:
            raise CareerRecordTransitionRejected("only a draft achievement can be converted")
        if self.delivered is None:
            raise CareerRecordValidationError(
                "delivered outcome must be answered before conversion"
            )
        self.status = AchievementStatus.CONVERTED
        self.converted_evidence_id = evidence_id
        self.conversion_idempotency_key = _text(idempotency_key, "idempotency key", 128, minimum=8)
        self.updated_at = now
        self.version += 1


class AuditAction(StrEnum):
    PROFILE_CREATED = "career.profile_created"
    PROFILE_UPDATED = "career.profile_updated"
    ENTITY_CREATED = "career.entity_created"
    ENTITY_UPDATED = "career.entity_updated"
    ENTITY_DELETED = "career.entity_deleted"
    ENTITIES_REORDERED = "career.entities_reordered"
    SKILL_CREATED = "career.skill_created"
    SKILL_UPDATED = "career.skill_updated"
    SKILL_DELETED = "career.skill_deleted"
    ENTITY_SKILL_LINKED = "career.entity_skill_linked"
    PROPOSAL_CREATED = "career.proposal_created"
    PROPOSAL_ACCEPTED = "career.proposal_accepted"
    PROPOSAL_REJECTED = "career.proposal_rejected"
    EVIDENCE_CREATED = "evidence.created"
    EVIDENCE_REVISED = "evidence.revised"
    EVIDENCE_TRANSITIONED = "evidence.transitioned"
    EVIDENCE_ARCHIVED = "evidence.archived"
    EVIDENCE_RESTORED = "evidence.restored"
    EVIDENCE_DELETED = "evidence.deleted"
    EVIDENCE_LINKED = "evidence.linked"
    ATTACHMENT_REQUESTED = "evidence.attachment_requested"
    ATTACHMENT_FINALIZED = "evidence.attachment_finalized"
    ATTACHMENT_DELETED = "evidence.attachment_deleted"
    CONFLICT_CREATED = "evidence.conflict_created"
    CONFLICT_RESOLVED = "evidence.conflict_resolved"
    ACHIEVEMENT_CREATED = "achievement.created"
    ACHIEVEMENT_UPDATED = "achievement.updated"
    ACHIEVEMENT_CONVERTED = "achievement.converted"
    ACHIEVEMENT_ARCHIVED = "achievement.archived"
    REMINDERS_UPDATED = "achievement.reminders_updated"


_AUDIT_DETAIL_KEYS = frozenset(
    {
        "entity_kind",
        "proposal_status",
        "previous_strength",
        "next_strength",
        "reason_code",
        "lifecycle",
        "conflict_kind",
        "resolution",
        "achievement_status",
        "count",
    }
)


@dataclass(frozen=True, slots=True)
class CareerAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: AuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    details: tuple[tuple[str, str], ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.target_kind, "audit target kind", 80)
        _text(self.request_id, "request ID", 128)
        _text(self.trace_id, "trace ID", 128)
        for key, value in self.details:
            if key not in _AUDIT_DETAIL_KEYS:
                raise CareerRecordValidationError("audit detail key is not allowlisted")
            _text(value, f"audit detail {key}", 120)
