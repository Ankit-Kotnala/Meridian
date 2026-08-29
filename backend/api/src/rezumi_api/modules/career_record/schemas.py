"""Strict Phase 3 career-record, evidence, and achievement wire schemas."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


def _safe_text(value: str, *, required: bool = False) -> str:
    normalized = value.strip()
    if required and not normalized:
        raise ValueError("a value is required")
    if "\x00" in normalized or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in normalized
    ):
        raise ValueError("control characters are not accepted")
    return normalized


class CareerRecordSchema(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")


YearMonth = Annotated[str, Field(pattern=r"^(19|20|21)\d{2}-(0[1-9]|1[0-2])$")]
PartialCareerDate = Annotated[str, Field(pattern=r"^(19|20|21)\d{2}(?:-(0[1-9]|1[0-2]))?$")]
PositiveVersion = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
EvidenceState = Literal["verified", "confirmed", "supported", "inferred", "unsupported"]
EvidenceLifecycle = Literal["active", "archived"]
CareerItemKind = Literal[
    "education",
    "project",
    "credential",
    "publication",
    "award",
    "volunteering",
    "language",
    "portfolio_link",
]


class PageResponse(CareerRecordSchema):
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_cursor: str | None


class AccountPreferenceSnapshotResponse(CareerRecordSchema):
    display_name: str
    email: str
    target_role: str | None
    preferred_location: str | None
    work_model: str | None
    seniority: str | None
    industry: str | None
    language: str


class CareerProfileUpdateRequest(CareerRecordSchema):
    professional_headline: str | None = Field(default=None, max_length=240)
    professional_summary: str | None = Field(default=None, max_length=4_000)
    work_authorization: str | None = Field(default=None, max_length=500)

    @field_validator(
        "professional_headline",
        "professional_summary",
        "work_authorization",
    )
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value)

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one career profile field is required")
        return self


class CareerProfileResponse(CareerRecordSchema):
    id: UUID
    version: PositiveVersion
    professional_headline: str
    professional_summary: str
    work_authorization: str
    account_preferences: AccountPreferenceSnapshotResponse
    created_at: datetime
    updated_at: datetime


class PersonalFactInput(CareerRecordSchema):
    kind: Literal["name", "email", "phone", "location", "link"]
    value: str = Field(min_length=1, max_length=2_048)
    label: str | None = Field(default=None, max_length=80)
    is_primary: bool = False

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @model_validator(mode="after")
    def validate_kind_value(self) -> Self:
        if self.kind == "email":
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.value) is None:
                raise ValueError("enter a valid email address")
        elif self.kind == "link":
            self.value = str(TypeAdapter(HttpUrl).validate_python(self.value))
        return self


class PersonalFactUpdateRequest(CareerRecordSchema):
    value: str = Field(min_length=1, max_length=2_048)
    label: str | None = Field(default=None, max_length=80)
    is_primary: bool = False

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)


class CareerRelationshipInput(CareerRecordSchema):
    experience_id: UUID
    project_id: UUID
    kind: Literal["experience_project"] = "experience_project"

    @model_validator(mode="after")
    def validate_distinct_entities(self) -> Self:
        if self.experience_id == self.project_id:
            raise ValueError("a career relationship requires two records")
        return self


class CareerRelationshipResponse(CareerRelationshipInput):
    id: UUID
    created_at: datetime


class CareerRelationshipListResponse(CareerRecordSchema):
    data: list[CareerRelationshipResponse] = Field(max_length=500)


class SourceSpanResponse(CareerRecordSchema):
    id: UUID
    page: int | None = Field(default=None, ge=1, le=100_000)
    start: int = Field(ge=0, le=100_000_000)
    end: int = Field(ge=1, le=100_000_000)
    excerpt: str = Field(max_length=2_000)
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ProvenanceResponse(CareerRecordSchema):
    id: UUID
    source_type: Literal["manual", "resume", "achievement", "attachment", "url"]
    source_label: str
    source_document_id: UUID | None = None
    source_snapshot_id: UUID | None = None
    source_revision: int | None = Field(default=None, ge=1)
    parser_version: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    user_confirmed: bool
    available: bool
    spans: list[SourceSpanResponse] = Field(max_length=100)


class PersonalFactResponse(PersonalFactInput):
    id: UUID
    confirmation: Literal["needs_review", "confirmed"]
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    provenance: list[ProvenanceResponse] = Field(default_factory=list, max_length=20)


class PersonalFactListResponse(CareerRecordSchema):
    data: list[PersonalFactResponse] = Field(max_length=100)


class DeclaredProfileEnrichmentJobResponse(CareerRecordSchema):
    job_id: UUID
    personal_fact_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "dead_lettered"]
    attempts: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    result_platform: str | None = Field(default=None, max_length=40)
    result_achievements_created: int | None = Field(default=None, ge=0, le=200)
    result_evidence_created: int | None = Field(default=None, ge=0, le=200)
    error_message: str | None = Field(default=None, max_length=300)
    created_at: datetime
    updated_at: datetime


class ProfileConflictResponse(CareerRecordSchema):
    id: UUID
    field: str
    code: str
    message: str
    severity: Literal["information", "review"]
    related_entity_ids: list[UUID] = Field(max_length=20)


class ExperienceInput(CareerRecordSchema):
    employer: str = Field(min_length=1, max_length=240)
    official_title: str = Field(min_length=1, max_length=240)
    display_title: str | None = Field(default=None, max_length=240)
    start_date: YearMonth
    end_date: YearMonth | None = None
    current: bool = False
    location: str | None = Field(default=None, max_length=240)
    employment_type: (
        Literal[
            "full_time", "part_time", "contract", "internship", "temporary", "volunteer", "other"
        ]
        | None
    ) = None
    description: str = Field(default="", max_length=8_000)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=100)
    group_with_experience_id: UUID | None = None

    @field_validator("employer", "official_title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("display_title", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _safe_text(value)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.current and self.end_date is not None:
            raise ValueError("a current experience cannot have an end date")
        if not self.current and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("experience end date must not precede its start date")
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise ValueError("skill identifiers must be unique")
        return self


class ExperienceResponse(ExperienceInput):
    start_date: PartialCareerDate
    end_date: PartialCareerDate | None = None
    id: UUID
    version: PositiveVersion
    order: int = Field(ge=0)
    user_confirmed: bool
    promotion_group_id: UUID | None = None
    concurrent_group_id: UUID | None = None
    conflicts: list[ProfileConflictResponse] = Field(max_length=50)
    provenance: list[ProvenanceResponse] = Field(max_length=100)
    created_at: datetime
    updated_at: datetime


class ExperienceListResponse(CareerRecordSchema):
    data: list[ExperienceResponse] = Field(max_length=500)
    findings: list[ProfileConflictResponse] = Field(max_length=500)


class ReorderItem(CareerRecordSchema):
    id: UUID
    position: int = Field(strict=True, ge=0, le=499)
    version: PositiveVersion


class ReorderRequest(CareerRecordSchema):
    items: list[ReorderItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        identifiers = [item.id for item in self.items]
        positions = [item.position for item in self.items]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("ordered identifiers must be unique")
        if sorted(positions) != list(range(len(positions))):
            raise ValueError("positions must form a complete zero-based order")
        return self


class CareerItemInput(CareerRecordSchema):
    kind: CareerItemKind
    title: str = Field(min_length=1, max_length=300)
    organization: str | None = Field(default=None, max_length=300)
    description: str = Field(default="", max_length=8_000)
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    url: HttpUrl | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("organization")
    @classmethod
    def validate_organization(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @field_validator("description")
    @classmethod
    def validate_item_description(cls, value: str) -> str:
        return _safe_text(value)

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        if self.end_date is not None and self.start_date is None:
            raise ValueError("an end date requires a start date")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("item end date must not precede its start date")
        if self.kind == "portfolio_link" and self.url is None:
            raise ValueError("a portfolio link requires an HTTP(S) URL")
        return self


class CareerItemResponse(CareerItemInput):
    start_date: PartialCareerDate | None = None
    end_date: PartialCareerDate | None = None
    id: UUID
    version: PositiveVersion
    order: int = Field(ge=0)
    user_confirmed: bool
    provenance: list[ProvenanceResponse] = Field(max_length=100)
    created_at: datetime
    updated_at: datetime


class CareerItemListResponse(CareerRecordSchema):
    data: list[CareerItemResponse] = Field(max_length=500)


class SkillInput(CareerRecordSchema):
    name: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=120)
    proficiency: Literal["learning", "working", "advanced", "expert"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_text(value, required=True)


class SkillResponse(SkillInput):
    id: UUID
    version: PositiveVersion
    order: int = Field(ge=0)
    user_confirmed: bool
    provenance: list[ProvenanceResponse] = Field(default_factory=list, max_length=20)
    created_at: datetime
    updated_at: datetime


class SkillListResponse(CareerRecordSchema):
    data: list[SkillResponse] = Field(max_length=500)


class ResumeImportProposalRequest(CareerRecordSchema):
    document_id: UUID
    snapshot_id: UUID
    block_id: UUID
    page: int = Field(strict=True, ge=1, le=100_000)
    start: int = Field(strict=True, ge=0, le=100_000_000)
    end: int = Field(strict=True, ge=1, le=100_000_000)
    target_entity_id: UUID | None = None
    kind: Literal[
        "experience",
        "education",
        "project",
        "credential",
        "publication",
        "award",
        "volunteering",
        "language",
        "portfolio_link",
    ]
    title: str = Field(min_length=1, max_length=300)
    organization: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=8_000)
    official_title: str | None = Field(default=None, max_length=300)
    display_title: str | None = Field(default=None, max_length=300)
    employment_type: (
        Literal[
            "full_time", "part_time", "contract", "internship", "temporary", "volunteer", "other"
        ]
        | None
    ) = None
    location: str | None = Field(default=None, max_length=240)
    url: HttpUrl | None = None
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    current: bool = False
    group_id: UUID | None = None

    @model_validator(mode="after")
    def validate_proposal(self) -> Self:
        if self.end <= self.start:
            raise ValueError("source span end must follow its start")
        if self.current and self.end_date is not None:
            raise ValueError("a current entity cannot have an end date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("entity end date must not precede its start date")
        if self.kind == "experience" and self.organization is None:
            raise ValueError("an experience proposal requires an organization")
        if self.kind == "portfolio_link" and self.url is None:
            raise ValueError("a portfolio proposal requires an HTTP(S) URL")
        return self


class ImportProposalAcceptRequest(CareerRecordSchema):
    edits: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("edits")
    @classmethod
    def validate_edits(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"title", "organization", "description", "startDate", "endDate", "review"}
        if not set(value).issubset(allowed):
            raise ValueError("proposal edits contain an unsupported field")
        normalized = {key: _safe_text(item) for key, item in value.items()}
        if any(len(item) > 8_000 for item in normalized.values()):
            raise ValueError("a proposal edit must not exceed 8000 characters")
        return normalized


class ImportProposalChangeResponse(CareerRecordSchema):
    id: UUID
    field: str
    label: str
    current_value: str | None
    proposed_value: str
    conflict: str | None
    source: ProvenanceResponse


class ImportProposalResponse(CareerRecordSchema):
    id: UUID
    source_document_name: str
    status: Literal["pending", "accepted", "rejected"]
    version: PositiveVersion
    changes: list[ImportProposalChangeResponse] = Field(min_length=1, max_length=500)
    created_at: datetime
    decided_at: datetime | None = None


class ImportProposalPageResponse(CareerRecordSchema):
    data: list[ImportProposalResponse] = Field(max_length=100)
    page: PageResponse


class ImportProposalDecisionRequest(CareerRecordSchema):
    decision: Literal["accept", "reject"]
    accepted_change_ids: list[UUID] = Field(default_factory=list, max_length=500)
    edited_values: dict[UUID, str] = Field(default_factory=dict, max_length=500)

    @field_validator("edited_values")
    @classmethod
    def validate_edits(cls, value: dict[UUID, str]) -> dict[UUID, str]:
        return {key: _safe_text(item, required=True) for key, item in value.items()}

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.decision == "reject" and (self.accepted_change_ids or self.edited_values):
            raise ValueError("a rejected proposal cannot accept or edit changes")
        if len(set(self.accepted_change_ids)) != len(self.accepted_change_ids):
            raise ValueError("accepted change identifiers must be unique")
        if not set(self.edited_values).issubset(set(self.accepted_change_ids)):
            raise ValueError("edited changes must also be explicitly accepted")
        return self


class SemanticImportCreateRequest(CareerRecordSchema):
    document_id: UUID
    snapshot_id: UUID


class SemanticImportAcceptRequest(CareerRecordSchema):
    values: dict[UUID, str] = Field(min_length=1, max_length=500)
    target_record_id: UUID | None = None

    @field_validator("values")
    @classmethod
    def validate_values(cls, value: dict[UUID, str]) -> dict[UUID, str]:
        return {field_id: _safe_text(item, required=True) for field_id, item in value.items()}


class SemanticImportAnchorResponse(CareerRecordSchema):
    block_id: UUID
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    digest: str
    excerpt: str


class SemanticImportFieldResponse(CareerRecordSchema):
    id: UUID
    name: str
    field_type: Literal["text", "email", "phone", "url", "date", "bullet"]
    proposed_value: str
    accepted_value: str | None
    review_state: Literal["confirmed", "corrected", "user_added"]
    confidence: float = Field(ge=0, le=1)
    date_precision: Literal["day", "month", "year", "unknown"] | None
    anchors: list[SemanticImportAnchorResponse] = Field(max_length=100)


class SemanticImportProposalResponse(CareerRecordSchema):
    id: UUID
    target: Literal["personalFacts", "entity", "skill"]
    target_record_id: UUID | None
    document_id: UUID
    snapshot_id: UUID
    snapshot_revision: int = Field(ge=1)
    schema_version: str
    parser_version: str
    semantic_entity_id: UUID
    semantic_kind: Literal[
        "contact", "experience", "education", "project", "skill", "certification"
    ]
    status: Literal["pending", "accepted", "rejected"]
    conflict_code: str | None
    source_available: bool
    version: PositiveVersion
    fields: list[SemanticImportFieldResponse] = Field(min_length=1, max_length=500)
    created_at: datetime
    reviewed_at: datetime | None


class SemanticImportQuestionResponse(CareerRecordSchema):
    semantic_entity_id: UUID
    code: Literal["semantic_candidate_requires_review"]
    missing_fields: list[str] = Field(min_length=1, max_length=20)


class SemanticImportBatchResponse(CareerRecordSchema):
    proposals: list[SemanticImportProposalResponse] = Field(max_length=500)
    questions: list[SemanticImportQuestionResponse] = Field(max_length=500)
    applied_count: int = Field(default=0, ge=0)


class SemanticImportProposalListResponse(CareerRecordSchema):
    data: list[SemanticImportProposalResponse] = Field(max_length=500)


class EvidenceSourceInput(CareerRecordSchema):
    source_type: Literal["manual", "resume", "attachment", "url"]
    document_id: UUID | None = None
    snapshot_id: UUID | None = None
    block_id: UUID | None = None
    page: int | None = Field(default=None, ge=1, le=100_000)
    start: int | None = Field(default=None, ge=0, le=100_000_000)
    end: int | None = Field(default=None, ge=1, le=100_000_000)
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        span_values = (self.page, self.start, self.end)
        resume_ids = (self.document_id, self.snapshot_id, self.block_id)
        if self.source_type == "resume":
            if any(value is None for value in resume_ids):
                raise ValueError("resume provenance requires document, snapshot, and block IDs")
            if any(value is None for value in span_values):
                raise ValueError("resume provenance requires a complete source span")
            if self.start is not None and self.end is not None and self.end <= self.start:
                raise ValueError("source span end must follow its start")
        elif any(value is not None for value in (*resume_ids, *span_values)):
            raise ValueError("resume identifiers and spans are accepted only for resume provenance")
        if self.source_type == "url" and self.url is None:
            raise ValueError("URL provenance requires an HTTP(S) URL")
        if self.source_type != "url" and self.url is not None:
            raise ValueError("a URL is accepted only for URL provenance")
        return self


class EvidenceMetricInput(CareerRecordSchema):
    name: str = Field(min_length=1, max_length=160)
    value: Decimal = Field(max_digits=18, decimal_places=4)
    unit: str = Field(min_length=1, max_length=80)
    period_start: YearMonth
    period_end: YearMonth | None = None
    baseline: str | None = Field(default=None, max_length=500)
    comparator: str | None = Field(default=None, max_length=240)
    precision: Literal["exact", "approximate"]
    attribution: Literal["individual", "team", "shared"]

    @field_validator("name", "unit")
    @classmethod
    def validate_metric_text(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @field_validator("baseline", "comparator")
    @classmethod
    def validate_optional_metric_text(cls, value: str | None) -> str | None:
        return None if value is None else (_safe_text(value) or None)

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.period_end is not None and self.period_end < self.period_start:
            raise ValueError("metric period end must not precede its start")
        return self


class EvidenceMetricResponse(EvidenceMetricInput):
    id: UUID | None


class EvidenceInput(CareerRecordSchema):
    type: Literal[
        "resume_statement",
        "user_confirmed_achievement",
        "metric",
        "project",
        "certificate",
        "publication",
        "award",
        "performance_review_excerpt",
        "portfolio_link",
        "github_link",
        "testimonial",
        "supporting_document",
        "user_note",
    ]
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=8_000)
    organization_or_project: str | None = Field(default=None, max_length=300)
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    source: EvidenceSourceInput
    metrics: list[EvidenceMetricInput] = Field(default_factory=list, max_length=20)
    experience_ids: list[UUID] = Field(default_factory=list, max_length=100)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=100)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("title", "description")
    @classmethod
    def validate_evidence_text(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.end_date is not None and self.start_date is None:
            raise ValueError("an evidence end date requires a start date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("evidence end date must not precede its start")
        for identifiers in (self.experience_ids, self.skill_ids, self.attachment_ids):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError("linked identifiers must be unique")
        if self.source.source_type == "attachment" or self.attachment_ids:
            raise ValueError("create evidence first, then add private attachments")
        return self


class EvidenceUpdateRequest(CareerRecordSchema):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=8_000)
    organization_or_project: str | None = Field(default=None, max_length=300)
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    metrics: list[EvidenceMetricInput] | None = Field(default=None, max_length=20)

    @field_validator("title", "description")
    @classmethod
    def validate_update_text(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one evidence field is required")
        return self


class EvidenceAttachmentResponse(CareerRecordSchema):
    id: UUID
    display_filename: str
    media_type: str
    size_bytes: int = Field(ge=1)
    status: Literal["uploading", "scanning", "ready", "failed", "deleting"]
    safe_error_code: str | None = None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class EvidenceUsageResponse(CareerRecordSchema):
    id: UUID
    type: Literal["experience", "skill", "requirement", "output"]
    label: str


class EvidenceHistoryResponse(CareerRecordSchema):
    id: UUID
    from_state: EvidenceState | None
    to_state: EvidenceState
    reason: str
    actor_label: str
    created_at: datetime


class EvidenceConflictResponse(CareerRecordSchema):
    id: UUID
    code: Literal["duplicate_claim", "metric_mismatch", "entity_mismatch", "date_mismatch"]
    message: str
    related_evidence_id: UUID
    status: Literal["open", "resolved"]
    version: PositiveVersion


class EvidenceResponse(CareerRecordSchema):
    id: UUID
    type: str
    title: str
    description: str
    organization_or_project: str | None
    start_date: PartialCareerDate | None
    end_date: PartialCareerDate | None
    state: EvidenceState
    lifecycle: EvidenceLifecycle
    version: PositiveVersion
    revision: PositiveVersion
    user_confirmed: bool
    factual_eligible: bool
    numeric_eligible: bool
    eligibility_reasons: list[str] = Field(max_length=20)
    archived_at: datetime | None
    provenance: list[ProvenanceResponse] = Field(min_length=1, max_length=100)
    metrics: list[EvidenceMetricResponse] = Field(max_length=50)
    attachments: list[EvidenceAttachmentResponse] = Field(max_length=20)
    usage: list[EvidenceUsageResponse] = Field(max_length=500)
    history: list[EvidenceHistoryResponse] = Field(max_length=500)
    conflicts: list[EvidenceConflictResponse] = Field(max_length=100)
    created_at: datetime
    updated_at: datetime


class EvidencePageResponse(CareerRecordSchema):
    data: list[EvidenceResponse] = Field(max_length=100)
    page: PageResponse


class EvidenceConflictResolutionRequest(CareerRecordSchema):
    resolution: Literal["keep_both", "prefer_current", "prefer_related", "mark_unsupported"]


class EvidenceUsageListResponse(CareerRecordSchema):
    data: list[EvidenceUsageResponse] = Field(max_length=500)


class AttachmentUploadIntentRequest(CareerRecordSchema):
    display_filename: str = Field(min_length=1, max_length=255)
    expected_size_bytes: int = Field(ge=1)
    media_type: Literal[
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    @field_validator("display_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or "/" in normalized or "\\" in normalized or "\x00" in normalized:
            raise ValueError("display filename must be a plain filename")
        return normalized


class AttachmentUploadIntentResponse(CareerRecordSchema):
    upload_id: UUID
    attachment_id: UUID
    url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: datetime


class AttachmentFinalizeResponse(CareerRecordSchema):
    attachment: EvidenceAttachmentResponse
    job_id: UUID


class AttachmentDownloadResponse(CareerRecordSchema):
    url: str
    expires_at: datetime


class AchievementAnswers(CareerRecordSchema):
    delivered: str = Field(default="", max_length=2_000)
    problem: str = Field(default="", max_length=2_000)
    changed: str = Field(default="", max_length=2_000)
    affected: str = Field(default="", max_length=2_000)
    measurement: str = Field(default="", max_length=2_000)
    collaboration: str = Field(default="", max_length=2_000)
    methods: str = Field(default="", max_length=2_000)

    @field_validator(
        "delivered", "problem", "changed", "affected", "measurement", "collaboration", "methods"
    )
    @classmethod
    def validate_answer(cls, value: str) -> str:
        return _safe_text(value)


class AchievementInput(CareerRecordSchema):
    title: str = Field(min_length=1, max_length=300)
    answers: AchievementAnswers
    metric: EvidenceMetricInput | None = None
    employer_id: UUID | None = None
    project_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def validate_achievement_title(cls, value: str) -> str:
        return _safe_text(value, required=True)

    @model_validator(mode="after")
    def validate_association(self) -> Self:
        if self.employer_id is not None and self.project_id is not None:
            raise ValueError("an achievement can be associated with one career entity")
        return self


class AchievementResponse(AchievementInput):
    id: UUID
    status: Literal["draft", "ready", "converted", "archived"]
    evidence_id: UUID | None
    version: PositiveVersion
    created_at: datetime
    updated_at: datetime


class AchievementPageResponse(CareerRecordSchema):
    data: list[AchievementResponse] = Field(max_length=100)
    page: PageResponse


class AchievementConversionResponse(CareerRecordSchema):
    achievement: AchievementResponse
    evidence: EvidenceResponse


class ReminderPreferencesUpdateRequest(CareerRecordSchema):
    enabled: bool
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    timezone: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_reminder(self) -> Self:
        if self.enabled and self.day_of_month is None:
            raise ValueError("an enabled monthly reminder requires a day")
        if not self.enabled and self.day_of_month is not None:
            raise ValueError("a disabled reminder cannot set a day")
        return self


class ReminderPreferencesResponse(ReminderPreferencesUpdateRequest):
    version: PositiveVersion
    updated_at: datetime


class DeleteResponse(CareerRecordSchema):
    status: Literal["deleted"] = "deleted"
