"""Transport-neutral Job Match commands and views."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from careeros.modules.job_match.domain import (
    EmploymentType,
    JobMatchAnalysis,
    JobMatchComponent,
    JobMatchValidationError,
    JobPosting,
    JobRequirement,
    JobSourceKind,
    OpportunityPriorityAnalysis,
    PreferenceFit,
    RequirementEvidenceLink,
    RequirementMatch,
    TailoringEffort,
    WorkModel,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class PageCursor:
    offset: int

    @classmethod
    def decode(cls, value: str | None) -> PageCursor | None:
        if value is None:
            return None
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii") + b"===")
            payload = json.loads(raw)
            offset = payload["offset"]
        except (binascii.Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise JobMatchValidationError("cursor is invalid") from exc
        if not isinstance(offset, int) or offset < 0:
            raise JobMatchValidationError("cursor is invalid")
        return cls(offset=offset)

    def encode(self) -> str:
        payload = json.dumps({"offset": self.offset}, separators=(",", ":")).encode("utf-8")
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
        data=visible, page=Page(limit=limit, has_more=has_more, next_cursor=next_cursor)
    )


@dataclass(frozen=True, slots=True)
class JobFilter:
    query: str | None = None
    source_kind: JobSourceKind | None = None
    target_role_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ImportedJobSource:
    final_url: str
    source_text: str
    title: str | None = None
    company: str | None = None
    location: str | None = None


@dataclass(frozen=True, slots=True)
class CreateJob:
    title: str | None
    company: str | None
    location: str | None
    work_model: WorkModel
    employment_type: EmploymentType
    compensation: str | None
    application_deadline: date | None
    source_kind: JobSourceKind
    source_url: str | None
    source_text: str
    target_role_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ImportJob:
    url: str
    target_role_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateJob:
    title: str
    company: str | None
    location: str | None
    work_model: WorkModel
    employment_type: EmploymentType
    compensation: str | None
    application_deadline: date | None
    source_text: str
    target_role_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class JobRecord:
    job: JobPosting
    requirements: tuple[JobRequirement, ...]


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    analysis: JobMatchAnalysis
    components: tuple[JobMatchComponent, ...]
    requirement_matches: tuple[RequirementMatch, ...]
    evidence_links: tuple[RequirementEvidenceLink, ...]


@dataclass(frozen=True, slots=True)
class JobMatchView:
    job: JobPosting
    requirements: tuple[JobRequirement, ...]
    analysis: JobMatchAnalysis
    components: tuple[JobMatchComponent, ...]
    requirement_matches: tuple[RequirementMatch, ...]
    evidence_links: tuple[RequirementEvidenceLink, ...]


@dataclass(frozen=True, slots=True)
class PrioritizeOpportunity:
    analysis_id: UUID | None
    user_interest: int
    career_direction_fit: int
    compensation_fit: PreferenceFit
    location_fit: PreferenceFit
    work_model_fit: PreferenceFit
    tailoring_effort: TailoringEffort
    existing_contacts: int


@dataclass(frozen=True, slots=True)
class OpportunityPriorityView:
    priority: OpportunityPriorityAnalysis
    job: JobPosting
    analysis: JobMatchAnalysis
