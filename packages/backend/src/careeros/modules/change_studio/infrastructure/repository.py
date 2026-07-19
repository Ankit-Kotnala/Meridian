"""Async SQLAlchemy unit of work for Change Studio."""

from __future__ import annotations

from types import TracebackType
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.change_studio.application.models import ChangeSetRecord
from careeros.modules.change_studio.application.ports import ChangeStudioUnitOfWork
from careeros.modules.change_studio.domain import (
    ChangeClaim,
    ChangeOperation,
    ChangeOperationStatus,
    ChangeOperationType,
    ChangeSet,
    ChangeSetPurpose,
    ChangeSetStatus,
    ChangeSetVersion,
    ChangeStudioAuditEvent,
    ChangeStudioConflict,
    ChangeStudioIdempotencyRecord,
    ChangeStudioUnavailable,
    ChangeTargetKind,
    ClaimKind,
    ClarificationStatus,
    ClarifyingQuestion,
    GroundingStatus,
    ProviderRun,
    ProviderRunStatus,
    RiskLevel,
    ValidationStatus,
)

from .models import (
    ChangeClaimModel,
    ChangeOperationModel,
    ChangeSetModel,
    ChangeSetVersionModel,
    ChangeStudioAuditEventModel,
    ChangeStudioIdempotencyModel,
    ClarifyingQuestionModel,
    ProviderRunModel,
)


class SqlAlchemyChangeStudioUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyChangeStudioUnitOfWork:
        self._session = await self._session_context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("change studio unit of work is not active")
        return self._session

    async def add_record(self, record: ChangeSetRecord) -> None:
        _validate_record_ownership(record)
        self.session.add(ChangeSetModel(**_change_set_values(record.change_set)))
        await self._flush()
        self.session.add_all(_operation_model(operation) for operation in record.operations)
        await self._flush()
        self.session.add_all(_version_model(version) for version in record.versions)
        self.session.add_all(_claim_model(claim) for claim in record.claims)
        self.session.add_all(_question_model(question) for question in record.questions)
        self.session.add_all(_provider_run_model(run) for run in record.provider_runs)
        await self._flush()

    async def save_record(self, record: ChangeSetRecord) -> None:
        _validate_record_ownership(record)
        await self._execute(
            update(ChangeSetModel)
            .where(
                ChangeSetModel.owner_user_id == record.change_set.owner_user_id,
                ChangeSetModel.id == record.change_set.id,
            )
            .values(**_change_set_values(record.change_set, include_identity=False))
        )
        for operation in record.operations:
            await self.session.merge(_operation_model(operation))
        for question in record.questions:
            await self.session.merge(_question_model(question))
        for version in record.versions:
            await self.session.merge(_version_model(version))
        await self._execute(
            delete(ChangeClaimModel).where(
                ChangeClaimModel.owner_user_id == record.change_set.owner_user_id,
                ChangeClaimModel.change_set_id == record.change_set.id,
            )
        )
        self.session.add_all(_claim_model(claim) for claim in record.claims)
        await self._flush()

    async def get_record(
        self, owner_user_id: UUID, change_set_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None:
        statement = select(ChangeSetModel).where(
            ChangeSetModel.owner_user_id == owner_user_id,
            ChangeSetModel.id == change_set_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        return await self._record_from_model(model)

    async def get_record_for_question(
        self, owner_user_id: UUID, question_id: UUID, *, for_update: bool = False
    ) -> ChangeSetRecord | None:
        statement = select(ClarifyingQuestionModel).where(
            ClarifyingQuestionModel.owner_user_id == owner_user_id,
            ClarifyingQuestionModel.id == question_id,
        )
        if for_update:
            statement = statement.with_for_update()
        question = await self.session.scalar(statement)
        if question is None:
            return None
        return await self.get_record(owner_user_id, question.change_set_id, for_update=for_update)

    async def find_change_set_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeSetRecord | None:
        model = await self.session.scalar(
            select(ChangeSetModel).where(
                ChangeSetModel.owner_user_id == owner_user_id,
                ChangeSetModel.idempotency_key == idempotency_key,
            )
        )
        if model is None:
            return None
        return await self._record_from_model(model)

    async def find_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> ChangeStudioIdempotencyRecord | None:
        model = await self.session.scalar(
            select(ChangeStudioIdempotencyModel).where(
                ChangeStudioIdempotencyModel.owner_user_id == owner_user_id,
                ChangeStudioIdempotencyModel.idempotency_key == idempotency_key,
            )
        )
        return _idempotency(model) if model is not None else None

    async def add_idempotency(self, record: ChangeStudioIdempotencyRecord) -> None:
        self.session.add(_idempotency_model(record))
        await self._flush()

    async def add_provider_run(self, run: ProviderRun) -> None:
        self.session.add(_provider_run_model(run))
        await self._flush()

    async def add_audit(self, event: ChangeStudioAuditEvent) -> None:
        self.session.add(_audit_model(event))

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _record_from_model(self, model: ChangeSetModel) -> ChangeSetRecord:
        owner_user_id = model.owner_user_id
        change_set_id = model.id
        operations = (
            await self.session.scalars(
                select(ChangeOperationModel)
                .where(
                    ChangeOperationModel.owner_user_id == owner_user_id,
                    ChangeOperationModel.change_set_id == change_set_id,
                )
                .order_by(ChangeOperationModel.sort_order, ChangeOperationModel.id)
            )
        ).all()
        claims = (
            await self.session.scalars(
                select(ChangeClaimModel)
                .where(
                    ChangeClaimModel.owner_user_id == owner_user_id,
                    ChangeClaimModel.change_set_id == change_set_id,
                )
                .order_by(
                    ChangeClaimModel.operation_id,
                    ChangeClaimModel.sort_order,
                    ChangeClaimModel.id,
                )
            )
        ).all()
        questions = (
            await self.session.scalars(
                select(ClarifyingQuestionModel)
                .where(
                    ClarifyingQuestionModel.owner_user_id == owner_user_id,
                    ClarifyingQuestionModel.change_set_id == change_set_id,
                )
                .order_by(ClarifyingQuestionModel.created_at, ClarifyingQuestionModel.id)
            )
        ).all()
        versions = (
            await self.session.scalars(
                select(ChangeSetVersionModel)
                .where(
                    ChangeSetVersionModel.owner_user_id == owner_user_id,
                    ChangeSetVersionModel.change_set_id == change_set_id,
                )
                .order_by(ChangeSetVersionModel.version_number, ChangeSetVersionModel.id)
            )
        ).all()
        provider_runs = (
            await self.session.scalars(
                select(ProviderRunModel)
                .where(
                    ProviderRunModel.owner_user_id == owner_user_id,
                    ProviderRunModel.change_set_id == change_set_id,
                )
                .order_by(ProviderRunModel.created_at, ProviderRunModel.id)
            )
        ).all()
        return ChangeSetRecord(
            change_set=_change_set(model),
            operations=tuple(_operation(item) for item in operations),
            claims=tuple(_claim(item) for item in claims),
            questions=tuple(_question(item) for item in questions),
            versions=tuple(_version(item) for item in versions),
            provider_runs=tuple(_provider_run(item) for item in provider_runs),
        )

    async def _execute(self, statement: Any) -> None:
        try:
            await self.session.execute(statement)
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)


class SqlAlchemyChangeStudioUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> ChangeStudioUnitOfWork:
        return SqlAlchemyChangeStudioUnitOfWork(self._database)


def _change_set(model: ChangeSetModel) -> ChangeSet:
    return ChangeSet(
        id=model.id,
        owner_user_id=model.owner_user_id,
        purpose=ChangeSetPurpose(model.purpose),
        target_kind=ChangeTargetKind(model.target_kind),
        status=ChangeSetStatus(model.status),
        job_id=model.job_id,
        analysis_id=model.analysis_id,
        current_version_id=model.current_version_id,
        provider_name=model.provider_name,
        provider_model=model.provider_model,
        prompt_version=model.prompt_version,
        policy_version=model.policy_version,
        schema_version=model.schema_version,
        grounding_version=model.grounding_version,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _change_set_values(
    change_set: ChangeSet, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "purpose": change_set.purpose.value,
        "target_kind": change_set.target_kind.value,
        "status": change_set.status.value,
        "job_id": change_set.job_id,
        "analysis_id": change_set.analysis_id,
        "current_version_id": change_set.current_version_id,
        "provider_name": change_set.provider_name,
        "provider_model": change_set.provider_model,
        "prompt_version": change_set.prompt_version,
        "policy_version": change_set.policy_version,
        "schema_version": change_set.schema_version,
        "grounding_version": change_set.grounding_version,
        "idempotency_key": change_set.idempotency_key,
        "idempotency_fingerprint": change_set.idempotency_fingerprint,
        "version": change_set.version,
        "created_at": change_set.created_at,
        "updated_at": change_set.updated_at,
    }
    if include_identity:
        values["id"] = change_set.id
        values["owner_user_id"] = change_set.owner_user_id
    return values


def _operation(model: ChangeOperationModel) -> ChangeOperation:
    return ChangeOperation(
        id=model.id,
        owner_user_id=model.owner_user_id,
        change_set_id=model.change_set_id,
        operation_type=ChangeOperationType(model.operation_type),
        target_kind=ChangeTargetKind(model.target_kind),
        target_id=model.target_id,
        before_text=model.before_text,
        after_text=model.after_text,
        reason=model.reason,
        status=ChangeOperationStatus(model.status),
        risk=RiskLevel(model.risk),
        confidence_basis_points=model.confidence_basis_points,
        requires_confirmation=model.requires_confirmation,
        grounding_status=GroundingStatus(model.grounding_status),
        grounding_codes=tuple(model.grounding_codes),
        expected_score_delta_basis_points=model.expected_score_delta_basis_points,
        requirement_id=model.requirement_id,
        requirement_text=model.requirement_text,
        locked=model.locked,
        sort_order=model.sort_order,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _operation_model(operation: ChangeOperation) -> ChangeOperationModel:
    return ChangeOperationModel(
        id=operation.id,
        owner_user_id=operation.owner_user_id,
        change_set_id=operation.change_set_id,
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
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


def _claim(model: ChangeClaimModel) -> ChangeClaim:
    return ChangeClaim(
        id=model.id,
        owner_user_id=model.owner_user_id,
        change_set_id=model.change_set_id,
        operation_id=model.operation_id,
        claim_kind=ClaimKind(model.claim_kind),
        text=model.text,
        evidence_id=model.evidence_id,
        evidence_title=model.evidence_title,
        evidence_strength=model.evidence_strength,
        source_excerpt=model.source_excerpt,
        validation_status=ValidationStatus(model.validation_status),
        validation_codes=tuple(model.validation_codes),
        sort_order=model.sort_order,
        created_at=model.created_at,
    )


def _claim_model(claim: ChangeClaim) -> ChangeClaimModel:
    return ChangeClaimModel(
        id=claim.id,
        owner_user_id=claim.owner_user_id,
        change_set_id=claim.change_set_id,
        operation_id=claim.operation_id,
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


def _question(model: ClarifyingQuestionModel) -> ClarifyingQuestion:
    return ClarifyingQuestion(
        id=model.id,
        owner_user_id=model.owner_user_id,
        change_set_id=model.change_set_id,
        operation_id=model.operation_id,
        requirement_id=model.requirement_id,
        evidence_id=model.evidence_id,
        question=model.question,
        reason=model.reason,
        status=ClarificationStatus(model.status),
        answer_text=model.answer_text,
        answered_at=model.answered_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _question_model(question: ClarifyingQuestion) -> ClarifyingQuestionModel:
    return ClarifyingQuestionModel(
        id=question.id,
        owner_user_id=question.owner_user_id,
        change_set_id=question.change_set_id,
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


def _version(model: ChangeSetVersionModel) -> ChangeSetVersion:
    return ChangeSetVersion(
        id=model.id,
        owner_user_id=model.owner_user_id,
        change_set_id=model.change_set_id,
        version_number=model.version_number,
        parent_version_id=model.parent_version_id,
        created_by_operation_id=model.created_by_operation_id,
        title=model.title,
        content=model.content,
        operation_ids=tuple(UUID(value) for value in model.operation_ids),
        created_at=model.created_at,
    )


def _version_model(version: ChangeSetVersion) -> ChangeSetVersionModel:
    return ChangeSetVersionModel(
        id=version.id,
        owner_user_id=version.owner_user_id,
        change_set_id=version.change_set_id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        created_by_operation_id=version.created_by_operation_id,
        title=version.title,
        content=version.content,
        operation_ids=[str(value) for value in version.operation_ids],
        created_at=version.created_at,
    )


def _provider_run(model: ProviderRunModel) -> ProviderRun:
    return ProviderRun(
        id=model.id,
        owner_user_id=model.owner_user_id,
        change_set_id=model.change_set_id,
        provider_name=model.provider_name,
        provider_model=model.provider_model,
        operation=model.operation,
        prompt_version=model.prompt_version,
        policy_version=model.policy_version,
        schema_version=model.schema_version,
        grounding_version=model.grounding_version,
        request_fingerprint=model.request_fingerprint,
        input_evidence_ids=tuple(UUID(value) for value in model.input_evidence_ids),
        input_requirement_ids=tuple(UUID(value) for value in model.input_requirement_ids),
        output_operation_count=model.output_operation_count,
        status=ProviderRunStatus(model.status),
        latency_ms=model.latency_ms,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        cost_micros=model.cost_micros,
        validation_codes=tuple(model.validation_codes),
        created_at=model.created_at,
    )


def _provider_run_model(run: ProviderRun) -> ProviderRunModel:
    return ProviderRunModel(
        id=run.id,
        owner_user_id=run.owner_user_id,
        change_set_id=run.change_set_id,
        provider_name=run.provider_name,
        provider_model=run.provider_model,
        operation=run.operation,
        prompt_version=run.prompt_version,
        policy_version=run.policy_version,
        schema_version=run.schema_version,
        grounding_version=run.grounding_version,
        request_fingerprint=run.request_fingerprint,
        input_evidence_ids=[str(value) for value in run.input_evidence_ids],
        input_requirement_ids=[str(value) for value in run.input_requirement_ids],
        output_operation_count=run.output_operation_count,
        status=run.status.value,
        latency_ms=run.latency_ms,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        cost_micros=run.cost_micros,
        validation_codes=list(run.validation_codes),
        created_at=run.created_at,
    )


def _idempotency(model: ChangeStudioIdempotencyModel) -> ChangeStudioIdempotencyRecord:
    return ChangeStudioIdempotencyRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        target_kind=model.target_kind,
        target_id=model.target_id,
        created_at=model.created_at,
    )


def _idempotency_model(record: ChangeStudioIdempotencyRecord) -> ChangeStudioIdempotencyModel:
    return ChangeStudioIdempotencyModel(
        id=record.id,
        owner_user_id=record.owner_user_id,
        idempotency_key=record.idempotency_key,
        idempotency_fingerprint=record.idempotency_fingerprint,
        target_kind=record.target_kind,
        target_id=record.target_id,
        created_at=record.created_at,
    )


def _audit_model(event: ChangeStudioAuditEvent) -> ChangeStudioAuditEventModel:
    return ChangeStudioAuditEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        action=event.action.value,
        target_kind=event.target_kind,
        target_id=event.target_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        details=[{"key": key, "value": value} for key, value in event.details],
        created_at=event.created_at,
    )


def _validate_record_ownership(record: ChangeSetRecord) -> None:
    owner_user_id = record.change_set.owner_user_id
    change_set_id = record.change_set.id
    operation_ids = {operation.id for operation in record.operations}
    version_ids = {version.id for version in record.versions}
    if (
        record.change_set.current_version_id is not None
        and record.change_set.current_version_id not in version_ids
    ):
        raise ChangeStudioConflict("change set current version is missing")
    for operation in record.operations:
        if operation.owner_user_id != owner_user_id or operation.change_set_id != change_set_id:
            raise ChangeStudioConflict("change operation ownership mismatch")
    for claim in record.claims:
        if (
            claim.owner_user_id != owner_user_id
            or claim.change_set_id != change_set_id
            or claim.operation_id not in operation_ids
        ):
            raise ChangeStudioConflict("change claim ownership mismatch")
    for question in record.questions:
        if question.owner_user_id != owner_user_id or question.change_set_id != change_set_id:
            raise ChangeStudioConflict("clarifying question ownership mismatch")
        if question.operation_id is not None and question.operation_id not in operation_ids:
            raise ChangeStudioConflict("clarifying question operation mismatch")
    for version in record.versions:
        if version.owner_user_id != owner_user_id or version.change_set_id != change_set_id:
            raise ChangeStudioConflict("change version ownership mismatch")
        if (
            version.created_by_operation_id is not None
            and version.created_by_operation_id not in operation_ids
        ):
            raise ChangeStudioConflict("change version operation mismatch")
    for run in record.provider_runs:
        if run.owner_user_id != owner_user_id or run.change_set_id != change_set_id:
            raise ChangeStudioConflict("provider run ownership mismatch")


def _raise_integrity(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc)).casefold()
    if "foreign key" in message:
        raise ChangeStudioUnavailable from exc
    raise ChangeStudioConflict from exc
