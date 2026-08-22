"""Domain entities for Phase 8 application tracking and packs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from .errors import ApplicationWorkspaceValidationError

MAX_INT32 = 2_147_483_647
MAX_RESUME_CLAIMS = 12 * 24
MAX_EVIDENCE_LINKS_PER_CLAIM = 20
MAX_RESUME_EVIDENCE_PINS = 200
MAX_APPLICATION_DOCUMENT_BODY_LENGTH = 131_000
DELETED_DOCUMENT_TEXT = "[deleted]"


def _text(value: str, field: str, maximum: int, *, minimum: int = 1) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ApplicationWorkspaceValidationError(
            f"{field} must contain between {minimum} and {maximum} characters"
        )
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise ApplicationWorkspaceValidationError(f"{field} contains unsupported characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return _text(normalized, field, maximum) if normalized else None


def _version(value: int) -> None:
    if not 1 <= value <= MAX_INT32:
        raise ApplicationWorkspaceValidationError("version must be a positive int32")


def _sha256(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if re.fullmatch(r"[a-f0-9]{64}", normalized) is None:
        raise ApplicationWorkspaceValidationError(f"{field} must be a SHA-256 hex digest")
    return normalized


class ApplicationStage(StrEnum):
    SAVED = "saved"
    RESEARCHING = "researching"
    PREPARING = "preparing"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    RECRUITER_SCREEN = "recruiter_screen"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ReferralStatus(StrEnum):
    NONE = "none"
    NEEDED = "needed"
    REQUESTED = "requested"
    REFERRED = "referred"


class OutcomeStatus(StrEnum):
    NONE = "none"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationEventKind(StrEnum):
    CREATED = "created"
    STAGE_CHANGED = "stage_changed"
    DEADLINE_CHANGED = "deadline_changed"
    FOLLOW_UP_CHANGED = "follow_up_changed"
    NOTE_ADDED = "note_added"
    TASK_ADDED = "task_added"
    TASK_COMPLETED = "task_completed"
    PACK_GENERATED = "pack_generated"
    OUTCOME_RECORDED = "outcome_recorded"
    RESUME_VERSION_CHANGED = "resume_version_changed"
    INTERVIEW = "interview"
    CONTACT = "contact"
    CUSTOM = "custom"


class ApplicationDocumentKind(StrEnum):
    TAILORED_RESUME = "tailored_resume"
    COVER_LETTER = "cover_letter"
    PROFESSIONAL_BIO = "professional_bio"
    INTEREST_ANSWER = "interest_answer"
    FIT_ANSWER = "fit_answer"
    RECRUITER_MESSAGE = "recruiter_message"
    HIRING_MANAGER_MESSAGE = "hiring_manager_message"
    REFERRAL_REQUEST = "referral_request"
    LINKEDIN_CONNECTION_NOTE = "linkedin_connection_note"
    FOLLOW_UP_EMAIL = "follow_up_email"
    INTERVIEW_INTRODUCTION = "interview_introduction"
    ACHIEVEMENT_SUMMARY = "achievement_summary"
    ASSISTED_APPLY_HANDOFF = "assisted_apply_handoff"


class ApplicationDocumentStatus(StrEnum):
    GENERATED = "generated"
    BLOCKED = "blocked"
    DELETED = "deleted"


class ApplicationPackStatus(StrEnum):
    GENERATED = "generated"
    BLOCKED = "blocked"


class ConsistencyStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class ApplicationConsistencySeverity(StrEnum):
    WARNING = "warning"
    BLOCKING = "blocking"


class ApplicationAuditAction(StrEnum):
    APPLICATION_CREATED = "application_created"
    APPLICATION_UPDATED = "application_updated"
    APPLICATION_STAGE_CHANGED = "application_stage_changed"
    RESUME_VERSION_CHANGED = "resume_version_changed"
    APPLICATION_DELETED = "application_deleted"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    NOTE_CREATED = "note_created"
    EVENT_RECORDED = "event_recorded"
    PACK_GENERATED = "pack_generated"
    DOCUMENT_DELETED = "document_deleted"


_ACTIVE_STAGE_TRANSITIONS: dict[ApplicationStage, frozenset[ApplicationStage]] = {
    ApplicationStage.SAVED: frozenset(
        {
            ApplicationStage.RESEARCHING,
            ApplicationStage.PREPARING,
            ApplicationStage.READY_TO_APPLY,
            ApplicationStage.APPLIED,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.RESEARCHING: frozenset(
        {
            ApplicationStage.SAVED,
            ApplicationStage.PREPARING,
            ApplicationStage.READY_TO_APPLY,
            ApplicationStage.APPLIED,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.PREPARING: frozenset(
        {
            ApplicationStage.RESEARCHING,
            ApplicationStage.READY_TO_APPLY,
            ApplicationStage.APPLIED,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.READY_TO_APPLY: frozenset(
        {
            ApplicationStage.PREPARING,
            ApplicationStage.APPLIED,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.APPLIED: frozenset(
        {
            ApplicationStage.RECRUITER_SCREEN,
            ApplicationStage.INTERVIEW,
            ApplicationStage.ASSESSMENT,
            ApplicationStage.OFFER,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.RECRUITER_SCREEN: frozenset(
        {
            ApplicationStage.APPLIED,
            ApplicationStage.INTERVIEW,
            ApplicationStage.ASSESSMENT,
            ApplicationStage.OFFER,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.INTERVIEW: frozenset(
        {
            ApplicationStage.RECRUITER_SCREEN,
            ApplicationStage.ASSESSMENT,
            ApplicationStage.OFFER,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.ASSESSMENT: frozenset(
        {
            ApplicationStage.INTERVIEW,
            ApplicationStage.OFFER,
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
    ApplicationStage.OFFER: frozenset(
        {
            ApplicationStage.REJECTED,
            ApplicationStage.WITHDRAWN,
        }
    ),
}
TERMINAL_APPLICATION_STAGES = frozenset({ApplicationStage.REJECTED, ApplicationStage.WITHDRAWN})
REOPEN_APPLICATION_STAGES = frozenset(
    {
        ApplicationStage.SAVED,
        ApplicationStage.RESEARCHING,
        ApplicationStage.PREPARING,
        ApplicationStage.READY_TO_APPLY,
        ApplicationStage.APPLIED,
    }
)


def validate_stage_transition(
    current: ApplicationStage,
    requested: ApplicationStage,
    *,
    reopen_reason: str | None = None,
) -> str | None:
    """Validate an audited workflow move and normalize a required reopen reason."""

    if requested == current:
        return None
    if current in TERMINAL_APPLICATION_STAGES:
        if requested not in REOPEN_APPLICATION_STAGES:
            raise ApplicationWorkspaceValidationError(
                "terminal applications may reopen only to an active preparation stage"
            )
        normalized_reason = _optional_text(reopen_reason, "reopen reason", 500)
        if normalized_reason is None:
            raise ApplicationWorkspaceValidationError(
                "reopening a terminal application requires a reason"
            )
        return normalized_reason
    if requested not in _ACTIVE_STAGE_TRANSITIONS[current]:
        raise ApplicationWorkspaceValidationError(
            f"stage transition from {current.value} to {requested.value} is not allowed"
        )
    return None


@dataclass(frozen=True, slots=True)
class ApplicationContact:
    name: str
    role: str | None = None
    email: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "contact name", 120))
        object.__setattr__(self, "role", _optional_text(self.role, "contact role", 120))
        object.__setattr__(self, "email", _optional_text(self.email, "contact email", 254))
        object.__setattr__(self, "url", _optional_text(self.url, "contact URL", 500))
        if self.email is not None and "@" not in self.email:
            raise ApplicationWorkspaceValidationError("contact email is invalid")
        if self.url is not None and not self.url.startswith(("https://", "http://")):
            raise ApplicationWorkspaceValidationError("contact URL must be HTTP(S)")


@dataclass(frozen=True, slots=True)
class ApplicationRequirementSnapshot:
    id: UUID
    requirement_type: str
    importance: str
    text: str
    source_start: int
    source_end: int

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]{2,31}", self.requirement_type) is None:
            raise ApplicationWorkspaceValidationError("requirement type is invalid")
        if self.importance not in {"mandatory", "preferred", "helpful"}:
            raise ApplicationWorkspaceValidationError("requirement importance is invalid")
        object.__setattr__(self, "text", _text(self.text, "job requirement", 1_000))
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ApplicationWorkspaceValidationError("requirement source span is invalid")


@dataclass(frozen=True, slots=True)
class ApplicationRequirementSupport:
    analysis_id: UUID
    requirement_id: UUID
    evidence_id: UUID


@dataclass(frozen=True, slots=True)
class ApplicationEvidencePin:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement: str
    statement_sha256: str
    strength: str
    has_numeric_claim: bool

    def __post_init__(self) -> None:
        _version(self.revision_number)
        object.__setattr__(self, "statement", _text(self.statement, "evidence statement", 8_000))
        object.__setattr__(
            self,
            "statement_sha256",
            _sha256(self.statement_sha256, "evidence statement hash"),
        )
        if self.statement_sha256 != hashlib.sha256(self.statement.encode("utf-8")).hexdigest():
            raise ApplicationWorkspaceValidationError(
                "evidence statement hash must match the pinned statement"
            )
        if self.strength not in {"supported", "confirmed", "verified"}:
            raise ApplicationWorkspaceValidationError(
                "only generation-eligible evidence may be pinned"
            )


@dataclass(frozen=True, slots=True)
class ApplicationClaimEvidenceLink:
    evidence_id: UUID
    evidence_revision_id: UUID


@dataclass(frozen=True, slots=True)
class ApplicationDocumentClaim:
    id: UUID
    text: str
    evidence_links: tuple[ApplicationClaimEvidenceLink, ...]
    requirement_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _text(self.text, "document claim", 700))
        if not self.evidence_links:
            raise ApplicationWorkspaceValidationError("document claim requires evidence")
        if len(self.evidence_links) > MAX_EVIDENCE_LINKS_PER_CLAIM:
            raise ApplicationWorkspaceValidationError(
                "document claim may cite at most 20 evidence revisions"
            )
        if len({link.evidence_id for link in self.evidence_links}) != len(self.evidence_links):
            raise ApplicationWorkspaceValidationError(
                "document claim evidence links must be unique"
            )
        if len(set(self.requirement_ids)) != len(self.requirement_ids):
            raise ApplicationWorkspaceValidationError(
                "document claim requirement links must be unique"
            )

    @property
    def evidence_ids(self) -> tuple[UUID, ...]:
        return tuple(link.evidence_id for link in self.evidence_links)

    @property
    def evidence_revision_ids(self) -> tuple[UUID, ...]:
        return tuple(link.evidence_revision_id for link in self.evidence_links)


@dataclass(frozen=True, slots=True)
class ApplicationConsistencyFinding:
    code: str
    severity: ApplicationConsistencySeverity
    message: str
    claim_id: UUID | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9_]{3,80}", self.code) is None:
            raise ApplicationWorkspaceValidationError("consistency finding code is invalid")
        object.__setattr__(self, "message", _text(self.message, "consistency finding", 500))


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    id: UUID
    owner_user_id: UUID
    job_id: UUID
    job_version: int
    job_title: str
    company: str | None
    location: str | None
    job_analysis_id: UUID | None
    job_source_sha256: str
    job_requirements: tuple[ApplicationRequirementSnapshot, ...]
    requirement_support: tuple[ApplicationRequirementSupport, ...]
    resume_id: UUID
    resume_version_id: UUID
    resume_version_number: int
    resume_title: str
    resume_evidence_ids: tuple[UUID, ...]
    evidence_pins: tuple[ApplicationEvidencePin, ...]
    resume_claims: tuple[ApplicationDocumentClaim, ...]
    source: str | None
    industry: str | None
    stage: ApplicationStage
    application_deadline: date | None
    follow_up_at: date | None
    contacts: tuple[ApplicationContact, ...]
    referral_status: ReferralStatus
    outcome_status: OutcomeStatus
    rejection_reason: str | None
    offer_summary: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _version(self.job_version)
        _version(self.resume_version_number)
        _version(self.version)
        object.__setattr__(self, "job_title", _text(self.job_title, "job title", 200))
        object.__setattr__(self, "company", _optional_text(self.company, "company", 200))
        object.__setattr__(self, "location", _optional_text(self.location, "location", 200))
        object.__setattr__(
            self,
            "job_source_sha256",
            _sha256(self.job_source_sha256, "job source hash"),
        )
        object.__setattr__(self, "resume_title", _text(self.resume_title, "resume title", 120))
        object.__setattr__(self, "source", _optional_text(self.source, "application source", 120))
        object.__setattr__(self, "industry", _optional_text(self.industry, "industry", 120))
        object.__setattr__(
            self,
            "rejection_reason",
            _optional_text(self.rejection_reason, "rejection reason", 500),
        )
        object.__setattr__(
            self,
            "offer_summary",
            _optional_text(self.offer_summary, "offer summary", 500),
        )
        requirement_ids = {requirement.id for requirement in self.job_requirements}
        if len(requirement_ids) != len(self.job_requirements):
            raise ApplicationWorkspaceValidationError("job requirement snapshots must be unique")
        support_keys = {
            (support.analysis_id, support.requirement_id, support.evidence_id)
            for support in self.requirement_support
        }
        if len(support_keys) != len(self.requirement_support):
            raise ApplicationWorkspaceValidationError(
                "job requirement support links must be unique"
            )
        if any(
            support.requirement_id not in requirement_ids
            or self.job_analysis_id is None
            or support.analysis_id != self.job_analysis_id
            for support in self.requirement_support
        ):
            raise ApplicationWorkspaceValidationError(
                "job requirement support must belong to the pinned analysis"
            )
        pins_by_id = {pin.evidence_id: pin for pin in self.evidence_pins}
        if len(pins_by_id) != len(self.evidence_pins):
            raise ApplicationWorkspaceValidationError("evidence pins must be unique")
        if len(pins_by_id) > MAX_RESUME_EVIDENCE_PINS:
            raise ApplicationWorkspaceValidationError(
                "application resume evidence exceeds the supported limit"
            )
        claim_ids = {claim.id for claim in self.resume_claims}
        if len(claim_ids) != len(self.resume_claims):
            raise ApplicationWorkspaceValidationError("resume claim ids must be globally unique")
        if len(self.resume_claims) > MAX_RESUME_CLAIMS:
            raise ApplicationWorkspaceValidationError(
                "application resume may contain at most 288 claims"
            )
        if len(set(self.resume_evidence_ids)) != len(self.resume_evidence_ids):
            raise ApplicationWorkspaceValidationError("resume evidence IDs must be unique")
        if set(self.resume_evidence_ids) != set(pins_by_id):
            raise ApplicationWorkspaceValidationError(
                "resume evidence IDs must match exact evidence pins"
            )
        for claim in self.resume_claims:
            for link in claim.evidence_links:
                pin = pins_by_id.get(link.evidence_id)
                if pin is None or pin.evidence_revision_id != link.evidence_revision_id:
                    raise ApplicationWorkspaceValidationError(
                        "resume claim evidence revision is not pinned"
                    )
            if not set(claim.requirement_ids).issubset(requirement_ids):
                raise ApplicationWorkspaceValidationError("resume claim requirement is not pinned")
        expected_outcome = {
            ApplicationStage.OFFER: OutcomeStatus.OFFER,
            ApplicationStage.REJECTED: OutcomeStatus.REJECTED,
            ApplicationStage.WITHDRAWN: OutcomeStatus.WITHDRAWN,
        }.get(self.stage, OutcomeStatus.NONE)
        if self.outcome_status != expected_outcome:
            raise ApplicationWorkspaceValidationError(
                "application stage and outcome must describe the same state"
            )
        if self.rejection_reason is not None and self.outcome_status != OutcomeStatus.REJECTED:
            raise ApplicationWorkspaceValidationError(
                "rejection reason requires a rejected outcome"
            )
        if self.offer_summary is not None and self.outcome_status != OutcomeStatus.OFFER:
            raise ApplicationWorkspaceValidationError("offer summary requires an offer outcome")


@dataclass(frozen=True, slots=True)
class ApplicationTask:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    title: str
    due_at: date | None
    completed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _text(self.title, "task title", 200))
        _version(self.version)


@dataclass(frozen=True, slots=True)
class ApplicationNote:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    body: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", _text(self.body, "note", 2_000))


@dataclass(frozen=True, slots=True)
class ApplicationEvent:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    event_kind: ApplicationEventKind
    occurred_at: datetime
    title: str
    description: str | None
    metadata: dict[str, str]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _text(self.title, "event title", 200))
        object.__setattr__(
            self, "description", _optional_text(self.description, "event description", 1_000)
        )
        for key, value in self.metadata.items():
            if re.fullmatch(r"[a-z0-9_]{3,80}", key) is None:
                raise ApplicationWorkspaceValidationError("event metadata key is invalid")
            _text(value, f"event metadata {key}", 200)


@dataclass(frozen=True, slots=True)
class ApplicationPack:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    job_id: UUID
    job_version: int
    resume_version_id: UUID
    resume_version_number: int
    application_version: int
    evidence_revision_ids: tuple[UUID, ...]
    requirement_ids: tuple[UUID, ...]
    status: ApplicationPackStatus
    consistency_status: ConsistencyStatus
    consistency_findings: tuple[ApplicationConsistencyFinding, ...]
    idempotency_key: str
    idempotency_fingerprint: str
    created_at: datetime

    def __post_init__(self) -> None:
        _version(self.job_version)
        _version(self.resume_version_number)
        _version(self.application_version)
        if not self.evidence_revision_ids:
            raise ApplicationWorkspaceValidationError("application pack requires evidence pins")
        object.__setattr__(
            self, "idempotency_key", _text(self.idempotency_key, "idempotency key", 128)
        )
        object.__setattr__(
            self,
            "idempotency_fingerprint",
            _text(self.idempotency_fingerprint, "idempotency fingerprint", 128),
        )


@dataclass(frozen=True, slots=True)
class ApplicationDocument:
    id: UUID
    owner_user_id: UUID
    application_id: UUID
    pack_id: UUID
    kind: ApplicationDocumentKind
    title: str
    body: str
    source_evidence_ids: tuple[UUID, ...]
    source_requirement_ids: tuple[UUID, ...]
    claims: tuple[ApplicationDocumentClaim, ...]
    status: ApplicationDocumentStatus
    consistency_status: ConsistencyStatus
    consistency_findings: tuple[ApplicationConsistencyFinding, ...]
    content_sha256: str
    created_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _text(self.title, "document title", 200))
        object.__setattr__(
            self,
            "body",
            _text(
                self.body,
                "document body",
                MAX_APPLICATION_DOCUMENT_BODY_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "content_sha256",
            _sha256(self.content_sha256, "document content hash"),
        )
        expected_hash = hashlib.sha256(self.body.encode("utf-8")).hexdigest()
        if self.content_sha256 != expected_hash:
            raise ApplicationWorkspaceValidationError(
                "document content hash must match the document body"
            )
        if self.status == ApplicationDocumentStatus.DELETED:
            if (
                self.title != DELETED_DOCUMENT_TEXT
                or self.body != DELETED_DOCUMENT_TEXT
                or self.source_evidence_ids
                or self.source_requirement_ids
                or self.claims
                or self.consistency_status != ConsistencyStatus.PASSED
                or self.consistency_findings
                or self.deleted_at is None
            ):
                raise ApplicationWorkspaceValidationError(
                    "deleted documents must contain only the canonical tombstone"
                )
        elif self.deleted_at is not None:
            raise ApplicationWorkspaceValidationError(
                "only deleted documents may have a deletion time"
            )


@dataclass(frozen=True, slots=True)
class ApplicationIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_fingerprint: str
    target_kind: str
    target_id: UUID | None
    response_kind: str
    response_id: UUID | None
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "idempotency_key", _text(self.idempotency_key, "idempotency key", 128)
        )
        object.__setattr__(
            self,
            "request_fingerprint",
            _text(self.request_fingerprint, "request fingerprint", 128),
        )
        object.__setattr__(self, "target_kind", _text(self.target_kind, "target kind", 80))
        object.__setattr__(self, "response_kind", _text(self.response_kind, "response kind", 80))


@dataclass(frozen=True, slots=True)
class ApplicationProfileLink:
    label: str
    url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _text(self.label, "profile link label", 120))
        object.__setattr__(self, "url", _text(self.url, "profile link URL", 500))
        if not self.url.startswith(("https://", "http://")):
            raise ApplicationWorkspaceValidationError("profile link URL must be HTTP(S)")


@dataclass(frozen=True, slots=True)
class ApplicationProfile:
    id: UUID
    owner_user_id: UUID
    work_authorization: str | None
    notice_period_days: int | None
    compensation_min: int | None
    compensation_max: int | None
    compensation_currency: str
    preferred_locations: tuple[str, ...]
    profile_links: tuple[ApplicationProfileLink, ...]
    voluntary_disclosures: dict[str, str]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _version(self.version)
        object.__setattr__(
            self,
            "work_authorization",
            _optional_text(self.work_authorization, "work authorization", 500),
        )
        if self.notice_period_days is not None and not 0 <= self.notice_period_days <= 730:
            raise ApplicationWorkspaceValidationError("notice period is out of range")
        for field_name, value in (
            ("compensation_min", self.compensation_min),
            ("compensation_max", self.compensation_max),
        ):
            if value is not None and value < 0:
                raise ApplicationWorkspaceValidationError(f"{field_name} must be non-negative")
        if (
            self.compensation_min is not None
            and self.compensation_max is not None
            and self.compensation_min > self.compensation_max
        ):
            raise ApplicationWorkspaceValidationError(
                "compensation minimum cannot exceed compensation maximum"
            )
        currency = self.compensation_currency.strip().upper()
        if re.fullmatch(r"[A-Z]{3}", currency) is None:
            raise ApplicationWorkspaceValidationError("compensation currency must be ISO 4217")
        object.__setattr__(self, "compensation_currency", currency)
        normalized_locations: list[str] = []
        for location in self.preferred_locations:
            normalized = _text(location, "preferred location", 200)
            if normalized not in normalized_locations:
                normalized_locations.append(normalized)
        object.__setattr__(self, "preferred_locations", tuple(normalized_locations))
        if len(self.preferred_locations) > 50:
            raise ApplicationWorkspaceValidationError("preferred locations exceed the supported limit")
        if len(self.profile_links) > 30:
            raise ApplicationWorkspaceValidationError("profile links exceed the supported limit")
        normalized_disclosures: dict[str, str] = {}
        for key, value in self.voluntary_disclosures.items():
            if re.fullmatch(r"[a-z0-9_]{3,80}", key) is None:
                raise ApplicationWorkspaceValidationError("voluntary disclosure key is invalid")
            normalized_disclosures[key] = _text(value, f"voluntary disclosure {key}", 500)
        object.__setattr__(self, "voluntary_disclosures", normalized_disclosures)


@dataclass(frozen=True, slots=True)
class ApplicationAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID
    action: ApplicationAuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", _text(self.target_kind, "audit target", 80))
        object.__setattr__(self, "request_id", _text(self.request_id, "request ID", 128))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "trace ID", 128))
