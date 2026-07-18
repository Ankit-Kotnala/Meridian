"""Transport-neutral Role Explorer commands and views."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from uuid import UUID

from careeros.modules.role_readiness.domain import (
    CompetencyEvidenceLink,
    CompetencyImportance,
    CompetencyResult,
    ReadinessComponent,
    RoleCompetency,
    RoleDefinition,
    RoleReadinessAnalysis,
    RoleReadinessValidationError,
    RoleSeniority,
    RoleTaxonomyVersion,
    SavedRole,
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
            raise RoleReadinessValidationError("cursor is invalid") from exc
        if not isinstance(offset, int) or offset < 0:
            raise RoleReadinessValidationError("cursor is invalid")
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
class RoleFilter:
    query: str | None = None
    seniority: RoleSeniority | None = None
    industry: str | None = None
    domain: str | None = None


@dataclass(frozen=True, slots=True)
class RoleDetail:
    taxonomy: RoleTaxonomyVersion
    role: RoleDefinition
    competencies: tuple[RoleCompetency, ...]


@dataclass(frozen=True, slots=True)
class SaveRole:
    role_id: UUID
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateSavedRole:
    notes: str | None


@dataclass(frozen=True, slots=True)
class SavedRoleView:
    saved_role: SavedRole
    role: RoleDefinition
    taxonomy: RoleTaxonomyVersion


@dataclass(frozen=True, slots=True)
class AnalyzeRoleReadiness:
    role_id: UUID | None = None
    saved_role_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    analysis: RoleReadinessAnalysis
    components: tuple[ReadinessComponent, ...]
    competency_results: tuple[CompetencyResult, ...]
    evidence_links: tuple[CompetencyEvidenceLink, ...]


@dataclass(frozen=True, slots=True)
class RoleReadinessView:
    analysis: RoleReadinessAnalysis
    role: RoleDefinition
    taxonomy: RoleTaxonomyVersion
    saved_role: SavedRole | None
    components: tuple[ReadinessComponent, ...]
    competency_results: tuple[CompetencyResult, ...]
    evidence_links: tuple[CompetencyEvidenceLink, ...]


@dataclass(frozen=True, slots=True)
class RoleComparisonEntry:
    role: RoleDefinition
    taxonomy: RoleTaxonomyVersion
    latest_analysis: RoleReadinessView | None
    required_gap_count: int
    demonstrated_count: int
    helpful_gap_count: int
    strongest_evidence_count: int


@dataclass(frozen=True, slots=True)
class RoleComparisonView:
    entries: tuple[RoleComparisonEntry, ...]
    note: str


def importance_weight(value: CompetencyImportance) -> int:
    return 3 if value is CompetencyImportance.REQUIRED else 1
