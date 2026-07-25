"""Role Explorer application service and deterministic readiness orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from careeros.modules.role_readiness.domain import (
    CompetencyEvidenceLink,
    CompetencyImportance,
    CompetencyResult,
    ReadinessComponent,
    RoleAuditAction,
    RoleReadinessAnalysis,
    RoleReadinessAuditEvent,
    RoleReadinessConflict,
    RoleReadinessIdempotencyConflict,
    RoleReadinessNotFound,
    RoleReadinessValidationError,
    RoleReadinessVersionConflict,
    SavedRole,
    SkillMatchState,
    score_role_readiness,
)

from .models import (
    AnalysisRecord,
    AnalyzeRoleReadiness,
    PageCursor,
    PagedResult,
    RequestContext,
    RoleComparisonEntry,
    RoleComparisonView,
    RoleDetail,
    RoleFilter,
    RoleReadinessAnalyticsPoint,
    RoleReadinessAnalyticsWatermark,
    RoleReadinessView,
    SavedRoleView,
    SaveRole,
    UpdateSavedRole,
    page_result,
)
from .ports import (
    CareerSnapshotProvider,
    Clock,
    IdentifierFactory,
    RoleReadinessUnitOfWork,
    RoleReadinessUnitOfWorkFactory,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
# Career Analytics expands its public 3,650-day window by one UTC day on both
# sides before reading this purpose-limited source.
_ANALYTICS_SOURCE_MAX_WINDOW_DAYS = 3_652


@dataclass(frozen=True, slots=True)
class RoleReadinessPolicy:
    default_page_size: int = 25
    max_page_size: int = 100
    max_saved_roles: int = 100
    max_history: int = 500

    def __post_init__(self) -> None:
        if not 1 <= self.default_page_size <= self.max_page_size <= 200:
            raise ValueError("role readiness page limits are invalid")
        if self.max_saved_roles < 1 or self.max_history < 1:
            raise ValueError("role readiness collection limits must be positive")


class RoleReadinessService:
    """Owner-scoped Phase 4 use cases for roles and readiness snapshots."""

    def __init__(
        self,
        *,
        unit_of_work: RoleReadinessUnitOfWorkFactory,
        clock: Clock,
        identifiers: IdentifierFactory,
        career_snapshots: CareerSnapshotProvider,
        policy: RoleReadinessPolicy | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._clock = clock
        self._ids = identifiers
        self._career = career_snapshots
        self._policy = policy or RoleReadinessPolicy()

    async def list_roles(
        self,
        filter_by: RoleFilter | None = None,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[RoleDetail]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            roles = await uow.list_roles(filter_by or RoleFilter(), after, page_size + 1)
            details = [await self._role_detail(uow, role.id) for role in roles]
        return page_result(details, cursor=after, limit=page_size)

    async def get_role(self, role_id: UUID) -> RoleDetail:
        async with self._uow() as uow:
            return await self._role_detail(uow, role_id)

    async def save_role(
        self, owner_user_id: UUID, command: SaveRole, context: RequestContext
    ) -> SavedRoleView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            detail = await self._role_detail(uow, command.role_id)
            existing = await uow.get_saved_role_by_role(
                owner_user_id, command.role_id, for_update=True
            )
            if existing is None:
                existing_saved = await uow.list_saved_roles(
                    owner_user_id, None, self._policy.max_saved_roles + 1
                )
                if len(existing_saved) >= self._policy.max_saved_roles:
                    raise RoleReadinessConflict("saved role limit reached")
                saved = SavedRole(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    role_id=command.role_id,
                    notes=command.notes,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.add_saved_role(saved)
                action = RoleAuditAction.SAVED_ROLE_CREATED
            else:
                existing.edit(notes=command.notes, now=now)
                await uow.save_saved_role(existing)
                saved = existing
                action = RoleAuditAction.SAVED_ROLE_UPDATED
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    action,
                    "saved_role",
                    saved.id,
                    context,
                    now,
                    role_id=command.role_id,
                )
            )
            await uow.commit()
        return SavedRoleView(saved_role=saved, role=detail.role, taxonomy=detail.taxonomy)

    async def update_saved_role(
        self,
        owner_user_id: UUID,
        saved_role_id: UUID,
        expected_version: int,
        command: UpdateSavedRole,
        context: RequestContext,
    ) -> SavedRoleView:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            saved = await uow.get_saved_role(owner_user_id, saved_role_id, for_update=True)
            if saved is None:
                raise RoleReadinessNotFound
            self._version(saved.version, expected_version)
            saved.edit(notes=command.notes, now=now)
            await uow.save_saved_role(saved)
            detail = await self._role_detail(uow, saved.role_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    RoleAuditAction.SAVED_ROLE_UPDATED,
                    "saved_role",
                    saved.id,
                    context,
                    now,
                    role_id=saved.role_id,
                )
            )
            await uow.commit()
        return SavedRoleView(saved_role=saved, role=detail.role, taxonomy=detail.taxonomy)

    async def list_saved_roles(
        self, owner_user_id: UUID, *, cursor: str | None = None, limit: int | None = None
    ) -> PagedResult[SavedRoleView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            saved_roles = await uow.list_saved_roles(owner_user_id, after, page_size + 1)
            views = []
            for saved in saved_roles:
                detail = await self._role_detail(uow, saved.role_id)
                views.append(
                    SavedRoleView(saved_role=saved, role=detail.role, taxonomy=detail.taxonomy)
                )
        return page_result(views, cursor=after, limit=page_size)

    async def delete_saved_role(
        self,
        owner_user_id: UUID,
        saved_role_id: UUID,
        expected_version: int,
        context: RequestContext,
    ) -> None:
        self._authorize(owner_user_id, context)
        now = self._clock.now()
        async with self._uow() as uow:
            saved = await uow.get_saved_role(owner_user_id, saved_role_id, for_update=True)
            if saved is None:
                raise RoleReadinessNotFound
            self._version(saved.version, expected_version)
            await uow.delete_saved_role(owner_user_id, saved_role_id)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    RoleAuditAction.SAVED_ROLE_DELETED,
                    "saved_role",
                    saved.id,
                    context,
                    now,
                    role_id=saved.role_id,
                )
            )
            await uow.commit()

    async def analyze_role(
        self,
        owner_user_id: UUID,
        command: AnalyzeRoleReadiness,
        idempotency_key: str,
        context: RequestContext,
    ) -> RoleReadinessView:
        self._authorize(owner_user_id, context)
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise RoleReadinessValidationError("idempotency key is invalid")
        now = self._clock.now()
        async with self._uow() as uow:
            role_id, saved_role = await self._resolve_analysis_role(uow, owner_user_id, command)
            detail = await self._role_detail(uow, role_id)
            fingerprint = _fingerprint(
                role_id=role_id, saved_role_id=saved_role.id if saved_role else None
            )
            existing = await uow.find_analysis_by_idempotency(owner_user_id, idempotency_key)
            if existing is not None:
                if existing.analysis.idempotency_fingerprint != fingerprint:
                    raise RoleReadinessIdempotencyConflict
                return await self._analysis_view(uow, existing)
            snapshot = await self._career.snapshot(owner_user_id)
            score = score_role_readiness(detail.role, detail.competencies, snapshot)
            analysis = RoleReadinessAnalysis(
                id=self._ids.new(),
                owner_user_id=owner_user_id,
                role_id=role_id,
                saved_role_id=saved_role.id if saved_role else None,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=fingerprint,
                engine_version=score.engine_version,
                configuration_version=score.configuration_version,
                feature_schema_version=score.feature_schema_version,
                taxonomy_version=detail.taxonomy.version,
                input_snapshot=score.input_snapshot,
                feature_set_hash=score.feature_set_hash,
                raw_score_basis_points=score.raw_score_basis_points,
                display_score=score.display_score,
                readiness_label=score.readiness_label,
                insufficient_reason=score.insufficient_reason,
                summary=score.summary,
                created_at=now,
            )
            components = tuple(
                ReadinessComponent(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    analysis_id=analysis.id,
                    dimension=item.dimension,
                    weight_basis_points=item.weight_basis_points,
                    score_basis_points=item.score_basis_points,
                    contribution_basis_points=item.contribution_basis_points,
                    explanation=item.explanation,
                )
                for item in score.components
            )
            competency_results: list[CompetencyResult] = []
            evidence_links: list[CompetencyEvidenceLink] = []
            for match in score.competency_matches:
                result = CompetencyResult(
                    id=self._ids.new(),
                    owner_user_id=owner_user_id,
                    analysis_id=analysis.id,
                    competency_id=match.competency.id,
                    dimension=match.competency.dimension,
                    label=match.competency.label,
                    importance=match.competency.importance,
                    match_state=match.state,
                    score_basis_points=match.score_basis_points,
                    explanation=match.explanation,
                    gap_kind=match.gap_kind,
                )
                competency_results.append(result)
                evidence_links.extend(
                    CompetencyEvidenceLink(
                        id=self._ids.new(),
                        owner_user_id=owner_user_id,
                        analysis_id=analysis.id,
                        competency_result_id=result.id,
                        evidence_id=link.evidence_id,
                        evidence_title=link.evidence_title,
                        evidence_strength=link.evidence_strength,
                        relevance_basis_points=link.relevance_basis_points,
                        rationale=link.rationale,
                    )
                    for link in match.evidence
                )
            record = AnalysisRecord(
                analysis=analysis,
                components=components,
                competency_results=tuple(competency_results),
                evidence_links=tuple(evidence_links),
            )
            await uow.add_analysis(record)
            await uow.add_audit(
                self._audit(
                    owner_user_id,
                    RoleAuditAction.READINESS_ANALYZED,
                    "role_readiness_analysis",
                    analysis.id,
                    context,
                    now,
                    role_id=role_id,
                    saved_role_id=saved_role.id if saved_role else None,
                    analysis_id=analysis.id,
                )
            )
            await uow.commit()
            return RoleReadinessView(
                analysis=analysis,
                role=detail.role,
                taxonomy=detail.taxonomy,
                saved_role=saved_role,
                components=components,
                competency_results=tuple(competency_results),
                evidence_links=tuple(evidence_links),
            )

    async def get_analysis(self, owner_user_id: UUID, analysis_id: UUID) -> RoleReadinessView:
        async with self._uow() as uow:
            record = await uow.get_analysis(owner_user_id, analysis_id)
            if record is None:
                raise RoleReadinessNotFound
            return await self._analysis_view(uow, record)

    async def list_history(
        self,
        owner_user_id: UUID,
        *,
        role_id: UUID | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PagedResult[RoleReadinessView]:
        after = PageCursor.decode(cursor)
        page_size = self._page_size(limit)
        async with self._uow() as uow:
            records = await uow.list_analyses(owner_user_id, role_id, after, page_size + 1)
            views = [await self._analysis_view(uow, record) for record in records]
        return page_result(views, cursor=after, limit=page_size)

    async def list_analytics_history(
        self,
        owner_user_id: UUID,
        *,
        window_start: date,
        window_end: date,
        limit: int,
    ) -> tuple[RoleReadinessAnalyticsPoint, ...]:
        """Return purpose-minimized, deterministically bounded history."""

        if (
            window_end < window_start
            or (window_end - window_start).days > _ANALYTICS_SOURCE_MAX_WINDOW_DAYS
        ):
            raise RoleReadinessValidationError(
                "analytics source window exceeds the bounded timezone guard"
            )
        if not 1 <= limit <= self._policy.max_history + 1:
            raise RoleReadinessValidationError("analytics history limit is out of range")
        async with self._uow() as uow:
            values = await uow.list_analytics_history(
                owner_user_id,
                window_start,
                window_end,
                limit,
            )
        return tuple(values)

    async def analytics_watermark(
        self,
        owner_user_id: UUID,
    ) -> RoleReadinessAnalyticsWatermark:
        async with self._uow() as uow:
            state = await uow.get_analytics_source_state(owner_user_id)
        return state.watermark()

    async def compare_roles(
        self, owner_user_id: UUID, role_ids: tuple[UUID, ...]
    ) -> RoleComparisonView:
        if not 2 <= len(role_ids) <= 3 or len(set(role_ids)) != len(role_ids):
            raise RoleReadinessValidationError("compare two or three distinct roles")
        entries: list[RoleComparisonEntry] = []
        async with self._uow() as uow:
            for role_id in role_ids:
                detail = await self._role_detail(uow, role_id)
                records = await uow.list_analyses(owner_user_id, role_id, None, 1)
                latest = await self._analysis_view(uow, records[0]) if records else None
                results = latest.competency_results if latest is not None else ()
                entries.append(
                    RoleComparisonEntry(
                        role=detail.role,
                        taxonomy=detail.taxonomy,
                        latest_analysis=latest,
                        required_gap_count=sum(
                            1
                            for item in results
                            if item.importance is CompetencyImportance.REQUIRED
                            and item.match_state
                            in {SkillMatchState.MISSING, SkillMatchState.UNKNOWN}
                        ),
                        demonstrated_count=sum(
                            1
                            for item in results
                            if item.match_state is SkillMatchState.DEMONSTRATED
                        ),
                        helpful_gap_count=sum(
                            1
                            for item in results
                            if item.importance is CompetencyImportance.HELPFUL
                            and item.match_state
                            in {SkillMatchState.MISSING, SkillMatchState.UNKNOWN}
                        ),
                        strongest_evidence_count=sum(1 for link in latest.evidence_links)
                        if latest is not None
                        else 0,
                    )
                )
        return RoleComparisonView(
            entries=tuple(entries),
            note="Role comparison uses the latest saved readiness snapshot for each role.",
        )

    async def _resolve_analysis_role(
        self, uow: RoleReadinessUnitOfWork, owner_user_id: UUID, command: AnalyzeRoleReadiness
    ) -> tuple[UUID, SavedRole | None]:
        role_id = command.role_id
        saved_role: SavedRole | None = None
        if (role_id is None) == (command.saved_role_id is None):
            raise RoleReadinessValidationError("provide exactly one role or saved role")
        if command.saved_role_id is not None:
            saved_role = await uow.get_saved_role(owner_user_id, command.saved_role_id)
            if saved_role is None:
                raise RoleReadinessNotFound
            role_id = saved_role.role_id
        if role_id is None:
            raise RoleReadinessValidationError("role is required")
        return role_id, saved_role

    async def _role_detail(self, uow: RoleReadinessUnitOfWork, role_id: UUID) -> RoleDetail:
        role = await uow.get_role(role_id)
        if role is None:
            raise RoleReadinessNotFound
        taxonomy = await uow.get_taxonomy_version(role.taxonomy_version_id)
        if taxonomy is None:
            raise RoleReadinessNotFound
        competencies = tuple(
            sorted(
                await uow.list_role_competencies(role.id),
                key=lambda item: (item.sort_order, str(item.id)),
            )
        )
        return RoleDetail(taxonomy=taxonomy, role=role, competencies=competencies)

    async def _analysis_view(
        self, uow: RoleReadinessUnitOfWork, record: AnalysisRecord
    ) -> RoleReadinessView:
        detail = await self._role_detail(uow, record.analysis.role_id)
        saved_role = (
            await uow.get_saved_role(record.analysis.owner_user_id, record.analysis.saved_role_id)
            if record.analysis.saved_role_id is not None
            else None
        )
        return RoleReadinessView(
            analysis=record.analysis,
            role=detail.role,
            taxonomy=detail.taxonomy,
            saved_role=saved_role,
            components=record.components,
            competency_results=record.competency_results,
            evidence_links=record.evidence_links,
        )

    def _page_size(self, value: int | None) -> int:
        if value is None:
            return self._policy.default_page_size
        if not 1 <= value <= self._policy.max_page_size:
            raise RoleReadinessValidationError("page limit is out of range")
        return value

    def _authorize(self, owner_user_id: UUID, context: RequestContext) -> None:
        if owner_user_id != context.actor_user_id:
            raise RoleReadinessNotFound

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if not 1 <= expected <= 2_147_483_647:
            raise RoleReadinessValidationError("expected version must be a positive int32")
        if actual != expected:
            raise RoleReadinessVersionConflict

    def _audit(
        self,
        owner_user_id: UUID,
        action: RoleAuditAction,
        target_kind: str,
        target_id: UUID,
        context: RequestContext,
        created_at: datetime,
        **details: UUID | None,
    ) -> RoleReadinessAuditEvent:
        return RoleReadinessAuditEvent(
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


def _fingerprint(*, role_id: UUID, saved_role_id: UUID | None) -> str:
    payload = json.dumps(
        {"roleId": str(role_id), "savedRoleId": str(saved_role_id) if saved_role_id else None},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
