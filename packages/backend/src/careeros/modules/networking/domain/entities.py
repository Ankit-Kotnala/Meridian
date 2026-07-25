"""Domain entities for the consent-based networking CRM."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .errors import NetworkingValidationError

MAX_INT32 = 2_147_483_647
DELETED_TEXT = "[deleted]"
NETWORKING_CONTACT_CONSENT_POLICY_VERSION = "networking-contact-consent/1"
NETWORKING_CONTACT_DELETION_POLICY_VERSION = "contact-deletion-v1"
NETWORKING_CONSENT_LEDGER_POLICY_VERSIONS = (
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NETWORKING_CONTACT_DELETION_POLICY_VERSION,
)
_TRACE_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


def text(value: str, field_name: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not minimum <= len(normalized) <= maximum:
        raise NetworkingValidationError(
            f"{field_name} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise NetworkingValidationError(f"{field_name} contains unsupported characters")
    return normalized


def optional_text(value: str | None, field_name: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    return text(normalized, field_name, maximum) if normalized else None


def aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NetworkingValidationError(f"{field_name} must include a timezone")
    return value


def version(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_INT32:
        raise NetworkingValidationError("version must be a positive int32")
    return value


def normalize_search(*values: str | None) -> str:
    """Create a bounded, Unicode-normalized search document."""

    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().casefold()
        for value in values
        if value is not None and value.strip()
    )
    return normalized[:2_000]


def normalize_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    tags: list[str] = []
    for value in values:
        normalized = unicodedata.normalize("NFKC", value).strip().casefold()
        if not normalized:
            continue
        if not 1 <= len(normalized) <= 40:
            raise NetworkingValidationError("tags must contain at most 40 characters")
        if not re.fullmatch(r"[\w][\w .+&/-]*", normalized, flags=re.UNICODE):
            raise NetworkingValidationError("tag contains unsupported characters")
        if normalized not in tags:
            tags.append(normalized)
    if len(tags) > 20:
        raise NetworkingValidationError("a record may contain at most 20 tags")
    return tuple(sorted(tags))


class RelationshipStage(StrEnum):
    NEW = "new"
    WARM = "warm"
    ACTIVE = "active"
    TRUSTED = "trusted"
    DORMANT = "dormant"
    ARCHIVED = "archived"


class ContactReferralState(StrEnum):
    NONE = "none"
    CONSIDERING = "considering"
    REQUESTED = "requested"
    REFERRED = "referred"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class ConsentPurpose(StrEnum):
    COLLECTION = "collection"
    STORAGE = "storage"
    OUTREACH = "outreach"


class ConsentAction(StrEnum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


class InteractionKind(StrEnum):
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    MESSAGE = "message"
    SOCIAL = "social"
    REFERRAL = "referral"
    OTHER = "other"


class InteractionDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    MUTUAL = "mutual"


class InteractionDeliveryState(StrEnum):
    """The CRM records history; it never delivers communication."""

    RECORDED_ONLY = "recorded_only"


class ReferralStatus(StrEnum):
    PLANNED = "planned"
    REQUESTED = "requested"
    REFERRED = "referred"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class TemplateKind(StrEnum):
    INTRODUCTION = "introduction"
    FOLLOW_UP = "follow_up"
    REFERRAL_REQUEST = "referral_request"
    THANK_YOU = "thank_you"
    CUSTOM = "custom"


class ReminderStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderOccurrenceStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class ReminderOutboxStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    PROCESSED = "processed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class ReminderOutboxKind(StrEnum):
    LOCAL_REMINDER_DUE = "local_reminder_due"


class NetworkingAuditAction(StrEnum):
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"
    ORGANIZATION_DELETED = "organization_deleted"
    CONTACT_CREATED = "contact_created"
    CONTACT_UPDATED = "contact_updated"
    CONTACT_DELETED = "contact_deleted"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    NOTE_CREATED = "note_created"
    INTERACTION_RECORDED = "interaction_recorded"
    REFERRAL_CREATED = "referral_created"
    REFERRAL_UPDATED = "referral_updated"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    REMINDER_CREATED = "reminder_created"
    REMINDER_UPDATED = "reminder_updated"
    REMINDER_OCCURRENCE_MATERIALIZED = "reminder_occurrence_materialized"
    REMINDER_OCCURRENCE_DUE = "reminder_occurrence_due"
    REMINDER_OCCURRENCE_ACKNOWLEDGED = "reminder_occurrence_acknowledged"
    REMINDER_OCCURRENCE_SNOOZED = "reminder_occurrence_snoozed"
    REMINDER_OCCURRENCE_FAILED = "reminder_occurrence_failed"


@dataclass(frozen=True, slots=True)
class NetworkingOrganization:
    id: UUID
    owner_user_id: UUID
    name: str
    website: str | None
    industry: str | None
    location: str | None
    tags: tuple[str, ...]
    normalized_search: str
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", text(self.name, "organization name", 200))
        object.__setattr__(self, "website", optional_text(self.website, "website", 500))
        if self.website is not None and not self.website.startswith(("https://", "http://")):
            raise NetworkingValidationError("website must be an HTTP(S) URL")
        object.__setattr__(self, "industry", optional_text(self.industry, "industry", 120))
        object.__setattr__(self, "location", optional_text(self.location, "location", 200))
        object.__setattr__(self, "tags", normalize_tags(self.tags))
        object.__setattr__(
            self,
            "normalized_search",
            text(self.normalized_search, "normalized search", 2_000),
        )
        version(self.version)
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")
        if self.deleted_at is not None:
            aware(self.deleted_at, "deleted at")


@dataclass(frozen=True, slots=True)
class NetworkingContact:
    id: UUID
    owner_user_id: UUID
    organization_id: UUID | None
    name: str
    role: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    location: str | None
    relationship_stage: RelationshipStage
    referral_state: ContactReferralState
    tags: tuple[str, ...]
    normalized_search: str
    last_contact_at: datetime | None
    next_contact_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", text(self.name, "contact name", 160))
        object.__setattr__(self, "role", optional_text(self.role, "role", 160))
        object.__setattr__(self, "email", optional_text(self.email, "email", 254))
        if self.email is not None:
            if self.email.count("@") != 1 or " " in self.email:
                raise NetworkingValidationError("email is invalid")
            local, domain = self.email.rsplit("@", 1)
            if not local or "." not in domain.strip("."):
                raise NetworkingValidationError("email is invalid")
        object.__setattr__(self, "phone", optional_text(self.phone, "phone", 40))
        object.__setattr__(
            self,
            "profile_url",
            optional_text(self.profile_url, "profile URL", 500),
        )
        if self.profile_url is not None and not self.profile_url.startswith(
            ("https://", "http://")
        ):
            raise NetworkingValidationError("profile URL must be HTTP(S)")
        object.__setattr__(self, "location", optional_text(self.location, "location", 200))
        object.__setattr__(self, "tags", normalize_tags(self.tags))
        object.__setattr__(
            self,
            "normalized_search",
            text(self.normalized_search, "normalized search", 2_000),
        )
        if self.last_contact_at is not None:
            aware(self.last_contact_at, "last contact at")
        if self.next_contact_at is not None:
            aware(self.next_contact_at, "next contact at")
        version(self.version)
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")
        if self.deleted_at is not None:
            aware(self.deleted_at, "deleted at")
            if (
                self.organization_id is not None
                or self.name != DELETED_TEXT
                or self.role is not None
                or self.email is not None
                or self.phone is not None
                or self.profile_url is not None
                or self.location is not None
                or self.tags
                or self.normalized_search != DELETED_TEXT
                or self.last_contact_at is not None
                or self.next_contact_at is not None
            ):
                raise NetworkingValidationError("deleted contacts must be redacted")


@dataclass(frozen=True, slots=True)
class NetworkingConsentEvent:
    id: UUID
    owner_user_id: UUID
    contact_id: UUID
    purpose: ConsentPurpose
    action: ConsentAction
    policy_version: str
    actor_user_id: UUID
    sequence: int
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            text(self.policy_version, "consent policy version", 80),
        )
        if type(self.sequence) is not int or not 1 <= self.sequence <= MAX_INT32:
            raise NetworkingValidationError("consent sequence must be a positive int32")
        aware(self.occurred_at, "consent time")


@dataclass(frozen=True, slots=True)
class NetworkingContactNote:
    id: UUID
    owner_user_id: UUID
    contact_id: UUID
    body: str
    created_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", text(self.body, "note", 4_000))
        aware(self.created_at, "created at")
        if self.deleted_at is not None:
            aware(self.deleted_at, "deleted at")
            if self.body != DELETED_TEXT:
                raise NetworkingValidationError("deleted notes must be redacted")


@dataclass(frozen=True, slots=True)
class NetworkingInteraction:
    id: UUID
    owner_user_id: UUID
    contact_id: UUID
    template_id: UUID | None
    kind: InteractionKind
    direction: InteractionDirection
    occurred_at: datetime
    summary: str
    delivery_state: InteractionDeliveryState
    created_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", text(self.summary, "interaction summary", 4_000))
        aware(self.occurred_at, "interaction time")
        aware(self.created_at, "created at")
        if self.delivery_state is not InteractionDeliveryState.RECORDED_ONLY:
            raise NetworkingValidationError("networking interactions are record-only")
        if self.deleted_at is not None:
            aware(self.deleted_at, "deleted at")
            if self.summary != DELETED_TEXT:
                raise NetworkingValidationError("deleted interactions must be redacted")


@dataclass(frozen=True, slots=True)
class NetworkingReferral:
    id: UUID
    owner_user_id: UUID
    contact_id: UUID
    application_id: UUID
    status: ReferralStatus
    context: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", optional_text(self.context, "referral context", 2_000))
        version(self.version)
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")


@dataclass(frozen=True, slots=True)
class NetworkingTemplate:
    id: UUID
    owner_user_id: UUID
    kind: TemplateKind
    name: str
    body: str
    reviewed_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", text(self.name, "template name", 120))
        object.__setattr__(self, "body", text(self.body, "template body", 4_000))
        aware(self.reviewed_at, "reviewed at")
        version(self.version)
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")
        if self.deleted_at is not None:
            aware(self.deleted_at, "deleted at")
            if self.name != DELETED_TEXT or self.body != DELETED_TEXT:
                raise NetworkingValidationError("deleted templates must be redacted")


@dataclass(frozen=True, slots=True)
class NetworkingReminder:
    id: UUID
    owner_user_id: UUID
    contact_id: UUID
    title: str
    due_at: datetime
    recurrence_days: int | None
    max_attempts: int
    status: ReminderStatus
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", text(self.title, "reminder title", 240))
        aware(self.due_at, "due at")
        if self.recurrence_days is not None and (
            type(self.recurrence_days) is not int or not 1 <= self.recurrence_days <= 365
        ):
            raise NetworkingValidationError("recurrence days must be between 1 and 365")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 20:
            raise NetworkingValidationError("max attempts must be between 1 and 20")
        version(self.version)
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")


@dataclass(frozen=True, slots=True)
class NetworkingReminderOccurrence:
    id: UUID
    owner_user_id: UUID
    reminder_id: UUID
    contact_id: UUID
    scheduled_for: datetime
    occurrence_number: int
    status: ReminderOccurrenceStatus
    trace_id: str
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        aware(self.scheduled_for, "scheduled for")
        if type(self.occurrence_number) is not int or not 1 <= self.occurrence_number <= MAX_INT32:
            raise NetworkingValidationError("occurrence number must be a positive int32")
        if _TRACE_ID_PATTERN.fullmatch(self.trace_id) is None:
            raise NetworkingValidationError(
                "trace ID must contain exactly 32 lowercase hexadecimal characters"
            )
        if self.acknowledged_at is not None:
            aware(self.acknowledged_at, "acknowledged at")
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")


@dataclass(frozen=True, slots=True)
class NetworkingReminderOutboxEntry:
    id: UUID
    owner_user_id: UUID
    occurrence_id: UUID
    kind: ReminderOutboxKind
    status: ReminderOutboxStatus
    trace_id: str
    available_at: datetime
    attempt_count: int
    max_attempts: int
    lease_token: UUID | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if _TRACE_ID_PATTERN.fullmatch(self.trace_id) is None:
            raise NetworkingValidationError(
                "trace ID must contain exactly 32 lowercase hexadecimal characters"
            )
        aware(self.available_at, "available at")
        if type(self.attempt_count) is not int or self.attempt_count < 0:
            raise NetworkingValidationError("attempt count must be non-negative")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 20:
            raise NetworkingValidationError("max attempts must be between 1 and 20")
        if self.attempt_count > self.max_attempts:
            raise NetworkingValidationError("attempt count exceeds max attempts")
        if (self.lease_token is None) != (self.lease_expires_at is None):
            raise NetworkingValidationError("lease token and expiry must be set together")
        if self.lease_expires_at is not None:
            aware(self.lease_expires_at, "lease expiry")
        object.__setattr__(
            self,
            "last_error_code",
            optional_text(self.last_error_code, "error code", 80),
        )
        if (
            self.last_error_code is not None
            and re.fullmatch(r"[a-z0-9_:-]+", self.last_error_code) is None
        ):
            raise NetworkingValidationError("error code must be redacted and machine-readable")
        aware(self.created_at, "created at")
        aware(self.updated_at, "updated at")


@dataclass(frozen=True, slots=True)
class NetworkingIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_fingerprint: str
    response_kind: str
    response_id: UUID | None
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "idempotency_key", text(self.idempotency_key, "idempotency key", 128)
        )
        if re.fullmatch(r"[a-f0-9]{64}", self.request_fingerprint) is None:
            raise NetworkingValidationError("request fingerprint must be a SHA-256 digest")
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.response_kind) is None:
            raise NetworkingValidationError("response kind is invalid")
        aware(self.created_at, "created at")


_SAFE_AUDIT_KEYS = frozenset(
    {
        "purpose",
        "stage_from",
        "stage_to",
        "status_from",
        "status_to",
        "version",
        "organization_id",
        "contact_id",
        "application_id",
        "template_id",
        "reminder_id",
        "occurrence_id",
        "occurrence_number",
        "attempt_count",
        "detached_contact_count",
        "outbox_status",
        "recurring",
    }
)


@dataclass(frozen=True, slots=True)
class NetworkingAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID | None
    action: NetworkingAuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", text(self.target_kind, "audit target", 80))
        object.__setattr__(self, "request_id", text(self.request_id, "request ID", 128))
        object.__setattr__(self, "trace_id", text(self.trace_id, "trace ID", 128))
        if not set(self.metadata).issubset(_SAFE_AUDIT_KEYS):
            raise NetworkingValidationError("audit metadata contains sensitive or unsupported keys")
        aware(self.created_at, "created at")
