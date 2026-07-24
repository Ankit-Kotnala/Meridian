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


class ResumeExportStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    FAILED = "failed"
    DELETED = "deleted"


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
    DOWNLOAD_INTENT_CREATED = "download_intent_created"
    EXPORT_DELETED = "export_deleted"


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
class ResumeBullet:
    id: UUID
    text: str
    evidence_ids: tuple[UUID, ...]
    source: str
    evidence_references: tuple[ResumeEvidenceReference, ...] = ()


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
