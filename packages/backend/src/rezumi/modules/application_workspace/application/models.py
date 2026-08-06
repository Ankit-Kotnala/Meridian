"""Transport-neutral commands and purpose-minimized views for application workspace."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from rezumi.modules.application_workspace.domain import (
    ApplicationContact,
    ApplicationDocument,
    ApplicationDocumentClaim,
    ApplicationEvent,
    ApplicationEventKind,
    ApplicationEvidencePin,
    ApplicationPack,
    ApplicationRecord,
    ApplicationRequirementSnapshot,
    ApplicationRequirementSupport,
    ApplicationStage,
    ApplicationWorkspaceValidationError,
    OutcomeStatus,
    ReferralStatus,
)


@dataclass(frozen=True, slots=True)
class UnsetType:
    """Sentinel used by PATCH commands to distinguish omission from clearing."""


UNSET = UnsetType()


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class PageCursor:
    offset: int

    def __post_init__(self) -> None:
        if type(self.offset) is not int or not 0 <= self.offset <= 10_000:
            raise ApplicationWorkspaceValidationError("cursor is invalid")

    @classmethod
    def decode(cls, value: str | None) -> PageCursor | None:
        if value is None:
            return None
        if len(value) > 256:
            raise ApplicationWorkspaceValidationError("cursor is invalid")
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii") + b"===")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {"offset"}:
                raise ValueError
            offset = payload["offset"]
        except (
            binascii.Error,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ApplicationWorkspaceValidationError("cursor is invalid") from exc
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ApplicationWorkspaceValidationError("cursor is invalid")
        return cls(offset=offset)

    def encode(self) -> str:
        payload = json.dumps({"offset": self.offset}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class ApplicationEventCursor:
    application_id: UUID
    occurred_at: datetime
    event_id: UUID

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ApplicationWorkspaceValidationError("cursor is invalid")

    @classmethod
    def decode(
        cls,
        value: str | None,
        *,
        application_id: UUID,
    ) -> ApplicationEventCursor | None:
        if value is None:
            return None
        if len(value) > 512:
            raise ApplicationWorkspaceValidationError("cursor is invalid")
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii") + b"===")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {
                "applicationId",
                "eventId",
                "occurredAt",
                "v",
            }:
                raise ValueError
            if type(payload["v"]) is not int or payload["v"] != 1:
                raise ValueError
            if not all(
                isinstance(payload[key], str) for key in ("applicationId", "eventId", "occurredAt")
            ):
                raise ValueError
            decoded_application_id = UUID(payload["applicationId"])
            occurred_at = datetime.fromisoformat(payload["occurredAt"])
            event_id = UUID(payload["eventId"])
        except (
            binascii.Error,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ApplicationWorkspaceValidationError("cursor is invalid") from exc
        if decoded_application_id != application_id:
            raise ApplicationWorkspaceValidationError("cursor is invalid")
        return cls(
            application_id=decoded_application_id,
            occurred_at=occurred_at,
            event_id=event_id,
        )

    def encode(self) -> str:
        payload = json.dumps(
            {
                "applicationId": str(self.application_id),
                "eventId": str(self.event_id),
                "occurredAt": self.occurred_at.isoformat(),
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


def page_result[T](items: list[T], *, cursor: PageCursor | None, limit: int) -> PagedResult[T]:
    has_more = len(items) > limit
    visible = tuple(items[:limit])
    offset = cursor.offset if cursor is not None else 0
    next_cursor = PageCursor(offset=offset + limit).encode() if has_more else None
    return PagedResult(
        data=visible,
        page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor),
    )


def event_page_result(
    items: list[ApplicationEvent],
    *,
    application_id: UUID,
    limit: int,
) -> PagedResult[ApplicationEvent]:
    has_more = len(items) > limit
    visible = tuple(items[:limit])
    next_cursor = None
    if has_more:
        anchor = visible[-1]
        next_cursor = ApplicationEventCursor(
            application_id=application_id,
            occurred_at=anchor.occurred_at,
            event_id=anchor.id,
        ).encode()
    return PagedResult(
        data=visible,
        page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor),
    )


@dataclass(frozen=True, slots=True)
class ApplicationFilter:
    query: str | None = None
    stage: ApplicationStage | None = None
    outcome: OutcomeStatus | None = None
    source: str | None = None
    industry: str | None = None
    sort: str = "updated_desc"


@dataclass(frozen=True, slots=True)
class ApplicationJobSnapshot:
    job_id: UUID
    version: int
    title: str
    company: str | None
    location: str | None
    application_deadline: date | None
    latest_analysis_id: UUID | None
    source_sha256: str
    source: str | None
    industry: str | None
    requirements: tuple[ApplicationRequirementSnapshot, ...]
    requirement_support: tuple[ApplicationRequirementSupport, ...]


@dataclass(frozen=True, slots=True)
class ApplicationSourceEvidenceReference:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    claim_sha256: str
    link_basis: str
    source_skill_id: UUID | None


@dataclass(frozen=True, slots=True)
class ApplicationSourceClaim:
    id: UUID
    text: str
    evidence_references: tuple[ApplicationSourceEvidenceReference, ...]

    @property
    def evidence_ids(self) -> tuple[UUID, ...]:
        return tuple(reference.evidence_id for reference in self.evidence_references)


@dataclass(frozen=True, slots=True)
class ApplicationResumeSnapshot:
    resume_id: UUID
    version_id: UUID
    version_number: int
    title: str
    target_role: str | None
    evidence_references: tuple[ApplicationSourceEvidenceReference, ...]
    claims: tuple[ApplicationSourceClaim, ...]
    plain_text: str

    @property
    def evidence_ids(self) -> tuple[UUID, ...]:
        return tuple(dict.fromkeys(reference.evidence_id for reference in self.evidence_references))


@dataclass(frozen=True, slots=True)
class CreateApplication:
    job_id: UUID
    resume_version_id: UUID
    stage: ApplicationStage = ApplicationStage.SAVED
    application_deadline: date | None = None
    follow_up_at: date | None = None
    contacts: tuple[ApplicationContact, ...] = ()
    referral_status: ReferralStatus = ReferralStatus.NONE
    source: str | None = None
    industry: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateApplication:
    stage: ApplicationStage | UnsetType = UNSET
    resume_version_id: UUID | UnsetType = UNSET
    application_deadline: date | None | UnsetType = UNSET
    follow_up_at: date | None | UnsetType = UNSET
    contacts: tuple[ApplicationContact, ...] | UnsetType = UNSET
    referral_status: ReferralStatus | UnsetType = UNSET
    outcome_status: OutcomeStatus | UnsetType = UNSET
    rejection_reason: str | None | UnsetType = UNSET
    offer_summary: str | None | UnsetType = UNSET
    source: str | None | UnsetType = UNSET
    industry: str | None | UnsetType = UNSET
    reopen_reason: str | None = None
    resume_change_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CreateApplicationTask:
    title: str
    due_at: date | None = None


@dataclass(frozen=True, slots=True)
class UpdateApplicationTask:
    title: str | UnsetType = UNSET
    due_at: date | None | UnsetType = UNSET
    completed: bool | UnsetType = UNSET


@dataclass(frozen=True, slots=True)
class CreateApplicationNote:
    body: str


@dataclass(frozen=True, slots=True)
class CreateApplicationEvent:
    event_kind: ApplicationEventKind
    occurred_at: datetime | None
    title: str
    description: str | None = None
    metadata: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class GenerateApplicationPack:
    include_kinds: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationPackView:
    pack: ApplicationPack
    documents: tuple[ApplicationDocument, ...]


@dataclass(frozen=True, slots=True)
class ApplicationSummary:
    application: ApplicationRecord
    task_count: int
    open_task_count: int
    note_count: int
    event_count: int
    pack_count: int


# Backward-compatible name while callers move to the lightweight summary shape.
ApplicationView = ApplicationSummary


@dataclass(frozen=True, slots=True)
class ApplicationCalendarEntry:
    id: UUID
    application_id: UUID
    kind: str
    title: str
    on_date: date
    completed: bool


@dataclass(frozen=True, slots=True)
class ApplicationReference:
    """Content-free application identity exposed to other product modules."""

    application_id: UUID
    stage: ApplicationStage


@dataclass(frozen=True, slots=True)
class ApplicationInterviewContext:
    """Evidence-backed facts exposed to Phase 9 without notes, contacts, or offers."""

    application_id: UUID
    stage: ApplicationStage
    job_id: UUID
    job_version: int
    job_title: str
    company: str | None
    requirements: tuple[ApplicationRequirementSnapshot, ...]
    resume_version_id: UUID
    resume_version_number: int
    claims: tuple[ApplicationDocumentClaim, ...]
    evidence_pins: tuple[ApplicationEvidencePin, ...]


@dataclass(frozen=True, slots=True)
class ApplicationInterviewEvidenceReference:
    """Content-minimized evidence identity used for live generation eligibility checks."""

    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    strength: str
    has_numeric_claim: bool

    def __post_init__(self) -> None:
        if type(self.revision_number) is not int or not 1 <= self.revision_number <= 2_147_483_647:
            raise ApplicationWorkspaceValidationError(
                "interview evidence revision number is invalid"
            )
        digest = self.statement_sha256.strip().lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ApplicationWorkspaceValidationError(
                "interview evidence statement hash is invalid"
            )
        object.__setattr__(self, "statement_sha256", digest)
        if self.strength not in {"supported", "confirmed", "verified"}:
            raise ApplicationWorkspaceValidationError(
                "interview evidence strength is not generation eligible"
            )
        if type(self.has_numeric_claim) is not bool:
            raise ApplicationWorkspaceValidationError(
                "interview evidence numeric-claim marker is invalid"
            )


@dataclass(frozen=True, slots=True)
class ApplicationMilestones:
    """Content-free milestone timestamps derived from immutable audit events."""

    first_applied_at: datetime | None = None
    first_response_at: datetime | None = None
    first_interview_at: datetime | None = None
    first_offer_at: datetime | None = None
    outcome_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsSnapshot:
    """Content-minimized workflow facts exposed to aggregate analytics."""

    application_id: UUID
    stage: ApplicationStage
    outcome_status: OutcomeStatus
    role_title: str
    source: str | None
    industry: str | None
    job_id: UUID
    job_version: int
    job_analysis_id: UUID | None
    resume_version_id: UUID
    resume_version_number: int
    requirement_coverage_basis_points: int | None
    application_deadline: date | None
    first_applied_at: datetime | None
    first_response_at: datetime | None
    first_interview_at: datetime | None
    first_offer_at: datetime | None
    outcome_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsCursor:
    """Internal keyset cursor for complete, bounded analytics source reads."""

    created_at: datetime
    application_id: UUID

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ApplicationWorkspaceValidationError("analytics cursor is invalid")


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsPage:
    """One purpose-minimized source page; callers must follow ``next_cursor``."""

    data: tuple[ApplicationAnalyticsSnapshot, ...]
    next_cursor: ApplicationAnalyticsCursor | None


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsSourceState:
    """Content-free source facts used to detect concurrent aggregation changes."""

    application_count: int
    application_version_sum: int
    event_count: int
    max_application_updated_at: datetime | None
    max_event_created_at: datetime | None

    def __post_init__(self) -> None:
        if min(self.application_count, self.application_version_sum, self.event_count) < 0:
            raise ApplicationWorkspaceValidationError("analytics source state is invalid")
        for value in (self.max_application_updated_at, self.max_event_created_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ApplicationWorkspaceValidationError("analytics source state is invalid")

    def watermark(self) -> ApplicationAnalyticsWatermark:
        payload = {
            "applicationCount": self.application_count,
            "applicationVersionSum": self.application_version_sum,
            "eventCount": self.event_count,
            "maxApplicationUpdatedAt": (
                self.max_application_updated_at.isoformat()
                if self.max_application_updated_at is not None
                else None
            ),
            "maxEventCreatedAt": (
                self.max_event_created_at.isoformat()
                if self.max_event_created_at is not None
                else None
            ),
            "v": 1,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return ApplicationAnalyticsWatermark(
            token=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            application_count=self.application_count,
            event_count=self.event_count,
            max_updated_at=max(
                (
                    value
                    for value in (
                        self.max_application_updated_at,
                        self.max_event_created_at,
                    )
                    if value is not None
                ),
                default=None,
            ),
        )


@dataclass(frozen=True, slots=True)
class ApplicationAnalyticsWatermark:
    """Stable content-free token persisted with a Phase 9 analytics snapshot."""

    token: str
    application_count: int
    event_count: int
    max_updated_at: datetime | None

    def __post_init__(self) -> None:
        if (
            len(self.token) != 71
            or not self.token.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in self.token[7:])
            or min(self.application_count, self.event_count) < 0
        ):
            raise ApplicationWorkspaceValidationError("analytics watermark is invalid")
        if self.max_updated_at is not None and (
            self.max_updated_at.tzinfo is None or self.max_updated_at.utcoffset() is None
        ):
            raise ApplicationWorkspaceValidationError("analytics watermark is invalid")
