"""Strict Phase 7 resume builder wire schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ResumeBuilderSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
ResumeTemplate = Literal[
    "standard_professional",
    "compact_technical",
    "executive",
    "graduate",
    "consulting_finance",
]
ResumeFormat = Literal["pdf", "docx", "text", "json"]
ResumePageSize = Literal["letter", "a4"]
ResumeFontFamily = Literal["sans", "serif"]
ResumeLineSpacing = Literal["compact", "standard", "relaxed"]
ResumeMarginSize = Literal["narrow", "standard", "wide"]
ResumeExportStatus = Literal[
    "pending",
    "rendering",
    "retry_wait",
    "verified",
    "blocked",
    "failed",
    "dead_lettered",
    "deletion_pending",
    "deleting",
    "deletion_retry_wait",
    "deletion_dead_lettered",
    "deleted",
]
ResumeVerificationStatus = Literal["passed", "warning", "failed"]
ResumeEvidenceLinkBasis = Literal[
    "evidence_statement",
    "evidence_skill",
    "change_studio_claim",
]


class ResumeLayoutSchema(ResumeBuilderSchema):
    page_size: ResumePageSize = "letter"
    page_limit: Literal[1, 2] = 1
    font_family: ResumeFontFamily = "sans"
    font_size_pt: int = Field(default=10, ge=9, le=12)
    line_spacing: ResumeLineSpacing = "standard"
    margins: ResumeMarginSize = "standard"


class ResumeCreateRequest(ResumeBuilderSchema):
    title: str = Field(min_length=1, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
    template: ResumeTemplate = "standard_professional"
    change_set_id: UUID | None = None
    change_set_version_id: UUID | None = None
    layout: ResumeLayoutSchema = Field(default_factory=ResumeLayoutSchema)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("target_role")
    @classmethod
    def validate_target_role(cls, value: str | None) -> str | None:
        return _safe_text(value) if value is not None else None


class ResumeBulletRequest(ResumeBuilderSchema):
    id: UUID
    text: str = Field(min_length=1, max_length=450)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)
    source: str = Field(min_length=1, max_length=80)
    entity_id: UUID | None = None

    @field_validator("text", "source")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ResumeSectionRequest(ResumeBuilderSchema):
    id: UUID
    title: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=40)
    items: list[ResumeBulletRequest] = Field(default_factory=list, max_length=24)

    @field_validator("title", "kind")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _safe_text(value, required=True)


class ResumeUpdateRequest(ResumeBuilderSchema):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
    template: ResumeTemplate | None = None
    sections: list[ResumeSectionRequest] | None = Field(default=None, min_length=1, max_length=12)
    personal_fact_ids: list[UUID] | None = Field(default=None, max_length=20)
    layout: ResumeLayoutSchema | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return _safe_text(value, required=True) if value is not None else None

    @field_validator("target_role")
    @classmethod
    def validate_target_role(cls, value: str | None) -> str | None:
        return _safe_text(value) if value is not None else None


class ResumeExportRequest(ResumeBuilderSchema):
    format: ResumeFormat


class ResumeEvidenceReferenceResponse(ResumeBuilderSchema):
    evidence_id: UUID
    evidence_revision_id: UUID
    revision_number: PositiveVersion
    statement_sha256: str = Field(min_length=64, max_length=64)
    claim_sha256: str = Field(min_length=64, max_length=64)
    link_basis: ResumeEvidenceLinkBasis
    source_skill_id: UUID | None


class ResumeBulletResponse(ResumeBuilderSchema):
    id: UUID
    text: str
    evidence_ids: list[UUID] = Field(max_length=20)
    source: str
    entity_id: UUID | None = None
    evidence_references: list[ResumeEvidenceReferenceResponse] = Field(max_length=20)


class ResumeSectionResponse(ResumeBuilderSchema):
    id: UUID
    title: str
    kind: str
    items: list[ResumeBulletResponse] = Field(max_length=24)


class ResumePersonalFactResponse(ResumeBuilderSchema):
    id: UUID
    kind: str
    value: str
    label: str | None
    is_primary: bool


class ResumePartialDateResponse(ResumeBuilderSchema):
    year: int = Field(ge=1900, le=2200)
    month: int | None = Field(default=None, ge=1, le=12)


class ResumeEntityResponse(ResumeBuilderSchema):
    id: UUID
    kind: str
    title: str
    organization: str | None
    official_title: str | None
    display_title: str | None
    location: str | None
    start_date: ResumePartialDateResponse | None
    end_date: ResumePartialDateResponse | None
    is_current: bool
    evidence_ids: list[UUID] = Field(max_length=200)


class ResumeVersionResponse(ResumeBuilderSchema):
    id: UUID
    resume_id: UUID
    version_number: PositiveVersion
    parent_version_id: UUID | None
    title: str
    target_role: str | None
    template: ResumeTemplate
    layout: ResumeLayoutSchema = Field(default_factory=ResumeLayoutSchema)
    personal_facts: list[ResumePersonalFactResponse] = Field(default_factory=list, max_length=20)
    entities: list[ResumeEntityResponse] = Field(default_factory=list, max_length=100)
    sections: list[ResumeSectionResponse] = Field(max_length=12)
    plain_text: str
    source_evidence_ids: list[UUID] = Field(max_length=200)
    source_change_set_id: UUID | None
    source_change_set_version_id: UUID | None
    created_at: datetime


class ResumeResponse(ResumeBuilderSchema):
    id: UUID
    title: str
    target_role: str | None
    template: ResumeTemplate
    layout: ResumeLayoutSchema = Field(default_factory=ResumeLayoutSchema)
    current_version_id: UUID
    current_version: ResumeVersionResponse
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class ResumeListResponse(ResumeBuilderSchema):
    items: list[ResumeResponse] = Field(max_length=100)


class ResumeVersionListResponse(ResumeBuilderSchema):
    items: list[ResumeVersionResponse] = Field(max_length=200)


class ResumeExportResponse(ResumeBuilderSchema):
    id: UUID
    resume_id: UUID
    version_id: UUID
    format: ResumeFormat
    status: ResumeExportStatus
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256_digest: str | None
    verification_status: ResumeVerificationStatus | None
    verification_codes: list[str] = Field(max_length=40)
    critical_failures: list[str] = Field(max_length=100)
    warnings: list[str] = Field(max_length=100)
    renderer_version: str
    parser_version: str | None
    attempts: int = Field(default_factory=lambda: 0, ge=0)
    max_attempts: int = Field(default_factory=lambda: 3, ge=1)
    cleanup_attempts: int = Field(default_factory=lambda: 0, ge=0)
    cleanup_max_attempts: int = Field(default_factory=lambda: 3, ge=1)
    last_error: str | None = None
    retry_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    version_content_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    fidelity_manifest_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    requested_at: datetime
    completed_at: datetime | None
    deleted_at: datetime | None


class ResumeVerificationResponse(ResumeBuilderSchema):
    id: UUID
    export_id: UUID
    version_id: UUID
    status: ResumeVerificationStatus
    critical_failures: list[str] = Field(max_length=100)
    warnings: list[str] = Field(max_length=100)
    detected_lines: list[str] = Field(max_length=500)
    missing_lines: list[str] = Field(max_length=500)
    duplicate_lines: list[str] = Field(max_length=500)
    reading_order: list[str] = Field(max_length=500)
    grounding_codes: list[str] = Field(max_length=40)
    occurrence_mismatches: list[str] = Field(default_factory=list, max_length=500)
    reading_order_failures: list[str] = Field(default_factory=list, max_length=500)
    file_sha256: str
    manifest_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    version_content_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    page_count: int = Field(default_factory=lambda: 0, ge=0)
    parser_version: str
    created_at: datetime


class ResumeExportRecordResponse(ResumeBuilderSchema):
    export: ResumeExportResponse
    verification: ResumeVerificationResponse | None


class ResumeDownloadIntentResponse(ResumeBuilderSchema):
    export_id: UUID
    method: Literal["GET"]
    url: str
    expires_at: datetime


class ResumeSourceBulletResponse(ResumeBuilderSchema):
    text: str
    evidence_ids: list[UUID] = Field(max_length=20)
    source: str
    section_kind: str
    entity_id: UUID | None = None
    evidence_references: list[ResumeEvidenceReferenceResponse] = Field(max_length=20)


class ResumeSourceOptionsResponse(ResumeBuilderSchema):
    headline: str | None
    summary: str | None
    skills: list[str] = Field(max_length=200)
    bullets: list[ResumeSourceBulletResponse] = Field(max_length=500)
    source_evidence_ids: list[UUID] = Field(max_length=500)
    personal_facts: list[ResumePersonalFactResponse] = Field(default_factory=list, max_length=20)
    entities: list[ResumeEntityResponse] = Field(default_factory=list, max_length=100)
