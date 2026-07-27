"""Strict Phase 2 resume upload, review, and health-report schemas."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ResumeHealthSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        extra="forbid",
    )


MediaType = Literal[
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "deadLettered"]
JobStage = Literal[
    "queued",
    "admission",
    "malwareScan",
    "extraction",
    "canonicalization",
    "analysis",
    "complete",
    "cleanup",
]


class UploadPolicyResponse(ResumeHealthSchema):
    accepted_media_types: list[MediaType]
    max_bytes: int
    max_pages: int
    guest_retention_hours: int
    upload_intent_ttl_seconds: int


class UploadIntentRequest(ResumeHealthSchema):
    display_filename: str = Field(min_length=1, max_length=255)
    expected_size_bytes: int = Field(ge=1)
    media_type: MediaType
    purpose: Literal["resume_health"] = "resume_health"

    @field_validator("display_filename")
    @classmethod
    def validate_display_filename(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or any(character in normalized for character in ("/", "\\", "\x00")):
            raise ValueError("display filename must be a plain filename")
        return normalized


class UploadIntentResponse(ResumeHealthSchema):
    upload_id: UUID
    url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: datetime
    guest_expires_at: datetime | None = None


class SourceSpanResponse(ResumeHealthSchema):
    page: int | None
    start: int
    end: int
    excerpt: str


class CanonicalFieldResponse(ResumeHealthSchema):
    id: str
    label: str
    value: str
    original_value: str | None
    confidence: int = Field(ge=0, le=100)
    source_spans: list[SourceSpanResponse]


class CanonicalSectionResponse(ResumeHealthSchema):
    id: str
    kind: Literal[
        "contact",
        "summary",
        "experience",
        "education",
        "skills",
        "projects",
        "certifications",
        "other",
    ]
    title: str
    fields: list[CanonicalFieldResponse]


class ParserWarningResponse(ResumeHealthSchema):
    code: str
    message: str
    field_id: str | None = None


SemanticEntityKindValue = Literal[
    "contact",
    "experience",
    "education",
    "project",
    "skill",
    "certification",
]
SemanticFieldTypeValue = Literal["text", "email", "phone", "url", "date", "bullet"]
SemanticReviewStateValue = Literal[
    "unreviewed",
    "confirmed",
    "corrected",
    "user_added",
    "removed",
]
DatePrecisionValue = Literal["day", "month", "year", "unknown"]


class SemanticSourceAnchorResponse(ResumeHealthSchema):
    block_id: UUID
    page: int
    start: int
    end: int
    source_sha256: str
    excerpt: str


class SemanticFieldResponse(ResumeHealthSchema):
    id: UUID
    name: str
    field_type: SemanticFieldTypeValue
    value: str
    confidence: int = Field(ge=0, le=100)
    review_state: SemanticReviewStateValue
    anchors: list[SemanticSourceAnchorResponse]
    date_precision: DatePrecisionValue | None = None


class SemanticEntityResponse(ResumeHealthSchema):
    id: UUID
    kind: SemanticEntityKindValue
    review_state: SemanticReviewStateValue
    source_section_id: UUID | None
    fields: list[SemanticFieldResponse]


class CanonicalResumeResponse(ResumeHealthSchema):
    id: UUID
    document_id: UUID
    schema_version: str
    version: int
    sections: list[CanonicalSectionResponse]
    warnings: list[ParserWarningResponse]
    semantic_schema_version: str | None
    semantic_parser_version: str | None
    semantic_review_state: SemanticReviewStateValue | None
    semantic_entities: list[SemanticEntityResponse]
    semantic_warnings: list[ParserWarningResponse]
    legacy_upgrade_required: bool
    corrected_by_user: bool
    created_at: datetime


class CanonicalFieldUpdate(ResumeHealthSchema):
    id: UUID
    value: str = Field(min_length=1, max_length=10_000)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "\x00" in normalized:
            raise ValueError("canonical values must contain safe text")
        return normalized


class SemanticValueInput(ResumeHealthSchema):
    name: str = Field(min_length=1, max_length=80)
    field_type: SemanticFieldTypeValue
    value: str = Field(min_length=1, max_length=10_000)
    date_precision: DatePrecisionValue | None = None

    @model_validator(mode="after")
    def validate_semantic_value(self) -> Self:
        self.value = self.value.strip()
        if not self.value or "\x00" in self.value:
            raise ValueError("semantic values must contain safe text")
        if (self.field_type == "date") != (self.date_precision is not None):
            raise ValueError("semantic date values require precision")
        return self


class ConfirmSemanticFieldRequest(ResumeHealthSchema):
    operation: Literal["confirmField"]
    field_id: UUID


class CorrectSemanticFieldRequest(ResumeHealthSchema):
    operation: Literal["correctField"]
    field_id: UUID
    value: str = Field(min_length=1, max_length=10_000)
    date_precision: DatePrecisionValue | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "\x00" in normalized:
            raise ValueError("semantic values must contain safe text")
        return normalized


class AddSemanticFieldRequest(SemanticValueInput):
    operation: Literal["addField"]
    entity_id: UUID


class RemoveSemanticFieldRequest(ResumeHealthSchema):
    operation: Literal["removeField"]
    field_id: UUID


class SemanticFieldReclassificationRequest(ResumeHealthSchema):
    field_id: UUID
    name: str = Field(min_length=1, max_length=80)


class ReclassifySemanticEntityRequest(ResumeHealthSchema):
    operation: Literal["reclassifyEntity"]
    entity_id: UUID
    kind: SemanticEntityKindValue
    fields: list[SemanticFieldReclassificationRequest] = Field(min_length=1, max_length=100)


class AddSemanticEntityRequest(ResumeHealthSchema):
    operation: Literal["addEntity"]
    kind: SemanticEntityKindValue
    fields: list[SemanticValueInput] = Field(min_length=1, max_length=100)


class RemoveSemanticEntityRequest(ResumeHealthSchema):
    operation: Literal["removeEntity"]
    entity_id: UUID


SemanticReviewOperationRequest = Annotated[
    ConfirmSemanticFieldRequest
    | CorrectSemanticFieldRequest
    | AddSemanticFieldRequest
    | RemoveSemanticFieldRequest
    | ReclassifySemanticEntityRequest
    | AddSemanticEntityRequest
    | RemoveSemanticEntityRequest,
    Field(discriminator="operation"),
]


class CanonicalResumeUpdateRequest(ResumeHealthSchema):
    fields: list[CanonicalFieldUpdate] = Field(default_factory=list, max_length=250)
    semantic_operations: list[SemanticReviewOperationRequest] = Field(
        default_factory=list,
        max_length=250,
    )
    confirm_no_changes: bool = False

    @model_validator(mode="after")
    def require_unique_fields(self) -> Self:
        modes = sum(
            (
                bool(self.fields),
                bool(self.semantic_operations),
                self.confirm_no_changes,
            )
        )
        if modes != 1:
            raise ValueError("choose exactly one canonical review mode")
        identifiers = [field.id for field in self.fields]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("canonical field identifiers must be unique")
        return self


class JobErrorResponse(ResumeHealthSchema):
    code: str
    retryable: bool
    message: str


class ProcessingJobResponse(ResumeHealthSchema):
    id: UUID
    document_id: UUID
    job_type: Literal["parse", "analyze", "delete"]
    status: JobStatus
    stage: JobStage
    progress: int | None = Field(default=None, ge=0, le=100)
    attempts: int = Field(ge=0)
    result_type: Literal["document", "analysis"] | None = None
    result_id: UUID | None = None
    result_url: str | None = None
    error: JobErrorResponse | None = None
    created_at: datetime
    updated_at: datetime


class DocumentSummaryResponse(ResumeHealthSchema):
    id: UUID
    display_filename: str
    media_type: MediaType
    size_bytes: int
    status: Literal[
        "quarantined",
        "processing",
        "reviewReady",
        "failed",
        "cancelled",
        "deleting",
    ]
    version: int
    current_canonical_resume_id: UUID | None
    latest_analysis_id: UUID | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None


class DocumentResponse(DocumentSummaryResponse):
    canonical_resume: CanonicalResumeResponse | None


class DocumentListResponse(ResumeHealthSchema):
    data: list[DocumentSummaryResponse]


class FinalizeUploadResponse(ResumeHealthSchema):
    document_id: UUID
    job: ProcessingJobResponse


class PlainTextResponse(ResumeHealthSchema):
    document_id: UUID
    text: str
    truncated: bool = False


class ReadingOrderBlockResponse(ResumeHealthSchema):
    index: int = Field(ge=0)
    page: int | None
    text: str


class ReadingOrderResponse(ResumeHealthSchema):
    document_id: UUID
    blocks: list[ReadingOrderBlockResponse]


class ResumeHealthRequest(ResumeHealthSchema):
    document_id: UUID


ResumeHealthFeatureKey = Literal[
    "text_characters",
    "page_count",
    "image_only",
    "section_count",
    "recognized_section_count",
    "block_count",
    "concise_block_count",
    "bullet_count",
    "action_bullet_count",
    "outcome_bullet_count",
    "duplicate_block_count",
    "chronology_signal_count",
    "warning_count",
    "reading_order_violation_count",
    "average_confidence_basis_points",
    "semantic_entity_count",
    "semantic_field_count",
    "parsed_semantic_field_count",
    "source_anchored_field_count",
    "reviewed_semantic_field_count",
    "date_field_count",
    "precise_date_field_count",
]
ResumeHealthContributionKey = Literal[
    "searchable_text",
    "parser_confidence",
    "reading_order_integrity",
    "recognized_section_ratio",
    "concise_block_ratio",
    "section_breadth",
    "chronology_coverage",
    "action_bullet_ratio",
    "outcome_bullet_ratio",
    "duplicate_content_integrity",
    "page_fit",
    "parser_warning_integrity",
    "source_anchor_coverage",
    "semantic_breadth",
    "semantic_review_coverage",
    "date_precision_coverage",
]
BoundedFeatureInteger = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]


class ResumeHealthFeatureValueResponse(ResumeHealthSchema):
    key: ResumeHealthFeatureKey
    label: str = Field(min_length=1, max_length=80)
    kind: Literal["count", "boolean", "percentage"]
    raw_value: BoundedFeatureInteger | bool
    display_value: str = Field(min_length=1, max_length=40)


class ResumeHealthFeatureContributionResponse(ResumeHealthSchema):
    key: ResumeHealthContributionKey
    label: str = Field(min_length=1, max_length=80)
    score: int = Field(ge=0, le=100)
    raw_score_basis_points: int = Field(ge=0, le=10_000)
    weight: int = Field(ge=0, le=100)
    raw_weight_basis_points: int = Field(ge=0, le=10_000)
    contribution: int = Field(ge=0, le=100)
    raw_contribution_basis_points: int = Field(ge=0, le=10_000)


class ResumeHealthComponentResponse(ResumeHealthSchema):
    key: Literal[
        "machine_readability",
        "recruiter_clarity",
        "content_impact",
        "achievement_strength",
        "structure",
        "consistency_truth",
    ]
    label: str
    score: int = Field(ge=0, le=100)
    raw_score_basis_points: int = Field(ge=0, le=10_000)
    weight: int = Field(ge=0, le=100)
    contribution: int = Field(ge=0, le=100)
    raw_contribution_basis_points: int = Field(ge=0, le=10_000)
    explanation: str
    feature_contributions: list[ResumeHealthFeatureContributionResponse] = Field(max_length=7)


class ResumeFindingResponse(ResumeHealthSchema):
    id: str
    severity: Literal["info", "warning", "critical"]
    category: Literal["issue", "quick_win", "section_feedback", "parser_warning"]
    title: str
    description: str
    section: str | None
    action: str | None


class ResumeHealthReportResponse(ResumeHealthSchema):
    id: UUID
    document_id: UUID
    canonical_resume_id: UUID
    status: Literal["insufficientData", "complete"]
    score: int | None
    raw_score_basis_points: int | None
    score_band: Literal["needsAttention", "developing", "strong"] | None
    score_type: Literal["resume_health"] = "resume_health"
    engine_version: str
    configuration_version: str
    feature_schema_version: str = Field(min_length=1, max_length=80)
    feature_values: list[ResumeHealthFeatureValueResponse] = Field(max_length=24)
    feature_set_hash: str
    components: list[ResumeHealthComponentResponse]
    findings: list[ResumeFindingResponse]
    warnings: list[str]
    disclaimer: str
    computed_at: datetime
    expires_at: datetime | None


class JobAcceptedResponse(ResumeHealthSchema):
    job: ProcessingJobResponse


class ClaimGuestDocumentRequest(ResumeHealthSchema):
    consent: Literal[True]


class ClaimGuestDocumentResponse(ResumeHealthSchema):
    document_id: UUID
    access_mode: Literal["account"] = "account"


class DeleteDocumentResponse(ResumeHealthSchema):
    status: Literal["deleted"] = "deleted"
