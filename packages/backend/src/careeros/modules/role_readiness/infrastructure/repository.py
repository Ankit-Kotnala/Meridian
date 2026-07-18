"""Async SQLAlchemy unit of work for Role Explorer and Role Readiness."""

from __future__ import annotations

from collections import defaultdict
from types import TracebackType
from typing import Any, NoReturn, cast
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.foundation.database import Database
from careeros.modules.role_readiness.application.models import (
    AnalysisRecord,
    PageCursor,
    RoleFilter,
)
from careeros.modules.role_readiness.application.ports import RoleReadinessUnitOfWork
from careeros.modules.role_readiness.domain import (
    CompetencyDimension,
    CompetencyEvidenceLink,
    CompetencyImportance,
    CompetencyResult,
    ReadinessComponent,
    ReadinessLabel,
    RoleCompetency,
    RoleDefinition,
    RoleReadinessAnalysis,
    RoleReadinessAuditEvent,
    RoleReadinessConflict,
    RoleReadinessIdempotencyConflict,
    RoleReadinessUnavailable,
    RoleSeniority,
    RoleTaxonomyVersion,
    SavedRole,
    SkillMatchState,
)

from .models import (
    CompetencyEvidenceLinkModel,
    CompetencyResultModel,
    RoleCompetencyModel,
    RoleDefinitionModel,
    RoleReadinessAnalysisModel,
    RoleReadinessAuditEventModel,
    RoleReadinessComponentModel,
    RoleTaxonomyVersionModel,
    SavedRoleModel,
)


