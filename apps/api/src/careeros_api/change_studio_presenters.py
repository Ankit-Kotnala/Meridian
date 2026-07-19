"""Presentation mapping for Change Studio responses."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from careeros.modules.change_studio.application import ChangeSetRecord
from careeros.modules.change_studio.domain import (
    ChangeClaim,
    ChangeOperation,
    ChangeSetVersion,
    ClarifyingQuestion,
    ProviderRun,
)

from careeros_api.change_studio_schemas import (
    ChangeClaimResponse,
    ChangeOperationResponse,
    ChangeSetResponse,
    ChangeSetVersionResponse,
    ClarifyingQuestionResponse,
    ProviderRunResponse,
)


def change_set_response(record: ChangeSetRecord) -> ChangeSetResponse:
    claims_by_operation: defaultdict[UUID, list[ChangeClaim]] = defaultdict(list)
    for claim in record.claims:
        claims_by_operation[claim.operation_id].append(claim)
    versions = [_version_response(version) for version in record.versions]
    current_version = next(
        (version for version in versions if version.id == record.change_set.current_version_id),
        None,
    )
    return ChangeSetResponse(
        id=record.change_set.id,
        purpose=record.change_set.purpose.value,
        target_kind=record.change_set.target_kind.value,
        status=record.change_set.status.value,
        job_id=record.change_set.job_id,
        analysis_id=record.change_set.analysis_id,
        current_version_id=record.change_set.current_version_id,
        current_version=current_version,
        provider_name=record.change_set.provider_name,
        provider_model=record.change_set.provider_model,
        prompt_version=record.change_set.prompt_version,
        policy_version=record.change_set.policy_version,
        schema_version=record.change_set.schema_version,
        grounding_version=record.change_set.grounding_version,
        version=record.change_set.version,
        operations=[
            _operation_response(operation, tuple(claims_by_operation[operation.id]))
            for operation in record.operations
        ],
        questions=[_question_response(question) for question in record.questions],
        versions=versions,
        provider_runs=[_provider_run_response(run) for run in record.provider_runs[-20:]],
        created_at=record.change_set.created_at,
        updated_at=record.change_set.updated_at,
    )


def _operation_response(
    operation: ChangeOperation, claims: tuple[ChangeClaim, ...]
) -> ChangeOperationResponse:
    return ChangeOperationResponse(
        id=operation.id,
        operation_type=operation.operation_type.value,
        target_kind=operation.target_kind.value,
        target_id=operation.target_id,
        before_text=operation.before_text,
        after_text=operation.after_text,
        reason=operation.reason,
        status=operation.status.value,
        risk=operation.risk.value,
        confidence_basis_points=operation.confidence_basis_points,
        requires_confirmation=operation.requires_confirmation,
        grounding_status=operation.grounding_status.value,
        grounding_codes=list(operation.grounding_codes),
        expected_score_delta_basis_points=operation.expected_score_delta_basis_points,
        requirement_id=operation.requirement_id,
        requirement_text=operation.requirement_text,
        locked=operation.locked,
        sort_order=operation.sort_order,
        version=operation.version,
        claims=[_claim_response(claim) for claim in claims],
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


def _claim_response(claim: ChangeClaim) -> ChangeClaimResponse:
    return ChangeClaimResponse(
        id=claim.id,
        claim_kind=claim.claim_kind.value,
        text=claim.text,
        evidence_id=claim.evidence_id,
        evidence_title=claim.evidence_title,
        evidence_strength=claim.evidence_strength,
        source_excerpt=claim.source_excerpt,
        validation_status=claim.validation_status.value,
        validation_codes=list(claim.validation_codes),
        sort_order=claim.sort_order,
        created_at=claim.created_at,
    )


def _question_response(question: ClarifyingQuestion) -> ClarifyingQuestionResponse:
    return ClarifyingQuestionResponse(
        id=question.id,
        operation_id=question.operation_id,
        requirement_id=question.requirement_id,
        evidence_id=question.evidence_id,
        question=question.question,
        reason=question.reason,
        status=question.status.value,
        answer_text=question.answer_text,
        answered_at=question.answered_at,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


def _version_response(version: ChangeSetVersion) -> ChangeSetVersionResponse:
    return ChangeSetVersionResponse(
        id=version.id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        created_by_operation_id=version.created_by_operation_id,
        title=version.title,
        content=version.content,
        operation_ids=list(version.operation_ids),
        created_at=version.created_at,
    )


def _provider_run_response(run: ProviderRun) -> ProviderRunResponse:
    return ProviderRunResponse(
        id=run.id,
        provider_name=run.provider_name,
        provider_model=run.provider_model,
        operation=run.operation,
        prompt_version=run.prompt_version,
        policy_version=run.policy_version,
        schema_version=run.schema_version,
        grounding_version=run.grounding_version,
        input_evidence_ids=list(run.input_evidence_ids),
        input_requirement_ids=list(run.input_requirement_ids),
        output_operation_count=run.output_operation_count,
        status=run.status.value,
        latency_ms=run.latency_ms,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        cost_micros=run.cost_micros,
        validation_codes=list(run.validation_codes),
        created_at=run.created_at,
    )
