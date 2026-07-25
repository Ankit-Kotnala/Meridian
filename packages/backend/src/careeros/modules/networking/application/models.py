"""Transport-neutral commands and views for networking."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from careeros.modules.networking.domain import (
    ConsentPurpose,
    ContactReferralState,
    InteractionDirection,
    InteractionKind,
    NetworkingConsentEvent,
    NetworkingContact,
    NetworkingOrganization,
    NetworkingReminder,
    NetworkingValidationError,
    ReferralStatus,
    RelationshipStage,
    ReminderOccurrenceStatus,
    ReminderOutboxStatus,
    ReminderStatus,
    TemplateKind,
)


@dataclass(frozen=True, slots=True)
class UnsetType:
    """PATCH sentinel that distinguishes omission from clearing."""


UNSET = UnsetType()


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class NetworkingCursor:
    """Opaque, purpose-bound cursor for top-level networking collections."""

    scope: str
    updated_at: datetime
    record_id: UUID

    def __post_init__(self) -> None:
        if not self.scope or len(self.scope) > 128 or not self.scope.isascii():
            raise NetworkingValidationError("cursor is invalid")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise NetworkingValidationError("cursor is invalid")

    @classmethod
    def decode(
        cls,
        value: str | None,
        *,
        expected_scope: str,
    ) -> NetworkingCursor | None:
        if value is None:
            return None
        if (
            len(value) > 512
            or not value.isascii()
            or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
        ):
            raise NetworkingValidationError("cursor is invalid")
        try:
            payload = json.loads(base64.urlsafe_b64decode(value.encode("ascii") + b"==="))
            if not isinstance(payload, dict) or set(payload) != {
                "id",
                "scope",
                "updatedAt",
                "v",
            }:
                raise ValueError
            if payload["v"] != 2 or type(payload["v"]) is not int:
                raise ValueError
            if (
                payload["scope"] != expected_scope
                or not isinstance(payload["id"], str)
                or not isinstance(payload["updatedAt"], str)
            ):
                raise ValueError
            record_id = UUID(payload["id"])
            updated_at = datetime.fromisoformat(payload["updatedAt"])
        except (
            binascii.Error,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            ValueError,
        ) as exc:
            raise NetworkingValidationError("cursor is invalid") from exc
        return cls(scope=expected_scope, updated_at=updated_at, record_id=record_id)

    def encode(self) -> str:
        payload = json.dumps(
            {
                "id": str(self.record_id),
                "scope": self.scope,
                "updatedAt": self.updated_at.isoformat(),
                "v": 2,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class NetworkingKeysetCursor:
    """Opaque cursor for a single purpose-bound child collection."""

    scope: str
    position: datetime | int
    record_id: UUID

    def __post_init__(self) -> None:
        if not self.scope or len(self.scope) > 128 or not self.scope.isascii():
            raise NetworkingValidationError("cursor is invalid")
        if isinstance(self.position, datetime):
            if self.position.tzinfo is None or self.position.utcoffset() is None:
                raise NetworkingValidationError("cursor is invalid")
        elif type(self.position) is not int or self.position < 1:
            raise NetworkingValidationError("cursor is invalid")

    @classmethod
    def decode(
        cls,
        value: str | None,
        *,
        expected_scope: str,
        numeric: bool = False,
    ) -> NetworkingKeysetCursor | None:
        if value is None:
            return None
        if (
            len(value) > 512
            or not value.isascii()
            or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
        ):
            raise NetworkingValidationError("cursor is invalid")
        try:
            payload = json.loads(base64.urlsafe_b64decode(value.encode("ascii") + b"==="))
            if not isinstance(payload, dict) or set(payload) != {
                "id",
                "position",
                "scope",
                "v",
            }:
                raise ValueError
            if payload["v"] != 1 or type(payload["v"]) is not int:
                raise ValueError
            if payload["scope"] != expected_scope or not isinstance(payload["id"], str):
                raise ValueError
            record_id = UUID(payload["id"])
            raw_position = payload["position"]
            if numeric:
                if type(raw_position) is not int or raw_position < 1:
                    raise ValueError
                position: datetime | int = raw_position
            else:
                if not isinstance(raw_position, str):
                    raise ValueError
                position = datetime.fromisoformat(raw_position)
        except (
            binascii.Error,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            ValueError,
        ) as exc:
            raise NetworkingValidationError("cursor is invalid") from exc
        return cls(scope=expected_scope, position=position, record_id=record_id)

    def encode(self) -> str:
        position = (
            self.position.isoformat() if isinstance(self.position, datetime) else self.position
        )
        payload = json.dumps(
            {
                "id": str(self.record_id),
                "position": position,
                "scope": self.scope,
                "v": 1,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    has_more: bool
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class PagedResult[T]:
    data: tuple[T, ...]
    page: Page


def page_result[T](items: list[T], *, limit: int, scope: str) -> PagedResult[T]:
    has_more = len(items) > limit
    visible = tuple(items[:limit])
    next_cursor: str | None = None
    if has_more:
        anchor = visible[-1]
        if isinstance(anchor, (NetworkingContact, NetworkingOrganization)):
            updated_at, record_id = anchor.updated_at, anchor.id
        else:
            raise NetworkingValidationError("paged record type is unsupported")
        next_cursor = NetworkingCursor(
            scope=scope,
            updated_at=updated_at,
            record_id=record_id,
        ).encode()
    return PagedResult(
        data=visible,
        page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor),
    )


def keyset_page_result[T](
    items: list[T],
    *,
    limit: int,
    scope: str,
    position_of: Callable[[T], datetime | int],
    id_of: Callable[[T], UUID],
) -> PagedResult[T]:
    has_more = len(items) > limit
    visible = tuple(items[:limit])
    next_cursor = (
        NetworkingKeysetCursor(
            scope=scope,
            position=position_of(visible[-1]),
            record_id=id_of(visible[-1]),
        ).encode()
        if has_more
        else None
    )
    return PagedResult(
        data=visible,
        page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor),
    )


@dataclass(frozen=True, slots=True)
class OrganizationFilter:
    query: str | None = None
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class ContactFilter:
    query: str | None = None
    organization_id: UUID | None = None
    relationship_stage: RelationshipStage | None = None
    referral_state: ContactReferralState | None = None
    tag: str | None = None
    outreach_consent: bool | None = None


@dataclass(frozen=True, slots=True)
class ContactConsentState:
    collection: bool
    storage: bool
    outreach: bool

    @property
    def allows_outreach(self) -> bool:
        return self.collection and self.storage and self.outreach


@dataclass(frozen=True, slots=True)
class ContactView:
    contact: NetworkingContact
    consent: ContactConsentState


@dataclass(frozen=True, slots=True)
class NetworkingApplicationReference:
    application_id: UUID
    stage: str


@dataclass(frozen=True, slots=True)
class CreateOrganization:
    name: str
    website: str | None = None
    industry: str | None = None
    location: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateOrganization:
    name: str | UnsetType = UNSET
    website: str | None | UnsetType = UNSET
    industry: str | None | UnsetType = UNSET
    location: str | None | UnsetType = UNSET
    tags: tuple[str, ...] | UnsetType = UNSET


@dataclass(frozen=True, slots=True)
class CreateContact:
    name: str
    organization_id: UUID | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_url: str | None = None
    location: str | None = None
    relationship_stage: RelationshipStage = RelationshipStage.NEW
    referral_state: ContactReferralState = ContactReferralState.NONE
    tags: tuple[str, ...] = ()
    collection_attested: bool = False
    storage_attested: bool = False
    outreach_attested: bool = False
    consent_policy_version: str = ""


@dataclass(frozen=True, slots=True)
class UpdateContact:
    organization_id: UUID | None | UnsetType = UNSET
    name: str | UnsetType = UNSET
    role: str | None | UnsetType = UNSET
    email: str | None | UnsetType = UNSET
    phone: str | None | UnsetType = UNSET
    profile_url: str | None | UnsetType = UNSET
    location: str | None | UnsetType = UNSET
    relationship_stage: RelationshipStage | UnsetType = UNSET
    referral_state: ContactReferralState | UnsetType = UNSET
    tags: tuple[str, ...] | UnsetType = UNSET
    next_contact_at: datetime | None | UnsetType = UNSET


@dataclass(frozen=True, slots=True)
class ChangeContactConsent:
    purpose: ConsentPurpose
    policy_version: str


@dataclass(frozen=True, slots=True)
class CreateContactNote:
    body: str


@dataclass(frozen=True, slots=True)
class RecordInteraction:
    kind: InteractionKind
    direction: InteractionDirection
    occurred_at: datetime
    summary: str
    template_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateReferral:
    application_id: UUID
    status: ReferralStatus = ReferralStatus.PLANNED
    context: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateReferral:
    status: ReferralStatus | UnsetType = UNSET
    context: str | None | UnsetType = UNSET


@dataclass(frozen=True, slots=True)
class CreateTemplate:
    kind: TemplateKind
    name: str
    body: str
    user_reviewed: bool = False


@dataclass(frozen=True, slots=True)
class UpdateTemplate:
    kind: TemplateKind | UnsetType = UNSET
    name: str | UnsetType = UNSET
    body: str | UnsetType = UNSET
    user_reviewed: bool = False


@dataclass(frozen=True, slots=True)
class CreateReminder:
    title: str
    due_at: datetime
    recurrence_days: int | None = None
    max_attempts: int = 5


@dataclass(frozen=True, slots=True)
class UpdateReminder:
    title: str | UnsetType = UNSET
    due_at: datetime | UnsetType = UNSET
    recurrence_days: int | None | UnsetType = UNSET
    status: ReminderStatus | UnsetType = UNSET


class ReminderResolutionAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    COMPLETE = "complete"
    SNOOZE = "snooze"


@dataclass(frozen=True, slots=True)
class ResolveReminder:
    action: ReminderResolutionAction
    snooze_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReminderQueueFilter:
    status: ReminderOutboxStatus | None = None


@dataclass(frozen=True, slots=True)
class ReminderExecutionView:
    occurrence_id: UUID
    occurrence_number: int
    scheduled_for: datetime
    occurrence_status: ReminderOccurrenceStatus
    attempt_count: int
    max_attempts: int
    queue_status: ReminderOutboxStatus
    last_error_code: str | None


@dataclass(frozen=True, slots=True)
class DueReminderView:
    reminder: NetworkingReminder
    execution: ReminderExecutionView


@dataclass(frozen=True, slots=True)
class ContactConsentHistory:
    current: ContactConsentState
    events: tuple[NetworkingConsentEvent, ...]
    page: Page