class SqlAlchemyRoleReadinessUnitOfWork:
    """Owner-scoped persistence boundary with one transaction per use case."""

    def __init__(self, database: Database) -> None:
        self._session_context = database.session()
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyRoleReadinessUnitOfWork:
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
            raise RuntimeError("role readiness unit of work is not active")
        return self._session

    async def get_taxonomy_version(self, taxonomy_id: UUID) -> RoleTaxonomyVersion | None:
        model = await self.session.scalar(
            select(RoleTaxonomyVersionModel).where(RoleTaxonomyVersionModel.id == taxonomy_id)
        )
        return _taxonomy(model) if model is not None else None

    async def get_active_taxonomy(self) -> RoleTaxonomyVersion | None:
        model = await self.session.scalar(
            select(RoleTaxonomyVersionModel)
            .where(RoleTaxonomyVersionModel.active.is_(True))
            .order_by(RoleTaxonomyVersionModel.published_at.desc(), RoleTaxonomyVersionModel.id)
            .limit(1)
        )
        return _taxonomy(model) if model is not None else None

    async def get_role(self, role_id: UUID) -> RoleDefinition | None:
        model = await self.session.scalar(
            select(RoleDefinitionModel).where(RoleDefinitionModel.id == role_id)
        )
        return _role(model) if model is not None else None

    async def list_roles(
        self, filter_by: RoleFilter, after: PageCursor | None, limit: int
    ) -> list[RoleDefinition]:
        statement = select(RoleDefinitionModel)
        if filter_by.seniority is not None:
            statement = statement.where(RoleDefinitionModel.seniority == filter_by.seniority.value)
        if filter_by.industry is not None:
            statement = statement.where(
                RoleDefinitionModel.industry.ilike(_pattern(filter_by.industry))
            )
        if filter_by.domain is not None:
            statement = statement.where(
                RoleDefinitionModel.domain.ilike(_pattern(filter_by.domain))
            )
        if filter_by.query is not None:
            pattern = _pattern(filter_by.query)
            statement = statement.where(
                or_(
                    RoleDefinitionModel.title.ilike(pattern),
                    RoleDefinitionModel.industry.ilike(pattern),
                    RoleDefinitionModel.domain.ilike(pattern),
                    RoleDefinitionModel.description.ilike(pattern),
                )
            )
        models = (
            await self.session.scalars(
                statement.order_by(RoleDefinitionModel.title, RoleDefinitionModel.id)
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_role(model) for model in models]

    async def list_role_competencies(self, role_id: UUID) -> list[RoleCompetency]:
        models = (
            await self.session.scalars(
                select(RoleCompetencyModel)
                .where(RoleCompetencyModel.role_id == role_id)
                .order_by(RoleCompetencyModel.sort_order, RoleCompetencyModel.id)
            )
        ).all()
        return [_competency(model) for model in models]

    async def get_saved_role(
        self, owner_user_id: UUID, saved_role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None:
        statement = select(SavedRoleModel).where(
            SavedRoleModel.owner_user_id == owner_user_id,
            SavedRoleModel.id == saved_role_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _saved_role(model) if model is not None else None

    async def get_saved_role_by_role(
        self, owner_user_id: UUID, role_id: UUID, *, for_update: bool = False
    ) -> SavedRole | None:
        statement = select(SavedRoleModel).where(
            SavedRoleModel.owner_user_id == owner_user_id,
            SavedRoleModel.role_id == role_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _saved_role(model) if model is not None else None

    async def list_saved_roles(
        self, owner_user_id: UUID, after: PageCursor | None, limit: int
    ) -> list[SavedRole]:
        models = (
            await self.session.scalars(
                select(SavedRoleModel)
                .where(SavedRoleModel.owner_user_id == owner_user_id)
                .order_by(SavedRoleModel.updated_at.desc(), SavedRoleModel.id.desc())
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return [_saved_role(model) for model in models]

    async def add_saved_role(self, saved_role: SavedRole) -> None:
        self.session.add(SavedRoleModel(**_saved_role_values(saved_role)))
        await self._flush()

    async def save_saved_role(self, saved_role: SavedRole) -> None:
        await self._execute(
            update(SavedRoleModel)
            .where(
                SavedRoleModel.owner_user_id == saved_role.owner_user_id,
                SavedRoleModel.id == saved_role.id,
            )
            .values(**_saved_role_values(saved_role, include_identity=False))
        )

    async def delete_saved_role(self, owner_user_id: UUID, saved_role_id: UUID) -> None:
        await self._execute(
            delete(SavedRoleModel).where(
                SavedRoleModel.owner_user_id == owner_user_id,
                SavedRoleModel.id == saved_role_id,
            )
        )

    async def add_analysis(self, record: AnalysisRecord) -> None:
        _validate_record_ownership(record)
        self.session.add(RoleReadinessAnalysisModel(**_analysis_values(record.analysis)))
        await self._flush()
        self.session.add_all(_component_model(item) for item in record.components)
        self.session.add_all(_result_model(item) for item in record.competency_results)
        self.session.add_all(_evidence_link_model(item) for item in record.evidence_links)
        await self._flush()

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> AnalysisRecord | None:
        model = await self.session.scalar(
            select(RoleReadinessAnalysisModel).where(
                RoleReadinessAnalysisModel.owner_user_id == owner_user_id,
                RoleReadinessAnalysisModel.id == analysis_id,
            )
        )
        records = await self._analysis_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def list_analyses(
        self, owner_user_id: UUID, role_id: UUID | None, after: PageCursor | None, limit: int
    ) -> list[AnalysisRecord]:
        statement = select(RoleReadinessAnalysisModel).where(
            RoleReadinessAnalysisModel.owner_user_id == owner_user_id
        )
        if role_id is not None:
            statement = statement.where(RoleReadinessAnalysisModel.role_id == role_id)
        models = (
            await self.session.scalars(
                statement.order_by(
                    RoleReadinessAnalysisModel.created_at.desc(),
                    RoleReadinessAnalysisModel.id.desc(),
                )
                .offset(after.offset if after is not None else 0)
                .limit(limit)
            )
        ).all()
        return await self._analysis_records(owner_user_id, list(models))

    async def find_analysis_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> AnalysisRecord | None:
        model = await self.session.scalar(
            select(RoleReadinessAnalysisModel).where(
                RoleReadinessAnalysisModel.owner_user_id == owner_user_id,
                RoleReadinessAnalysisModel.idempotency_key == idempotency_key,
            )
        )
        records = await self._analysis_records(owner_user_id, [model] if model else [])
        return records[0] if records else None

    async def add_audit(self, event: RoleReadinessAuditEvent) -> None:
        self.session.add(_audit_model(event))

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            _raise_integrity(exc)
        self._committed = True

    async def _analysis_records(
        self, owner_user_id: UUID, analyses: list[RoleReadinessAnalysisModel]
    ) -> list[AnalysisRecord]:
        if not analyses:
            return []
        analysis_ids = [analysis.id for analysis in analyses]
        components = await self._group_models(
            RoleReadinessComponentModel,
            RoleReadinessComponentModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        results = await self._group_models(
            CompetencyResultModel,
            CompetencyResultModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        links = await self._group_models(
            CompetencyEvidenceLinkModel,
            CompetencyEvidenceLinkModel.analysis_id,
            owner_user_id,
            analysis_ids,
        )
        return [
            AnalysisRecord(
                analysis=_analysis(analysis),
                components=tuple(_component(model) for model in components[analysis.id]),
                competency_results=tuple(_result(model) for model in results[analysis.id]),
                evidence_links=tuple(_evidence_link(model) for model in links[analysis.id]),
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


class SqlAlchemyRoleReadinessUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __call__(self) -> RoleReadinessUnitOfWork:
        return SqlAlchemyRoleReadinessUnitOfWork(self._database)


def _pattern(value: str) -> str:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _taxonomy(model: RoleTaxonomyVersionModel) -> RoleTaxonomyVersion:
    return RoleTaxonomyVersion(
        id=model.id,
        version=model.version,
        source_name=model.source_name,
        source_license=model.source_license,
        description=model.description,
        active=model.active,
        published_at=model.published_at,
        created_at=model.created_at,
    )


def _role(model: RoleDefinitionModel) -> RoleDefinition:
    return RoleDefinition(
        id=model.id,
        taxonomy_version_id=model.taxonomy_version_id,
        slug=model.slug,
        title=model.title,
        seniority=RoleSeniority(model.seniority),
        industry=model.industry,
        domain=model.domain,
        location_scope=model.location_scope,
        company_type=model.company_type,
        description=model.description,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _competency(model: RoleCompetencyModel) -> RoleCompetency:
    return RoleCompetency(
        id=model.id,
        role_id=model.role_id,
        dimension=CompetencyDimension(model.dimension),
        label=model.label,
        description=model.description,
        importance=CompetencyImportance(model.importance),
        skill_keywords=_string_tuple(model.skill_keywords),
        evidence_keywords=_string_tuple(model.evidence_keywords),
        transferable_keywords=_string_tuple(model.transferable_keywords),
        adjacent_keywords=_string_tuple(model.adjacent_keywords),
        sort_order=model.sort_order,
    )


def _saved_role(model: SavedRoleModel) -> SavedRole:
    return SavedRole(
        id=model.id,
        owner_user_id=model.owner_user_id,
        role_id=model.role_id,
        notes=model.notes,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _saved_role_values(
    saved_role: SavedRole, *, include_identity: bool = True
) -> dict[str, object]:
    values: dict[str, object] = {
        "role_id": saved_role.role_id,
        "notes": saved_role.notes,
        "version": saved_role.version,
        "created_at": saved_role.created_at,
        "updated_at": saved_role.updated_at,
    }
    if include_identity:
        values.update(id=saved_role.id, owner_user_id=saved_role.owner_user_id)
    return values


def _analysis(model: RoleReadinessAnalysisModel) -> RoleReadinessAnalysis:
    return RoleReadinessAnalysis(
        id=model.id,
        owner_user_id=model.owner_user_id,
        role_id=model.role_id,
        saved_role_id=model.saved_role_id,
        idempotency_key=model.idempotency_key,
        idempotency_fingerprint=model.idempotency_fingerprint,
        engine_version=model.engine_version,
        configuration_version=model.configuration_version,
        feature_schema_version=model.feature_schema_version,
        taxonomy_version=model.taxonomy_version,
        input_snapshot=dict(model.input_snapshot),
        feature_set_hash=model.feature_set_hash,
        raw_score_basis_points=model.raw_score_basis_points,
        display_score=model.display_score,
        readiness_label=ReadinessLabel(model.readiness_label),
        insufficient_reason=model.insufficient_reason,
        summary=model.summary,
        created_at=model.created_at,
    )


def _analysis_values(analysis: RoleReadinessAnalysis) -> dict[str, object]:
    return {
        "id": analysis.id,
        "owner_user_id": analysis.owner_user_id,
        "role_id": analysis.role_id,
        "saved_role_id": analysis.saved_role_id,
        "idempotency_key": analysis.idempotency_key,
        "idempotency_fingerprint": analysis.idempotency_fingerprint,
        "engine_version": analysis.engine_version,
        "configuration_version": analysis.configuration_version,
        "feature_schema_version": analysis.feature_schema_version,
        "taxonomy_version": analysis.taxonomy_version,
        "input_snapshot": analysis.input_snapshot,
        "feature_set_hash": analysis.feature_set_hash,
        "raw_score_basis_points": analysis.raw_score_basis_points,
        "display_score": analysis.display_score,
        "readiness_label": analysis.readiness_label.value,
        "insufficient_reason": analysis.insufficient_reason,
        "summary": analysis.summary,
        "created_at": analysis.created_at,
    }


def _component(model: RoleReadinessComponentModel) -> ReadinessComponent:
    return ReadinessComponent(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        dimension=CompetencyDimension(model.dimension),
        weight_basis_points=model.weight_basis_points,
        score_basis_points=model.score_basis_points,
        contribution_basis_points=model.contribution_basis_points,
        explanation=model.explanation,
    )


def _component_model(component: ReadinessComponent) -> RoleReadinessComponentModel:
    return RoleReadinessComponentModel(
        id=component.id,
        owner_user_id=component.owner_user_id,
        analysis_id=component.analysis_id,
        dimension=component.dimension.value,
        weight_basis_points=component.weight_basis_points,
        score_basis_points=component.score_basis_points,
        contribution_basis_points=component.contribution_basis_points,
        explanation=component.explanation,
    )


def _result(model: CompetencyResultModel) -> CompetencyResult:
    return CompetencyResult(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        competency_id=model.competency_id,
        dimension=CompetencyDimension(model.dimension),
        label=model.label,
        importance=CompetencyImportance(model.importance),
        match_state=SkillMatchState(model.match_state),
        score_basis_points=model.score_basis_points,
        explanation=model.explanation,
        gap_kind=model.gap_kind,
    )


def _result_model(result: CompetencyResult) -> CompetencyResultModel:
    return CompetencyResultModel(
        id=result.id,
        owner_user_id=result.owner_user_id,
        analysis_id=result.analysis_id,
        competency_id=result.competency_id,
        dimension=result.dimension.value,
        label=result.label,
        importance=result.importance.value,
        match_state=result.match_state.value,
        score_basis_points=result.score_basis_points,
        explanation=result.explanation,
        gap_kind=result.gap_kind,
    )


def _evidence_link(model: CompetencyEvidenceLinkModel) -> CompetencyEvidenceLink:
    return CompetencyEvidenceLink(
        id=model.id,
        owner_user_id=model.owner_user_id,
        analysis_id=model.analysis_id,
        competency_result_id=model.competency_result_id,
        evidence_id=model.evidence_id,
        evidence_title=model.evidence_title,
        evidence_strength=model.evidence_strength,
        relevance_basis_points=model.relevance_basis_points,
        rationale=model.rationale,
    )


def _evidence_link_model(link: CompetencyEvidenceLink) -> CompetencyEvidenceLinkModel:
    return CompetencyEvidenceLinkModel(
        id=link.id,
        owner_user_id=link.owner_user_id,
        analysis_id=link.analysis_id,
        competency_result_id=link.competency_result_id,
        evidence_id=link.evidence_id,
        evidence_title=link.evidence_title,
        evidence_strength=link.evidence_strength,
        relevance_basis_points=link.relevance_basis_points,
        rationale=link.rationale,
    )


def _audit_model(event: RoleReadinessAuditEvent) -> RoleReadinessAuditEventModel:
    return RoleReadinessAuditEventModel(
        id=event.id,
        owner_user_id=event.owner_user_id,
        actor_user_id=event.actor_user_id,
        action=event.action.value,
        target_kind=event.target_kind,
        target_id=event.target_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        details=dict(event.details),
        created_at=event.created_at,
    )


def _validate_record_ownership(record: AnalysisRecord) -> None:
    owner_user_id = record.analysis.owner_user_id
    analysis_id = record.analysis.id
    result_ids = {result.id for result in record.competency_results}
    if (
        any(
            component.owner_user_id != owner_user_id or component.analysis_id != analysis_id
            for component in record.components
        )
        or any(
            result.owner_user_id != owner_user_id or result.analysis_id != analysis_id
            for result in record.competency_results
        )
        or any(
            link.owner_user_id != owner_user_id
            or link.analysis_id != analysis_id
            or link.competency_result_id not in result_ids
            for link in record.evidence_links
        )
    ):
        raise RoleReadinessConflict("readiness analysis ownership does not match")


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RoleReadinessUnavailable("stored role keywords are invalid")
    return tuple(value)


def _raise_integrity(exc: IntegrityError) -> NoReturn:
    constraint_name = _constraint_name(exc)
    if "idempotency" in constraint_name:
        raise RoleReadinessIdempotencyConflict from exc
    raise RoleReadinessConflict from exc


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        diag = getattr(current, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if isinstance(name, str):
            return name
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return ""
