"""Strict wire schemas for the private, consent-based Networking CRM."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rezumi.modules.networking.domain import (
    NETWORKING_CONTACT_CONSENT_POLICY_VERSION,
    NETWORKING_CONTACT_DELETION_POLICY_VERSION,
)


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


_BIDI_CONTROLS = {
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def _safe_text(value: str, *, required: bool = False) -> str:
    normalized = value.strip()
    if required and not normalized:
        raise ValueError("a value is required")
    if "\x00" in normalized or any(
        (ord(character) < 32 and character not in {"\n", "\r", "\t"}) or character in _BIDI_CONTROLS
        for character in normalized
    ):
        raise ValueError("control characters are not accepted")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _safe_text(value) or None


def _aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must include a UTC offset")
    return value


class NetworkingSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
RelationshipStageValue = Literal["new", "warm", "active", "trusted", "dormant", "archived"]
ContactReferralStateValue = Literal[
    "none",
    "considering",
    "requested",
    "referred",
    "declined",
    "cancelled",
]
ConsentPurposeValue = Literal["collection", "storage", "outreach"]
ConsentActionValue = Literal["granted", "withdrawn"]


class ConsentPolicyVersionValue(StrEnum):
    CONTACT_CONSENT_V1 = NETWORKING_CONTACT_CONSENT_POLICY_VERSION


class ConsentLedgerPolicyVersionValue(StrEnum):
    CONTACT_CONSENT_V1 = NETWORKING_CONTACT_CONSENT_POLICY_VERSION
    CONTACT_DELETION_V1 = NETWORKING_CONTACT_DELETION_POLICY_VERSION


InteractionKindValue = Literal[
    "email",
    "call",
    "meeting",
    "message",
    "social",
    "referral",
    "other",
]
InteractionDirectionValue = Literal["inbound", "outbound", "mutual"]
ReferralStatusValue = Literal["planned", "requested", "referred", "declined", "cancelled"]
TemplateKindValue = Literal[
    "introduction",
    "follow_up",
    "referral_request",
    "thank_you",
    "custom",
]
ReminderStatusValue = Literal["active", "completed", "cancelled"]
ReminderOccurrenceStatusValue = Literal[
    "scheduled",
    "due",
    "acknowledged",
    "cancelled",
    "dead_letter",
]
ReminderQueueStatusValue = Literal[
    "pending",
    "leased",
    "processed",
    "cancelled",
    "dead_letter",
]


class PageResponse(NetworkingSchema):
    limit: int = Field(ge=1, le=200)
    has_more: bool
    next_cursor: str | None


class OrganizationCreateRequest(NetworkingSchema):
    name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("website", "industry", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("website must use HTTP(S)")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized = [_safe_text(item, required=True) for item in value]
        if len(normalized) != len({item.casefold() for item in normalized}):
            raise ValueError("tags must not contain duplicates")
        return normalized


class OrganizationUpdateRequest(NetworkingSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @field_validator("website", "industry", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("website must use HTTP(S)")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [_safe_text(item, required=True) for item in value]
        if len(normalized) != len({item.casefold() for item in normalized}):
            raise ValueError("tags must not contain duplicates")
        return normalized

    @model_validator(mode="after")
    def validate_update(self) -> OrganizationUpdateRequest:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "tags" in self.model_fields_set and self.tags is None:
            raise ValueError("tags cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class OrganizationResponse(NetworkingSchema):
    id: UUID
    name: str
    website: str | None
    industry: str | None
    location: str | None
    tags: list[str] = Field(max_length=20)
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class OrganizationPageResponse(NetworkingSchema):
    data: list[OrganizationResponse] = Field(max_length=100)
    page: PageResponse


class ConsentAttestationRequest(NetworkingSchema):
    collection_attested: bool
    storage_attested: bool
    outreach_attested: bool = False
    policy_version: ConsentPolicyVersionValue

    @model_validator(mode="after")
    def validate_required_attestations(self) -> ConsentAttestationRequest:
        if self.collection_attested is not True or self.storage_attested is not True:
            raise ValueError("collection and storage attestations must be explicitly accepted")
        return self


class ContactCreateRequest(NetworkingSchema):
    name: str = Field(min_length=1, max_length=160)
    organization_id: UUID | None = None
    role: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    profile_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    relationship_stage: RelationshipStageValue = "new"
    referral_state: ContactReferralStateValue = "none"
    tags: list[str] = Field(default_factory=list, max_length=20)
    consent: ConsentAttestationRequest

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("role", "email", "phone", "profile_url", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None:
            if value.count("@") != 1 or " " in value:
                raise ValueError("email is invalid")
            local, domain = value.rsplit("@", 1)
            if not local or "." not in domain.strip("."):
                raise ValueError("email is invalid")
        return value

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("profileUrl must use HTTP(S)")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized = [_safe_text(item, required=True) for item in value]
        if len(normalized) != len({item.casefold() for item in normalized}):
            raise ValueError("tags must not contain duplicates")
        return normalized


class ContactUpdateRequest(NetworkingSchema):
    organization_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    profile_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    relationship_stage: RelationshipStageValue | None = None
    referral_state: ContactReferralStateValue | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    next_contact_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @field_validator("role", "email", "phone", "profile_url", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None:
            if value.count("@") != 1 or " " in value:
                raise ValueError("email is invalid")
            local, domain = value.rsplit("@", 1)
            if not local or "." not in domain.strip("."):
                raise ValueError("email is invalid")
        return value

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("profileUrl must use HTTP(S)")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [_safe_text(item, required=True) for item in value]
        if len(normalized) != len({item.casefold() for item in normalized}):
            raise ValueError("tags must not contain duplicates")
        return normalized

    @field_validator("next_contact_at")
    @classmethod
    def validate_next_contact_at(cls, value: datetime | None) -> datetime | None:
        return _aware(value, "nextContactAt")

    @model_validator(mode="after")
    def validate_update(self) -> ContactUpdateRequest:
        for field_name in ("name", "relationship_stage", "referral_state", "tags"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ConsentStateResponse(NetworkingSchema):
    collection: bool
    storage: bool
    outreach: bool
    allows_outreach: bool


class ContactResponse(NetworkingSchema):
    id: UUID
    organization_id: UUID | None
    name: str
    role: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    location: str | None
    relationship_stage: RelationshipStageValue
    referral_state: ContactReferralStateValue
    tags: list[str] = Field(max_length=20)
    last_contact_at: datetime | None
    next_contact_at: datetime | None
    consent: ConsentStateResponse
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ContactPageResponse(NetworkingSchema):
    data: list[ContactResponse] = Field(max_length=100)
    page: PageResponse


class ConsentChangeRequest(NetworkingSchema):
    purpose: ConsentPurposeValue
    policy_version: ConsentPolicyVersionValue


class ConsentEventResponse(NetworkingSchema):
    id: UUID
    contact_id: UUID
    purpose: ConsentPurposeValue
    action: ConsentActionValue
    policy_version: ConsentLedgerPolicyVersionValue
    sequence: PositiveVersion
    occurred_at: datetime


class ConsentHistoryResponse(NetworkingSchema):
    current: ConsentStateResponse
    events: list[ConsentEventResponse] = Field(max_length=200)
    page: PageResponse


class ContactNoteCreateRequest(NetworkingSchema):
    body: str = Field(min_length=1, max_length=4_000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ContactNoteResponse(NetworkingSchema):
    id: UUID
    contact_id: UUID
    body: str
    created_at: datetime


class ContactNoteListResponse(NetworkingSchema):
    data: list[ContactNoteResponse] = Field(max_length=200)
    page: PageResponse


class InteractionCreateRequest(NetworkingSchema):
    kind: InteractionKindValue
    direction: InteractionDirectionValue
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=4_000)
    template_id: UUID | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurredAt must include a UTC offset")
        return value

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        return _safe_text(value, required=True)


class InteractionResponse(NetworkingSchema):
    id: UUID
    contact_id: UUID
    template_id: UUID | None
    kind: InteractionKindValue
    direction: InteractionDirectionValue
    occurred_at: datetime
    summary: str
    delivery_state: Literal["recorded_only"]
    created_at: datetime


class InteractionListResponse(NetworkingSchema):
    data: list[InteractionResponse] = Field(max_length=200)
    page: PageResponse


class ReferralCreateRequest(NetworkingSchema):
    application_id: UUID
    status: ReferralStatusValue = "planned"
    context: str | None = Field(default=None, max_length=2_000)

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ReferralUpdateRequest(NetworkingSchema):
    status: ReferralStatusValue | None = None
    context: str | None = Field(default=None, max_length=2_000)

    @field_validator("context")
    @classmethod
    def validate_context(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_update(self) -> ReferralUpdateRequest:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ReferralResponse(NetworkingSchema):
    id: UUID
    contact_id: UUID
    application_id: UUID
    status: ReferralStatusValue
    context: str | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ReferralListResponse(NetworkingSchema):
    data: list[ReferralResponse] = Field(max_length=200)
    page: PageResponse


class TemplateCreateRequest(NetworkingSchema):
    kind: TemplateKindValue
    name: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4_000)
    user_reviewed: Literal[True]

    @field_validator("name", "body")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class TemplateUpdateRequest(NetworkingSchema):
    kind: TemplateKindValue | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, min_length=1, max_length=4_000)
    user_reviewed: Literal[True]

    @field_validator("name", "body")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_update(self) -> TemplateUpdateRequest:
        for field_name in ("kind", "name", "body"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        if not (self.model_fields_set - {"user_reviewed"}):
            raise ValueError("at least one template field is required")
        return self


class TemplateResponse(NetworkingSchema):
    id: UUID
    kind: TemplateKindValue
    name: str
    body: str
    reviewed_at: datetime
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(NetworkingSchema):
    data: list[TemplateResponse] = Field(max_length=200)
    page: PageResponse


class ReminderCreateRequest(NetworkingSchema):
    title: str = Field(min_length=1, max_length=240)
    due_at: datetime
    recurrence_days: int | None = Field(default=None, strict=True, ge=1, le=365)
    max_attempts: int = Field(default=5, strict=True, ge=1, le=20)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dueAt must include a UTC offset")
        return value


class ReminderUpdateRequest(NetworkingSchema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    due_at: datetime | None = None
    recurrence_days: int | None = Field(default=None, strict=True, ge=1, le=365)
    status: ReminderStatusValue | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        return _aware(value, "dueAt")

    @model_validator(mode="after")
    def validate_update(self) -> ReminderUpdateRequest:
        for field_name in ("title", "due_at", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ReminderResponse(NetworkingSchema):
    id: UUID
    contact_id: UUID
    title: str
    due_at: datetime
    recurrence_days: int | None
    max_attempts: int = Field(ge=1, le=20)
    status: ReminderStatusValue
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ReminderExecutionResponse(NetworkingSchema):
    occurrence_id: UUID
    occurrence_number: PositiveVersion
    scheduled_for: datetime
    occurrence_status: ReminderOccurrenceStatusValue
    attempt_count: int = Field(strict=True, ge=0, le=20)
    max_attempts: int = Field(strict=True, ge=1, le=20)
    queue_status: ReminderQueueStatusValue
    last_error_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9_:-]+$",
    )


class ReminderExecutionItemResponse(NetworkingSchema):
    reminder_id: UUID
    execution: ReminderExecutionResponse


class ReminderExecutionBatchResponse(NetworkingSchema):
    data: list[ReminderExecutionItemResponse] = Field(max_length=100)


class DueReminderResponse(NetworkingSchema):
    reminder: ReminderResponse
    execution: ReminderExecutionResponse


class DueReminderListResponse(NetworkingSchema):
    data: list[DueReminderResponse] = Field(max_length=100)
    page: PageResponse


ReminderResolutionActionValue = Literal["acknowledge", "complete", "snooze"]


class ReminderResolutionRequest(NetworkingSchema):
    action: ReminderResolutionActionValue
    snooze_until: datetime | None = None

    @field_validator("snooze_until")
    @classmethod
    def validate_snooze_until(cls, value: datetime | None) -> datetime | None:
        return _aware(value, "snoozeUntil")

    @model_validator(mode="after")
    def validate_resolution(self) -> ReminderResolutionRequest:
        if self.action == "snooze" and self.snooze_until is None:
            raise ValueError("snoozeUntil is required for snooze")
        if self.action != "snooze" and self.snooze_until is not None:
            raise ValueError("snoozeUntil is only valid for snooze")
        return self


class ReminderListResponse(NetworkingSchema):
    data: list[ReminderResponse] = Field(max_length=200)
    page: PageResponse
