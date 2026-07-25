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
ResumeExportStatus = Literal["pending", "rendering", "verified", "blocked", "failed", "deleted"]
ResumeVerificationStatus = Literal["passed", "warning", "failed"]
ResumeEvidenceLinkBasis = Literal[
    "evidence_statement",
    "evidence_skill",
    "change_studio_claim",
]


class ResumeCreateRequest(ResumeBuilderSchema):
    title: str = Field(min_length=1, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
    template: ResumeTemplate = "standard_professional"
    change_set_id: UUID | None = None
    change_set_version_id: UUID | None = None

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
    evidence_references: list[ResumeEvidenceReferenceResponse] = Field(max_length=20)


class ResumeSectionResponse(ResumeBuilderSchema):
    id: UUID
    title: str
    kind: str
    items: list[ResumeBulletResponse] = Field(max_length=24)


class ResumeVersionResponse(ResumeBuilderSchema):
    id: UUID
    resume_id: UUID
    version_number: PositiveVersion
    parent_version_id: UUID | None
    title: str
    target_role: str | None
    template: ResumeTemplate
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
    file_sha256: str
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
