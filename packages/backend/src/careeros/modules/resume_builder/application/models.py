"""Transport-neutral commands and views for the Phase 7 resume builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from careeros.modules.resume_builder.domain import (
    ResumeDocument,
    ResumeEvidenceReference,
    ResumeExport,
    ResumeFormat,
    ResumeSection,
    ResumeTemplate,
    ResumeVerificationReport,
    ResumeVersion,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class CreateResume:
    title: str
    target_role: str | None
    template: ResumeTemplate
    change_set_id: UUID | None = None
    change_set_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateResume:
    title: str | None = None
    target_role: str | None = None
    template: ResumeTemplate | None = None
    sections: tuple[ResumeSection, ...] | None = None


@dataclass(frozen=True, slots=True)
class ExportResume:
    format: ResumeFormat


@dataclass(frozen=True, slots=True)
class ResumeSourceBullet:
    text: str
    evidence_ids: tuple[UUID, ...]
    source: str
    evidence_references: tuple[ResumeEvidenceReference, ...] = ()
    section_kind: str = "experience"


@dataclass(frozen=True, slots=True)
class ResumeSourceSnapshot:
    headline: str | None
    summary: str | None
    skills: tuple[str, ...]
    bullets: tuple[ResumeSourceBullet, ...]
    source_evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ResumeRecord:
    resume: ResumeDocument
    current_version: ResumeVersion


@dataclass(frozen=True, slots=True)
class ResumeList:
    items: tuple[ResumeRecord, ...]


@dataclass(frozen=True, slots=True)
class ResumeVersionList:
    items: tuple[ResumeVersion, ...]


@dataclass(frozen=True, slots=True)
class ResumeExportRecord:
    export: ResumeExport
    verification: ResumeVerificationReport | None


@dataclass(frozen=True, slots=True)
class ResumeExportList:
    items: tuple[ResumeExportRecord, ...]


@dataclass(frozen=True, slots=True)
class RenderedResume:
    media_type: str
    filename: str
    content: bytes
    expected_lines: tuple[str, ...]
    renderer_version: str


@dataclass(frozen=True, slots=True)
class ExtractedDocumentText:
    plain_text: str
    reading_order: tuple[str, ...]
    parser_version: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: str
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    detected_lines: tuple[str, ...]
    missing_lines: tuple[str, ...]
    duplicate_lines: tuple[str, ...]
    reading_order: tuple[str, ...]
    grounding_codes: tuple[str, ...]
    parser_version: str


@dataclass(frozen=True, slots=True)
class DownloadIntentView:
    export_id: UUID
    url: str
    expires_at: datetime
    method: Literal["GET"] = "GET"
