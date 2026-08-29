"""Domain entities for verified resume building and export."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ResumeTemplate(StrEnum):
    STANDARD_PROFESSIONAL = "standard_professional"
    COMPACT_TECHNICAL = "compact_technical"
    EXECUTIVE = "executive"
    GRADUATE = "graduate"
    CONSULTING_FINANCE = "consulting_finance"


class ResumeFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"
    JSON = "json"


class ResumePageSize(StrEnum):
    LETTER = "letter"
    A4 = "a4"


class ResumeFontFamily(StrEnum):
    SANS = "sans"
    SERIF = "serif"


class ResumeLineSpacing(StrEnum):
    COMPACT = "compact"
    STANDARD = "standard"
    RELAXED = "relaxed"


class ResumeMarginSize(StrEnum):
    NARROW = "narrow"
    STANDARD = "standard"
    WIDE = "wide"


class ResumeExportStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    RETRY_WAIT = "retry_wait"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    DELETION_PENDING = "deletion_pending"
    DELETING = "deleting"
    DELETION_RETRY_WAIT = "deletion_retry_wait"
    DELETION_DEAD_LETTERED = "deletion_dead_lettered"
    DELETED = "deleted"


class ResumeExportOperation(StrEnum):
    RENDER = "render"
    DELETE = "delete"


class ResumeVerificationStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class ResumeAuditAction(StrEnum):
    RESUME_CREATED = "resume_created"
    RESUME_UPDATED = "resume_updated"
    VERSION_CREATED = "version_created"
    VERSION_RESTORED = "version_restored"
    EXPORT_REQUESTED = "export_requested"
    EXPORT_VERIFIED = "export_verified"
    EXPORT_BLOCKED = "export_blocked"
    EXPORT_RETRY_SCHEDULED = "export_retry_scheduled"
    EXPORT_DEAD_LETTERED = "export_dead_lettered"
    EXPORT_DISPATCHED = "export_dispatched"
    EXPORT_DISPATCH_RETRY_SCHEDULED = "export_dispatch_retry_scheduled"
    EXPORT_DISPATCH_DEAD_LETTERED = "export_dispatch_dead_lettered"
    EXPORT_RECOVERY_SCHEDULED = "export_recovery_scheduled"
    EXPORT_DELETION_REQUESTED = "export_deletion_requested"
    EXPORT_DELETION_RETRY_SCHEDULED = "export_deletion_retry_scheduled"
    EXPORT_DELETION_DEAD_LETTERED = "export_deletion_dead_lettered"
    EXPORT_DELETION_RECOVERY_SCHEDULED = "export_deletion_recovery_scheduled"
    DOWNLOAD_INTENT_CREATED = "download_intent_created"
    EXPORT_DELETED = "export_deleted"
    EXPORT_ORPHAN_CLEANUP_COMPLETED = "export_orphan_cleanup_completed"
    EXPORT_ORPHAN_CLEANUP_RETRY_SCHEDULED = "export_orphan_cleanup_retry_scheduled"
    EXPORT_ORPHAN_CLEANUP_DEAD_LETTERED = "export_orphan_cleanup_dead_lettered"


class ResumeEvidenceLinkBasis(StrEnum):
    EVIDENCE_STATEMENT = "evidence_statement"
    EVIDENCE_SKILL = "evidence_skill"
    CHANGE_STUDIO_CLAIM = "change_studio_claim"


@dataclass(frozen=True, slots=True)
class ResumeEvidenceReference:
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: int
    statement_sha256: str
    claim_sha256: str
    link_basis: ResumeEvidenceLinkBasis
    source_skill_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.revision_number < 1:
            raise ValueError("evidence revision number must be positive")
        if re.fullmatch(r"[0-9a-f]{64}", self.statement_sha256) is None:
            raise ValueError("evidence statement hash must be lowercase SHA-256")
        if re.fullmatch(r"[0-9a-f]{64}", self.claim_sha256) is None:
            raise ValueError("resume claim hash must be lowercase SHA-256")
        if not isinstance(self.link_basis, ResumeEvidenceLinkBasis):
            raise ValueError("evidence link basis is invalid")
        if self.link_basis is ResumeEvidenceLinkBasis.EVIDENCE_STATEMENT:
            if self.source_skill_id is not None:
                raise ValueError("statement links cannot cite a source skill")
        elif self.link_basis is ResumeEvidenceLinkBasis.EVIDENCE_SKILL:
            if self.source_skill_id is None:
                raise ValueError("skill links require the exact source skill")
        elif self.source_skill_id is not None:
            raise ValueError("change studio links cannot cite a source skill")


@dataclass(frozen=True, slots=True)
class ResumeLayout:
    page_size: ResumePageSize = ResumePageSize.LETTER
    page_limit: int = 1
    font_family: ResumeFontFamily = ResumeFontFamily.SANS
    font_size_pt: int = 10
    line_spacing: ResumeLineSpacing = ResumeLineSpacing.STANDARD
    margins: ResumeMarginSize = ResumeMarginSize.STANDARD

    def __post_init__(self) -> None:
        if self.page_limit not in {1, 2}:
            raise ValueError("resume page limit must be one or two")
        if not 9 <= self.font_size_pt <= 12:
            raise ValueError("resume font size must be between 9 and 12 points")
        if not isinstance(self.page_size, ResumePageSize):
            raise ValueError("resume page size is invalid")
        if not isinstance(self.font_family, ResumeFontFamily):
            raise ValueError("resume font family is invalid")
        if not isinstance(self.line_spacing, ResumeLineSpacing):
            raise ValueError("resume line spacing is invalid")
        if not isinstance(self.margins, ResumeMarginSize):
            raise ValueError("resume margins are invalid")


@dataclass(frozen=True, slots=True)
class ResumePersonalFact:
    id: UUID
    kind: str
    value: str
    label: str | None
    is_primary: bool


@dataclass(frozen=True, slots=True)
class ResumePartialDate:
    year: int
    month: int | None = None

    def __post_init__(self) -> None:
        if not 1900 <= self.year <= 2200:
            raise ValueError("resume partial-date year is invalid")
        if self.month is not None and not 1 <= self.month <= 12:
            raise ValueError("resume partial-date month is invalid")


@dataclass(frozen=True, slots=True)
class ResumeEntityFact:
    id: UUID
    kind: str
    title: str
    organization: str | None
    official_title: str | None
    display_title: str | None
    location: str | None
    start_date: ResumePartialDate | None
    end_date: ResumePartialDate | None
    is_current: bool
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ResumeBullet:
    id: UUID
    text: str
    evidence_ids: tuple[UUID, ...]
    source: str
    evidence_references: tuple[ResumeEvidenceReference, ...] = ()
    entity_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ResumeSection:
    id: UUID
    title: str
    kind: str
    items: tuple[ResumeBullet, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumeDocument:
    id: UUID
    owner_user_id: UUID
    title: str
    target_role: str | None
    template: ResumeTemplate
    current_version_id: UUID | None
    source_change_set_id: UUID | None
    source_change_set_version_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
    layout: ResumeLayout = field(default_factory=ResumeLayout)


@dataclass(frozen=True, slots=True)
class ResumeVersion:
    id: UUID
    owner_user_id: UUID
    resume_id: UUID
    version_number: int
    parent_version_id: UUID | None
    title: str
    target_role: str | None
    template: ResumeTemplate
    sections: tuple[ResumeSection, ...]
    plain_text: str
    source_evidence_ids: tuple[UUID, ...]
    source_change_set_id: UUID | None
    source_change_set_version_id: UUID | None
    created_at: datetime
    personal_facts: tuple[ResumePersonalFact, ...] = ()
    entities: tuple[ResumeEntityFact, ...] = ()
    layout: ResumeLayout = field(default_factory=ResumeLayout)


@dataclass(frozen=True, slots=True)
class ResumeVerificationReport:
    id: UUID
    owner_user_id: UUID
    export_id: UUID
    version_id: UUID
    status: ResumeVerificationStatus
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    detected_lines: tuple[str, ...]
    missing_lines: tuple[str, ...]
    duplicate_lines: tuple[str, ...]
    reading_order: tuple[str, ...]
    grounding_codes: tuple[str, ...]
    file_sha256: str
    parser_version: str
    created_at: datetime
    occurrence_mismatches: tuple[str, ...] = ()
    reading_order_failures: tuple[str, ...] = ()
    manifest_sha256: str = ""
    version_content_sha256: str = ""
    page_count: int = 0


@dataclass(frozen=True, slots=True)
class ResumeExport:
    id: UUID
    owner_user_id: UUID
    resume_id: UUID
    version_id: UUID
    format: ResumeFormat
    status: ResumeExportStatus
    object_key: str | None
    media_type: str
    size_bytes: int
    sha256_digest: str | None
    verification_status: ResumeVerificationStatus | None
    verification_codes: tuple[str, ...]
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    renderer_version: str
    parser_version: str | None
    idempotency_key: str
    idempotency_fingerprint: str
    attempts: int
    requested_at: datetime
    completed_at: datetime | None
    deleted_at: datetime | None
    last_error: str | None
    version_content_sha256: str = ""
    fidelity_manifest: dict[str, object] = field(default_factory=dict)
    fidelity_manifest_sha256: str = ""
    trace_id: str = ""
    max_attempts: int = 3
    fence: int = 0
    execution_token_hash: str | None = None
    lease_expires_at: datetime | None = None
    retry_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    cleanup_attempts: int = 0
    cleanup_max_attempts: int = 3


@dataclass(frozen=True, slots=True)
class ResumeExportOutboxMessage:
    id: UUID
    owner_user_id: UUID
    export_id: UUID
    operation: ResumeExportOperation
    trace_id: str
    available_at: datetime
    attempts: int
    max_attempts: int
    lease_token: UUID | None
    leased_at: datetime | None
    lease_expires_at: datetime | None
    published_at: datetime | None
    dead_lettered_at: datetime | None
    last_error: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResumeExportObjectCleanup:
    """Durable deletion intent for one attempt-scoped export object."""

    id: UUID
    owner_user_id: UUID
    export_id: UUID
    attempt_fence: int
    object_key: str
    trace_id: str
    not_before: datetime
    attempts: int
    max_attempts: int
    last_error: str | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    dead_lettered_at: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.attempt_fence < 1:
            raise ValueError("export object cleanup fence must be positive")
        if not self.object_key or len(self.object_key) > 500:
            raise ValueError("export object cleanup key is invalid")
        if not self.trace_id or len(self.trace_id) > 128:
            raise ValueError("export object cleanup trace is invalid")
        if not 0 <= self.attempts <= self.max_attempts or not 1 <= self.max_attempts <= 10:
            raise ValueError("export object cleanup attempts are invalid")
        terminal = sum(
            value is not None
            for value in (self.completed_at, self.cancelled_at, self.dead_lettered_at)
        )
        if terminal > 1:
            raise ValueError("export object cleanup terminal state is invalid")

    @property
    def terminal(self) -> bool:
        return any(
            value is not None
            for value in (self.completed_at, self.cancelled_at, self.dead_lettered_at)
        )


@dataclass(frozen=True, slots=True)
class ResumeDownloadIntent:
    id: UUID
    owner_user_id: UUID
    export_id: UUID
    object_key: str
    url: str
    expires_at: datetime
    idempotency_key: str
    idempotency_fingerprint: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResumeBuilderIdempotencyRecord:
    id: UUID
    owner_user_id: UUID
    idempotency_key: str
    request_fingerprint: str
    target_kind: str
    target_id: UUID | None
    response_kind: str
    response_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResumeBuilderAuditEvent:
    id: UUID
    owner_user_id: UUID
    actor_user_id: UUID
    action: ResumeAuditAction
    target_kind: str
    target_id: UUID
    request_id: str
    trace_id: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)
