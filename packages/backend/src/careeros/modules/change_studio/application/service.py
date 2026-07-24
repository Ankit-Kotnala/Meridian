"""Change Studio application service and truth-locked orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from time import perf_counter
from uuid import UUID

from careeros.modules.change_studio.domain import (
    GROUNDING_VERSION,
    POLICY_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ChangeAuditAction,
    ChangeClaim,
    ChangeOperation,
    ChangeOperationStatus,
    ChangeSet,
    ChangeSetPurpose,
    ChangeSetStatus,
    ChangeSetVersion,
    ChangeStudioAuditEvent,
    ChangeStudioConflict,
    ChangeStudioIdempotencyConflict,
    ChangeStudioIdempotencyRecord,
    ChangeStudioNotFound,
    ChangeStudioValidationError,
    ChangeStudioVersionConflict,
    ClarificationStatus,
    ClarifyingQuestion,
    EvidenceGroundingContext,
    GroundingDecision,
    GroundingFailed,
    GroundingStatus,
    ProviderCandidateResponse,
    ProviderOperationCandidate,
    ProviderOutputRejected,
    ProviderQuestionCandidate,
    ProviderRun,
    ProviderRunStatus,
    RequirementGroundingContext,
    RiskLevel,
    ground_operation,
    parse_provider_payload,
    validate_question,
)

from .models import (
    AiGenerationRequest,
    AlternativeRequest,
    AnswerClarification,
    ChangeSetRecord,
    CreateChangeSet,
    EditOperation,
    JobMatchAnalysisContext,
    RequestContext,
)
from .ports import (
    CareerEvidenceProvider,
    ChangeStudioUnitOfWork,
    ChangeStudioUnitOfWorkFactory,
    Clock,
    IdentifierFactory,
    JobMatchAnalysisProvider,
    SuggestionProvider,
)


class ChangeStudioPolicy:
    max_evidence: int = 40
    max_requirements: int = 40
    max_operations: int = 8


class ChangeStudioService:
    """Owner-scoped Phase 6 use cases for grounded suggestions and review."""

    def __init__(
        self,
        *,
        unit_of_work: ChangeStudioUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        provider: SuggestionProvider,
        evidence: CareerEvidenceProvider,
        job_matches: JobMatchAnalysisProvider,
        policy: ChangeStudioPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._provider = provider
        self._evidence = evidence
        self._job_matches = job_matches
        self._policy = policy or ChangeStudioPolicy()

    async def create_change_set(
        self,
        owner_user_id: UUID,
        command: CreateChangeSet,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        self._style(command.tone, command.length)
        if not 1 <= command.max_operations <= self._policy.max_operations:
            raise ChangeStudioValidationError("max operations is out of range")
        fingerprint = _fingerprint(
            "change-set-create",
            {
                "analysisId": str(command.analysis_id),
                "targetKind": command.target_kind.value,
                "tone": command.tone,
                "length": command.length,
                "maxOperations": command.max_operations,
            },
        )
        async with self._uow() as uow:
            existing = await uow.find_change_set_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.change_set.idempotency_fingerprint != fingerprint:
                    raise ChangeStudioIdempotencyConflict
                return existing

        job = await self._job_matches.analysis(owner_user_id, command.analysis_id)
        evidence = await self._load_evidence(owner_user_id, job)
        now = self._clock.now()
        change_set_id = self._ids.new()
        baseline = ChangeSetVersion(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            change_set_id=change_set_id,
            version_number=1,
            parent_version_id=None,
            created_by_operation_id=None,
            title=f"Baseline for {job.job_title}",
            content="",
            operation_ids=(),
            created_at=now,
        )
        ai_request = AiGenerationRequest(
            owner_user_id=owner_user_id,
            purpose=ChangeSetPurpose.JOB_TAILORING.value,
            target_kind=command.target_kind,
            tone=command.tone,
            length=command.length,
            max_operations=command.max_operations,
            job=job,
            evidence=evidence,
        )
        provider_start = perf_counter()
        provider_response = await self._provider.generate(ai_request)
        parsed, provider_codes = self._parse_provider(provider_response.payload)
        run = ProviderRun(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            change_set_id=change_set_id,
            provider_name=provider_response.provider_name,
            provider_model=provider_response.provider_model,
            operation="create_change_set",
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            schema_version=SCHEMA_VERSION,
            grounding_version=GROUNDING_VERSION,
            request_fingerprint=_request_fingerprint(ai_request),
            input_evidence_ids=tuple(item.id for item in evidence),
            input_requirement_ids=tuple(item.requirement.id for item in job.requirements),
            output_operation_count=len(parsed.operations),
            status=(
                ProviderRunStatus.SUCCEEDED
                if provider_codes == ("schema_valid",)
                else ProviderRunStatus.BLOCKED
            ),
            latency_ms=max(0, int((perf_counter() - provider_start) * 1000))
            + provider_response.latency_ms,
            prompt_tokens=parsed.usage.prompt_tokens,
            completion_tokens=parsed.usage.completion_tokens,
            cost_micros=parsed.usage.cost_micros,
            validation_codes=provider_codes,
            created_at=now,
        )
        change_set = ChangeSet(
            id=change_set_id,
            owner_user_id=owner_user_id,
            purpose=ChangeSetPurpose.JOB_TAILORING,
            target_kind=command.target_kind,
            status=ChangeSetStatus.DRAFT,
            job_id=job.job_id,
            analysis_id=job.analysis_id,
            current_version_id=baseline.id,
            provider_name=provider_response.provider_name,
            provider_model=provider_response.provider_model,
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            schema_version=SCHEMA_VERSION,
            grounding_version=GROUNDING_VERSION,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            version=1,
            created_at=now,
            updated_at=now,
        )
        operations, claims = self._operations_from_candidates(
            owner_user_id,
            change_set_id,
            parsed.operations,
            evidence,
            job,
            now,
            start_order=10,
        )
        questions = self._questions_from_candidates(
            owner_user_id,
            change_set_id,
            parsed.questions,
            evidence,
            job,
            now,
        )
        questions += self._missing_evidence_questions(
            owner_user_id, change_set_id, job, evidence, operations, now
        )
        record = ChangeSetRecord(
            change_set=change_set,
            operations=operations,
            claims=claims,
            questions=questions,
            versions=(baseline,),
            provider_runs=(run,),
        )
        async with self._uow() as uow:
            await uow.add_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.CHANGE_SET_CREATED,
                    "change_set",
                    change_set_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    analysis_id=job.analysis_id,
                    job_id=job.job_id,
                )
            )
            await uow.commit()
        return record

    async def get_change_set(self, owner_user_id: UUID, change_set_id: UUID) -> ChangeSetRecord:
        async with self._uow() as uow:
            record = await uow.get_record(owner_user_id, change_set_id)
        if record is None:
            raise ChangeStudioNotFound
        return record

    async def accept_operation(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        return await self._operation_decision(
            owner_user_id,
            change_set_id,
            operation_id,
            expected_version,
            idempotency_key,
            context,
            accept=True,
        )

    async def reject_operation(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        return await self._operation_decision(
            owner_user_id,
            change_set_id,
            operation_id,
            expected_version,
            idempotency_key,
            context,
            accept=False,
        )

    async def edit_operation(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        command: EditOperation,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "operation-edit",
            {
                "changeSetId": str(change_set_id),
                "operationId": str(operation_id),
                "expectedVersion": expected_version,
                "afterSha": hashlib.sha256(command.after_text.encode()).hexdigest(),
            },
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            operation = self._operation(record, operation_id)
            evidence = await self._operation_evidence(owner_user_id, record, operation)
            requirement = self._operation_requirement(record, operation)
            candidate = replace(
                _candidate_from_operation(operation, record.claims),
                after=command.after_text,
                claims=tuple(
                    replace(claim.candidate, text=command.after_text)
                    for claim in (
                        ground_operation(
                            _candidate_from_operation(operation, record.claims),
                            evidence={item.id: item for item in evidence},
                            requirements={requirement.id: requirement} if requirement else {},
                        ).claims
                    )
                ),
            )
            decision = ground_operation(
                candidate,
                evidence={item.id: item for item in evidence},
                requirements={requirement.id: requirement} if requirement else {},
            )
            if decision.status is not GroundingStatus.GROUNDED:
                raise GroundingFailed("user edit is not grounded")
            claims = self._claims_from_decision(
                owner_user_id, record.change_set.id, operation.id, decision, now
            )
            operation.edit(
                after_text=command.after_text,
                reason="User edit revalidated against the original evidence ledger.",
                risk=RiskLevel.MEDIUM if _has_number(command.after_text) else RiskLevel.LOW,
                confidence_basis_points=9_000,
                grounding_status=decision.status,
                grounding_codes=decision.codes,
                expected_score_delta_basis_points=operation.expected_score_delta_basis_points,
                now=now,
            )
            record = replace(
                record,
                claims=tuple(claim for claim in record.claims if claim.operation_id != operation.id)
                + claims,
            )
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.OPERATION_EDITED,
                    "operation",
                    operation_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    operation_id=operation_id,
                )
            )
            await uow.commit()
            return record

    async def create_alternative(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        command: AlternativeRequest,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        self._style(command.tone, command.length)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "operation-alternative",
            {
                "changeSetId": str(change_set_id),
                "operationId": str(operation_id),
                "expectedVersion": expected_version,
                "tone": command.tone,
                "length": command.length,
                "preserveTerms": list(command.preserve_terms),
            },
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            operation = self._operation(record, operation_id)
            if operation.locked:
                raise ChangeStudioConflict("locked operations cannot be regenerated")
        if record.change_set.analysis_id is None:
            raise ChangeStudioConflict("change set is not linked to a job analysis")
        job = await self._job_matches.analysis(owner_user_id, record.change_set.analysis_id)
        evidence = await self._operation_evidence(owner_user_id, record, operation)
        ai_request = AiGenerationRequest(
            owner_user_id=owner_user_id,
            purpose=record.change_set.purpose.value,
            target_kind=operation.target_kind,
            tone=command.tone,
            length=command.length,
            max_operations=1,
            job=job,
            evidence=evidence,
            alternative_for_operation_id=operation_id,
            preserve_terms=command.preserve_terms,
        )
        provider_response = await self._provider.generate(ai_request)
        parsed, _codes = self._parse_provider(provider_response.payload)
        operations, claims = self._operations_from_candidates(
            owner_user_id,
            change_set_id,
            parsed.operations[:1],
            evidence,
            job,
            now,
            start_order=max((item.sort_order for item in record.operations), default=0) + 10,
        )
        if not operations:
            raise ProviderOutputRejected("provider returned no alternative")
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            record = replace(
                record,
                operations=record.operations + operations,
                claims=record.claims + claims,
            )
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_provider_run(
                ProviderRun(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    change_set_id=change_set_id,
                    provider_name=provider_response.provider_name,
                    provider_model=provider_response.provider_model,
                    operation="operation_alternative",
                    prompt_version=PROMPT_VERSION,
                    policy_version=POLICY_VERSION,
                    schema_version=SCHEMA_VERSION,
                    grounding_version=GROUNDING_VERSION,
                    request_fingerprint=_request_fingerprint(ai_request),
                    input_evidence_ids=tuple(item.id for item in evidence),
                    input_requirement_ids=tuple(item.requirement.id for item in job.requirements),
                    output_operation_count=len(parsed.operations),
                    status=ProviderRunStatus.SUCCEEDED,
                    latency_ms=provider_response.latency_ms,
                    prompt_tokens=parsed.usage.prompt_tokens,
                    completion_tokens=parsed.usage.completion_tokens,
                    cost_micros=parsed.usage.cost_micros,
                    validation_codes=("schema_valid",),
                    created_at=now,
                )
            )
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.OPERATION_ALTERNATIVE_CREATED,
                    "operation",
                    operations[0].id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    operation_id=operations[0].id,
                )
            )
            await uow.commit()
            return record

    async def lock_operation(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
        *,
        locked: bool,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "operation-lock",
            {
                "changeSetId": str(change_set_id),
                "operationId": str(operation_id),
                "expectedVersion": expected_version,
                "locked": locked,
            },
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            operation = self._operation(record, operation_id)
            operation.set_locked(locked, now)
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.OPERATION_LOCKED
                    if locked
                    else ChangeAuditAction.OPERATION_UNLOCKED,
                    "operation",
                    operation_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    operation_id=operation_id,
                )
            )
            await uow.commit()
            return record

    async def apply_safe(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "apply-safe",
            {"changeSetId": str(change_set_id), "expectedVersion": expected_version},
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            accepted_any = False
            for operation in record.operations:
                if operation.acceptable and not operation.requires_confirmation:
                    operation.mark_accepted(now)
                    record = self._append_version(record, operation, now)
                    accepted_any = True
            if accepted_any:
                record.change_set.touch(now)
                await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.SAFE_CHANGES_APPLIED,
                    "change_set",
                    change_set_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                )
            )
            await uow.commit()
            return record

    async def undo(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        return await self._move_version(
            owner_user_id,
            change_set_id,
            expected_version,
            idempotency_key,
            context,
            action=ChangeAuditAction.CHANGE_SET_UNDONE,
            direction="undo",
        )

    async def redo(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        return await self._move_version(
            owner_user_id,
            change_set_id,
            expected_version,
            idempotency_key,
            context,
            action=ChangeAuditAction.CHANGE_SET_REDONE,
            direction="redo",
        )

    async def restore_version(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        version_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "version-restore",
            {
                "changeSetId": str(change_set_id),
                "versionId": str(version_id),
                "expectedVersion": expected_version,
            },
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            self._version_by_id(record, version_id)
            record.change_set.current_version_id = version_id
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.VERSION_RESTORED,
                    "version",
                    version_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    version_id=version_id,
                )
            )
            await uow.commit()
            return record

    async def answer_clarification(
        self,
        owner_user_id: UUID,
        clarification_id: UUID,
        expected_version: int,
        command: AnswerClarification,
        idempotency_key: str,
        context: RequestContext,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "clarification-answer",
            {
                "clarificationId": str(clarification_id),
                "expectedVersion": expected_version,
                "answerSha": hashlib.sha256(command.answer_text.encode()).hexdigest(),
            },
        )
        async with self._uow() as uow:
            record = await uow.get_record_for_question(
                owner_user_id, clarification_id, for_update=True
            )
            if record is None:
                raise ChangeStudioNotFound
            repeated = await self._idempotent_action(
                uow,
                owner_user_id,
                idempotency_key,
                fingerprint,
                "change_set",
                record.change_set.id,
                now,
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            question = next(
                (item for item in record.questions if item.id == clarification_id),
                None,
            )
            if question is None:
                raise ChangeStudioNotFound
            question.answer(command.answer_text, now)
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.CLARIFICATION_ANSWERED,
                    "clarification",
                    clarification_id,
                    context,
                    now,
                    change_set_id=record.change_set.id,
                    question_id=clarification_id,
                )
            )
            await uow.commit()
            return record

    async def _operation_decision(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
        *,
        accept: bool,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            "operation-accept" if accept else "operation-reject",
            {
                "changeSetId": str(change_set_id),
                "operationId": str(operation_id),
                "expectedVersion": expected_version,
            },
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            operation = self._operation(record, operation_id)
            if accept:
                operation.mark_accepted(now)
                record = self._append_version(record, operation, now)
            else:
                operation.mark_rejected(now)
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    ChangeAuditAction.OPERATION_ACCEPTED
                    if accept
                    else ChangeAuditAction.OPERATION_REJECTED,
                    "operation",
                    operation_id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    operation_id=operation_id,
                )
            )
            await uow.commit()
            return record

    async def _move_version(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        expected_version: int,
        idempotency_key: str,
        context: RequestContext,
        *,
        action: ChangeAuditAction,
        direction: str,
    ) -> ChangeSetRecord:
        self._authorize(owner_user_id, context)
        self._idempotency(idempotency_key)
        now = self._clock.now()
        fingerprint = _fingerprint(
            f"version-{direction}",
            {"changeSetId": str(change_set_id), "expectedVersion": expected_version},
        )
        async with self._uow() as uow:
            record = await self._record_for_update(uow, owner_user_id, change_set_id)
            repeated = await self._idempotent_action(
                uow, owner_user_id, idempotency_key, fingerprint, "change_set", change_set_id, now
            )
            if repeated:
                return record
            self._version(record.change_set.version, expected_version)
            current = self._current_version(record)
            if direction == "undo":
                if current.parent_version_id is None:
                    raise ChangeStudioConflict("there is no earlier version to restore")
                next_version = self._version_by_id(record, current.parent_version_id)
            else:
                candidates = [
                    item for item in record.versions if item.parent_version_id == current.id
                ]
                if not candidates:
                    raise ChangeStudioConflict("there is no later version to redo")
                next_version = max(candidates, key=lambda item: item.version_number)
            record.change_set.current_version_id = next_version.id
            record.change_set.touch(now)
            await uow.save_record(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    action,
                    "version",
                    next_version.id,
                    context,
                    now,
                    change_set_id=change_set_id,
                    version_id=next_version.id,
                )
            )
            await uow.commit()
            return record

    def _operations_from_candidates(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        candidates: tuple[ProviderOperationCandidate, ...],
        evidence: tuple[EvidenceGroundingContext, ...],
        job: JobMatchAnalysisContext,
        now: datetime,
        *,
        start_order: int,
    ) -> tuple[tuple[ChangeOperation, ...], tuple[ChangeClaim, ...]]:
        evidence_map = {item.id: item for item in evidence}
        requirement_map = {item.requirement.id: item.requirement for item in job.requirements}
        operations: list[ChangeOperation] = []
        claims: list[ChangeClaim] = []
        for index, candidate in enumerate(candidates):
            decision = ground_operation(
                candidate,
                evidence=evidence_map,
                requirements=requirement_map,
            )
            requirement = (
                requirement_map[candidate.requirement_ids[0]]
                if candidate.requirement_ids and candidate.requirement_ids[0] in requirement_map
                else None
            )
            operation = ChangeOperation(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                change_set_id=change_set_id,
                operation_type=candidate.operation_type,
                target_kind=candidate.target_kind,
                target_id=candidate.target_id,
                before_text=candidate.before,
                after_text=candidate.after,
                reason=candidate.reason,
                status=(
                    ChangeOperationStatus.PROPOSED
                    if decision.status is GroundingStatus.GROUNDED
                    else ChangeOperationStatus.BLOCKED
                ),
                risk=candidate.risk,
                confidence_basis_points=candidate.confidence_basis_points,
                requires_confirmation=candidate.requires_confirmation,
                grounding_status=decision.status,
                grounding_codes=decision.codes,
                expected_score_delta_basis_points=_expected_score_delta(job, decision.status),
                requirement_id=requirement.id if requirement is not None else None,
                requirement_text=requirement.text if requirement is not None else None,
                locked=False,
                sort_order=start_order + index * 10,
                version=1,
                created_at=now,
                updated_at=now,
            )
            operations.append(operation)
            claims.extend(
                self._claims_from_decision(
                    owner_user_id,
                    change_set_id,
                    operation.id,
                    decision,
                    now,
                )
            )
        return tuple(operations), tuple(claims)

    def _claims_from_decision(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        operation_id: UUID,
        decision: GroundingDecision,
        now: datetime,
    ) -> tuple[ChangeClaim, ...]:
        return tuple(
            ChangeClaim(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                change_set_id=change_set_id,
                operation_id=operation_id,
                claim_kind=claim.candidate.kind,
                text=claim.candidate.text,
                evidence_id=claim.evidence.id,
                evidence_revision_id=claim.evidence.evidence_revision_id,
                evidence_revision_number=claim.evidence.revision_number,
                evidence_statement_sha256=claim.evidence.statement_sha256,
                evidence_title=claim.evidence.title,
                evidence_strength=claim.evidence.strength,
                source_excerpt=claim.evidence.statement[:1_500],
                validation_status=claim.status,
                validation_codes=claim.codes,
                sort_order=index * 10,
                created_at=now,
            )
            for index, claim in enumerate(decision.claims, start=1)
        )

    def _questions_from_candidates(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        candidates: tuple[ProviderQuestionCandidate, ...],
        evidence: tuple[EvidenceGroundingContext, ...],
        job: JobMatchAnalysisContext,
        now: datetime,
    ) -> tuple[ClarifyingQuestion, ...]:
        evidence_map = {item.id: item for item in evidence}
        requirement_map = {item.requirement.id: item.requirement for item in job.requirements}
        questions: list[ClarifyingQuestion] = []
        for candidate in candidates:
            codes = validate_question(
                candidate,
                requirements=requirement_map,
                evidence=evidence_map,
            )
            if codes != ("question_valid",):
                continue
            questions.append(
                ClarifyingQuestion(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    change_set_id=change_set_id,
                    operation_id=None,
                    requirement_id=candidate.requirement_id,
                    evidence_id=candidate.evidence_id,
                    question=candidate.question,
                    reason=candidate.reason,
                    status=ClarificationStatus.OPEN,
                    answer_text=None,
                    answered_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        return tuple(questions)

    def _missing_evidence_questions(
        self,
        owner_user_id: UUID,
        change_set_id: UUID,
        job: JobMatchAnalysisContext,
        evidence: tuple[EvidenceGroundingContext, ...],
        operations: tuple[ChangeOperation, ...],
        now: datetime,
    ) -> tuple[ClarifyingQuestion, ...]:
        evidence_ids = {item.id for item in evidence}
        covered = {operation.requirement_id for operation in operations if operation.acceptable}
        questions: list[ClarifyingQuestion] = []
        for item in job.requirements:
            if item.requirement.id in covered:
                continue
            if item.evidence_ids and any(
                evidence_id in evidence_ids for evidence_id in item.evidence_ids
            ):
                continue
            if len(questions) >= 5:
                break
            questions.append(
                ClarifyingQuestion(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    change_set_id=change_set_id,
                    operation_id=None,
                    requirement_id=item.requirement.id,
                    evidence_id=None,
                    question=f"What evidence can support this requirement: {item.requirement.text}",
                    reason=(
                        "No currently eligible evidence can ground a resume change for "
                        "this requirement."
                    ),
                    status=ClarificationStatus.OPEN,
                    answer_text=None,
                    answered_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        return tuple(questions)

    async def _load_evidence(
        self, owner_user_id: UUID, job: JobMatchAnalysisContext
    ) -> tuple[EvidenceGroundingContext, ...]:
        ids = tuple(
            dict.fromkeys(
                evidence_id
                for requirement in job.requirements[: self._policy.max_requirements]
                for evidence_id in requirement.evidence_ids
            )
        )[: self._policy.max_evidence]
        return await self._evidence.evidence_contexts(owner_user_id, ids)

    async def _operation_evidence(
        self, owner_user_id: UUID, record: ChangeSetRecord, operation: ChangeOperation
    ) -> tuple[EvidenceGroundingContext, ...]:
        evidence_ids = tuple(
            dict.fromkeys(
                claim.evidence_id for claim in record.claims if claim.operation_id == operation.id
            )
        )
        return await self._evidence.evidence_contexts(owner_user_id, evidence_ids)

    def _operation_requirement(
        self, record: ChangeSetRecord, operation: ChangeOperation
    ) -> RequirementGroundingContext | None:
        if operation.requirement_id is None or operation.requirement_text is None:
            return None
        return RequirementGroundingContext(
            id=operation.requirement_id,
            text=operation.requirement_text,
            requirement_type="other",
            importance="mandatory",
        )

    async def _record_for_update(
        self, uow: ChangeStudioUnitOfWork, owner_user_id: UUID, change_set_id: UUID
    ) -> ChangeSetRecord:
        record = await uow.get_record(owner_user_id, change_set_id, for_update=True)
        if record is None:
            raise ChangeStudioNotFound
        return record

    async def _idempotent_action(
        self,
        uow: ChangeStudioUnitOfWork,
        owner_user_id: UUID,
        idempotency_key: str,
        fingerprint: str,
        target_kind: str,
        target_id: UUID,
        now: datetime,
    ) -> bool:
        existing = await uow.find_idempotency(owner_user_id, idempotency_key)
        if existing is not None:
            if existing.idempotency_fingerprint != fingerprint:
                raise ChangeStudioIdempotencyConflict
            return True
        await uow.add_idempotency(
            ChangeStudioIdempotencyRecord(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=fingerprint,
                target_kind=target_kind,
                target_id=target_id,
                created_at=now,
            )
        )
        return False

    def _append_version(
        self, record: ChangeSetRecord, operation: ChangeOperation, now: datetime
    ) -> ChangeSetRecord:
        current = self._current_version(record)
        content_parts = [
            part for part in (current.content.strip(), operation.after_text.strip()) if part
        ]
        version = ChangeSetVersion(
            id=self._ids.new(),
            owner_user_id=record.change_set.owner_user_id,
            change_set_id=record.change_set.id,
            version_number=max(item.version_number for item in record.versions) + 1,
            parent_version_id=current.id,
            created_by_operation_id=operation.id,
            title=f"Accepted change {operation.sort_order // 10}",
            content="\n".join(content_parts),
            operation_ids=(*current.operation_ids, operation.id),
            created_at=now,
        )
        record.change_set.current_version_id = version.id
        return replace(record, versions=(*record.versions, version))

    def _current_version(self, record: ChangeSetRecord) -> ChangeSetVersion:
        if record.change_set.current_version_id is None:
            raise ChangeStudioConflict("change set has no current version")
        return self._version_by_id(record, record.change_set.current_version_id)

    @staticmethod
    def _version_by_id(record: ChangeSetRecord, version_id: UUID) -> ChangeSetVersion:
        for version in record.versions:
            if version.id == version_id:
                return version
        raise ChangeStudioNotFound

    @staticmethod
    def _operation(record: ChangeSetRecord, operation_id: UUID) -> ChangeOperation:
        for operation in record.operations:
            if operation.id == operation_id:
                return operation
        raise ChangeStudioNotFound

    @staticmethod
    def _parse_provider(
        payload: dict[str, object],
    ) -> tuple[ProviderCandidateResponse, tuple[str, ...]]:
        try:
            return parse_provider_payload(payload), ("schema_valid",)
        except ProviderOutputRejected:
            raise
        except (TypeError, ValueError) as exc:
            raise ProviderOutputRejected("provider output failed strict schema validation") from exc

    @staticmethod
    def _authorize(owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise ChangeStudioNotFound

    @staticmethod
    def _idempotency(value: str) -> None:
        from careeros.modules.change_studio.domain.entities import _idempotency

        _idempotency(value)

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if not 1 <= expected <= 2_147_483_647:
            raise ChangeStudioValidationError("expected version must be a positive int32")
        if actual != expected:
            raise ChangeStudioVersionConflict

    @staticmethod
    def _style(tone: str, length: str) -> None:
        if tone not in {"direct", "warm", "technical"}:
            raise ChangeStudioValidationError("tone is not supported")
        if length not in {"concise", "standard"}:
            raise ChangeStudioValidationError("length is not supported")

    def _audit(
        self,
        owner_user_id: UUID,
        action: ChangeAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        **details: UUID | str | None,
    ) -> ChangeStudioAuditEvent:
        return ChangeStudioAuditEvent(
            id=self._ids.new(),
            owner_user_id=owner_user_id,
            actor_user_id=context.actor_user_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            details=tuple((key, str(value)) for key, value in details.items() if value is not None),
            created_at=created_at,
        )


def _candidate_from_operation(
    operation: ChangeOperation,
    claims: tuple[ChangeClaim, ...],
) -> ProviderOperationCandidate:
    from careeros.modules.change_studio.domain import (
        ProviderClaimCandidate,
        ProviderOperationCandidate,
    )

    operation_claims = tuple(claim for claim in claims if claim.operation_id == operation.id)
    return ProviderOperationCandidate(
        operation_type=operation.operation_type,
        target_id=operation.target_id,
        target_kind=operation.target_kind,
        before=operation.before_text,
        after=operation.after_text,
        reason=operation.reason,
        claims=tuple(
            ProviderClaimCandidate(
                text=claim.text,
                kind=claim.claim_kind,
                evidence_ids=(claim.evidence_id,),
            )
            for claim in operation_claims
        ),
        requirement_ids=(
            (operation.requirement_id,) if operation.requirement_id is not None else ()
        ),
        confidence_basis_points=operation.confidence_basis_points,
        risk=operation.risk,
        requires_confirmation=operation.requires_confirmation,
        expected_score_delta_basis_points=operation.expected_score_delta_basis_points,
    )


def _has_number(value: str) -> bool:
    return any(character.isdigit() for character in value)


def _expected_score_delta(
    job: JobMatchAnalysisContext,
    grounding_status: GroundingStatus,
) -> int | None:
    if job.display_score is None or grounding_status is not GroundingStatus.GROUNDED:
        return None
    return 150


def _request_fingerprint(request: AiGenerationRequest) -> str:
    return _fingerprint(
        "ai-generation-request",
        {
            "purpose": request.purpose,
            "targetKind": request.target_kind.value,
            "tone": request.tone,
            "length": request.length,
            "jobId": str(request.job.job_id),
            "analysisId": str(request.job.analysis_id),
            "evidenceIds": [str(item.id) for item in request.evidence],
            "requirementIds": [str(item.requirement.id) for item in request.job.requirements],
            "alternativeForOperationId": (
                str(request.alternative_for_operation_id)
                if request.alternative_for_operation_id is not None
                else None
            ),
            "preserveTerms": list(request.preserve_terms),
        },
    )


def _fingerprint(kind: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        {"kind": kind, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
