"""Transport-neutral Change Studio commands, contexts, and views."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from careeros.modules.change_studio.domain import (
    ChangeClaim,
    ChangeOperation,
    ChangeSet,
    ChangeSetVersion,
    ChangeTargetKind,
    ClarifyingQuestion,
    EvidenceGroundingContext,
    ProviderRun,
    RequirementGroundingContext,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    actor_user_id: UUID
    request_id: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class CreateChangeSet:
    analysis_id: UUID
    target_kind: ChangeTargetKind = ChangeTargetKind.TAILORED_RESUME_BULLET
    tone: str = "direct"
    length: str = "standard"
    max_operations: int = 5


@dataclass(frozen=True, slots=True)
class EditOperation:
    after_text: str


@dataclass(frozen=True, slots=True)
class AlternativeRequest:
    tone: str = "direct"
    length: str = "standard"
    preserve_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerClarification:
    answer_text: str


@dataclass(frozen=True, slots=True)
class RequirementMatchContext:
    requirement: RequirementGroundingContext
    match_state: str
    hard_gap: bool
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class JobMatchAnalysisContext:
    job_id: UUID
    job_title: str
    analysis_id: UUID
    display_score: int | None
    requirements: tuple[RequirementMatchContext, ...]


@dataclass(frozen=True, slots=True)
class AiGenerationRequest:
    owner_user_id: UUID
    purpose: str
    target_kind: ChangeTargetKind
    tone: str
    length: str
    max_operations: int
    job: JobMatchAnalysisContext
    evidence: tuple[EvidenceGroundingContext, ...]
    alternative_for_operation_id: UUID | None = None
    preserve_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AiProviderResponse:
    provider_name: str
    provider_model: str
    latency_ms: int
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChangeSetRecord:
    change_set: ChangeSet
    operations: tuple[ChangeOperation, ...]
    claims: tuple[ChangeClaim, ...]
    questions: tuple[ClarifyingQuestion, ...]
    versions: tuple[ChangeSetVersion, ...]
    provider_runs: tuple[ProviderRun, ...] = ()

    @property
    def id(self) -> UUID:
        return self.change_set.id
