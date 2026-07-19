"""Async SQLAlchemy unit of work for Job Match."""

from __future__ import annotations

from collections import defaultdict
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.job_match.application.models import (
    AnalysisRecord,
    JobFilter,
    JobRecord,
    PageCursor,
)
from careeros.modules.job_match.application.ports import JobMatchUnitOfWork
from careeros.modules.job_match.domain import (
    ApplicationReadinessLabel,
    EmploymentType,
    JobMatchAnalysis,
    JobMatchAuditEvent,
    JobMatchComponent,
    JobMatchConflict,
    JobMatchUnavailable,
    JobPosting,
    JobRequirement,
    JobSourceKind,
    OpportunityPriorityAnalysis,
    OpportunityPriorityLabel,
    RequirementEvidenceLink,
    RequirementImportance,
    RequirementMatch,
    RequirementMatchState,
    RequirementType,
    WorkModel,
)

from .models import (
    JobMatchAnalysisModel,
    JobMatchAuditEventModel,
    JobMatchComponentModel,
    JobPostingModel,
    JobRequirementModel,
    OpportunityPriorityModel,
    RequirementEvidenceLinkModel,
    RequirementMatchModel,
)


class SqlAlchemyJobMatchUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyJobMatchUnitOfWork:
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
            raise RuntimeError("job match unit of work is not active")
        return self._session

    async def add_job(self, record: JobRecord) -> None:
        _validate_job_ownership(record)
        self.session.add(JobPostingModel(**_job_values(record.job)))
        await self._flush()
        self.session.add_all(_requirement_model(requirement) for requirement in record.requirements)
        await self._flush()

    async def save_job(self, record: JobRecord) -> None:
        _validate_job_ownership(record)
        await self._execute(
            update(JobPostingModel)
            .where(
                JobPostingModel.owner_user_id == record.job.owner_user_id,
                JobPostingModel.id == record.job.id,
            )
            .values(**_job_values(record.job, include_identity=False))
        )
        await self._execute(
            delete(JobRequirementModel).where(
                JobRequirementModel.owner_user_id == record.job.owner_user_id,
                JobRequirementModel.job_id == record.job.id,
            )
        )
        self.session.add_all(_requirement_model(requirement) for requirement in record.requirements)
        await self._flush()

    async def get_job(
        self, owner_user_id: UUID, job_id: UUID, *, for_update: bool = False
    ) -> JobRecord | None:
        statement = select(JobPostingModel).where(
            JobPostingModel.owner_user_id == owner_user_id,
            JobPostingModel.id == job_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        if model is None:
            return None
        return JobRecord(job=_job(model), requirements=tuple(await self._requirements(model.id)))

    async def list_jobs(
        self, owner_user_id: UUID, filter_by: JobFilter, after: PageCursor | None, limit: int
    ) -> list[JobRecord]:
        statement = select(JobPostingModel).where(JobPostingModel.owner_user_id == owner_user_id)
        if filter_by.source_kind is not None:
            statement = statement.where(JobPostingModel.source_kind == filter_by.source_kind.value)
        if filter_by.target_role_id is not None:
            statement = statement.where(JobPostingModel.target_role_id == filter_by.target_role_id)
        if filter_by.query is not None:
            pattern = _pattern(filter_by.query)
            statement = statement.where(
                or_(
                    JobPostingModel.title.ilike(pattern),
                    JobPostingModel.company.ilike(pattern),
                    JobPostingModel.location.ilike(pattern),
                    JobPostingModel.source_text.ilike(pattern),
                )
            )
        models = (
            await self.session.scalars(
                statement.order_by(JobPostingModel.updated_at.desc(), JobPostingModel.id.desc())
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [
            JobRecord(job=_job(model), requirements=tuple(await self._requirements(model.id)))
            for model in models
        ]

    async def delete_job(self, owner_user_id: UUID, job_id: UUID) -> None:
        await self._execute(
            delete(JobPostingModel).where(
                JobPostingModel.owner_user_id == owner_user_id,
                JobPostingModel.id == job_id,
            )
        )

    async def find_job_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> JobRecord | None:
        model = await self.session.scalar(
            select(JobPostingModel).where(
                JobPostingModel.owner_user_id == owner_user_id,
                JobPostingModel.idempotency_key == idempotency_key,
            )
        )
        if model is None:
            return None
        return JobRecord(job=_job(model), requirements=tuple(await self._requirements(model.id)))

    async def add_analysis(self, record: AnalysisRecord) -> None:
        _validate_analysis_ownership(record)
        self.session.add(JobMatchAnalysisModel(**_analysis_values(record.analysis)))
        await self._flush()
        self.session.add_all(_component_model(component) for component in record.components)
        self.session.add_all(_match_model(match) for match in record.requirement_matches)
        await self._flush()
        self.session.add_all(_link_model(link) for link in record.evidence_links)
        await self._flush()

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> AnalysisRecord | None:
        model = await self.session.scalar(
            select(JobMatchAnalysisModel).where(
                JobMatchAnalysisModel.owner_user_id == owner_user_id,
                JobMatchAnalysisModel.id == analysis_id,
            )
        )
        records = await self._analysis_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def latest_analysis_for_job(
        self, owner_user_id: UUID, job_id: UUID
    ) -> AnalysisRecord | None:
        model = await self.session.scalar(
            select(JobMatchAnalysisModel)
            .where(
                JobMatchAnalysisModel.owner_user_id == owner_user_id,
                JobMatchAnalysisModel.job_id == job_id,
            )
            .order_by(JobMatchAnalysisModel.created_at.desc(), JobMatchAnalysisModel.id.desc())
            .limit(1)
        )
        records = await self._analysis_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None:
        model = await self.session.scalar(
            select(JobMatchAnalysisModel).where(
                JobMatchAnalysisModel.owner_user_id == owner_user_id,
                JobMatchAnalysisModel.idempotency_key == idempotency_key,
            )
        )
        records = await self._analysis_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def add_priority(self, priority: OpportunityPriorityAnalysis) -> None:
        self.session.add(OpportunityPriorityModel(**_priority_values(priority)))
        await self._flush()

    async def get_priority(
        self, owner_user_id: UUID, priority_id: UUID
    ) -> OpportunityPriorityAnalysis | None:
        model = await self.session.scalar(
            select(OpportunityPriorityModel).where(
                OpportunityPriorityModel.owner_user_id == owner_user_id,
                OpportunityPriorityModel.id == priority_id,
            )
        )
        return _priority(model) if model is not None else None

    async def find_priority_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> OpportunityPriorityAnalysis | None:
        model = await self.session.scalar(
            select(OpportunityPriorityModel).where(
                OpportunityPriorityModel.owner_user_id == owner_user_id,
                OpportunityPriorityModel.idempotency_key == idempotency_key,
            )
        )
        return _priority(model) if model is not None else None

    async def add_audit(self, event: JobMatchAuditEvent) -> None:
        self.session.add(_audit_model(event))

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _requirements(self, job_id: UUID) -> list[JobRequirement]:
        models = (
            await self.session.scalars(
                select(JobRequirementModel)
                .where(JobRequirementModel.job_id == job_id)
                .order_by(JobRequirementModel.sort_order, JobRequirementModel.id)
            )
        ).all()
        return [_requirement(model) for model in models]

    async def _analysis_records(
        self, owner_user_id: UUID, analyses: list[JobMatchAnalysisModel]
    ) -> list[AnalysisRecord]:
        if not analyses:
            return []
        analysis_ids = [analysis.id for analysis in analyses]
        components = await self._group_models(
            JobMatchComponentModel,
            JobMatchComponentModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        matches = await self._group_models(
            RequirementMatchModel,
            RequirementMatchModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        links = await self._group_models(
            RequirementEvidenceLinkModel,
            RequirementEvidenceLinkModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        return [
            AnalysisRecord(
                analysis=_analysis(analysis),
                components=tuple(_component(model) for model in components[analysis.id]),
                requirement_matches=tuple(_match(model) for model in matches[analysis.id]),
                evidence_links=tuple(_link(model) for model in links[analysis.id]),
            )
            for analysis in analyses
        ]

    async def _group_models(
        self,
        model_type: type[Any],
        group_column: Any,
        owner_user_id: UUID,
        analysis_ids: list[UUID],
    ) -> defaultdict[UUID, list[Any]]:
        models = (
            await self.session.scalars(
                select(model_type)
                .where(
                    model_type.owner_user_id == owner_user_id,
                    group_column.in_(analysis_ids),
                )
                .order_by(group_column, model_type.id)
            )
        ).all()
        result: defaultdict[UUID, list[Any]] = defaultdict(list)
        for model in models:
            result[cast(UUID, model.analysis_id)].append(model)
        return result

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


class SqlAlchemyJobMatchUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> JobMatchUnitOfWork:
        return SqlAlchemyJobMatchUnitOfWork(self._database)


def _pattern(value: str) -> str:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _job(model: JobPostingModel) -> JobPosting:
    return JobPosting(
        id=model.id,
        owner_user_id=model.owner_user_id,
        title=model.title,
        company=model.company,
        location=model.location,
        work_model=WorkModel(model.work_model),
        employment_type=EmploymentType(model.employment_type),
        compensation=model.compensation,
        application_deadline=model.application_deadline,
        source_kind=JobSourceKind(model.source_kind),
        source_url=model.source_url,
        source_text=model.source_text,
        source_sha256=model.source_sha256,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        target_role_id=model.target_role_id,
        target_role_title=model.target_role_title,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _job_values(job: JobPosting, *, include_identity: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_model": job.work_model.value,
        "employment_type": job.employment_type.value,
        "compensation": job.compensation,
        "application_deadline": job.application_deadline,
        "source_kind": job.source_kind.value,
        "source_url": job.source_url,
        "source_text": job.source_text,
        "source_sha256": job.source_sha256,
        "idempotency_key": job.idempotency_key,
        "idempotency_fingerprint": job.idempotency_fingerprint,
        "target_role_id": job.target_role_id,
        "target_role_title": job.target_role_title,
        "version": job.version,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if include_identity:
        values["id"] = job.id
        values["owner_user_id"] = job.owner_user_id
    return values


def _requirement(model: JobRequirementModel) -> JobRequirement:
    return JobRequirement(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        requirement_type=RequirementType(model.requirement_type),
        text=model.text,
        normalized_text=model.normalized_text,
        importance=RequirementImportance(model.importance),
        source_start=model.source_start,
        source_end=model.source_end,
        confidence_basis_points=model.confidence_basis_points,
        sort_order=model.sort_order,
    )


def _requirement_model(requirement: JobRequirement) -> JobRequirementModel:
    return JobRequirementModel(
        id=requirement.id,
        owner_user_id=requirement.owner_user_id,
        job_id=requirement.job_id,
        requirement_type=requirement.requirement_type.value,
        text=requirement.text,
        normalized_text=requirement.normalized_text,
        importance=requirement.importance.value,
        source_start=requirement.source_start,
        source_end=requirement.source_end,
        confidence_basis_points=requirement.confidence_basis_points,
        sort_order=requirement.sort_order,
    )


def _analysis(model: JobMatchAnalysisModel) -> JobMatchAnalysis:
    return JobMatchAnalysis(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        engine_version=model.engine_version,
        configuration_version=model.configuration_version,
        feature_schema_version=model.feature_schema_version,
        input_snapshot=model.input_snapshot,
        feature_set_hash=model.feature_set_hash,
        raw_score_basis_points=model.raw_score_basis_points,
        display_score=model.display_score,
        readiness_label=ApplicationReadinessLabel(model.readiness_label),
        hard_gap_count=model.hard_gap_count,
        insufficient_reason=model.insufficient_reason,
        summary=model.summary,
        created_at=model.created_at,
    )


def _analysis_values(analysis: JobMatchAnalysis) -> dict[str, object]:
    return {
        "id": analysis.id,
        "owner_user_id": analysis.owner_user_id,
        "job_id": analysis.job_id,
        "idempotency_key": analysis.idempotency_key,
        "idempotency_fingerprint": analysis.idempotency_fingerprint,
        "engine_version": analysis.engine_version,
        "configuration_version": analysis.configuration_version,
        "feature_schema_version": analysis.feature_schema_version,
        "input_snapshot": analysis.input_snapshot,
        "feature_set_hash": analysis.feature_set_hash,
        "raw_score_basis_points": analysis.raw_score_basis_points,
        "display_score": analysis.display_score,
        "readiness_label": analysis.readiness_label.value,
        "hard_gap_count": analysis.hard_gap_count,
        "insufficient_reason": analysis.insufficient_reason,
        "summary": analysis.summary,
        "created_at": analysis.created_at,
    }


def _component(model: JobMatchComponentModel) -> JobMatchComponent:
    return JobMatchComponent(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        dimension=model.dimension,
        weight_basis_points=model.weight_basis_points,
        score_basis_points=model.score_basis_points,
        contribution_basis_points=model.contribution_basis_points,
        explanation=model.explanation,
    )


def _component_model(component: JobMatchComponent) -> JobMatchComponentModel:
    return JobMatchComponentModel(
        id=component.id,
        owner_user_id=component.owner_user_id,
        analysis_id=component.analysis_id,
        dimension=component.dimension,
        weight_basis_points=component.weight_basis_points,
        score_basis_points=component.score_basis_points,
        contribution_basis_points=component.contribution_basis_points,
        explanation=component.explanation,
    )


def _match(model: RequirementMatchModel) -> RequirementMatch:
    return RequirementMatch(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        requirement_id=model.requirement_id,
        requirement_text=model.requirement_text,
        requirement_type=RequirementType(model.requirement_type),
        importance=RequirementImportance(model.importance),
        match_state=RequirementMatchState(model.match_state),
        score_basis_points=model.score_basis_points,
        explanation=model.explanation,
        recommended_action=model.recommended_action,
        hard_gap=model.hard_gap,
    )


def _match_model(match: RequirementMatch) -> RequirementMatchModel:
    return RequirementMatchModel(
        id=match.id,
        owner_user_id=match.owner_user_id,
        analysis_id=match.analysis_id,
        requirement_id=match.requirement_id,
        requirement_text=match.requirement_text,
        requirement_type=match.requirement_type.value,
        importance=match.importance.value,
        match_state=match.match_state.value,
        score_basis_points=match.score_basis_points,
        explanation=match.explanation,
        recommended_action=match.recommended_action,
        hard_gap=match.hard_gap,
    )


def _link(model: RequirementEvidenceLinkModel) -> RequirementEvidenceLink:
    return RequirementEvidenceLink(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        requirement_match_id=model.requirement_match_id,
        evidence_id=model.evidence_id,
        evidence_title=model.evidence_title,
        evidence_strength=model.evidence_strength,
        relevance_basis_points=model.relevance_basis_points,
        rationale=model.rationale,
    )


def _link_model(link: RequirementEvidenceLink) -> RequirementEvidenceLinkModel:
    return RequirementEvidenceLinkModel(
        id=link.id,
        owner_user_id=link.owner_user_id,
        analysis_id=link.analysis_id,
        requirement_match_id=link.requirement_match_id,
        evidence_id=link.evidence_id,
        evidence_title=link.evidence_title,
        evidence_strength=link.evidence_strength,
        relevance_basis_points=link.relevance_basis_points,
        rationale=link.rationale,
    )


def _priority(model: OpportunityPriorityModel) -> OpportunityPriorityAnalysis:
    return OpportunityPriorityAnalysis(
        id=model.id,
        owner_user_id=model.owner_user_id,
        job_id=model.job_id,
        analysis_id=model.analysis_id,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        priority_label=OpportunityPriorityLabel(model.priority_label),
        priority_score_basis_points=model.priority_score_basis_points,
        input_snapshot=model.input_snapshot,
        reasons_for=tuple(model.reasons_for),
        reconsiderations=tuple(model.reconsiderations),
        blockers=tuple(model.blockers),
        next_action=model.next_action,
        created_at=model.created_at,
    )


def _priority_values(priority: OpportunityPriorityAnalysis) -> dict[str, object]:
    return {
        "id": priority.id,
        "owner_user_id": priority.owner_user_id,
        "job_id": priority.job_id,
        "analysis_id": priority.analysis_id,
        "idempotency_key": priority.idempotency_key,
        "idempotency_fingerprint": priority.idempotency_fingerprint,
        "priority_label": priority.priority_label.value,
        "priority_score_basis_points": priority.priority_score_basis_points,
        "input_snapshot": priority.input_snapshot,
        "reasons_for": list(priority.reasons_for),
        "reconsiderations": list(priority.reconsiderations),
        "blockers": list(priority.blockers),
        "next_action": priority.next_action,
        "created_at": priority.created_at,
    }


def _audit_model(event: JobMatchAuditEvent) -> JobMatchAuditEventModel:
    return JobMatchAuditEventModel(
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


def _validate_job_ownership(record: JobRecord) -> None:
    for requirement in record.requirements:
        if (
            requirement.owner_user_id != record.job.owner_user_id
            or requirement.job_id != record.job.id
        ):
            raise JobMatchConflict("job requirement ownership mismatch")


def _validate_analysis_ownership(record: AnalysisRecord) -> None:
    owner_user_id = record.analysis.owner_user_id
    analysis_id = record.analysis.id
    for component in record.components:
        if component.owner_user_id != owner_user_id or component.analysis_id != analysis_id:
            raise JobMatchConflict("analysis component ownership mismatch")
    for match in record.requirement_matches:
        if match.owner_user_id != owner_user_id or match.analysis_id != analysis_id:
            raise JobMatchConflict("requirement match ownership mismatch")
    for link in record.evidence_links:
        if link.owner_user_id != owner_user_id or link.analysis_id != analysis_id:
            raise JobMatchConflict("evidence link ownership mismatch")


def _raise_integrity(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc)).casefold()
    if "foreign key" in message:
        raise JobMatchUnavailable from exc
    raise JobMatchConflict from exc
